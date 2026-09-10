# R3 Technical and Claim Review

Date: 2026-09-10. Status: INTERNAL_TECHNICAL_REVIEW_NOT_INDEPENDENT_APPROVAL.
Classification: public-safe research review; no production authority.

## Identity and Disclosure

Reviewed implementation: `be4383c1d5b4cdc9a1b1d3e49627db5ceab8dd17`,
tree `0c24b31848721349a481cf8316f4345d3816ceef`, development version
`0.1.2.dev0`. The accompanying R3 patch changes documentation and tests, not
runtime code. Its complete file manifest and dirty-state declaration must be
included in the handoff; the R2 commit alone does not identify that patch.

This is an automated internal review by Codex, conducted in the implementation
workspace with access to earlier implementation and review history. The user
requested xhigh reasoning effort. Tools used include source inspection, Python,
pytest, exact rational analytic tests, Git and primary mathematical references.
That access is a conflict with independent-review status. No named independent
reviewer, reviewer signature, empirical calibration approval or external peer
review is claimed. Distinct analytic oracles are not distinct accountable people.

Read with [Numerical Contract v1](NUMERICAL_CONTRACT_v1.md), the
[corrective manuscript draft](ARCANA_Corrective_Manuscript_Review_Draft.md) and
the [independent reviewer record](R3_REVIEWER_RECORD_TEMPLATE.md).

## Findings and Disposition

Severity here measures the consequence of publishing an unsupported technical
claim, not a security exploit rating. All dispositions are candidate changes,
not independent acceptance. Historical paper v1.0 remains immutable.

| ID | Severity | Evidence and finding | Candidate disposition |
| --- | --- | --- | --- |
| R3-C01 | High | v1.0 sections 7 and 13 describe computed radii and intermediate upward rounding; corrected `matrices.py` and `_numerics.py` return verified endpoints using exact rational certification. | Draft sections 2 and 3 distinguish mathematical radii, numerical endpoints, midpoint diagnostics and strict margins. |
| R3-C02 | High | `fastgate.py` subtracts a lower numerical endpoint of `K_before_upper`, not a lower bound on an unknown calibrated baseline. The exact counterexample below defeats the stronger incremental-risk interpretation. | Draft section 4 and active FastGate/numerical contracts restrict the budget to declared upper-model matrices. Latent-risk budget support remains outside this API. |
| R3-C03 | High | v1.0 sections 5-7 do not fully specify the generation operator needed for repeated propagation. Nilpotent and switching counterexamples invalidate broader finite-impact or time-varying stability claims. | Draft sections 1 and 5 state the conditional fixed-operator theorem, orientation and additional switching/transient requirements. |
| R3-C04 | High | Factor ranges, multiplying factor bounds and ordering matrix entries do not establish dependence assumptions or simultaneous statistical coverage. | Draft section 6 separates a declared score model from a probability model and requires external joint-coverage evidence. |
| R3-C05 | Medium | `LossBounds` has four numbers; `evaluate_loss_bounds` checks their domains and limits. It has no loss distribution, estimator, unit or horizon field. The stronger v1.0 section 8 horizon-validation claim exceeds that function, and tail averaging requires an atom/tie convention. | Draft section 7 describes supplied-value validation, a quantile-integral definition and upstream obligations. A typed loss contract with provenance and horizon is a future implementation gate, not supplied by this patch. |
| R3-C06 | Medium | v1.0 contribution 6 and the concluding faster-path wording exceed the available performance evidence. The reference constructs dense after-state and computes baseline bounds. | Draft sections 2 and 4 remove achieved speed/latency claims. Comparative performance remains unmeasured. |

No new counterexample to the represented-matrix numerical enclosure contract
was found in this bounded review. This is not a proof that the complete software
has no bugs. Claim corrections must not be described as new runtime safeguards.

## Proof Obligations

### P1: Positive-Vector Enclosure

