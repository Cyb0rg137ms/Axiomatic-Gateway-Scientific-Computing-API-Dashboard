"""Adapters for optional sibling engines. No mock fallbacks.

v1 returned hard-coded numbers (SAT "assignment all ones", entropy 80.5,
Tc 105 K) when an engine was missing. v2 either runs a real computation or
raises :class:`EngineUnavailable`, which the API maps to HTTP 503.
"""

from __future__ import annotations

import importlib.util
import time
from typing import Any, Dict, List, Sequence

from app.sat import check_model, solve_dpll, validate_cnf


class EngineUnavailable(RuntimeError):
    """The optional package backing this endpoint is not installed."""


def _has(module: str) -> bool:
    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, ValueError):
        return False


def engine_status() -> Dict[str, str]:
    return {
        "graph_sat_solver": "available" if _has("graphsat") else "builtin_dpll",
        "quantum_emulator": "available" if _has("simulator") else "unavailable",
        "materials_discovery": "available" if _has("materials") else "unavailable",
        "theorem_prover": "available",
    }


def solve_sat(num_vars: int, clauses: Sequence[Sequence[int]], timeout_s: float = 10.0) -> Dict[str, Any]:
    validate_cnf(num_vars, clauses)
    t0 = time.perf_counter()
    if _has("graphsat"):
        from graphsat import ManifoldConstraintSolver

        status, result = ManifoldConstraintSolver(num_vars, [list(c) for c in clauses]).solve()
        out: Dict[str, Any] = {"status": status, "result": result, "engine": "graphsat"}
    else:
        r = solve_dpll(num_vars, clauses, timeout_s=timeout_s)
        out = {"status": r.status, "result": r.model, "engine": "builtin_dpll", "decisions": r.decisions}
    if out["status"] == "SAT" and isinstance(out["result"], list):
        out["model_verified"] = check_model(clauses, out["result"])
    out["time_ms"] = round((time.perf_counter() - t0) * 1e3, 3)
    return out


def simulate_quantum(n_registers: int, dimension: int, bond_dim: int) -> Dict[str, Any]:
    if not _has("simulator"):
        raise EngineUnavailable("quantum emulator not installed (pip install Quantum_tensor_rbm)")
    from simulator.mps import MultiStateQuantumSimulator

    sim = MultiStateQuantumSimulator(n_qstates=n_registers, physical_dim=dimension, max_bond_dim=bond_dim)
    base = sim.calculate_reconstructed_entropy()
    for i in range(n_registers - 1):
        sim.apply_two_state_gate(i, i + 1)
    final = sim.calculate_reconstructed_entropy()
    return {
        "status": "completed",
        "initial_entropy": base,
        "final_entropy": final,
        "entanglement_gain": final - base,
        "engine": "q_tensor_rbm_emulator",
    }


def evaluate_materials(hydrogen_count: int, heavy_atom_mass: float) -> Dict[str, Any]:
    if not _has("materials"):
        raise EngineUnavailable("materials designer not installed (Superconductor-Design-ML)")
    from materials.designer import SuperconductorDesigner

    res: Dict[str, Any] = SuperconductorDesigner().evaluate_clathrate(hydrogen_count, heavy_atom_mass)
    return res


__all__: List[str] = ["EngineUnavailable", "engine_status", "evaluate_materials", "simulate_quantum", "solve_sat"]
