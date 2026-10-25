"""
main.py
=======
FastAPI gateway: a self-verifying resolution prover plus adapters for the
GraphSAT, Q-Tensor-RBM and Superconductor engines.

Every number this API returns comes from a computation it actually ran. When an
optional engine is missing the endpoint answers HTTP 503, never a placeholder.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app import engines
from app.cache import TelemetryCache, stable_key
from app.parser import ClauseSyntaxError, parse_clause
from app.problems import suite
from app.prover import prove
from app.registry import SimulationRegistry

__version__ = "2.0.0"
log = logging.getLogger("axiomatic")

app = FastAPI(title="Axiomatic Gateway API", version=__version__)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

cache = TelemetryCache(max_entries=1024)
registry = SimulationRegistry(max_workers=2)

MAX_CLAUSES = 2000
MAX_TIMEOUT_S = 30.0

# kept for backwards compatibility with v1 importers
SAT_AVAILABLE = engines.engine_status()["graph_sat_solver"] == "available"


# --- Request Schemas ---


class SATRequest(BaseModel):
    num_vars: int = Field(ge=0, le=100_000)
    clauses: List[List[int]] = Field(max_length=200_000)


class QuantumRequest(BaseModel):
    n_registers: int = Field(ge=1, le=64)
    dimension: int = Field(ge=2, le=64)
    bond_dim: int = Field(ge=1, le=512)


class MaterialsRequest(BaseModel):
    hydrogen_count: int = Field(ge=0, le=1000)
    heavy_atom_mass: float = Field(gt=0, le=500)


class ProveRequest(BaseModel):
    axioms: List[str] = Field(max_length=MAX_CLAUSES, description="Clauses, e.g. '~man(X) | mortal(X)'")
    goal: Optional[str] = Field(default=None, description="Goal clause; omit to test the axioms for unsatisfiability")
    timeout_s: float = Field(default=5.0, gt=0, le=MAX_TIMEOUT_S)
    max_iterations: int = Field(default=5000, ge=1, le=200_000)


class SimulationRequest(BaseModel):
    name: str
    params: Dict[str, Any] = Field(default_factory=dict)


# --- helpers ---


def _parse(req: ProveRequest) -> tuple[list[Any], Any]:
    try:
        axioms = [parse_clause(s) for s in req.axioms]
        goal = parse_clause(req.goal) if req.goal is not None else None
    except ClauseSyntaxError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return axioms, goal


def _run_prove(req: ProveRequest) -> Dict[str, Any]:
    axioms, goal = _parse(req)
    res = prove(axioms, goal, timeout_s=req.timeout_s, max_iterations=req.max_iterations)
    return res.to_dict()


# --- Endpoints ---


@app.get("/")
def get_health_status() -> Dict[str, Any]:
    """Gateway status and which engines are installed."""
    return {"status": "online", "version": __version__, "engines": engines.engine_status()}


@app.get("/metrics")
def get_metrics() -> Dict[str, Any]:
    counts: Dict[str, int] = {}
    for t in list(registry.tasks.values()):
        counts[t.status] = counts.get(t.status, 0) + 1
    return {"cache": cache.stats(), "tasks": counts}


@app.post("/solve/sat")
def solve_sat(payload: SATRequest) -> Dict[str, Any]:
    """Solve a CNF given as DIMACS-style integer clauses (GraphSAT if installed, else built-in DPLL)."""
    key = stable_key("sat", payload.model_dump())
    cached = cache.get(key)
    if cached is not None:
        return {**cached, "cached": True}
    try:
        out = engines.solve_sat(payload.num_vars, payload.clauses)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if out["status"] in ("SAT", "UNSAT"):
        cache.set(key, out, ttl_seconds=300)
    return {**out, "cached": False}


@app.post("/solve/quantum")
def solve_quantum(payload: QuantumRequest) -> Dict[str, Any]:
    """Multi-register MPS emulation via Q-Tensor-RBM (503 if not installed)."""
    try:
        return engines.simulate_quantum(payload.n_registers, payload.dimension, payload.bond_dim)
    except engines.EngineUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/solve/materials")
def solve_materials(payload: MaterialsRequest) -> Dict[str, Any]:
    """Clathrate Tc estimate via Superconductor-Design-ML (503 if not installed)."""
    try:
        return engines.evaluate_materials(payload.hydrogen_count, payload.heavy_atom_mass)
    except engines.EngineUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/prove")
def prove_endpoint(payload: ProveRequest) -> Dict[str, Any]:
    """Resolution refutation. ``status`` is proved | saturated | unknown; proofs are independently re-checked."""
    key = stable_key("prove", payload.model_dump())
    cached = cache.get(key)
    if cached is not None:
        return {**cached, "cached": True}
    out = _run_prove(payload)
    if out["status"] != "unknown":
        cache.set(key, out, ttl_seconds=300)
    return {**out, "cached": False}


@app.get("/problems")
def list_problems() -> List[Dict[str, Any]]:
    return [
        {
            "name": p.name,
            "description": p.description,
            "expected": p.expected,
            "axioms": [str(c) for c in p.axioms],
            "goal": None if p.goal is None else str(p.goal),
        }
        for p in suite().values()
    ]


@app.post("/simulation")
def start_simulation(payload: SimulationRequest) -> Dict[str, Any]:
    """Start a background task.

    ``name == "prove"`` (params = ProveRequest fields) and ``name == "sat"``
    (params = SATRequest fields) run real jobs. Any other name creates a v1-style
    manual-progress task that performs no computation.
    """
    if payload.name == "prove":
        req = ProveRequest(**payload.params)
        _parse(req)  # validate synchronously -> 422 instead of a failed job
        task = registry.submit("prove", payload.params, lambda: _run_prove(req))
    elif payload.name == "sat":
        sreq = SATRequest(**payload.params)
        task = registry.submit("sat", payload.params, lambda: engines.solve_sat(sreq.num_vars, sreq.clauses))
    else:
        task = registry.register_task(payload.name, payload.params)
    return {
        "status": "queued",
        "task_id": task.task_id,
        "kind": task.kind,
        "detail": f"Task '{payload.name}' registered ({task.kind}).",
    }


@app.get("/simulation/{task_id}")
def get_simulation_status(task_id: str) -> Dict[str, Any]:
    """Poll a task. Manual-progress tasks advance 20% per poll (v1 semantics)."""
    task = registry.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.kind == "manual":
        registry.update_all_tasks()
    return task.to_dict()
