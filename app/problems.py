"""A small, versioned problem suite with known answers, used by tests and benchmarks.

Each problem states its expected outcome. ``proved`` problems are theorems;
``saturated`` problems are non-theorems on which a complete prover must stop.
Pigeonhole instances PHP(n+1, n) are generated, because their resolution
refutations are known to need size exponential in n (Haken, 1985) - they are a
stress test, not a target.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from app.axioms import AxiomRegistry
from app.logic import Clause, Fn, Literal, Pred
from app.parser import parse_clause, parse_clauses


@dataclass(frozen=True)
class Problem:
    name: str
    axioms: List[Clause]
    goal: Optional[Clause]
    expected: str  # "proved" | "saturated"
    description: str


def _peano() -> List[Clause]:
    return AxiomRegistry().get_peano_axioms()


def _eq(a: object, b: object, sign: bool = True) -> Clause:
    return Clause([Literal(Pred("Equals", [a, b]), sign)])  # type: ignore[list-item]


def pigeonhole(holes: int) -> Problem:
    """PHP(holes+1, holes): unsatisfiable propositional CNF."""
    pigeons = holes + 1
    cls: List[Clause] = []
    for i in range(pigeons):
        cls.append(Clause([Literal(Pred(f"p{i}_{j}", [])) for j in range(holes)]))
    for j in range(holes):
        for i in range(pigeons):
            for k in range(i + 1, pigeons):
                cls.append(Clause([Literal(Pred(f"p{i}_{j}", []), False), Literal(Pred(f"p{k}_{j}", []), False)]))
    return Problem(f"php_{pigeons}_{holes}", cls, None, "proved", f"{pigeons} pigeons cannot fit in {holes} holes")


def suite() -> Dict[str, Problem]:
    zero = Fn("0")
    s0 = Fn("S", [zero])
    ss0 = Fn("S", [s0])
    probs = [
        Problem(
            "syllogism",
            parse_clauses(["~man(X) | mortal(X)", "man(socrates)"]),
            parse_clause("mortal(socrates)"),
            "proved",
            "All men are mortal; Socrates is a man.",
        ),
        Problem(
            "modus_ponens",
            parse_clauses(["~p | q", "p"]),
            parse_clause("q"),
            "proved",
            "Propositional modus ponens.",
        ),
        Problem(
            "needs_factoring",
            parse_clauses(["p(X) | p(Y)", "~p(U) | ~p(V)"]),
            None,
            "proved",
            "Unsatisfiable, but has no refutation by binary resolution without factoring.",
        ),
        Problem(
            "transitivity_chain",
            parse_clauses(["~lt(X,Y) | ~lt(Y,Z) | lt(X,Z)"] + [f"lt(c{i},c{i + 1})" for i in range(6)]),
            parse_clause("lt(c0,c6)"),
            "proved",
            "Transitive closure over a 7-element chain.",
        ),
        Problem("peano_s0_ne_0", _peano(), _eq(s0, zero, False), "proved", "S(0) != 0 (Peano axiom 1 instance)."),
        Problem("peano_ss0_ne_s0", _peano(), _eq(ss0, s0, False), "proved", "S(S(0)) != S(0) via injectivity of S."),
        Problem(
            "zfc_empty_has_no_members",
            AxiomRegistry().get_zfc_axioms(),
            Clause([Literal(Pred("Member", [Fn("a"), Fn("emptyset")]), False)]),
            "proved",
            "a is not a member of the empty set.",
        ),
        Problem(
            "drinker_style_non_theorem",
            parse_clauses(["p(a)"]),
            parse_clause("p(X)"),
            "saturated",
            "p(a) does NOT entail forall X. p(X); v1 'proved' this (unsound).",
        ),
        Problem(
            "satisfiable_set",
            parse_clauses(["p | q", "~p | q", "p | ~q"]),
            None,
            "saturated",
            "Satisfiable (p=q=true), so no refutation exists.",
        ),
    ]
    probs += [pigeonhole(h) for h in (2, 3, 4)]
    return {p.name: p for p in probs}
