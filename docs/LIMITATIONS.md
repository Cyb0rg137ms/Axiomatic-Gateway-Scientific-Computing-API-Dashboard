# Limitations

**Prover**
- **No built-in equality reasoning.** There is no paramodulation and no demodulation. `Equals` is an ordinary predicate, so any equality axioms a proof needs (reflexivity, symmetry, congruence) have to be stated explicitly.
- **Unrestricted binary resolution.** There is no ordering and no selection function, and no term indexing. Subsumption is forward-only and checked linearly against the processed set. PHP(5,4) does not finish in 10 s.
  - Resolution needs exponential size on pigeonhole formulas, so this is partly inherent.
  - A CDCL SAT solver would be the right tool for propositional problems like these.
- **What `saturated` means.** Binary resolution plus factoring is refutation-complete, so `saturated` really does mean "not a consequence". Most first-order problems with function symbols never saturate, though, and those end as `unknown`.
- **The independent checker** (`ProofChecker`) re-derives each resolvent using the same `unify` and `resolve_clauses` code as the prover. A bug in unification would therefore affect both, so the two are not fully independent.

**Built-in SAT fallback**
- It is a plain DPLL (no clause learning). When the GraphSAT CDCL package is installed, it is used instead.

**API**
- **No authentication and no rate limiting.** CORS is `*`. Run it behind a gateway before exposing it.
- **Single process.** The cache and the job table live in memory, are lost on restart, and are not shared between uvicorn workers.
- **Jobs.** Running jobs cannot be cancelled. Job time is bounded only by the per-request `timeout_s` (at most 30 s).
- **Optional engines.** The quantum and materials endpoints return 503 unless the sibling packages are installed. CI does not install them.
  - The quantum path was exercised locally with `qtensor-rbm` installed.
  - The materials path has **not** been exercised, because the Superconductor package does not yet expose `materials.designer`.
- **Package name.** The Python package is still named `app`, kept for v1 compatibility (`uvicorn app.main:app`). That name is generic and could collide with other installed packages.

**Backward chaining** (`prove_backward`)
- It is depth-limited SLD resolution with no tabling, so left-recursive rules are cut off at the depth limit.
