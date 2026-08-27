"""
test_logic.py
=============
Unit tests for the Axiomatic Gateway logical systems.
Covers terms, unification, clause resolution, axioms, proof checking, and derivation engines.
Contains 30+ distinct test cases to ensure deep coverage of mathematical reasoning features.
"""

import pytest
from app.logic import Var, Fn, Pred, Literal, Clause, Prop, And, Or, Implies, Not, unify, resolve_clauses
from app.axioms import AxiomRegistry
from app.proof import ProofStep, ProofChecker, DerivationEngine

# ==========================================
# 1. Term & Formula Constructor Tests (5 tests)
# ==========================================

def test_variable_creation():
    v1 = Var("x")
    v2 = Var("x")
    v3 = Var("y")
    assert v1 == v2
    assert v1 != v3
    assert repr(v1) == "x"

def test_function_creation():
    c = Fn("0")
    f = Fn("S", [Var("x")])
    assert repr(c) == "0"
    assert repr(f) == "S(x)"
    assert f == Fn("S", [Var("x")])
    assert f != Fn("S", [Var("y")])

def test_predicate_creation():
    p = Pred("Equals", [Var("x"), Fn("0")])
    assert repr(p) == "Equals(x, 0)"
    assert p == Pred("Equals", [Var("x"), Fn("0")])

def test_literal_and_negation():
    p = Pred("Member", [Var("x"), Var("y")])
    l1 = Literal(p, True)
    l2 = Literal(p, False)
    assert repr(l1) == "Member(x, y)"
    assert repr(l2) == "~Member(x, y)"
    assert l1.negate() == l2
    assert l2.negate() == l1

def test_propositional_formulas():
    p = Prop("A")
    q = Prop("B")
    conj = And(p, q)
    disj = Or(p, q)
    impl = Implies(p, q)
    neg = Not(p)
    assert repr(conj) == "(A & B)"
    assert repr(disj) == "(A | B)"
    assert repr(impl) == "(A -> B)"
    assert repr(neg) == "~A"

# ==========================================
# 2. Unification Tests (6 tests)
# ==========================================

def test_unify_identical_constants():
    sub = unify(Fn("c"), Fn("c"))
    assert sub == {}

def test_unify_variable_to_constant():
    sub = unify(Var("x"), Fn("c"))
    assert sub == {"x": Fn("c")}

def test_unify_variable_to_variable():
    sub = unify(Var("x"), Var("y"))
    assert sub == {"x": Var("y")}

def test_unify_functions():
    # unify f(x, g(y)) with f(a, g(b))
    t1 = Fn("f", [Var("x"), Fn("g", [Var("y")])])
    t2 = Fn("f", [Fn("a"), Fn("g", [Fn("b")])])
    sub = unify(t1, t2)
    assert sub == {"x": Fn("a"), "y": Fn("b")}

def test_unify_mismatch_fails():
    t1 = Fn("f", [Var("x")])
    t2 = Fn("g", [Var("x")])
    assert unify(t1, t2) is None

def test_unify_occurs_check():
    # unify x with f(x) -> should fail
    t1 = Var("x")
    t2 = Fn("f", [Var("x")])
    assert unify(t1, t2) is None

# ==========================================
# 3. Clause Resolution & Renaming Tests (5 tests)
# ==========================================

def test_clause_representation():
    l1 = Literal(Pred("P", [Var("x")]), True)
    l2 = Literal(Pred("Q", [Var("y")]), False)
    clause = Clause([l1, l2])
    assert "P(x)" in repr(clause)
    assert "~Q(y)" in repr(clause)

def test_resolution_propositional():
    # Resolve {P} and {~P}
    p = Pred("P", [])
    c1 = Clause([Literal(p, True)])
    c2 = Clause([Literal(p, False)])
    resolvents = resolve_clauses(c1, c2, 1)
    assert len(resolvents) == 1
    assert resolvents[0][0].is_empty()

def test_resolution_first_order():
    # Resolve {P(x)} and {~P(c)} -> resolvent should be empty (since x unifies with c)
    p = Pred("P", [Var("x")])
    c1 = Clause([Literal(p, True)])
    c2 = Clause([Literal(Pred("P", [Fn("c")]), False)])
    resolvents = resolve_clauses(c1, c2, 2)
    assert len(resolvents) == 1
    assert resolvents[0][0].is_empty()

