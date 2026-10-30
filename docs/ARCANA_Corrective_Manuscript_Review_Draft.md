# ARCANA Corrective Manuscript Review Draft

ARCANA: Autonomy Risk Calculus for Agentic Network Assurance

Date: 2026-09-10. Status: REVIEW_DRAFT_NOT_APPROVED_FOR_PUBLICATION.
Proposed corrective addendum to paper v1.0, not a replacement archive record.
Software scope: corrected development source
`be4383c1d5b4cdc9a1b1d3e49627db5ceab8dd17`, version `0.1.2.dev0`.
The accompanying documentation/test patch requires its own source manifest.

This candidate contains replacement claim language for the sections identified
below. It is not a complete new typeset manuscript, a released software version,
a new DOI deposit or a claim of independent review. The existing v1.0 manuscript,
LaTeX sources, citation metadata and DOI record retain their historical bytes.
Final manuscript version, release version and archive submission require separate
approval after review of this candidate.

## Abstract (Replacement)

ARCANA is an open research framework for autonomy accounting in agentic
systems. It evaluates declared nonnegative propagation models under explicit
model, calibration, horizon and evidence assumptions, separately from supplied
loss limits and enforcement policy. The corrected reference implementation
computes verified numerical enclosures for represented binary64 matrices and
uses strict upper-bound admission checks. It includes typed input validation,
sparse additive-update decision paths and reproducible synthetic scenarios.
Numerical enclosure does not establish empirical calibration coverage, absolute
safety, temporal stability of independently changing models or production
readiness. The current loss path validates supplied values; it does not estimate
a loss distribution. FastGate is a reference decision path with no demonstrated
latency advantage. This revision corrects the numerical and claim semantics of
the earlier manuscript; it does not retroactively certify earlier artifacts.

## 1. Model and Horizon (v1.0 Sections 4-6)

The decision horizon identifies the scope within which weights and evidence
are intended to apply. Matching its identifier, duration and context is
necessary, but does not prove that those weights form a valid propagation
operator. A calibration/model contract must also declare a generation or
transition unit, state meaning, edge orientation and an applicable recurrence.
Time-window cumulative event counts must not silently be treated as one-step
transition coefficients and repeatedly composed.

With `K_ij` denoting source-i to target-j propagation, a column-state linear
model uses `z_(g+1)=K^T*z_g`; a row-state model uses `z_(g+1)=z_g*K`.
All spectral statements are invariant under transpose. A fixed operator, or
a justified dominating operator for the relevant evolution, is an assumption
of the model interpretation. Syntactic horizon compatibility is not evidence
that this dynamical assumption is true.

The edge-factor product is a declared modeling rule. It is not a theorem that
marginal unsafe-transition, exposure and control probabilities can be multiplied
to obtain a conservative joint probability. Any probabilistic interpretation
requires conditional definitions, justified dependence assumptions or an
independently supported domination argument. Where these are absent, label the
weights as heuristic/static model inputs rather than calibrated probabilities.
Monetary values and impact remain outside `K`.

## 2. Contributions and Numerical Meaning (v1.0 Sections 1 and 7)

The contribution is a structured, inspectable decision contract and reference
implementation applying established nonnegative-matrix methods to a declared
agentic model. Perron-Frobenius and Collatz-Wielandt theory are prior mathematics,
not new ARCANA theorems. Proposed fast-path architecture must be distinguished
from measured runtime improvement.

For each represented matrix `A`, distinguish the mathematical radius `rho(A)`
from computed endpoints `lower_num(A)` and `upper_num(A)`:

```text
lower_num(A) <= rho(A) <= upper_num(A)

reported rho_lower = lower_num(K_lower)
reported rho_upper = upper_num(K_upper)
```

The compatibility API `spectral_radius` returns the verified upper endpoint,
not an exact floating-point eigenvalue. `rho_mean` is a diagnostic midpoint
of the `K_mean` numerical enclosure, clipped into the reported interval. It is
not an expected risk, an expected spectral radius or an admission metric.

Candidate positive vectors may come from an approximate eigensolver or decimal
iteration. Certification converts represented matrix/vector entries to rational
numbers, computes row products, sums and divisions exactly, and rounds only the
final numerical endpoints outward. Candidate convergence is not a correctness
premise; wide bounds can cause conservative denial. Unrepresentable bounds cause
an explicit validation failure rather than admission.

Matrix conversion rejects erased nonzero values but otherwise accepts ordinary
rounding into binary64. Thus calibration must supply a conservative represented
envelope; the numerical kernel does not construct statistical input intervals.

## 3. Conditional Admission (v1.0 Section 7)

