"""
proof.py
========
Proof verification system and automated theorem proving engines.
Includes:
1. ProofChecker: Verifies step-by-step proofs using resolution or natural deduction rules.
2. DerivationEngine: Performs automated backward-chaining (SLD-resolution) and resolution-based refutation.
"""

import copy
from typing import Dict, Any, List, Set, Optional, Tuple, Union
from app.logic import (
    Term, Var, Fn, Pred, Literal, Clause, Formula, Prop, And, Or, Implies, Not,
    apply_sub_term, apply_sub_pred, apply_sub_lit, apply_sub_clause, unify, resolve_clauses,
    rename_variables
)

class ProofStep:
    """Represents a single step in a formal proof."""
    def __init__(self, step_id: int, statement: Union[Clause, Formula], rule: str, premises: List[int] = None):
        self.step_id = step_id
        self.statement = statement
        self.rule = rule  # "Premise", "Axiom", "Resolution", "ModusPonens", "ModusTollens", "AndIntro", "AndElim", "OrIntro", "DNElim"
        self.premises = premises or []

    def __repr__(self):
        return f"{self.step_id}: {self.statement} ({self.rule} {self.premises})"

class ProofChecker:
    """Verifies the correctness of step-by-step proofs."""

    @staticmethod
    def verify_proof(proof: List[ProofStep], axioms: List[Union[Clause, Formula]] = None, allowed_premises: List[Union[Clause, Formula]] = None) -> Tuple[bool, str]:
        """
        Verifies a list of proof steps.
        Returns (True, "Proof is valid") if correct, else (False, error_message).
        """
        axioms = axioms or []
        allowed_premises = allowed_premises or []
        
        # Store verified statements by step_id
        steps_by_id: Dict[int, Union[Clause, Formula]] = {}

        for index, step in enumerate(proof):
            rule = step.rule
            stmt = step.statement
            prems = step.premises

            if rule == "Premise":
                # Must be in allowed_premises
                if stmt not in allowed_premises:
                    return False, f"Step {step.step_id}: Statement {stmt} is not an allowed premise."
                steps_by_id[step.step_id] = stmt

            elif rule == "Axiom":
                # For Clause representation (ZFC/Peano), check if it's identical or a substitution instance of an axiom.
                # For Formula representation (Propositional), check if it matches a propositional axiom pattern.
                is_valid = False
                for ax in axioms:
                    if isinstance(ax, Clause) and isinstance(stmt, Clause):
                        # Try to unify/subsume
                        if ProofChecker.check_subsumes(ax, stmt) and len(ax.literals) == len(stmt.literals):
                            is_valid = True
                            break
                    elif isinstance(ax, Formula) and isinstance(stmt, Formula):
                        if ProofChecker.match_formula(ax, stmt) is not None:
                            is_valid = True
                            break
                if not is_valid:
                    return False, f"Step {step.step_id}: Statement {stmt} is not a valid axiom instance."
                steps_by_id[step.step_id] = stmt

            elif rule == "Resolution":
                if len(prems) != 2:
                    return False, f"Step {step.step_id}: Resolution requires exactly 2 premises."
                if not all(p in steps_by_id for p in prems):
                    return False, f"Step {step.step_id}: Premise steps {prems} must be verified before this step."
                
                c1 = steps_by_id[prems[0]]
                c2 = steps_by_id[prems[1]]
                if not isinstance(c1, Clause) or not isinstance(c2, Clause) or not isinstance(stmt, Clause):
                    return False, f"Step {step.step_id}: Resolution premises and target must be Clauses."

                # Generate all possible resolvents
                resolvents = resolve_clauses(c1, c2, step.step_id)
                valid_resolution = False
                for res, _, _, _ in resolvents:
                    # Check if the target clause is equivalent to the resolvent (bi-subsumption)
                    if ProofChecker.check_subsumes(res, stmt) and ProofChecker.check_subsumes(stmt, res):
                        valid_resolution = True
                        break
                if not valid_resolution:
                    return False, f"Step {step.step_id}: Clause {stmt} is not a valid resolvent of {c1} and {c2}."
                steps_by_id[step.step_id] = stmt

            elif rule == "ModusPonens":
                if len(prems) != 2:
                    return False, f"Step {step.step_id}: Modus Ponens requires exactly 2 premises."
                if not all(p in steps_by_id for p in prems):
                    return False, f"Step {step.step_id}: Premise steps {prems} must be verified before this step."
                
                p1 = steps_by_id[prems[0]]
                p2 = steps_by_id[prems[1]]
                
                # One must be A -> B and the other A.
                # Find which is which
                antecedent, consequent = None, None
                if isinstance(p1, Implies):
                    if p1.antecedent == p2:
                        antecedent = p1.antecedent
                        consequent = p1.consequent
                if isinstance(p2, Implies) and consequent is None:
                    if p2.antecedent == p1:
                        antecedent = p2.antecedent
                        consequent = p2.consequent
                        
                if consequent is None or consequent != stmt:
                    return False, f"Step {step.step_id}: Invalid Modus Ponens application with {p1} and {p2} to derive {stmt}."
                steps_by_id[step.step_id] = stmt

            elif rule == "ModusTollens":
                if len(prems) != 2:
                    return False, f"Step {step.step_id}: Modus Tollens requires exactly 2 premises."
                if not all(p in steps_by_id for p in prems):
                    return False, f"Step {step.step_id}: Premise steps {prems} must be verified before this step."
                
                p1 = steps_by_id[prems[0]]
                p2 = steps_by_id[prems[1]]
                
                # One must be A -> B and the other ~B. Target must be ~A.
                impl, neg = None, None
                if isinstance(p1, Implies) and isinstance(p2, Not):
                    if p1.consequent == p2.formula:
                        impl, neg = p1, p2
                elif isinstance(p2, Implies) and isinstance(p1, Not):
                    if p2.consequent == p1.formula:
                        impl, neg = p2, p1
                        
                if impl is None or Not(impl.antecedent) != stmt:
                    return False, f"Step {step.step_id}: Invalid Modus Tollens application with {p1} and {p2} to derive {stmt}."
                steps_by_id[step.step_id] = stmt

            elif rule == "AndIntro":
                if len(prems) != 2:
                    return False, f"Step {step.step_id}: AndIntro requires exactly 2 premises."
                if not all(p in steps_by_id for p in prems):
                    return False, f"Step {step.step_id}: Premise steps {prems} must be verified."
                
                p1 = steps_by_id[prems[0]]
                p2 = steps_by_id[prems[1]]
                if stmt != And(p1, p2):
                    return False, f"Step {step.step_id}: Statement {stmt} is not the conjunction of {p1} and {p2}."
                steps_by_id[step.step_id] = stmt

            elif rule == "AndElim":
                if len(prems) != 1:
                    return False, f"Step {step.step_id}: AndElim requires exactly 1 premise."
                if prems[0] not in steps_by_id:
                    return False, f"Step {step.step_id}: Premise step {prems[0]} must be verified."
                
                p1 = steps_by_id[prems[0]]
                if not isinstance(p1, And):
                    return False, f"Step {step.step_id}: Premise {p1} is not an And formula."
                if stmt != p1.left and stmt != p1.right:
                    return False, f"Step {step.step_id}: Statement {stmt} is not a conjunct of {p1}."
                steps_by_id[step.step_id] = stmt

            elif rule == "OrIntro":
                if len(prems) != 1:
                    return False, f"Step {step.step_id}: OrIntro requires exactly 1 premise."
                if prems[0] not in steps_by_id:
                    return False, f"Step {step.step_id}: Premise step {prems[0]} must be verified."
                
                p1 = steps_by_id[prems[0]]
                if not isinstance(stmt, Or) or (stmt.left != p1 and stmt.right != p1):
                    return False, f"Step {step.step_id}: Statement {stmt} is not a valid disjunction containing {p1}."
                steps_by_id[step.step_id] = stmt

            elif rule == "DNElim":
                if len(prems) != 1:
                    return False, f"Step {step.step_id}: DNElim requires exactly 1 premise."
                if prems[0] not in steps_by_id:
                    return False, f"Step {step.step_id}: Premise step {prems[0]} must be verified."
                
                p1 = steps_by_id[prems[0]]
                if not isinstance(p1, Not) or not isinstance(p1.formula, Not):
                    return False, f"Step {step.step_id}: Premise {p1} is not a double negation."
                if stmt != p1.formula.formula:
                    return False, f"Step {step.step_id}: Statement {stmt} does not match double-negation elimination of {p1}."
                steps_by_id[step.step_id] = stmt

            else:
                return False, f"Step {step.step_id}: Unknown rule of inference '{rule}'."

        return True, "Proof is valid"

    @staticmethod
    def match_formula(pattern: Formula, instance: Formula, sub: Dict[str, Formula] = None) -> Optional[Dict[str, Formula]]:
        """Matches a formula pattern (with Prop variables) against an instance formula."""
        if sub is None:
            sub = {}
        if isinstance(pattern, Prop):
            if pattern.name in sub:
                return sub if sub[pattern.name] == instance else None
            new_sub = dict(sub)
            new_sub[pattern.name] = instance
            return new_sub
        if type(pattern) != type(instance):
            return None
        if isinstance(pattern, And) and isinstance(instance, And):
            sub = ProofChecker.match_formula(pattern.left, instance.left, sub)
            if sub is None:
                return None
            return ProofChecker.match_formula(pattern.right, instance.right, sub)
        if isinstance(pattern, Or) and isinstance(instance, Or):
            sub = ProofChecker.match_formula(pattern.left, instance.left, sub)
            if sub is None:
                return None
            return ProofChecker.match_formula(pattern.right, instance.right, sub)
        if isinstance(pattern, Implies) and isinstance(instance, Implies):
            sub = ProofChecker.match_formula(pattern.antecedent, instance.antecedent, sub)
            if sub is None:
                return None
            return ProofChecker.match_formula(pattern.consequent, instance.consequent, sub)
        if isinstance(pattern, Not) and isinstance(instance, Not):
            return ProofChecker.match_formula(pattern.formula, instance.formula, sub)
        return None

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

