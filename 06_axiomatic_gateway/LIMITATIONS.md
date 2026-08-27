"""
LIMITATIONS.md — Axiomatic Gateway
===================================

# Known Limitations and Future Work

## 1. Resolution Theorem Prover Performance
The resolution-based theorem prover in `proof.py` uses a simple saturation-based resolution loop:
- **Search Space Explosion**: In first-order logic, the number of generated resolvents can grow exponentially with the number of clauses. We mitigate this using basic subsumption checking and capping the maximum clause count at 300.
- **Advanced Strategies**: For complex mathematical proofs, more advanced search strategies (such as unit resolution, set-of-support resolution, ordered resolution, and term indexing) should be implemented.
- **Equality handling**: Currently, equality is handled as a standard relation. Integrating **paramodulation** or **demodulation** would dramatically speed up reasoning on equations in Peano arithmetic.

## 2. Backward-Chaining Engine
The `prove_backward` engine performs depth-limited backward-chaining (SLD-resolution):
- It is sensitive to the order of clauses. Left-recursive rules can cause infinite loops if the depth limit is set too high or if no limit is applied.
- It does not support negation-as-failure (NAF) or stratified datalog negation, which limit its expressiveness.

## 3. Natural Deduction Scope
The `ProofChecker` currently verifies step-by-step proofs for propositional logic and first-order clauses:
- It supports the main natural deduction rules (Modus Ponens, Modus Tollens, Conjunction, Disjunction, Double Negation).
- Universal and existential quantifier rules (introduction and elimination) are not fully supported for general natural deduction formulas. Instead, we use Skolemization and CNF conversion to resolve them via the resolution engine.
"""
