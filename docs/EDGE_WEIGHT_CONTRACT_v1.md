# Edge Weight Contract v1

Status: local unreleased reference candidate, 2026-10-30.
Model identifier: `arcana.edge_weight.v1`.
Implementation: `src/arcana/edge_weights.py`.

This contract fixes one versioned formula for the propagation entries of `K`.
It replaces the factor list of Formal Model v0.2 section 4 and the six-factor
variant of earlier runtime drafts. It is a declared model: it bounds what the
declared factors imply, not whether the factors are empirically right.

## Formula

For an edge `e` over horizon `H`:

```text
w_e(H) = activation_e(H)
         * p_unsafe_e(H) * exposure_e(H) * capability_e(H) * scope_e(H)
         * pass_1(H) * ... * pass_k(H)
```

| Factor | Domain | Meaning |
| --- | --- | --- |
| `activation` | `>= 0` | expected activations of the edge over `H`; may exceed 1 |
| `p_unsafe` | `[0, 1]` | an activation is unsafe |
| `exposure` | `[0, 1]` | the unsafe activation reaches the target |
| `capability` | `[0, 1]` | the target can act on it |
| `scope` | `[0, 1]` | the action falls inside the propagating scope |
| `pass_i` | `[0, 1]` | an unsafe transition reaching declared control `i` passes it |

Every factor is an interval `lower <= mean <= upper`. `K_ij` is the sum of the
weights of every edge from `i` to `j`. Every graph edge needs a factor set:
an edge without one cannot default, because `activation` has no conservative
upper bound (`edge_factors_missing`, `ARCANA_DENY_CALIBRATION_INSUFFICIENT`).
An unknown probability factor is declared as `[0, 1, 1]`: no lower support and
no control credit.

## Composition (audit F8)

Each edge declares `risk_semantics` for the four risk factors and
`control_semantics` for its controls. Each group composes by its own semantics:

| Semantics | Lower endpoint | Upper endpoint | Premise |
| --- | --- | --- | --- |
| `conditional_chain` | product of lowers | product of uppers | each factor is conditional on all preceding ones in its group, so the product is an identity |
| `unknown_dependence` | `max(0, sum(lowers) - (k - 1))` | minimum of uppers | only the Frechet bounds hold |

The groups multiply, and `activation` multiplies both:

```text
w = activation * R * C        R = risk group, C = control group (1 when no control)
```

This is valid because every pass-through is defined on unsafe transitions:
`P(risk and pass) = P(risk) * P(pass | risk)`. The mean is the product of all
means; it lies inside every interval and supports analysis, never admission.
For the same numbers, `unknown_dependence` always contains `conditional_chain`.

Two marginal risk events of probability `1/2` therefore give an upper weight of
`1/2`, not `1/4`, unless the calibration states and supports the conditional
chain. The common calibration, risk factors defined conditionally and controls
measured one at a time on unsafe transitions, declares
`risk_semantics = conditional_chain` and `control_semantics = unknown_dependence`:
`P(risk) * min_i P(pass_i | risk)`.

## Controls Instead Of Detectability And Gate

The v0.2 factors `(1 - detectability)` and `(1 - gate_effectiveness)` counted a
gate that acts only on detected transitions twice. In v1 each control declares
the probability that an unsafe transition passes it. A detector that feeds a
gate is one control whose pass-through is measured end to end
(`1 - P(detected and blocked)`). Under `control_semantics = unknown_dependence`,
several controls earn no more credit than the strongest one; more credit needs
a jointly measured chain or a supported conditional chain.

## Reversibility Belongs To L

Reversibility does not stop the next node from activating; it shortens or
undoes the consequence. It is therefore not a propagation factor. Its effect
belongs to the loss model `L` (Formal Model sections 9 and 10). A rollback that
blocks propagation before the target activates is a control and is declared
with its own pass-through evidence.

## Numerics

Endpoints are computed exactly from the binary64 inputs and rounded outward
once per matrix entry, so the sum of parallel edges is order independent. The
mean is rounded to nearest and clamped into the rounded interval. A weight
beyond binary64 range fails with `edge_weight_unrepresentable`.

## Validation

| Issue code | Reason code |
| --- | --- |
| `edge_factor_invalid`, `edge_factor_interval_order_invalid`, `edge_factor_probability_out_of_range`, `number_invalid` | `ARCANA_DENY_MODEL_INPUT_INVALID` |
| `edge_control_invalid`, `edge_control_duplicate`, `enum_invalid` (either semantics) | `ARCANA_DENY_MODEL_INPUT_INVALID` |
| `graph_edge_duplicate`, `graph_edge_endpoint_unknown`, `edge_factors_invalid` | `ARCANA_DENY_MODEL_INPUT_INVALID` |
| `edge_factors_duplicate`, `edge_factors_unknown_edge`, `edge_weight_unrepresentable` | `ARCANA_DENY_MODEL_INPUT_INVALID` |
| `edge_factors_horizon_mismatch` | `ARCANA_DENY_DECISION_HORIZON_MISMATCH` |
| `edge_factors_missing` | `ARCANA_DENY_CALIBRATION_INSUFFICIENT` |

## API

- `edge_weight(factors)` and `exact_edge_weight(factors)` give one edge's
  rounded and exact `(lower, mean, upper)`.
- `propagation_bundle(graph, edge_factors, decision_horizon)` returns the
  `MatrixBundle` for the evaluator, ordered by `graph.nodes` and bound to
  `graph.graph_hash`.
- `EdgeFactors.from_mapping` reads and fully validates the JSON shape used by
  the conformance corpus `tests/fixtures/edge_weight_v1.json`.

## Limits

- The semantics labels are declared premises. ARCANA cannot check that a
  `conditional_chain` calibration really estimated conditional factors.
- Factor sets carry no calibration profile id or evidence hash yet; binding
  them belongs with the graph builder and canonical graph hash (Fase 2).
- The graph hash is still supplied by the producer; canonical graph hashing
  (audit F9) is separate.
- The evaluator does not yet require that its matrices came from this builder.
- The JSON shape has no published schema yet; the conformance corpus is the
  portable reference for other implementations.

## Verification

`tests/test_edge_weights.py` reproduces the corpus exactly, checks the
identical-event, detection-gate and mixed-semantics cases, Frechet enclosure
of the chain product for every semantics pair, outward enclosure and ordering for 300 seeded random edges, control
monotonicity, order-independent matrix sums, graph/horizon binding and the
evaluator round trip.
