"""Given-clause resolution prover with factoring, subsumption and self-checked proofs.

This replaces the v1 "resolve every pair, truncate at 300 clauses" loop. The
calculus is binary resolution + binary factoring, which is refutation-complete for
first-order clause sets *without equality* when run without a budget (Robinson,
1965). Equality is treated as an ordinary predicate, so theories that need
equality reasoning must state the equality axioms they rely on.

Every proof found is replayed through :class:`app.proof.ProofChecker`, an
independent step-by-step checker, before ``status == "proved"`` is reported.
"""

from __future__ import annotations

import functools
import heapq
import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple
from typing import Literal as Lit

from app.logic import (
    Clause,
    Fn,
    Pred,
    Term,
    Var,
    factors,
    is_tautology,
    negate_goal,
    resolve_clauses,
    subsumes,
    symbol_count,
)

log = logging.getLogger(__name__)

Status = Lit["proved", "saturated", "unknown"]


@dataclass(frozen=True)
class Derived:
    """A clause plus the inference that produced it."""

    id: int
    clause: Clause
    rule: str  # "axiom" | "negated_goal" | "resolution" | "factor"
    parents: Tuple[int, ...] = ()


@dataclass
class ProveResult:
    """Outcome of :func:`prove`.

    ``status``:
      * ``proved``    - empty clause derived and the proof passed the checker;
      * ``saturated`` - no new clauses can be derived: the input is satisfiable
        (the goal does *not* follow), valid only because the calculus is complete;
      * ``unknown``   - a budget (time / iterations / clauses) ran out.
    """

    status: Status
    proof: List[Derived] = field(default_factory=list)
    iterations: int = 0
    generated: int = 0
    kept: int = 0
    elapsed_s: float = 0.0
    reason: str = ""
    verified: Optional[bool] = None

    def to_dict(self) -> Dict[str, object]:
        return {
            "status": self.status,
            "verified": self.verified,
            "iterations": self.iterations,
            "generated": self.generated,
            "kept": self.kept,
            "elapsed_ms": round(self.elapsed_s * 1e3, 3),
            "reason": self.reason,
            "proof": [
                {"id": d.id, "clause": str(d.clause), "rule": d.rule, "parents": list(d.parents)} for d in self.proof
            ],
        }


def _canonical(clause: Clause) -> str:
    """Variable-renaming-invariant key used only for duplicate detection."""
    names: Dict[str, str] = {}

    def term(t: object) -> str:
        if isinstance(t, Var):
            if t.name not in names:
                names[t.name] = f"V{len(names)}"
            return names[t.name]
        if isinstance(t, (Fn, Pred)):
            if not t.args:
                return t.name
            return f"{t.name}({','.join(term(a) for a in t.args)})"
        return str(t)

    # Sort by a variable-free skeleton first so renaming does not change the order.
    def skeleton(lit: object) -> str:
        return str(lit).translate(str.maketrans("", "", "abcdefghijklmnopqrstuvwxyz_0123456789"))

    lits = sorted(clause.literals, key=lambda lit: (skeleton(lit), lit.sign, lit.pred.name))
    return " | ".join(("" if lit.sign else "~") + term(lit.pred) for lit in lits)


