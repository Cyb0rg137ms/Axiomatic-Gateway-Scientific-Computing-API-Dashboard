"""
proof.py
========
Proof verification system and automated theorem proving engines.
Includes:
1. ProofChecker: Verifies step-by-step proofs using resolution or natural deduction rules.
2. DerivationEngine: Performs automated backward-chaining (SLD-resolution) and resolution-based refutation.
"""

import itertools
from typing import Dict, List, Optional, Tuple, Union

from app.logic import (
    And,
    Clause,
    Formula,
    Implies,
    Literal,
    Not,
    Or,
    Prop,
    Term,
    apply_sub_lit,
    factors,
    is_instance,
    rename_variables,
    resolve_clauses,
    subsumes,
    unify,
)

_fresh = itertools.count()

class ProofStep:
    """Represents a single step in a formal proof."""
    def __init__(self, step_id: int, statement: Union[Clause, Formula], rule: str, premises: Optional[List[int]] = None):
        self.step_id = step_id
        self.statement = statement
        self.rule = rule  # "Premise", "Axiom", "Resolution", "ModusPonens", "ModusTollens", "AndIntro", "AndElim", "OrIntro", "DNElim"
        self.premises = premises or []

    def __repr__(self):
        return f"{self.step_id}: {self.statement} ({self.rule} {self.premises})"

class ProofChecker:
    """Verifies the correctness of step-by-step proofs."""

    @staticmethod
    def verify_proof(proof: List[ProofStep], axioms: Optional[List[Union[Clause, Formula]]] = None, allowed_premises: Optional[List[Union[Clause, Formula]]] = None) -> Tuple[bool, str]:
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
                        # v2: exact instance check via one-way matching. v1 used two-way
                        # unification, which accepted P(x) as an "instance" of P(a).
                        if is_instance(ax, stmt):
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
                    # Sound: any clause subsumed by a resolvent is a consequence of it.
                    if subsumes(res, stmt):
                        valid_resolution = True
                        break
                if not valid_resolution:
                    return False, f"Step {step.step_id}: Clause {stmt} is not a valid resolvent of {c1} and {c2}."
                steps_by_id[step.step_id] = stmt

            elif rule == "Factor":
                if len(prems) != 1 or prems[0] not in steps_by_id:
                    return False, f"Step {step.step_id}: Factor requires 1 verified premise."
                c1 = steps_by_id[prems[0]]
                if not isinstance(c1, Clause) or not isinstance(stmt, Clause):
                    return False, f"Step {step.step_id}: Factor premise and target must be Clauses."
                if not any(subsumes(f, stmt) for f, _ in factors(c1)):
                    return False, f"Step {step.step_id}: Clause {stmt} is not a factor of {c1}."
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
                if stmt != And(p1, p2):  # type: ignore[arg-type]
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
    def match_formula(pattern: Formula, instance: Formula, sub: Optional[Dict[str, Formula]] = None) -> Optional[Dict[str, Formula]]:
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
            sub2 = ProofChecker.match_formula(pattern.left, instance.left, sub)
            if sub2 is None:
                return None
            return ProofChecker.match_formula(pattern.right, instance.right, sub2)
        if isinstance(pattern, Or) and isinstance(instance, Or):
            sub2 = ProofChecker.match_formula(pattern.left, instance.left, sub)
            if sub2 is None:
                return None
            return ProofChecker.match_formula(pattern.right, instance.right, sub2)
        if isinstance(pattern, Implies) and isinstance(instance, Implies):
            sub2 = ProofChecker.match_formula(pattern.antecedent, instance.antecedent, sub)
            if sub2 is None:
                return None
            return ProofChecker.match_formula(pattern.consequent, instance.consequent, sub2)
        if isinstance(pattern, Not) and isinstance(instance, Not):
            return ProofChecker.match_formula(pattern.formula, instance.formula, sub)
        return None

    @staticmethod
    def check_subsumes(c1: Clause, c2: Clause) -> bool:
        """True if c1 subsumes c2 (one-way matching; v1 wrongly used unification)."""
        return subsumes(c1, c2)


class DerivationEngine:
    """Engine for automated proof search and derivation."""

    @staticmethod
    def prove_backward(goals: List[Literal], database: List[Clause], limit: int = 5, depth: int = 0, sub: Optional[Dict[str, Term]] = None) -> List[Dict[str, Term]]:
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
            clause_renamed = rename_variables(clause, f"d{next(_fresh)}")
            
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
        """Back-compatible wrapper: True iff the given-clause prover finds a refutation.

        ``limit`` is kept for API compatibility and maps to a budget of
        ``limit * 20`` given-clause iterations. False means "not proved within
        budget", not "false".
        """
        from app.prover import prove

        return prove(axioms, theorem, max_iterations=limit * 20).status == "proved"