def test_resolution_multiple_literals():
    # Resolve {P(x), Q(x)} and {~P(c)} -> {Q(c)}
    c1 = Clause([Literal(Pred("P", [Var("x")]), True), Literal(Pred("Q", [Var("x")]), True)])
    c2 = Clause([Literal(Pred("P", [Fn("c")]), False)])
    resolvents = resolve_clauses(c1, c2, 3)
    assert len(resolvents) == 1
    assert Literal(Pred("Q", [Fn("c")]), True) in resolvents[0][0].literals

def test_clause_subsumption():
    # c1 = {P(x)}, c2 = {P(c), Q(y)}. c1 should subsume c2.
    c1 = Clause([Literal(Pred("P", [Var("x")]), True)])
    c2 = Clause([Literal(Pred("P", [Fn("c")]), True), Literal(Pred("Q", [Var("y")]), True)])
    assert ProofChecker.check_subsumes(c1, c2) is True
    # Reverse should be false
    assert ProofChecker.check_subsumes(c2, c1) is False

# ==========================================
# 4. Axiom Registry Tests (5 tests)
# ==========================================

def test_registry_initialization():
    registry = AxiomRegistry()
    assert len(registry.get_zfc_axioms()) > 0
    assert len(registry.get_peano_axioms()) > 0
    assert len(registry.get_propositional_axioms()) > 0

def test_zfc_emptyset_axiom():
    registry = AxiomRegistry()
    zfc = registry.get_zfc_axioms()
    # Check if empty set axiom ~Member(x, emptyset) is present
    found = False
    for clause in zfc:
        if len(clause.literals) == 1:
            lit = list(clause.literals)[0]
            if lit.pred.name == "Member" and lit.pred.args[1].name == "emptyset" and not lit.sign:
                found = True
                break
    assert found is True

def test_peano_zero_axiom():
    registry = AxiomRegistry()
    peano = registry.get_peano_axioms()
    # Check if ~Equals(S(x), 0) is present
    found = False
    for clause in peano:
        if len(clause.literals) == 1:
            lit = list(clause.literals)[0]
            if lit.pred.name == "Equals" and lit.pred.args[0].name == "S" and lit.pred.args[1].name == "0" and not lit.sign:
                found = True
                break
    assert found is True

def test_peano_addition_axiom():
    registry = AxiomRegistry()
    peano = registry.get_peano_axioms()
    # Check if Equals(plus(x, 0), x) is present
    found = False
    for clause in peano:
        if len(clause.literals) == 1:
            lit = list(clause.literals)[0]
            if lit.pred.name == "Equals" and lit.pred.args[0].name == "plus" and lit.sign:
                found = True
                break
    assert found is True

def test_propositional_axioms_structure():
    registry = AxiomRegistry()
    prop_axioms = registry.get_propositional_axioms()
    # Ensure all are instances of Implies
    for ax in prop_axioms:
        assert isinstance(ax, Implies)

# ==========================================
# 5. Proof Checker Verification Tests (6 tests)
# ==========================================

def test_proof_checker_premise():
    stmt = Prop("A")
    step = ProofStep(1, stmt, "Premise")
    success, msg = ProofChecker.verify_proof([step], allowed_premises=[stmt])
    assert success is True
    assert msg == "Proof is valid"

def test_proof_checker_modus_ponens():
    A = Prop("A")
    B = Prop("B")
    steps = [
        ProofStep(1, A, "Premise"),
        ProofStep(2, Implies(A, B), "Premise"),
        ProofStep(3, B, "ModusPonens", [1, 2])
    ]
    success, msg = ProofChecker.verify_proof(steps, allowed_premises=[A, Implies(A, B)])
    assert success is True

def test_proof_checker_modus_tollens():
    A = Prop("A")
    B = Prop("B")
    steps = [
        ProofStep(1, Implies(A, B), "Premise"),
        ProofStep(2, Not(B), "Premise"),
        ProofStep(3, Not(A), "ModusTollens", [1, 2])
    ]
    success, msg = ProofChecker.verify_proof(steps, allowed_premises=[Implies(A, B), Not(B)])
    assert success is True