class DerivationEngine:
    """Engine for automated proof search and derivation."""

    @staticmethod
    def prove_backward(goals: List[Literal], database: List[Clause], limit: int = 5, depth: int = 0, sub: Dict[str, Term] = None) -> List[Dict[str, Term]]:
        """
        Performs backward-chaining (SLD-resolution) proof search with depth limits.
        Returns a list of successful substitutions.
        """
        if sub is None:
            sub = {}
        if depth > limit:
            return []
        if not goals:
            return [sub]

        first = goals[0]
        rest = goals[1:]
        first_substituted = apply_sub_lit(first, sub)

        results = []
        for clause in database:
            # Standardize variables apart
            clause_renamed = rename_variables(clause, f"d{depth}")
            
            pos_lits = [l for l in clause_renamed.literals if l.sign]
            neg_lits = [l for l in clause_renamed.literals if not l.sign]

            if len(pos_lits) == 1:
                head = pos_lits[0]
                if first_substituted.sign == head.sign:
                    new_sub = unify(first_substituted.pred, head.pred, sub)
                    if new_sub is not None:
                        # Convert negated body literals into positive subgoals
                        subgoals = [Literal(l.pred, True) for l in neg_lits]
                        new_goals = subgoals + rest
                        solutions = DerivationEngine.prove_backward(new_goals, database, limit, depth + 1, new_sub)
                        results.extend(solutions)
        return results

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
                                if ProofChecker.check_subsumes(existing, res):
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
