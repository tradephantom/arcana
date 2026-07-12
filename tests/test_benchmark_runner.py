from __future__ import annotations

import copy
import dataclasses
import json
import os
import stat
import subprocess
import sys
from collections.abc import Callable

import numpy as np
import pytest

from arcana.bench import BenchmarkSuite, load_public_benchmark_suite, validate_benchmark_suite
from arcana.bench_runner import (
    BENCHMARK_CLAIM_BOUNDARY,
    BENCHMARK_METRIC_DECIMAL_PLACES,
    BENCHMARK_NUMERIC_REPORTING_POLICY,
    BenchmarkRunReport,
    build_input_manifest,
    execute_benchmark_suite,
    load_public_benchmark_execution_suite,
    report_json_bytes,
    run_public_benchmark,
    validate_execution_binding,
    verify_benchmark_report,
    verify_benchmark_report_against_source,
)
from arcana.benchmark_input import BenchmarkExecutionCase, BenchmarkExecutionSuite, sha256_json
from arcana.decision import DecisionEvaluationRequest, evaluate_decision
from arcana.errors import ArcanaValidationError, ReasonCode, Verdict
from arcana.model import DecisionResult
from arcana.schemas import ROOT


def _suites() -> tuple[BenchmarkSuite, BenchmarkExecutionSuite]:
    return load_public_benchmark_suite(), load_public_benchmark_execution_suite()


def _execute(
    benchmark_suite: BenchmarkSuite,
    execution_suite: BenchmarkExecutionSuite,
    evaluator: Callable[[DecisionEvaluationRequest], DecisionResult] = evaluate_decision,
) -> BenchmarkRunReport:
    return execute_benchmark_suite(
        benchmark_suite,
        execution_suite,
        build_input_manifest(),
        evaluator=evaluator,
    )


def _rehash_report(document: dict) -> None:
    body = dict(document)
    body.pop("report_hash")
    document["report_hash"] = sha256_json(body)


def test_execution_suite_binds_exactly_one_input_to_every_scenario() -> None:
    benchmark_suite, execution_suite = _suites()

    bindings = validate_execution_binding(benchmark_suite, execution_suite)

    assert len(bindings) == benchmark_suite.coverage.scenario_count == len(execution_suite.cases)
    assert [scenario.scenario_id for scenario, _ in bindings] == sorted(
        scenario.scenario_id for scenario in benchmark_suite.scenarios
    )


def test_normalized_sparse_matrix_uses_declared_edge_count_and_rho_targets() -> None:
    _, execution_suite = _suites()

    for case in execution_suite.cases:
        specification = case.evaluator_input.matrix_interval
        bundle = specification.to_matrix_bundle()
        radii = bundle.spectral_radii(case.evaluator_input.rho_threshold)

        assert np.count_nonzero(bundle.upper.values) == specification.edge_count
        assert radii.lower == pytest.approx(specification.rho_lower_target, abs=1e-10)
        assert radii.mean == pytest.approx(specification.rho_mean_target, abs=1e-10)
        assert radii.upper == pytest.approx(specification.rho_upper_target, abs=1e-10)


def test_runner_calls_real_evaluator_once_per_scenario() -> None:
    benchmark_suite, execution_suite = _suites()
    calls: list[DecisionEvaluationRequest] = []

    def recording_evaluator(request: DecisionEvaluationRequest) -> DecisionResult:
        calls.append(request)
        return evaluate_decision(request)

    report = _execute(benchmark_suite, execution_suite, recording_evaluator)

    assert report.execution_status == "passed"
    assert report.passed_count == 13
    assert report.failed_count == 0
    assert len(calls) == 13
    controlled_runs = [scenario for scenario in report.scenarios if scenario.observed.required_controls]
    assert {scenario.scenario_id for scenario in controlled_runs} == {
        "arcana-bench-memory-poisoning-001",
        "arcana-bench-prompt-injection-001",
    }
    assert all(scenario.required_controls_comparison == "pass" for scenario in controlled_runs)


def test_runner_does_not_echo_expected_fixture_values() -> None:
    benchmark_suite, execution_suite = _suites()

    def deliberately_wrong_evaluator(_: DecisionEvaluationRequest) -> DecisionResult:
        return DecisionResult(
            verdict=Verdict.DENY,
            reason_codes=(ReasonCode.DENY_MODEL_INPUT_INVALID,),
            metrics={"issue_code": "deliberately_wrong_test_evaluator"},
        )

    report = _execute(benchmark_suite, execution_suite, deliberately_wrong_evaluator)

    assert report.execution_status == "failed"
    assert report.failed_count == len(execution_suite.cases)
    assert all(not scenario.passed for scenario in report.scenarios)


