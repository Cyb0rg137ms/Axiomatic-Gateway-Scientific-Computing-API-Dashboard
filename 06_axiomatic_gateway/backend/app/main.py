"""
main.py
=======
FastAPI ASGI Backend server for the Axiomatic Scientific Computing Gateway.
Acts as a unified endpoint orchestrator for GraphSAT, Q-Tensor-RBM, and materials screening.
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, List, Optional

from app.cache import TelemetryCache
from app.registry import SimulationRegistry

# Try-except imports to allow stand-alone execution with graceful mock fallbacks
try:
    from graphsat.core import ManifoldConstraintSolver
    SAT_AVAILABLE = True
except ImportError:
    SAT_AVAILABLE = False

try:
    from simulator.mps import MultiStateQuantumSimulator
    QUANTUM_AVAILABLE = True
except ImportError:
    QUANTUM_AVAILABLE = False

try:
    from materials.designer import SuperconductorDesigner
    MATERIALS_AVAILABLE = True
except ImportError:
    MATERIALS_AVAILABLE = False


app = FastAPI(title="Axiomatic Gateway API", version="1.0.0")

# Enable CORS for frontend dashboard connections
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Core systems
cache = TelemetryCache()
registry = SimulationRegistry()

# --- Request Schemas ---

class SATRequest(BaseModel):
    num_vars: int
    clauses: List[List[int]]

class QuantumRequest(BaseModel):
    n_registers: int
    dimension: int
    bond_dim: int

class MaterialsRequest(BaseModel):
    hydrogen_count: int
    heavy_atom_mass: float

class SimulationRequest(BaseModel):
    name: str
    params: Dict[str, Any]

# --- Endpoints ---

@app.get("/")
def get_health_status():
    """Returns general gateway status and available computational engines."""
    return {
        "status": "online",
        "engines": {
            "graph_sat_solver": "available" if SAT_AVAILABLE else "fallback_mode",
            "quantum_emulator": "available" if QUANTUM_AVAILABLE else "fallback_mode",
            "materials_discovery": "available" if MATERIALS_AVAILABLE else "fallback_mode"
        }
    }

@app.post("/solve/sat")
def solve_sat(payload: SATRequest):
    """Solves a DIMACS SAT problem using the GraphSAT engine."""
    cache_key = f"sat_{hash(str(payload.clauses))}"
    cached_res = cache.get(cache_key)
    if cached_res:
        return {"result": cached_res, "cached": True}
        
    if not SAT_AVAILABLE:
        # Mock fallback mode
        time_elapsed = 12.5
        mock_solution = [1] * payload.num_vars
        return {"status": "SAT", "assignment": mock_solution, "engine": "mock_fallback", "time_ms": time_elapsed}
        
    try:
        solver = ManifoldConstraintSolver(payload.num_vars, payload.clauses)
        status, result = solver.solve()
        
        response_data = {
            "status": status,
            "result": result,
            "engine": "graph_sat_manifold_solver"
        }
        cache.set(cache_key, response_data, ttl_seconds=60)
        return response_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"GraphSAT execution error: {str(e)}")

@app.post("/solve/quantum")
def solve_quantum(payload: QuantumRequest):
    """Simulates a multi-state quantum register circuit."""
    if not QUANTUM_AVAILABLE:
        return {
            "status": "simulated",
            "entropy": 80.5,
            "engine": "mock_fallback"
        }
        
    try:
        sim = MultiStateQuantumSimulator(
            n_qstates=payload.n_registers, 
            physical_dim=payload.dimension, 
            max_bond_dim=payload.bond_dim
        )
        base_entropy = sim.calculate_reconstructed_entropy()
        
        # Apply sample gates
        for i in range(payload.n_registers - 1):
            sim.apply_two_state_gate(i, i + 1)
            
        final_entropy = sim.calculate_reconstructed_entropy()
        
        return {
            "status": "completed",
            "initial_entropy": base_entropy,
            "final_entropy": final_entropy,
            "entanglement_gain": final_entropy - base_entropy,
            "engine": "q_tensor_rbm_emulator"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Quantum Emulator error: {str(e)}")

@app.post("/solve/materials")
def solve_materials(payload: MaterialsRequest):
    """Evaluates transition temperature parameters of custom compound configurations."""
    if not MATERIALS_AVAILABLE:
        return {
            "predicted_tc": 105.0,
            "lambda": 1.2,
            "engine": "mock_fallback"
        }
        
    try:
        designer = SuperconductorDesigner()
        results = designer.evaluate_clathrate(payload.hydrogen_count, payload.heavy_atom_mass)
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Materials Designer error: {str(e)}")

@app.post("/simulation")
def start_simulation(payload: SimulationRequest, background_tasks: BackgroundTasks):
    """Starts a background simulation task and registers it."""
    task = registry.register_task(payload.name, payload.params)
    
    # Simulates background updates
    background_tasks.add_task(registry.update_all_tasks)
    
    return {
        "status": "queued",
        "task_id": task.task_id,
        "detail": f"Simulation '{payload.name}' started in background."
    }

@app.get("/simulation/{task_id}")
def get_simulation_status(task_id: str):
    """Polls the current execution status and progress of a background task."""
    task = registry.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Increment progress on polling to simulate active processing
    registry.update_all_tasks()
    
    return task.to_dict()
