"""Typed public ARCANA model contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping

from arcana._validation import (
    expect_bool,
    expect_calibration_profile_id,
    expect_datetime_string,
    expect_enum,
    expect_int_min,
    expect_mapping,
    expect_non_empty_string,
    expect_number_min,
    expect_number_range,
    expect_risk_model_version,
    expect_scenario_id,
    expect_sha256,
    expect_string_list,
    fail,
    require_value,
)
from arcana.errors import (
    ArcanaValidationError,
    CalibrationLevel,
    FastGateMode,
    PositiveVectorMethod,
    ReasonCode,
    ValidationIssue,
    Verdict,
)


ALLOWED_EVIDENCE_SOURCE_TYPES = {
    "synthetic_fixture",
    "public_benchmark",
    "empirical_public_benchmark",
    "controlled_test",
    "hash_bound_context",
}
ALLOWED_BENCHMARK_THREAT_CLASSES = {
    "indirect_prompt_injection",
    "persistent_memory_poisoning",
    "privilege_escalation",
    "unsafe_delegation_loop",
    "tool_misuse",
    "benchmark_gaming",
    "data_exfiltration_attempt",
    "resource_exhaustion",
    "stale_context",
    "over_scoped_operation",
    "dynamic_execution_abuse",
}
ALLOWED_BENCHMARK_METRICS = {
    "task_success_rate",
    "unsafe_action_rate",
    "policy_violation_rate",
    "delta_rho_upper",
    "rho_peak",
    "AaR_99_upper",
    "AES_99_upper",
    "containment_time_steps",
    "autonomy_budget_consumed",
    "human_intervention_efficiency",
    "artifact_contract_validity_rate",
}
ALLOWED_BENCHMARK_SCENARIO_TYPES = {
    "coverage_scenario",
    "negative_control",
}
ALLOWED_BENCHMARK_NEGATIVE_CONTROLS = {
    "missing_decision_horizon",
    "graph_hash_mismatch",
    "a0_artifact_used_for_admission",
    "rho_mean_below_threshold_rho_upper_above_threshold",
    "fastgate_inconclusive",
    "loss_model_missing_required",
    "stale_evidence",
}


class NodeClass(str, Enum):
    AGENT = "A"
    TOOL = "T"
    MEMORY = "M"
    HUMAN_GATE = "H"
    GRANT = "Gt"
    OPERATION = "O"
    DISTILLED_OPERATION = "D"
    EXTERNAL_SYSTEM = "X"


@dataclass(frozen=True)
class DecisionHorizon:
    id: str
    duration_seconds: int
    context: str

    @classmethod
    def from_mapping(cls, value: Any, path: tuple[str | int, ...] = ("decision_horizon",)) -> "DecisionHorizon":
        data = expect_mapping(value, path, ReasonCode.DENY_DECISION_HORIZON_MISMATCH)
        return cls(
            id=expect_non_empty_string(
                require_value(data, "id", path, ReasonCode.DENY_DECISION_HORIZON_MISMATCH),
                (*path, "id"),
                ReasonCode.DENY_DECISION_HORIZON_MISMATCH,
            ),
            duration_seconds=expect_int_min(
                require_value(data, "duration_seconds", path, ReasonCode.DENY_DECISION_HORIZON_MISMATCH),
                1,
                (*path, "duration_seconds"),
                ReasonCode.DENY_DECISION_HORIZON_MISMATCH,
            ),
            context=expect_non_empty_string(
                require_value(data, "context", path, ReasonCode.DENY_DECISION_HORIZON_MISMATCH),
                (*path, "context"),
                ReasonCode.DENY_DECISION_HORIZON_MISMATCH,
            ),
        )


@dataclass(frozen=True)
class EvidenceReference:
    source_type: str
    source_id: str
    synthetic: bool
    evidence_hash: str | None = None

    @classmethod
    def from_mapping(cls, value: Any, path: tuple[str | int, ...] = ("evidence",)) -> "EvidenceReference":
        data = expect_mapping(value, path, ReasonCode.DENY_CALIBRATION_INSUFFICIENT)
        evidence_hash = data.get("evidence_hash")
        source_type = expect_non_empty_string(
            require_value(data, "source_type", path, ReasonCode.DENY_CALIBRATION_INSUFFICIENT),
            (*path, "source_type"),
            ReasonCode.DENY_CALIBRATION_INSUFFICIENT,
        )
        if source_type not in ALLOWED_EVIDENCE_SOURCE_TYPES:
            fail("evidence_source_type_unsupported", ReasonCode.DENY_CALIBRATION_INSUFFICIENT, "unsupported evidence source_type", (*path, "source_type"))
        return cls(
            source_type=source_type,
            source_id=expect_non_empty_string(
                require_value(data, "source_id", path, ReasonCode.DENY_CALIBRATION_INSUFFICIENT),
                (*path, "source_id"),
                ReasonCode.DENY_CALIBRATION_INSUFFICIENT,
            ),
            synthetic=expect_bool(
                require_value(data, "synthetic", path, ReasonCode.DENY_CALIBRATION_INSUFFICIENT),
                (*path, "synthetic"),
                ReasonCode.DENY_CALIBRATION_INSUFFICIENT,
            ),
            evidence_hash=expect_sha256(evidence_hash, (*path, "evidence_hash"), ReasonCode.DENY_CALIBRATION_INSUFFICIENT)
            if evidence_hash is not None
            else None,
        )


@dataclass(frozen=True)
class RhoInterval:
    lower: float
    mean: float
    upper: float
    threshold: float

    @classmethod
    def from_mapping(cls, value: Any, path: tuple[str | int, ...] = ("rho_interval",)) -> "RhoInterval":
        data = expect_mapping(value, path, ReasonCode.DENY_MODEL_INPUT_INVALID)
        interval = cls(
            lower=expect_number_min(require_value(data, "lower", path, ReasonCode.DENY_MODEL_INPUT_INVALID), 0, (*path, "lower"), ReasonCode.DENY_MODEL_INPUT_INVALID),
            mean=expect_number_min(require_value(data, "mean", path, ReasonCode.DENY_MODEL_INPUT_INVALID), 0, (*path, "mean"), ReasonCode.DENY_MODEL_INPUT_INVALID),
            upper=expect_number_min(require_value(data, "upper", path, ReasonCode.DENY_MODEL_INPUT_INVALID), 0, (*path, "upper"), ReasonCode.DENY_MODEL_INPUT_INVALID),
            threshold=expect_number_range(require_value(data, "threshold", path, ReasonCode.DENY_MODEL_INPUT_INVALID), 0, 1, (*path, "threshold"), ReasonCode.DENY_MODEL_INPUT_INVALID),
        )
        if not interval.lower <= interval.mean <= interval.upper:
            fail("rho_interval_order_invalid", ReasonCode.DENY_MODEL_INPUT_INVALID, "expected lower <= mean <= upper", path)
        return interval


@dataclass(frozen=True)
class LossBounds:
    aar_99_upper: float
    aes_99_upper: float
    max_allowed_aar_99: float
    max_allowed_aes_99: float

    @classmethod
    def from_mapping(cls, value: Any, path: tuple[str | int, ...] = ("loss_bounds",)) -> "LossBounds":
        data = expect_mapping(value, path, ReasonCode.DENY_LOSS_MODEL_INVALID)
        return cls(
            aar_99_upper=expect_number_min(require_value(data, "aar_99_upper", path, ReasonCode.DENY_LOSS_MODEL_INVALID), 0, (*path, "aar_99_upper"), ReasonCode.DENY_LOSS_MODEL_INVALID),
            aes_99_upper=expect_number_min(require_value(data, "aes_99_upper", path, ReasonCode.DENY_LOSS_MODEL_INVALID), 0, (*path, "aes_99_upper"), ReasonCode.DENY_LOSS_MODEL_INVALID),
            max_allowed_aar_99=expect_number_min(require_value(data, "max_allowed_aar_99", path, ReasonCode.DENY_LOSS_MODEL_INVALID), 0, (*path, "max_allowed_aar_99"), ReasonCode.DENY_LOSS_MODEL_INVALID),
            max_allowed_aes_99=expect_number_min(require_value(data, "max_allowed_aes_99", path, ReasonCode.DENY_LOSS_MODEL_INVALID), 0, (*path, "max_allowed_aes_99"), ReasonCode.DENY_LOSS_MODEL_INVALID),
        )


@dataclass(frozen=True)
class FastGateContext:
    mode: FastGateMode
    positive_vector_method: PositiveVectorMethod | None = None
    upper_bound: float | None = None

    @classmethod
    def from_mapping(cls, value: Any, path: tuple[str | int, ...] = ("fastgate",)) -> "FastGateContext":
        data = expect_mapping(value, path, ReasonCode.DENY_FASTGATE_VECTOR_INVALID)
        mode = expect_enum(
            FastGateMode,
            require_value(data, "mode", path, ReasonCode.DENY_FASTGATE_VECTOR_INVALID),
            (*path, "mode"),
            ReasonCode.DENY_FASTGATE_VECTOR_INVALID,
        )
        method_value = data.get("positive_vector_method")
        method = (
            expect_enum(PositiveVectorMethod, method_value, (*path, "positive_vector_method"), ReasonCode.DENY_FASTGATE_VECTOR_INVALID)
            if method_value is not None
            else None
        )
        upper_value = data.get("upper_bound")
        upper_bound = (
            expect_number_min(upper_value, 0, (*path, "upper_bound"), ReasonCode.DENY_FASTGATE_UNCERTAIN)
            if upper_value is not None
            else None
        )
        if mode is FastGateMode.PERRON_COLLATZ_BOUND and method is None:
            fail(
                "fastgate_positive_vector_method_missing",
                ReasonCode.DENY_FASTGATE_VECTOR_INVALID,
                "perron_collatz_bound requires positive_vector_method",
                (*path, "positive_vector_method"),
            )
        if mode is FastGateMode.PERRON_COLLATZ_BOUND and upper_bound is None:
            fail(
                "fastgate_upper_bound_missing",
                ReasonCode.DENY_FASTGATE_UNCERTAIN,
                "perron_collatz_bound requires upper_bound",
                (*path, "upper_bound"),
            )
        return cls(mode=mode, positive_vector_method=method, upper_bound=upper_bound)


@dataclass(frozen=True)
class AutonomyBudget:
    expires_at: str
    max_delta_rho_upper: float | None = None
    max_external_requests: int | None = None
    max_memory_writes: int | None = None
    max_output_bytes: int | None = None

    @classmethod
    def from_mapping(cls, value: Any, path: tuple[str | int, ...] = ("autonomy_budget",)) -> "AutonomyBudget":
        data = expect_mapping(value, path, ReasonCode.DENY_BUDGET_EXHAUSTED)
        budget = cls(
            expires_at=expect_datetime_string(
                require_value(data, "expires_at", path, ReasonCode.DENY_BUDGET_EXHAUSTED),
                (*path, "expires_at"),
                ReasonCode.DENY_BUDGET_EXHAUSTED,
            ),
            max_delta_rho_upper=expect_number_min(data["max_delta_rho_upper"], 0, (*path, "max_delta_rho_upper"), ReasonCode.DENY_BUDGET_EXHAUSTED)
            if "max_delta_rho_upper" in data
            else None,
            max_external_requests=expect_int_min(data["max_external_requests"], 0, (*path, "max_external_requests"), ReasonCode.DENY_BUDGET_EXHAUSTED)
            if "max_external_requests" in data
            else None,
            max_memory_writes=expect_int_min(data["max_memory_writes"], 0, (*path, "max_memory_writes"), ReasonCode.DENY_BUDGET_EXHAUSTED)
            if "max_memory_writes" in data
            else None,
            max_output_bytes=expect_int_min(data["max_output_bytes"], 0, (*path, "max_output_bytes"), ReasonCode.DENY_BUDGET_EXHAUSTED)
            if "max_output_bytes" in data
            else None,
        )
        if (
            budget.max_delta_rho_upper is None
            and budget.max_external_requests is None
            and budget.max_memory_writes is None
            and budget.max_output_bytes is None
        ):
            fail("autonomy_budget_empty", ReasonCode.DENY_BUDGET_EXHAUSTED, "at least one budget counter is required", path)
        return budget


@dataclass(frozen=True)
class GraphNode:
    node_id: str
    node_class: NodeClass
    label: str | None = None

    @classmethod
    def from_mapping(cls, value: Any, path: tuple[str | int, ...] = ("node",)) -> "GraphNode":
        data = expect_mapping(value, path, ReasonCode.DENY_MODEL_INPUT_INVALID)
        label = data.get("label")
        return cls(
            node_id=expect_non_empty_string(require_value(data, "node_id", path, ReasonCode.DENY_MODEL_INPUT_INVALID), (*path, "node_id"), ReasonCode.DENY_MODEL_INPUT_INVALID),
            node_class=expect_enum(NodeClass, require_value(data, "node_class", path, ReasonCode.DENY_MODEL_INPUT_INVALID), (*path, "node_class"), ReasonCode.DENY_MODEL_INPUT_INVALID),
            label=expect_non_empty_string(label, (*path, "label"), ReasonCode.DENY_MODEL_INPUT_INVALID) if label is not None else None,
        )


@dataclass(frozen=True)
class GraphEdge:
    source: str
    target: str
    edge_type: str

    @classmethod
    def from_mapping(cls, value: Any, path: tuple[str | int, ...] = ("edge",)) -> "GraphEdge":
        data = expect_mapping(value, path, ReasonCode.DENY_MODEL_INPUT_INVALID)
        return cls(
            source=expect_non_empty_string(require_value(data, "source", path, ReasonCode.DENY_MODEL_INPUT_INVALID), (*path, "source"), ReasonCode.DENY_MODEL_INPUT_INVALID),
            target=expect_non_empty_string(require_value(data, "target", path, ReasonCode.DENY_MODEL_INPUT_INVALID), (*path, "target"), ReasonCode.DENY_MODEL_INPUT_INVALID),
            edge_type=expect_non_empty_string(require_value(data, "edge_type", path, ReasonCode.DENY_MODEL_INPUT_INVALID), (*path, "edge_type"), ReasonCode.DENY_MODEL_INPUT_INVALID),
        )


@dataclass(frozen=True)
class GraphState:
    graph_hash: str
    nodes: tuple[GraphNode, ...]
    edges: tuple[GraphEdge, ...]

    @classmethod
    def from_mapping(cls, value: Any, path: tuple[str | int, ...] = ("graph",)) -> "GraphState":
        data = expect_mapping(value, path, ReasonCode.DENY_MODEL_INPUT_INVALID)
        raw_nodes = require_value(data, "nodes", path, ReasonCode.DENY_MODEL_INPUT_INVALID)
        raw_edges = require_value(data, "edges", path, ReasonCode.DENY_MODEL_INPUT_INVALID)
        if not isinstance(raw_nodes, list):
            fail("graph_nodes_invalid", ReasonCode.DENY_MODEL_INPUT_INVALID, "nodes must be an array", (*path, "nodes"))
        if not isinstance(raw_edges, list):
            fail("graph_edges_invalid", ReasonCode.DENY_MODEL_INPUT_INVALID, "edges must be an array", (*path, "edges"))
        nodes = tuple(GraphNode.from_mapping(item, (*path, "nodes", index)) for index, item in enumerate(raw_nodes))
        edges = tuple(GraphEdge.from_mapping(item, (*path, "edges", index)) for index, item in enumerate(raw_edges))
        if not nodes:
            fail("graph_nodes_empty", ReasonCode.DENY_MODEL_INPUT_INVALID, "graph requires at least one node", (*path, "nodes"))
        node_id_sequence = tuple(node.node_id for node in nodes)
        node_ids = set(node_id_sequence)
        if len(node_id_sequence) != len(node_ids):
            fail("graph_node_id_duplicate", ReasonCode.DENY_MODEL_INPUT_INVALID, "graph node_id values must be unique", (*path, "nodes"))
        edge_keys = tuple((edge.source, edge.target, edge.edge_type) for edge in edges)
        if len(edge_keys) != len(set(edge_keys)):
            fail("graph_edge_duplicate", ReasonCode.DENY_MODEL_INPUT_INVALID, "graph edges must be unique by source,target,edge_type", (*path, "edges"))
        for index, edge in enumerate(edges):
            if edge.source not in node_ids or edge.target not in node_ids:
                fail("graph_edge_endpoint_unknown", ReasonCode.DENY_MODEL_INPUT_INVALID, "edge endpoint is not present in nodes", (*path, "edges", index))
        return cls(
            graph_hash=expect_sha256(require_value(data, "graph_hash", path, ReasonCode.DENY_GRAPH_HASH_MISMATCH), (*path, "graph_hash"), ReasonCode.DENY_GRAPH_HASH_MISMATCH),
            nodes=nodes,
            edges=edges,
        )


@dataclass(frozen=True)
class GraphDelta:
    delta_hash: str
    added_nodes: tuple[GraphNode, ...] = ()
    added_edges: tuple[GraphEdge, ...] = ()

    @classmethod
    def from_mapping(cls, value: Any, path: tuple[str | int, ...] = ("graph_delta",)) -> "GraphDelta":
        data = expect_mapping(value, path, ReasonCode.DENY_MODEL_INPUT_INVALID)
        raw_nodes = data.get("added_nodes", [])
        raw_edges = data.get("added_edges", [])
        if not isinstance(raw_nodes, list):
            fail("graph_delta_nodes_invalid", ReasonCode.DENY_MODEL_INPUT_INVALID, "added_nodes must be an array", (*path, "added_nodes"))
        if not isinstance(raw_edges, list):
            fail("graph_delta_edges_invalid", ReasonCode.DENY_MODEL_INPUT_INVALID, "added_edges must be an array", (*path, "added_edges"))
        added_nodes = tuple(GraphNode.from_mapping(item, (*path, "added_nodes", index)) for index, item in enumerate(raw_nodes))
        added_edges = tuple(GraphEdge.from_mapping(item, (*path, "added_edges", index)) for index, item in enumerate(raw_edges))
        added_node_ids = tuple(node.node_id for node in added_nodes)
        if len(added_node_ids) != len(set(added_node_ids)):
            fail("graph_delta_node_id_duplicate", ReasonCode.DENY_MODEL_INPUT_INVALID, "added node_id values must be unique", (*path, "added_nodes"))
        added_edge_keys = tuple((edge.source, edge.target, edge.edge_type) for edge in added_edges)
        if len(added_edge_keys) != len(set(added_edge_keys)):
            fail("graph_delta_edge_duplicate", ReasonCode.DENY_MODEL_INPUT_INVALID, "added edges must be unique by source,target,edge_type", (*path, "added_edges"))
        return cls(
            delta_hash=expect_sha256(require_value(data, "delta_hash", path, ReasonCode.DENY_MODEL_INPUT_INVALID), (*path, "delta_hash"), ReasonCode.DENY_MODEL_INPUT_INVALID),
            added_nodes=added_nodes,
            added_edges=added_edges,
        )


@dataclass(frozen=True)
class DecisionResult:
    verdict: Verdict
    reason_codes: tuple[ReasonCode, ...]
    metrics: Mapping[str, Any] = field(default_factory=dict)
    required_controls: tuple[str, ...] = ()
    caveats: tuple[str, ...] = ()

    @classmethod
    def from_mapping(cls, value: Any, path: tuple[str | int, ...] = ("decision_result",)) -> "DecisionResult":
        data = expect_mapping(value, path, ReasonCode.DENY_MODEL_INPUT_INVALID)
        raw_codes = require_value(data, "reason_codes", path, ReasonCode.DENY_MODEL_INPUT_INVALID)
        if not isinstance(raw_codes, list) or not raw_codes:
            fail("reason_codes_invalid", ReasonCode.DENY_MODEL_INPUT_INVALID, "reason_codes must be a non-empty array", (*path, "reason_codes"))
        reason_codes = tuple(expect_enum(ReasonCode, item, (*path, "reason_codes", index), ReasonCode.DENY_MODEL_INPUT_INVALID) for index, item in enumerate(raw_codes))
        if len(reason_codes) != len(set(reason_codes)):
            fail("reason_codes_not_unique", ReasonCode.DENY_MODEL_INPUT_INVALID, "reason_codes must be unique", (*path, "reason_codes"))
        metrics = expect_mapping(data.get("metrics", {}), (*path, "metrics"), ReasonCode.DENY_MODEL_INPUT_INVALID)
        return cls(
            verdict=expect_enum(Verdict, require_value(data, "verdict", path, ReasonCode.DENY_MODEL_INPUT_INVALID), (*path, "verdict"), ReasonCode.DENY_MODEL_INPUT_INVALID),
            reason_codes=reason_codes,
            metrics=dict(metrics),
            required_controls=expect_string_list(data.get("required_controls", []), (*path, "required_controls"), ReasonCode.DENY_MODEL_INPUT_INVALID, unique=True),
            caveats=expect_string_list(data.get("caveats", []), (*path, "caveats"), ReasonCode.DENY_MODEL_INPUT_INVALID),
        )


@dataclass(frozen=True)
class RiskContext:
    risk_model_version: str
    calibration_profile_id: str
    calibration_level: CalibrationLevel
    decision_horizon: DecisionHorizon
    graph_hash: str
    rho_interval: RhoInterval
    decision: Verdict
    reason_codes: tuple[ReasonCode, ...]
    evidence: EvidenceReference
    autonomy_budget: AutonomyBudget
    loss_bounds: LossBounds | None = None
    fastgate: FastGateContext | None = None
    required_controls: tuple[str, ...] = ()

    @classmethod
    def from_mapping(cls, value: Any, path: tuple[str | int, ...] = ()) -> "RiskContext":
        data = expect_mapping(value, path, ReasonCode.DENY_MODEL_INPUT_INVALID)
        raw_codes = require_value(data, "reason_codes", path, ReasonCode.DENY_MODEL_INPUT_INVALID)
        if not isinstance(raw_codes, list) or not raw_codes:
            fail("reason_codes_invalid", ReasonCode.DENY_MODEL_INPUT_INVALID, "reason_codes must be a non-empty array", (*path, "reason_codes"))
        reason_codes = tuple(expect_enum(ReasonCode, item, (*path, "reason_codes", index), ReasonCode.DENY_MODEL_INPUT_INVALID) for index, item in enumerate(raw_codes))
        if len(reason_codes) != len(set(reason_codes)):
            fail("reason_codes_not_unique", ReasonCode.DENY_MODEL_INPUT_INVALID, "reason_codes must be unique", (*path, "reason_codes"))
        return cls(
            risk_model_version=expect_risk_model_version(require_value(data, "risk_model_version", path, ReasonCode.DENY_RISK_MODEL_UNSUPPORTED), (*path, "risk_model_version")),
            calibration_profile_id=expect_calibration_profile_id(require_value(data, "calibration_profile_id", path, ReasonCode.DENY_CALIBRATION_INSUFFICIENT), (*path, "calibration_profile_id")),
            calibration_level=expect_enum(CalibrationLevel, require_value(data, "calibration_level", path, ReasonCode.DENY_CALIBRATION_INSUFFICIENT), (*path, "calibration_level"), ReasonCode.DENY_CALIBRATION_INSUFFICIENT),
            decision_horizon=DecisionHorizon.from_mapping(require_value(data, "decision_horizon", path, ReasonCode.DENY_DECISION_HORIZON_MISMATCH), (*path, "decision_horizon")),
            graph_hash=expect_sha256(require_value(data, "graph_hash", path, ReasonCode.DENY_GRAPH_HASH_MISMATCH), (*path, "graph_hash"), ReasonCode.DENY_GRAPH_HASH_MISMATCH),
            rho_interval=RhoInterval.from_mapping(require_value(data, "rho_interval", path, ReasonCode.DENY_MODEL_INPUT_INVALID), (*path, "rho_interval")),
            decision=expect_enum(Verdict, require_value(data, "decision", path, ReasonCode.DENY_MODEL_INPUT_INVALID), (*path, "decision"), ReasonCode.DENY_MODEL_INPUT_INVALID),
            reason_codes=reason_codes,
            evidence=EvidenceReference.from_mapping(require_value(data, "evidence", path, ReasonCode.DENY_CALIBRATION_INSUFFICIENT), (*path, "evidence")),
            autonomy_budget=AutonomyBudget.from_mapping(require_value(data, "autonomy_budget", path, ReasonCode.DENY_BUDGET_EXHAUSTED), (*path, "autonomy_budget")),
            loss_bounds=LossBounds.from_mapping(data["loss_bounds"], (*path, "loss_bounds")) if "loss_bounds" in data else None,
            fastgate=FastGateContext.from_mapping(data["fastgate"], (*path, "fastgate")) if "fastgate" in data else None,
            required_controls=expect_string_list(data.get("required_controls", []), (*path, "required_controls"), ReasonCode.DENY_MODEL_INPUT_INVALID, unique=True),
        )


@dataclass(frozen=True)
class BenchmarkGraphFixture:
    graph_hash: str
    node_count: int
    edge_count: int

    @classmethod
    def from_mapping(cls, value: Any, path: tuple[str | int, ...] = ("graph_fixture",)) -> "BenchmarkGraphFixture":
        data = expect_mapping(value, path, ReasonCode.DENY_MODEL_INPUT_INVALID)
        return cls(
            graph_hash=expect_sha256(require_value(data, "graph_hash", path, ReasonCode.DENY_GRAPH_HASH_MISMATCH), (*path, "graph_hash"), ReasonCode.DENY_GRAPH_HASH_MISMATCH),
            node_count=expect_int_min(require_value(data, "node_count", path, ReasonCode.DENY_MODEL_INPUT_INVALID), 1, (*path, "node_count"), ReasonCode.DENY_MODEL_INPUT_INVALID),
            edge_count=expect_int_min(require_value(data, "edge_count", path, ReasonCode.DENY_MODEL_INPUT_INVALID), 0, (*path, "edge_count"), ReasonCode.DENY_MODEL_INPUT_INVALID),
        )


@dataclass(frozen=True)
class BenchmarkScenario:
    scenario_id: str
    title: str
    summary: str
    synthetic: bool
    scenario_type: str
    threat_class: str
    calibration_level: CalibrationLevel
    initial_rho_upper: float
    graph_fixture: BenchmarkGraphFixture
    expected_response: DecisionResult
    reported_metrics: tuple[str, ...]
    negative_control: str | None = None

    @classmethod
    def from_mapping(cls, value: Any, path: tuple[str | int, ...] = ()) -> "BenchmarkScenario":
        data = expect_mapping(value, path, ReasonCode.DENY_MODEL_INPUT_INVALID)
        scenario_type = expect_non_empty_string(require_value(data, "scenario_type", path, ReasonCode.DENY_MODEL_INPUT_INVALID), (*path, "scenario_type"), ReasonCode.DENY_MODEL_INPUT_INVALID)
        if scenario_type not in ALLOWED_BENCHMARK_SCENARIO_TYPES:
            fail("benchmark_scenario_type_unsupported", ReasonCode.DENY_MODEL_INPUT_INVALID, "unsupported benchmark scenario_type", (*path, "scenario_type"))
        raw_negative_control = data.get("negative_control")
        if scenario_type == "negative_control":
            negative_control = expect_non_empty_string(require_value(data, "negative_control", path, ReasonCode.DENY_MODEL_INPUT_INVALID), (*path, "negative_control"), ReasonCode.DENY_MODEL_INPUT_INVALID)
            if negative_control not in ALLOWED_BENCHMARK_NEGATIVE_CONTROLS:
                fail("benchmark_negative_control_unsupported", ReasonCode.DENY_MODEL_INPUT_INVALID, "unsupported benchmark negative_control", (*path, "negative_control"))
        else:
            if raw_negative_control is not None:
                fail("benchmark_negative_control_unexpected", ReasonCode.DENY_MODEL_INPUT_INVALID, "coverage scenarios must not declare negative_control", (*path, "negative_control"))
            negative_control = None
        threat_class = expect_non_empty_string(require_value(data, "threat_class", path, ReasonCode.DENY_MODEL_INPUT_INVALID), (*path, "threat_class"), ReasonCode.DENY_MODEL_INPUT_INVALID)
        if threat_class not in ALLOWED_BENCHMARK_THREAT_CLASSES:
            fail("benchmark_threat_class_unsupported", ReasonCode.DENY_MODEL_INPUT_INVALID, "unsupported benchmark threat_class", (*path, "threat_class"))
        reported_metrics = expect_string_list(require_value(data, "reported_metrics", path, ReasonCode.DENY_MODEL_INPUT_INVALID), (*path, "reported_metrics"), ReasonCode.DENY_MODEL_INPUT_INVALID, min_items=1, unique=True)
        for index, metric in enumerate(reported_metrics):
            if metric not in ALLOWED_BENCHMARK_METRICS:
                fail("benchmark_metric_unsupported", ReasonCode.DENY_MODEL_INPUT_INVALID, "unsupported benchmark metric", (*path, "reported_metrics", index))
        return cls(
            scenario_id=expect_scenario_id(require_value(data, "scenario_id", path, ReasonCode.DENY_MODEL_INPUT_INVALID), (*path, "scenario_id")),
            title=expect_non_empty_string(require_value(data, "title", path, ReasonCode.DENY_MODEL_INPUT_INVALID), (*path, "title"), ReasonCode.DENY_MODEL_INPUT_INVALID),
            summary=expect_non_empty_string(require_value(data, "summary", path, ReasonCode.DENY_MODEL_INPUT_INVALID), (*path, "summary"), ReasonCode.DENY_MODEL_INPUT_INVALID),
            synthetic=expect_bool(require_value(data, "synthetic", path, ReasonCode.DENY_MODEL_INPUT_INVALID), (*path, "synthetic"), ReasonCode.DENY_MODEL_INPUT_INVALID),
            scenario_type=scenario_type,
            threat_class=threat_class,
            calibration_level=expect_enum(CalibrationLevel, require_value(data, "calibration_level", path, ReasonCode.DENY_CALIBRATION_INSUFFICIENT), (*path, "calibration_level"), ReasonCode.DENY_CALIBRATION_INSUFFICIENT),
            initial_rho_upper=expect_number_min(require_value(data, "initial_rho_upper", path, ReasonCode.DENY_MODEL_INPUT_INVALID), 0, (*path, "initial_rho_upper"), ReasonCode.DENY_MODEL_INPUT_INVALID),
            graph_fixture=BenchmarkGraphFixture.from_mapping(require_value(data, "graph_fixture", path, ReasonCode.DENY_MODEL_INPUT_INVALID), (*path, "graph_fixture")),
            expected_response=DecisionResult.from_mapping(require_value(data, "expected_arcana_response", path, ReasonCode.DENY_MODEL_INPUT_INVALID), (*path, "expected_arcana_response")),
            reported_metrics=reported_metrics,
            negative_control=negative_control,
        )


__all__ = [
    "ALLOWED_BENCHMARK_METRICS",
    "ALLOWED_BENCHMARK_NEGATIVE_CONTROLS",
    "ALLOWED_BENCHMARK_SCENARIO_TYPES",
    "ALLOWED_BENCHMARK_THREAT_CLASSES",
    "ALLOWED_EVIDENCE_SOURCE_TYPES",
    "ArcanaValidationError",
    "AutonomyBudget",
    "BenchmarkGraphFixture",
    "BenchmarkScenario",
    "DecisionHorizon",
    "DecisionResult",
    "EvidenceReference",
    "FastGateContext",
    "GraphDelta",
    "GraphEdge",
    "GraphNode",
    "GraphState",
    "LossBounds",
    "NodeClass",
    "ReasonCode",
    "RhoInterval",
    "RiskContext",
    "ValidationIssue",
    "Verdict",
]