def test_runner_detects_expected_verdict_mutation() -> None:
    benchmark_suite, execution_suite = _suites()
    scenarios = list(benchmark_suite.scenarios)
    target_index = next(index for index, scenario in enumerate(scenarios) if scenario.threat_class == "indirect_prompt_injection")
    target = scenarios[target_index]
    scenarios[target_index] = dataclasses.replace(
        target,
        expected_response=dataclasses.replace(target.expected_response, verdict=Verdict.ALLOW_BOUNDED_AUTONOMY),
    )
    mutated_suite = validate_benchmark_suite(scenarios)

    report = _execute(mutated_suite, execution_suite)

    target_run = next(item for item in report.scenarios if item.scenario_id == target.scenario_id)
    assert target_run.passed is False
    assert target_run.verdict_comparison == "fail"


def test_runner_detects_expected_reason_code_mutation() -> None:
    benchmark_suite, execution_suite = _suites()
    scenarios = list(benchmark_suite.scenarios)
    target_index = next(index for index, scenario in enumerate(scenarios) if scenario.threat_class == "indirect_prompt_injection")
    target = scenarios[target_index]
    scenarios[target_index] = dataclasses.replace(
        target,
        expected_response=dataclasses.replace(
            target.expected_response,
            reason_codes=(ReasonCode.INFO_SYNTHETIC_FIXTURE,),
        ),
    )
    mutated_suite = validate_benchmark_suite(scenarios)

    report = _execute(mutated_suite, execution_suite)

    target_run = next(item for item in report.scenarios if item.scenario_id == target.scenario_id)
    assert target_run.passed is False
    assert target_run.reason_codes_comparison == "fail"


def test_runner_detects_expected_required_controls_mutation() -> None:
    benchmark_suite, execution_suite = _suites()
    scenarios = list(benchmark_suite.scenarios)
    target_index = next(index for index, scenario in enumerate(scenarios) if scenario.threat_class == "indirect_prompt_injection")
    target = scenarios[target_index]
    scenarios[target_index] = dataclasses.replace(
        target,
        expected_response=dataclasses.replace(
            target.expected_response,
            required_controls=("different_control",),
        ),
    )
    mutated_suite = validate_benchmark_suite(scenarios)

    report = _execute(mutated_suite, execution_suite)

    target_run = next(item for item in report.scenarios if item.scenario_id == target.scenario_id)
    assert target_run.passed is False
    assert target_run.required_controls_comparison == "fail"


def test_execution_binding_detects_input_mutation_before_evaluation() -> None:
    benchmark_suite, execution_suite = _suites()
    cases = list(execution_suite.cases)
    target_index = next(index for index, case in enumerate(cases) if case.scenario_id == "arcana-bench-prompt-injection-001")
    target = cases[target_index]
    cases[target_index] = dataclasses.replace(
        target,
        evaluator_input=dataclasses.replace(target.evaluator_input, human_gate_required=False),
    )
    mutated_suite = dataclasses.replace(execution_suite, cases=tuple(cases))

    with pytest.raises(ArcanaValidationError) as exc_info:
        validate_execution_binding(benchmark_suite, mutated_suite)

    assert exc_info.value.code == "benchmark_execution_coverage_path_not_exercised"


def test_execution_binding_distinguishes_missing_and_unbound_inputs() -> None:
    benchmark_suite, execution_suite = _suites()
    with pytest.raises(ArcanaValidationError) as missing_exc:
        validate_execution_binding(
            benchmark_suite,
            dataclasses.replace(execution_suite, cases=execution_suite.cases[1:]),
        )
    assert missing_exc.value.code == "benchmark_execution_input_missing"

    extra_case = BenchmarkExecutionCase(
        scenario_id="arcana-bench-unbound-extra-001",
        evaluator_input=execution_suite.cases[0].evaluator_input,
    )
    with pytest.raises(ArcanaValidationError) as extra_exc:
        validate_execution_binding(
            benchmark_suite,
            dataclasses.replace(execution_suite, cases=(*execution_suite.cases, extra_case)),
        )
    assert extra_exc.value.code == "benchmark_execution_input_unbound"


def test_report_is_deterministic_and_source_bound() -> None:
    first = run_public_benchmark()
    second = run_public_benchmark()

    assert report_json_bytes(first) == report_json_bytes(second)
    assert first.report_hash == second.report_hash
    assert first.to_mapping()["claim_boundary"] == BENCHMARK_CLAIM_BOUNDARY
    assert first.to_mapping()["numeric_reporting_policy"] == BENCHMARK_NUMERIC_REPORTING_POLICY
    verify_benchmark_report_against_source(first.to_mapping())