For a finite nonnegative represented matrix and positive test vector, minimum
and maximum row ratios enclose its radius. Component decomposition extends the
implementation to reducible graphs. This uses standard nonnegative-matrix
theory; see equation (2) in
[Friedland](https://arxiv.org/abs/1710.07402) for the upper characterization.

If an actual MODEL matrix is entrywise dominated by the represented upper
matrix, monotonicity carries that upper spectral bound to the model. Whether
the real system is described or dominated by such a model remains an external
scientific and governance obligation.

The numerical admission condition is:

```text
upper_num(K_upper) + numeric_margin < threshold <= 1
```

The comparison uses the exact sum of represented endpoint and margin. Equality
and insufficient separation do not pass. The numerical margin is not an
empirical confidence interval or a production risk threshold. Other policy,
budget, calibration, freshness and loss preconditions remain necessary; a
spectral check by itself does not authorize action.

## 4. FastGate Scope (v1.0 Section 13 and Contribution 6)

FastGate evaluates a supplied upper-model baseline plus a nonnegative additive
delta. Updated entries are rounded upward, and positive-vector bounds use exact
rational certification. Its increment is conservatively bounded by subtracting
a LOWER numerical bound of that SAME baseline matrix from an after upper bound.
This is a budget on changes in the declared upper model.

It is not in general an upper bound on the increment of an unknown real or
calibrated matrix below the supplied baseline. For example:

```text
upper before = [[0, 1/2], [1/2, 0]]
other before = [[0, 1/2], [0,   0]]
same delta   = [[0, 0],   [9/32, 0]]
upper-model radius increases by 1/8; the compatible model increases by 3/8.
```

Bounding an unknown-model increment requires its own justified lower baseline
and upper after-state under joint evidence assumptions. The current FastGate
request does not carry a separate calibrated lower baseline. The general
decision evaluator also accepts `delta_rho_upper` from its caller; validating
that number does not independently derive or authenticate it.

`exact_recompute` means full recomputation through the verified enclosure
algorithm, not symbolic exact eigenvalues. Positive-vector failure and
insufficient threshold separation use the documented fallback or denial paths.
The reference still computes baseline bounds and materializes dense after-state.
No throughput, latency, amortized-complexity or sparse-update speedup result is
claimed without a separately reproducible comparative measurement.

## 5. Dynamics and Transient Limits (v1.0 Sections 7 and 18)

For a FIXED finite matrix, `rho(A)<1` implies convergence of `sum A^g`.
That conditional mathematical fact does not prove the fixed linear model is
valid for real agent behavior. It does not give a quantitative bound on impact,
loss or even short-run amplification from the radius alone.

A loop-free graph can have zero radius and very large transient propagation.
For `A=[[0,M,0],[0,0,M],[0,0,0]]`, the second power contains `M^2` while the
third power vanishes. This distinction between spectral radius and matrix norm
also appears in [Higham's discussion](https://nhigham.com/2024/01/12/what-is-the-spectral-radius-of-a-matrix/).
Finite-horizon claims require initial-state, generation-depth and transient
analysis plus separate loss/impact constraints. A finite generation sum exists
even for some supercritical matrices; subcritical admission is a conservative
policy criterion, not necessary for all finite-horizon acceptable outcomes.

Individual snapshots being subcritical is insufficient under arbitrary changes:
the two nonnegative matrices `[[0,2],[0,0]]` and `[[0,0],[2,0]]` each have zero
radius, while their product has radius four. A common entrywise upper operator
with radius below one, on fixed coordinates throughout the evolution, would be
one sufficient extra condition. A common contractive positive-vector norm or
another reviewed switching argument is also possible. Current per-request
validation establishes none of these temporal conditions automatically.

## 6. Calibration and Evidence (v1.0 Sections 6, 9 and 18)

The calibration envelope must be distinguished from the numerical enclosure
of any one supplied matrix. Simultaneous validity across relevant edges,
generations and before/after states requires an explicit evidence argument.
Individual `99%` marginal intervals need not constitute a `99%` joint envelope.
Adaptive reuse, multiple decisions, selection effects, drift and adversarial
behavior require their own analysis; a static input check does not solve them.

Model/profile identifiers, graph and evidence hashes, source classes and
timestamps support consistency and traceability. They do not authenticate an
untrusted producer or prove the content is complete, independently reviewed or
statistically calibrated. Caller-supplied matrices and scalar evidence claims
remain a trust boundary. No public synthetic benchmark is real A2/A3 evidence.

## 7. Loss Handling (v1.0 Sections 5 and 8)

Loss and propagation remain separate. The present `LossBounds` input contains
four supplied scalar values: two declared upper loss metrics and two allowed
limits. `evaluate_loss_bounds` validates required presence, numeric domains and
limit breaches. It does not estimate a distribution, quantile or expected
shortfall, verify a confidence level, or independently check a loss horizon,
unit, evidence source or model family absent from that input.

An integration must establish those semantics before submitting the numbers.
The general horizon checks bind request/profile and other represented horizon
fields; they must not be described as inspecting loss metadata that is not in
the current type. A future typed loss provenance contract and empirical loss
methodology are separate work, not completed features of this correction.

For an integrable loss `L`, define `q_u = inf {z : P(L<=z)>=u}` and
`AaR_alpha=q_alpha` for `0<alpha<1`. The intended expected-shortfall convention
is `AES_alpha = integral_alpha^1 q_u du / (1-alpha)`. This handles probability
mass at the quantile; a strict exceedance mean is not generally equivalent.
For equally likely losses `(1,1,1,5)` at `alpha=1/2`, those quantities are `3`
and `5` respectively. See
[Rockafellar and Uryasev, general loss distributions](https://sites.math.washington.edu/~rtr/papers/rtr187-CVaR2.pdf).
The reference compares supplied upper values; it does not calculate this integral.

## 8. Artifacts, Results and Publication Limits

The corrected source, installed-distribution replay and synthetic tests provide
reproducibility evidence for declared computations. New analytic counterexamples
in `tests/test_r3_mathematical_scope.py` are claim-scope checks, not an empirical
benchmark improvement or an independent reviewer endorsement. Test counts must
be tied to execution receipts and exact source, not treated as safety metrics.

This candidate incorporates R3-C01 through R3-C06 from the
[technical review](R3_TECHNICAL_CLAIM_REVIEW.md). Independent mathematical and
claim review, accepted finding dispositions, a complete revised manuscript and
typeset verification, clean source/CI reproduction and a maintainer publication
decision remain open. No existing release tag or archived paper is overwritten.

ARCANA remains standalone open research/reference. AXCP Core may integrate it
externally without requiring it. Production-grade AXCP Advanced/Enterprise
integration remains proprietary; NEMORG is an optional lab, not a dependency.
Neither this candidate nor a future DOI grants production authority or proves
absolute safety.