Let `A` be a finite nonnegative square matrix and `x > 0`. Put
`l = min_i (A*x)_i/x_i` and `u = max_i (A*x)_i/x_i`.
Then `l*x <= A*x <= u*x`. A nonzero nonnegative left Perron vector `y`
exists, including for reducible `A`. Multiplication by `y^T` and division by
`y^T*x > 0` give `l <= rho(A) <= u`.

This proof does not require `x` to be an accurate eigenvector, an irreducible
matrix or convergence of the candidate generator. The standard upper
characterization is stated in equation (2) of
[Friedland, Collatz-Wielandt quotient](https://arxiv.org/abs/1710.07402).
The code's finite candidate vectors are verified through rational row ratios;
NumPy/Decimal are candidate generators, not the bound oracle.

### P2: Components, Scaling and Rounding

A permutation into strongly connected components makes `A` block triangular.
Its characteristic polynomial factors over diagonal blocks, so the whole
radius is their maximum. Taking the maximum of verified lower endpoints and
the maximum of upper endpoints therefore preserves enclosure. A singleton
block contributes its diagonal; a loop-free DAG has radius zero.

Each represented float and candidate coordinate is an exact rational number.
Exact rational row sums and divisions preserve P1 before final conversion.
Directed endpoint conversion preserves the inequalities. Representability
failure must deny evaluation; it must not become zero or an unchecked estimate.
This argument is conditional on correctly implemented validation, rational
arithmetic, component decomposition and endpoint conversion. It is not a
machine-checked proof of Python, NumPy, the interpreter or hardware.

Regression oracles include characteristic-polynomial inequalities for 2-by-2
matrices and new dyadic cycles satisfying `A^n = r^n*I`. For the latter,
`rho(A)=r` follows algebraically, independently of an eigensolver. Transposing
the cycles and extreme diagonal similarity preserve this identity. Deliberate
candidate eigensolver failure must still leave an enclosing interval.

### P3: Model Intervals and Admission

For a supplied entrywise interval `0 <= K_lower <= K <= K_upper`,
nonnegative matrix monotonicity gives `rho(K_lower) <= rho(K) <= rho(K_upper)`.
Numerical endpoint enclosure then permits a decision using only the upper
endpoint. Strict `upper + margin < threshold <= 1` implies subcriticality of
that represented upper matrix. Equality cannot pass. A lower endpoint or
midpoint cannot justify admission.

The premise `K <= K_upper` is a calibration/model premise, not established by
computing an eigenvalue or by checking `K_lower <= K_mean <= K_upper`.
The scalar `rho_mean` is not an expected spectral radius or a probability.

### P4: Incremental Accounting Has a Specific Baseline

Write `B = K_before_upper`, `D = DeltaK_upper >= 0`, and let `C` be the
entrywise upward-rounded representation of `B+D`. If `l_B <= rho(B)` and
`u_C >= rho(C)`, then

```text
max(0, rho(B+D) - rho(B)) <= max(0, u_C - l_B).
```

The last subtraction and conversion are outward. This establishes conservative
accounting for the declared upper-model matrices, including rounding in the
updated entries. It does not establish the same bound for an unknown `B_real`
below `B`: the lower numerical endpoint of `B` need not be below `rho(B_real)`.

An exact, dyadic counterexample with the SAME additive update is:

```text
B      = [[0, 1/2], [1/2, 0]]       rho(B)      = 1/2
B_real = [[0, 1/2], [0,   0]]       rho(B_real) = 0
D      = [[0, 0],   [9/32, 0]]

rho(B+D)      = 5/8   -> upper-model increase = 1/8
rho(B_real+D) = 3/8   -> compatible-model increase = 3/8
```

A budget of `1/4` can pass the current upper-model increment check while the
compatible-model increment exceeds it. Both matrices remain below a `0.9`
absolute spectral threshold; this is an incremental-scope counterexample,
not a counterexample to absolute upper-matrix enclosure. Tests reproduce both
`exact_recompute` and `perron_collatz_bound` modes.

To bound a latent before/after increment, a future integration must instead
supply a justified lower baseline `L <= rho(B_real)` and an after upper bound
`U >= rho(C_real)` on the same joint evidence scope. With no justified lower
baseline, zero is conservative for nonnegative matrices. Current FastGate
does not accept that separate calibrated baseline; no such feature is claimed.

### P5: Fixed Operators, Transients and Switching

For a fixed finite matrix `A`, `rho(A)<1` implies convergence of the Neumann
series. To use it for propagation, define a generation coordinate and a
consistent linear recurrence or dominating operator. A horizon label alone
does not establish that recurrence. With source-row graph weights, a column
state evolves under `K^T`, not `K`; spectral radii agree under transpose.

A DAG can have `rho(A)=0` and an arbitrarily large finite transient. For
`A=[[0,M,0],[0,0,M],[0,0,0]]`, `A^2[0,2]=M^2` and `A^3=0`.
Thus subcriticality does not bound finite-horizon impact without initial
conditions, generation depth, transient and separate loss constraints. A
finite sum over a fixed number of generations can also be finite for `rho>1`;
the subcritical gate is a conservative model policy, not necessary for every
finite-horizon acceptable outcome. The distinction between spectral radius
and matrix norm is discussed by
[Higham](https://nhigham.com/2024/01/12/what-is-the-spectral-radius-of-a-matrix/).

Separate subcritical snapshots do not prove arbitrary switching stability:
`A=[[0,2],[0,0]]`, `B=[[0,0],[2,0]]` each have radius zero, but `A*B`
has radius four. This review supplies that counterexample directly.
One sufficient additional assumption for nonnegative operators on fixed
coordinates is a COMMON entrywise envelope `0<=A_t<=U` with `rho(U)<1`:
every length-m ordered product is entrywise at most `U^m`. A common positive
vector with `U*x<=q*x`, `q<1`, also supplies a weighted-norm contraction.
Current per-request checks do not establish either temporal premise.

### P6: Numerical Accuracy Is Not Statistical Coverage

Multiplying marginal event probabilities is not a general conjunction rule.
Two identical events of probability `1/2` have joint probability `1/2`, not
`1/4`. The edge factorization is a declared model unless supported by a valid
conditional factorization, justified independence or a separately proved
conservative domination. Control factors require the same scrutiny.

Similarly two marginal `99%` coverage events with disjoint `1%` failures have
only `98%` simultaneous coverage. Interval validity for a whole graph, multiple
steps and before/after comparisons needs an explicit joint/time-scope argument.
Numerical margins are not confidence levels; hashes and source-class labels
do not prove that argument or evidence authenticity. The tests are finite
sample-space counterexamples, not empirical calibration experiments.

## Reproduction and Open Gates

For discrete loss, a strict exceedance mean is not generally expected shortfall.
With equally likely losses `(1,1,1,5)` at level `1/2`, the upper half of
probability mass has mean `3`, while conditioning strictly above the quantile
`1` gives `5`. The candidate uses a quantile-integral definition, not a new loss
estimator. Handling mass at the quantile is discussed by
[Rockafellar and Uryasev](https://sites.math.washington.edu/~rtr/papers/rtr187-CVaR2.pdf).

Run `python -m pytest tests/test_r3_mathematical_scope.py` on the corrected
source and the complete repository gates from the reviewer packet. The 28 new
cases cover 18 scaled periodic-cycle configurations, failed candidate solving,
transients, switching, 126 short switching words under a common envelope,
finite sums, two FastGate modes, dependence, simultaneous coverage and loss ties.
Existing numerical, input, fallback, resource and tamper tests remain required.

Keep test logs, interpreter/dependency versions, source identity and candidate
manifest together. Counts are execution evidence only when accompanied by a
successful receipt for those exact bytes; the existence of tests is not a PASS.

Required next gates: independently challenge P1-P6 and all R3-C findings; record
reviewer expertise, conflicts, tool use and decision; incorporate accepted
changes into a new manuscript artifact; freeze a clean immutable commit; rerun
affected local/CI/package/paper gates; obtain a separate release/archive
decision. No runtime, production, release or DOI authority follows from this
internal review.
