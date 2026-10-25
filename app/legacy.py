"""Verbatim copy of the v1 resolution prover, kept only as a benchmark baseline.

Known defects (fixed in :mod:`app.prover`): subsumption uses two-way unification
instead of one-way matching, no factoring (incomplete), the negated goal is not
Skolemized (unsound for goals with variables), and the clause set is silently
truncated to 300 clauses.
"""
# ruff: noqa
# mypy: ignore-errors
from typing import List

from app.logic import Clause, unify, resolve_clauses


class LegacyProver:
    @staticmethod
    def check_subsumes(c1: Clause, c2: Clause) -> bool:
        """Returns True if c1 subsumes c2 (i.e. there exists a substitution s such that s(c1) is a subset of c2)."""
        lits1 = list(c1.literals)
        lits2 = list(c2.literals)
        
        def search(idx, sub):
            if idx == len(lits1):
                return True
            lit = lits1[idx]
            for target in lits2:
                if lit.sign == target.sign:
                    new_sub = unify(lit.pred, target.pred, sub)
                    if new_sub is not None:
                        if search(idx + 1, new_sub):
                            return True
            return False
        return search(0, {})

    @staticmethod
    def prove_resolution(axioms: List[Clause], theorem: Clause, limit: int = 150) -> bool:
        """
        Performs resolution refutation to prove a theorem from axioms.
        Returns True if a contradiction (empty clause) can be derived, False otherwise.
        """
        # Negate the theorem to get a set of unit clauses
        negated_clauses = []
        for lit in theorem.literals:
            negated_clauses.append(Clause([lit.negate()]))
            
        clauses = list(axioms) + negated_clauses
        resolved_pairs = set()

        for iteration in range(limit):
            new_clauses = []
            n = len(clauses)
            
            for i in range(n):
                for j in range(i + 1, n):
                    c1, c2 = clauses[i], clauses[j]
                    if (c1, c2) in resolved_pairs or (c2, c1) in resolved_pairs:
                        continue
                    
                    resolved_pairs.add((c1, c2))
                    resolvents = resolve_clauses(c1, c2, iteration * 1000 + i * 10 + j)
                    
                    for res, _, _, _ in resolvents:
                        if res.is_empty():
                            return True  # Contradiction derived! Theorem holds.
                        
                        # Avoid duplicates
                        if res not in clauses and res not in new_clauses:
                            # Prune if it is already subsumed by an existing clause
                            is_subsumed = False
                            for existing in clauses:
                                if LegacyProver.check_subsumes(existing, res):
                                    is_subsumed = True
                                    break
                            if not is_subsumed:
                                new_clauses.append(res)

            if not new_clauses:
                break  # No new clauses generated, cannot prove

            clauses.extend(new_clauses)
            
            # Simple heuristic to limit search space growth
            if len(clauses) > 300:
                clauses = clauses[:300]
                
        return False