def test_report_metric_states_are_explicit_and_have_provenance() -> None:
    report = run_public_benchmark()
    statuses = {
        metric.status
        for scenario in report.scenarios
        for metric in scenario.metrics
    }

    assert statuses == {"measured", "not_measured", "unavailable"}
    for scenario in report.scenarios:
        for metric in scenario.metrics:
            assert metric.provenance
            if metric.status == "measured":
                assert metric.value is not None
                assert metric.value == round(metric.value, BENCHMARK_METRIC_DECIMAL_PLACES)
            else:
                assert metric.value is None


def test_report_hash_verifier_detects_content_tamper() -> None:
    document = copy.deepcopy(run_public_benchmark().to_mapping())
    document["scenarios"][0]["observed"]["issue_code"] = "tampered_issue_code"

    with pytest.raises(ArcanaValidationError) as exc_info:
        verify_benchmark_report(document)

    assert exc_info.value.code == "benchmark_report_hash_mismatch"


def test_report_verifier_recomputes_comparisons_from_snapshots() -> None:
    document = copy.deepcopy(run_public_benchmark().to_mapping())
    document["scenarios"][0]["observed"]["verdict"] = "allow_bounded_autonomy"
    _rehash_report(document)

    with pytest.raises(ArcanaValidationError) as exc_info:
        verify_benchmark_report(document)

    assert exc_info.value.code == "benchmark_report_verdict_comparison_mismatch"


def test_report_verifier_rejects_duplicate_metric_names() -> None:
    document = copy.deepcopy(run_public_benchmark().to_mapping())
    document["scenarios"][0]["metrics"].append(copy.deepcopy(document["scenarios"][0]["metrics"][0]))
    _rehash_report(document)

    with pytest.raises(ArcanaValidationError) as exc_info:
        verify_benchmark_report(document)

    assert exc_info.value.code == "benchmark_report_metric_name_duplicate"


def test_report_source_verifier_reexecutes_observed_decisions() -> None:
    document = copy.deepcopy(run_public_benchmark().to_mapping())
    document["scenarios"][0]["observed"]["issue_code"] = "self_consistent_but_not_reproduced"
    _rehash_report(document)
    verify_benchmark_report(document)

    with pytest.raises(ArcanaValidationError) as exc_info:
        verify_benchmark_report_against_source(document)

    assert exc_info.value.code == "benchmark_report_source_observed_mismatch"


def test_report_source_verifier_detects_manifest_substitution() -> None:
    document = copy.deepcopy(run_public_benchmark().to_mapping())
    document["input_manifest"][0]["sha256"] = "sha256:" + "0" * 64
    document["suite_input_hash"] = sha256_json(document["input_manifest"])
    _rehash_report(document)

    with pytest.raises(ArcanaValidationError) as exc_info:
        verify_benchmark_report_against_source(document)

    assert exc_info.value.code == "benchmark_report_source_manifest_mismatch"


def test_benchmark_module_cli_stdout_is_deterministic() -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    command = [sys.executable, "-m", "arcana.bench_runner"]

    first = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, check=False)
    second = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, check=False)

    assert first.returncode == second.returncode == 0
    assert first.stderr == second.stderr == b""
    assert first.stdout == second.stdout
    assert json.loads(first.stdout)["execution_status"] == "passed"


def test_benchmark_module_cli_atomically_writes_and_verifies_report(tmp_path) -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    report_path = tmp_path / "arcana-bench-report.json"

    write_result = subprocess.run(
        [sys.executable, "-m", "arcana.bench_runner", "--output", str(report_path)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    verify_result = subprocess.run(
        [sys.executable, "-m", "arcana.bench_runner", "--verify", str(report_path)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert write_result.returncode == 0
    assert write_result.stdout == write_result.stderr == ""
    assert verify_result.returncode == 0
    assert verify_result.stderr == ""
    assert verify_result.stdout.startswith("benchmark report verification: PASS sha256:")
    if os.name != "nt":
        assert stat.S_IMODE(report_path.stat().st_mode) == 0o644


def test_benchmark_module_cli_rejects_missing_output_parent(tmp_path) -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    report_path = tmp_path / "missing" / "arcana-bench-report.json"

    completed = subprocess.run(
        [sys.executable, "-m", "arcana.bench_runner", "--output", str(report_path)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 2
    assert completed.stdout == ""
    assert "benchmark_report_output_parent_missing" in completed.stderr


@pytest.mark.skipif(os.name == "nt", reason="POSIX symlink semantics required")
def test_benchmark_module_cli_rejects_symlink_output(tmp_path) -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    target = tmp_path / "target.json"
    target.write_text("preserve", encoding="ascii")
    report_path = tmp_path / "report.json"
    report_path.symlink_to(target)

    completed = subprocess.run(
        [sys.executable, "-m", "arcana.bench_runner", "--output", str(report_path)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 2
    assert completed.stdout == ""
    assert "benchmark_report_output_symlink_rejected" in completed.stderr
    assert target.read_text(encoding="ascii") == "preserve"
