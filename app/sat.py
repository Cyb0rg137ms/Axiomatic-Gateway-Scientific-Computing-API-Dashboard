"""Built-in DPLL SAT solver used when the optional GraphSAT engine is not installed.

Small and dependency-free: unit propagation + pure-literal elimination + most-
frequent-variable branching, iterative with an explicit trail. Every SAT model
is checked against the clauses before it is returned. Not competitive with CDCL
solvers on large instances (see docs/LIMITATIONS.md).
"""

from __future__ import annotations

import time
from collections import Counter
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence


@dataclass
class SatResult:
    status: str  # "SAT" | "UNSAT" | "UNKNOWN"
    model: Optional[List[int]]
    decisions: int
    elapsed_ms: float


def validate_cnf(num_vars: int, clauses: Sequence[Sequence[int]]) -> None:
    if num_vars < 0:
        raise ValueError("num_vars must be >= 0")
    for c in clauses:
        for lit in c:
            if lit == 0 or abs(lit) > num_vars:
                raise ValueError(f"literal {lit} out of range 1..{num_vars}")


def check_model(clauses: Sequence[Sequence[int]], model: Sequence[int]) -> bool:
    true = set(model)
    return all(any(lit in true for lit in c) for c in clauses)


def _simplify(clauses: List[List[int]], lit: int) -> Optional[List[List[int]]]:
    out: List[List[int]] = []
    for c in clauses:
        if lit in c:
            continue
        if -lit in c:
            reduced = [x for x in c if x != -lit]
            if not reduced:
                return None
            out.append(reduced)
        else:
            out.append(c)
    return out


def solve_dpll(num_vars: int, clauses: Sequence[Sequence[int]], timeout_s: float = 10.0) -> SatResult:
    validate_cnf(num_vars, clauses)
    t0 = time.perf_counter()
    decisions = 0
    start = [sorted(set(c)) for c in clauses]
    if any(not c for c in start):
        return SatResult("UNSAT", None, 0, 0.0)
    stack: List[tuple[List[List[int]], Dict[int, bool]]] = [(start, {})]
    while stack:
        if time.perf_counter() - t0 > timeout_s:
            return SatResult("UNKNOWN", None, decisions, (time.perf_counter() - t0) * 1e3)
        cls, assign = stack.pop()
        conflict = False
        while True:  # unit propagation + pure literals
            unit = next((c[0] for c in cls if len(c) == 1), None)
            if unit is None:
                counts = Counter(lit for c in cls for lit in c)
                pure = next((lit for lit in counts if -lit not in counts), None)
                if pure is None:
                    break
                unit = pure
            assign[abs(unit)] = unit > 0
            nxt = _simplify(cls, unit)
            if nxt is None:
                conflict = True
                break
            cls = nxt
        if conflict:
            continue
        if not cls:
            model = [v if assign.get(v, False) else -v for v in range(1, num_vars + 1)]
            assert check_model(clauses, model), "internal error: DPLL model does not satisfy CNF"
            return SatResult("SAT", model, decisions, (time.perf_counter() - t0) * 1e3)
        var = Counter(abs(lit) for c in cls for lit in c).most_common(1)[0][0]
        decisions += 1
        for lit in (-var, var):  # pushed so that +var is tried first
            nxt = _simplify(cls, lit)
            if nxt is not None:
                stack.append((nxt, {**assign, var: lit > 0}))
    return SatResult("UNSAT", None, decisions, (time.perf_counter() - t0) * 1e3)