def prove(
    axioms: Sequence[Clause],
    goal: Optional[Clause] = None,
    *,
    max_iterations: int = 5000,
    max_clauses: int = 50_000,
    timeout_s: float = 10.0,
    age_ratio: int = 5,
    verify: bool = True,
) -> ProveResult:
    """Refute ``axioms ∧ ¬goal`` by given-clause saturation.

    ``goal`` is a clause (implicitly universally quantified) whose negation is
    Skolemized; pass ``None`` to test ``axioms`` alone for unsatisfiability.
    Selection alternates lightest-first with oldest-first (``age_ratio``: one
    oldest pick every ``age_ratio`` picks), which keeps the search fair.
    """
    t0 = time.perf_counter()
    store: List[Derived] = []
    seen: set[str] = set()
    passive: List[Tuple[int, int]] = []  # (weight, id) min-heap
    age_queue: List[int] = []  # ids in creation order
    age_pos = 0
    processed: List[Derived] = []
    result = ProveResult(status="unknown")

    def add(clause: Clause, rule: str, parents: Tuple[int, ...]) -> Optional[Derived]:
        result.generated += 1
        if is_tautology(clause):
            return None
        key = _canonical(clause)
        if key in seen:
            return None
        if any(_subsumes_strict(p.clause, clause) for p in processed):
            return None
        seen.add(key)
        d = Derived(len(store), clause, rule, parents)
        store.append(d)
        heapq.heappush(passive, (symbol_count(clause), d.id))
        age_queue.append(d.id)
        return d

    def finish(status: Status, empty: Optional[Derived], reason: str) -> ProveResult:
        result.status = status
        result.reason = reason
        result.kept = len(store)
        if empty is not None:
            result.proof = _extract(store, empty)
            if verify:
                result.verified = verify_proof(result.proof, axioms, goal)
                if not result.verified:  # pragma: no cover - would indicate a prover bug
                    result.status = "unknown"
                    result.reason = "internal error: proof failed independent check"
                    log.error("proof failed verification: %s", result.reason)
        result.elapsed_s = time.perf_counter() - t0
        return result

    inputs = [(c, "axiom") for c in axioms]
    if goal is not None:
        inputs += [(c, "negated_goal") for c in negate_goal(goal)]
    for c, rule in inputs:
        if c.is_empty():
            d = Derived(len(store), c, rule)
            store.append(d)
            return finish("proved", d, "input contains the empty clause")
        add(c, rule, ())

    done: set[int] = set()
    while True:
        if result.iterations >= max_iterations:
            return finish("unknown", None, f"iteration budget {max_iterations} exhausted")
        if len(store) >= max_clauses:
            return finish("unknown", None, f"clause budget {max_clauses} exhausted")
        if time.perf_counter() - t0 > timeout_s:
            return finish("unknown", None, f"timeout {timeout_s}s")
        # pick the given clause
        given: Optional[Derived] = None
        use_age = age_ratio > 0 and result.iterations % age_ratio == age_ratio - 1
        while given is None:
            if use_age:
                while age_pos < len(age_queue) and age_queue[age_pos] in done:
                    age_pos += 1
                if age_pos >= len(age_queue):
                    use_age = False
                    continue
                cand = age_queue[age_pos]
            else:
                while passive and passive[0][1] in done:
                    heapq.heappop(passive)
                if not passive:
                    return finish("saturated", None, "no unprocessed clauses remain")
                cand = heapq.heappop(passive)[1]
            done.add(cand)
            given = store[cand]
        result.iterations += 1
        if any(_subsumes_strict(p.clause, given.clause) for p in processed):
            continue
        processed.append(given)
        new: List[Tuple[Clause, str, Tuple[int, ...]]] = []
        for f, _ in factors(given.clause):
            new.append((f, "factor", (given.id,)))
        for other in processed:
            for res, _, _, _ in resolve_clauses(given.clause, other.clause, result.iterations):
                new.append((res, "resolution", (given.id, other.id)))
        for clause, rule, parents in new:
            if clause.is_empty():
                d = Derived(len(store), clause, rule, parents)
                store.append(d)
                return finish("proved", d, "empty clause derived")
            add(clause, rule, parents)


def _subsumes_strict(c: Clause, d: Clause) -> bool:
    """Subsumption restricted to |C| <= |D|, so a clause never deletes its own factors."""
    if len(c.literals) > len(d.literals):
        return False
    if not _signature(c) <= _signature(d):  # cheap pre-filter on (predicate, sign) sets
        return False
    return subsumes(c, d)


@functools.lru_cache(maxsize=65536)
def _signature(c: Clause) -> frozenset[Tuple[str, bool]]:
    # keyed by the (hashable, immutable) clause itself - not by id(), which CPython reuses
    return frozenset((lit.pred.name, lit.sign) for lit in c.literals)


def _extract(store: List[Derived], empty: Derived) -> List[Derived]:
    needed: set[int] = set()
    stack = [empty.id]
    while stack:
        i = stack.pop()
        if i in needed:
            continue
        needed.add(i)
        stack.extend(store[i].parents)
    return [store[i] for i in sorted(needed)]


def verify_proof(proof: Sequence[Derived], axioms: Sequence[Clause], goal: Optional[Clause]) -> bool:
    """Replay a proof through the independent :class:`ProofChecker`."""
    from app.proof import ProofChecker, ProofStep

    rule_map = {"axiom": "Axiom", "negated_goal": "Premise", "resolution": "Resolution", "factor": "Factor"}
    steps = [ProofStep(d.id, d.clause, rule_map[d.rule], list(d.parents)) for d in proof]
    premises: List[Clause] = negate_goal(goal) if goal is not None else []
    ok, msg = ProofChecker.verify_proof(steps, axioms=list(axioms), allowed_premises=list(premises))  # type: ignore[arg-type]
    if not ok:
        log.error("proof check failed: %s", msg)
        return False
    return bool(proof) and proof[-1].clause.is_empty()


__all__ = ["Derived", "ProveResult", "Term", "prove", "verify_proof"]