def test_proof_checker_conjunction():
    A = Prop("A")
    B = Prop("B")
    steps = [
        ProofStep(1, A, "Premise"),
        ProofStep(2, B, "Premise"),
        ProofStep(3, And(A, B), "AndIntro", [1, 2]),
        ProofStep(4, A, "AndElim", [3])
    ]
    success, msg = ProofChecker.verify_proof(steps, allowed_premises=[A, B])
    assert success is True

def test_proof_checker_disjunction_and_dn():
    A = Prop("A")
    B = Prop("B")
    steps = [
        ProofStep(1, A, "Premise"),
        ProofStep(2, Or(A, B), "OrIntro", [1]),
        ProofStep(3, Not(Not(A)), "Premise"),
        ProofStep(4, A, "DNElim", [3])
    ]
    success, msg = ProofChecker.verify_proof(steps, allowed_premises=[A, Not(Not(A))])
    assert success is True

def test_proof_checker_resolution():
    p = Pred("P", [])
    c1 = Clause([Literal(p, True)])
    c2 = Clause([Literal(p, False)])
    empty = Clause([])
    steps = [
        ProofStep(1, c1, "Premise"),
        ProofStep(2, c2, "Premise"),
        ProofStep(3, empty, "Resolution", [1, 2])
    ]
    success, msg = ProofChecker.verify_proof(steps, allowed_premises=[c1, c2])
    assert success is True

# ==========================================
# 6. Derivation Engine Tests (6 tests)
# ==========================================

def test_backward_chaining_basic():
    # Database: P(x) <- Q(x). Fact: Q(c). Goal: P(c).
    x = Var("x")
    c = Fn("c")
    database = [
        Clause([Literal(Pred("P", [x]), True), Literal(Pred("Q", [x]), False)]),
        Clause([Literal(Pred("Q", [c]), True)])
    ]
    goals = [Literal(Pred("P", [c]), True)]
    solutions = DerivationEngine.prove_backward(goals, database)
    assert len(solutions) > 0
    assert solutions[0] == {"x_d0": c}

def test_backward_chaining_no_solution():
    x = Var("x")
    c = Fn("c")
    d = Fn("d")
    database = [
        Clause([Literal(Pred("P", [x]), True), Literal(Pred("Q", [x]), False)]),
        Clause([Literal(Pred("Q", [d]), True)])
    ]
    goals = [Literal(Pred("P", [c]), True)]
    solutions = DerivationEngine.prove_backward(goals, database)
    assert len(solutions) == 0

def test_resolution_proving_simple():
    # Axioms: A | B, ~A. Theorem: B.
    A = Pred("A", [])
    B = Pred("B", [])
    axioms = [
        Clause([Literal(A, True), Literal(B, True)]),
        Clause([Literal(A, False)])
    ]
    theorem = Clause([Literal(B, True)])
    result = DerivationEngine.prove_resolution(axioms, theorem)
    assert result is True

def test_resolution_proving_first_order():
    # Axioms: For all x, P(x) -> Q(x). P(c). Theorem: Q(c).
    # In CNF:
    # 1. ~P(x) | Q(x)
    # 2. P(c)
    x = Var("x")
    c = Fn("c")
    axioms = [
        Clause([Literal(Pred("P", [x]), False), Literal(Pred("Q", [x]), True)]),
        Clause([Literal(Pred("P", [c]), True)])
    ]
    theorem = Clause([Literal(Pred("Q", [c]), True)])
    result = DerivationEngine.prove_resolution(axioms, theorem)
    assert result is True

def test_resolution_proving_unsatisfiable_fails():
    # Axioms: P(c). Theorem: ~P(c) -> wait, proving ~P(c) from P(c) should fail
    c = Fn("c")
    axioms = [Clause([Literal(Pred("P", [c]), True)])]
    theorem = Clause([Literal(Pred("P", [c]), False)])
    result = DerivationEngine.prove_resolution(axioms, theorem)
    assert result is False

def test_resolution_proving_peano_successor():
    # Prove that S(0) != 0 from Peano axioms
    registry = AxiomRegistry()
    peano = registry.get_peano_axioms()
    # Theorem: S(0) != 0
    # Let's check if the theorem is one of the axioms or if we can prove it.
    # Axiom: ~Equals(S(x), 0)
    # Theorem: ~Equals(S(0), 0)
    theorem = Clause([Literal(Pred("Equals", [Fn("S", [Fn("0")]), Fn("0")]), False)])
    result = DerivationEngine.prove_resolution(peano, theorem)
    assert result is True
