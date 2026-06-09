"""Deterministic public demo for ARCANA Slice 4."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from typing import Any, TextIO

from arcana._validation import fail
from arcana.calibration import CalibrationProfile
from arcana.certificate import (
    BoundedAutonomyCertificate,
    build_demo_non_certifiable_certificate,
    certificate_to_mapping,
    risk_context_to_mapping,
)
from arcana.decision import DecisionEvaluationRequest, evaluate_decision
from arcana.errors import ArcanaValidationError, CalibrationLevel, FastGateMode, ReasonCode, SchemaVersion, Verdict
from arcana.matrices import MatrixBundle
from arcana.model import AutonomyBudget, BenchmarkScenario, EvidenceReference, FastGateContext, LossBounds, RhoInterval, RiskContext
from arcana.schemas import EXAMPLE_DIR, load_typed_fixture, validate_document


SUPPORTED_SCENARIOS = ("synthetic_prompt_injection",)
CONTEXT_ARTIFACT_LABEL = "arcana.context.v0.2"
CERTIFICATE_ARTIFACT_LABEL = "arcana.certificate.v0.2"
DEMO_ISSUED_AT = "2026-06-09T00:00:00Z"
DEMO_EXPIRES_AT = "2026-06-09T00:05:00Z"
DEMO_EVIDENCE_HASH = "sha256:5555555555555555555555555555555555555555555555555555555555555555"


@dataclass(frozen=True)
class DemoArtifacts:
    scenario: str
    scenario_id: str
    context: RiskContext
    certificate: BoundedAutonomyCertificate

    def to_mapping(self) -> dict[str, Any]:
        context_document = risk_context_to_mapping(self.context)
        certificate_document = certificate_to_mapping(self.certificate)
        validate_document(context_document, SchemaVersion.CONTEXT_V02)
        validate_document(certificate_document, SchemaVersion.CERTIFICATE_V02)
        return {
            "schema_version": "arcana.demo_output.v0.1",
            "scenario": self.scenario,
            "scenario_id": self.scenario_id,
            "artifacts": {
                CONTEXT_ARTIFACT_LABEL: context_document,
                CERTIFICATE_ARTIFACT_LABEL: certificate_document,
            },
        }


def build_demo_artifacts(scenario: str = "synthetic_prompt_injection") -> DemoArtifacts:
    if scenario not in SUPPORTED_SCENARIOS:
        fail(
            "demo_scenario_unsupported",
            ReasonCode.DENY_MODEL_INPUT_INVALID,
            "unsupported demo scenario",
            ("scenario",),
        )
    calibration_profile = _load_a0_calibration_profile()
    benchmark = _load_prompt_injection_benchmark()
    budget = AutonomyBudget(
        expires_at=DEMO_EXPIRES_AT,
        max_delta_rho_upper=0.05,
        max_external_requests=0,
        max_memory_writes=0,
        max_output_bytes=65536,
    )
    loss_bounds = LossBounds(
        aar_99_upper=1200.0,
        aes_99_upper=1800.0,
        max_allowed_aar_99=2500.0,
        max_allowed_aes_99=3000.0,
    )
    fastgate = FastGateContext(mode=FastGateMode.OBSERVE_ONLY)
    matrix_bundle = MatrixBundle.from_values(
        lower=[[0.0, 0.2], [0.2, 0.0]],
        mean=[[0.0, 0.5], [0.5, 0.0]],
        upper=[[0.0, 0.9], [0.9, 0.0]],
        node_order=("research_agent", "external_tool"),
        graph_hash=benchmark.graph_fixture.graph_hash,
    )
    request = DecisionEvaluationRequest(
        risk_model_version=calibration_profile.risk_model_version,
        calibration_profile=calibration_profile,
        decision_horizon=calibration_profile.decision_horizon,
        graph_hash=benchmark.graph_fixture.graph_hash,
        matrix_bundle=matrix_bundle,
        rho_threshold=0.8,
        autonomy_budget=budget,
        decision_time=DEMO_ISSUED_AT,
        required_calibration_level=CalibrationLevel.A1,
        loss_in_scope=True,
        loss_bounds=loss_bounds,
        fastgate=fastgate,
        requested_output_bytes=4096,
        delta_rho_upper=0.0,
    )
    decision_result = evaluate_decision(request)
    _validate_demo_decision_result(decision_result_verdict=decision_result.verdict, reason_codes=decision_result.reason_codes)
    rho_interval = _rho_interval_from_metrics(decision_result.metrics)
    evidence = EvidenceReference(
        source_type="synthetic_fixture",
        source_id="arcana-public-demo-synthetic-prompt-injection-001",
        synthetic=True,
        evidence_hash=DEMO_EVIDENCE_HASH,
    )
    context = RiskContext(
        risk_model_version=calibration_profile.risk_model_version,
        calibration_profile_id=calibration_profile.profile_id,
        calibration_level=calibration_profile.level,
        decision_horizon=calibration_profile.decision_horizon,
        graph_hash=benchmark.graph_fixture.graph_hash,
        rho_interval=rho_interval,
        decision=decision_result.verdict,
        reason_codes=decision_result.reason_codes,
        evidence=evidence,
        autonomy_budget=budget,
        loss_bounds=loss_bounds,
        fastgate=fastgate,
        required_controls=decision_result.required_controls,
    )
    risk_context_to_mapping(context)
    certificate = build_demo_non_certifiable_certificate(
        certificate_id="arcana-cert-demo-a0-synthetic-prompt-injection-001",
        context=context,
        calibration_profile=calibration_profile,
        issued_at=DEMO_ISSUED_AT,
        caveats=(
            "A0 synthetic demo certificate is non-certifiable.",
            "No operational admission claim is made.",
        ),
    )
    return DemoArtifacts(
        scenario=scenario,
        scenario_id=benchmark.scenario_id,
        context=context,
        certificate=certificate,
    )


def main(argv: list[str] | None = None, stdout: TextIO | None = None, stderr: TextIO | None = None) -> int:
    output = stdout if stdout is not None else sys.stdout
    error_output = stderr if stderr is not None else sys.stderr
    parser = argparse.ArgumentParser(prog="arcana-demo")
    parser.add_argument("--scenario", default="synthetic_prompt_injection", help="demo scenario id")
    args = parser.parse_args(argv)
    try:
        artifacts = build_demo_artifacts(args.scenario)
        payload = artifacts.to_mapping()
    except ArcanaValidationError as exc:
        json.dump(_error_payload(exc), error_output, sort_keys=True)
        error_output.write("\n")
        return 2
    json.dump(payload, output, indent=2, sort_keys=True)
    output.write("\n")
    return 0


def _load_a0_calibration_profile() -> CalibrationProfile:
    document = load_typed_fixture(EXAMPLE_DIR / "calibration_profile_a0.synthetic.json")
    if not isinstance(document, CalibrationProfile):
        fail(
            "demo_calibration_fixture_type_invalid",
            ReasonCode.DENY_CALIBRATION_INSUFFICIENT,
            "calibration fixture did not parse as CalibrationProfile",
            ("examples", "calibration_profile_a0.synthetic.json"),
        )
    if document.level is not CalibrationLevel.A0:
        fail(
            "demo_calibration_fixture_not_a0",
            ReasonCode.DENY_CALIBRATION_INSUFFICIENT,
            "demo calibration fixture must be A0",
            ("examples", "calibration_profile_a0.synthetic.json", "level"),
        )
    return document


def _load_prompt_injection_benchmark() -> BenchmarkScenario:
    document = load_typed_fixture(EXAMPLE_DIR / "benchmark_prompt_injection.synthetic.json")
    if not isinstance(document, BenchmarkScenario):
        fail(
            "demo_benchmark_fixture_type_invalid",
            ReasonCode.DENY_MODEL_INPUT_INVALID,
            "benchmark fixture did not parse as BenchmarkScenario",
            ("examples", "benchmark_prompt_injection.synthetic.json"),
        )
    if not document.synthetic:
        fail(
            "demo_benchmark_fixture_not_synthetic",
            ReasonCode.DENY_MODEL_INPUT_INVALID,
            "demo benchmark fixture must be synthetic",
            ("examples", "benchmark_prompt_injection.synthetic.json", "synthetic"),
        )
    return document


def _validate_demo_decision_result(*, decision_result_verdict: Verdict, reason_codes: tuple[ReasonCode, ...]) -> None:
    if decision_result_verdict is not Verdict.OBSERVE_ONLY:
        fail(
            "demo_decision_verdict_invalid",
            ReasonCode.DENY_MODEL_INPUT_INVALID,
            "A0 demo decision must be observe_only",
            ("decision",),
        )
    required_codes = (
        ReasonCode.REQUIRE_OBSERVE_ONLY,
        ReasonCode.INFO_A0_NON_CERTIFIABLE,
        ReasonCode.INFO_SYNTHETIC_FIXTURE,
    )
    for reason_code in required_codes:
        if reason_code not in reason_codes:
            fail(
                "demo_decision_reason_code_missing",
                ReasonCode.DENY_MODEL_INPUT_INVALID,
                "A0 demo decision is missing a required reason code",
                ("reason_codes", reason_code.value),
            )


def _rho_interval_from_metrics(metrics: dict[str, Any]) -> RhoInterval:
    required = ("rho_lower", "rho_mean", "rho_upper", "rho_threshold")
    for key in required:
        if key not in metrics:
            fail(
                "demo_rho_metric_missing",
                ReasonCode.DENY_MODEL_INPUT_INVALID,
                f"{key} is required to emit rho_interval",
                ("decision_result", "metrics", key),
            )
    return RhoInterval.from_mapping(
        {
            "lower": metrics["rho_lower"],
            "mean": metrics["rho_mean"],
            "upper": metrics["rho_upper"],
            "threshold": metrics["rho_threshold"],
        },
        ("rho_interval",),
    )


def _error_payload(error: ArcanaValidationError) -> dict[str, Any]:
    issue = error.primary_issue
    return {
        "error": {
            "reason_code": issue.reason_code.value,
            "issue_code": issue.code,
            "message": issue.message,
            "path": issue.path_text,
        }
    }


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "CERTIFICATE_ARTIFACT_LABEL",
    "CONTEXT_ARTIFACT_LABEL",
    "DemoArtifacts",
    "SUPPORTED_SCENARIOS",
    "build_demo_artifacts",
    "main",
]
