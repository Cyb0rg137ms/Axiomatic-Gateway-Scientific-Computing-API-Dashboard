import pytest
from fastapi.testclient import TestClient
from app.cache import TelemetryCache
from app.registry import SimulationRegistry, SimulationTask
from app.main import app

def test_cache_telemetry():
    cache = TelemetryCache()
    cache.set("key_1", "value_1", ttl_seconds=1)
    assert cache.get("key_1") == "value_1"
    
    # Test missing
    assert cache.get("missing") is None

def test_simulation_registry():
    registry = SimulationRegistry()
    task = registry.register_task("PigeonholeSearch", {"pigeons": 3, "holes": 2})
    assert task.status == "queued"
    assert task.progress == 0.0
    
    # Update progress
    registry.update_all_tasks()
    assert task.progress == 20.0
    assert task.status == "running"
    
    # Update to completion
    for _ in range(4):
        registry.update_all_tasks()
    assert task.progress == 100.0
    assert task.status == "completed"
    assert task.result is not None

def test_api_health_endpoint():
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert "engines" in data

def test_api_solve_sat():
    client = TestClient(app)
    payload = {
        "num_vars": 2,
        "clauses": [[1, 2], [-1, 2]]
    }
    response = client.post("/solve/sat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    # Fallback or real solver output should return assignment/result
    assert "result" in data or "assignment" in data

def test_api_solve_quantum():
    client = TestClient(app)
    payload = {
        "n_registers": 5,
        "dimension": 4,
        "bond_dim": 8
    }
    response = client.post("/solve/quantum", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "entropy" in data["status"] or "final_entropy" in data or data["status"] == "simulated"

def test_api_solve_materials():
    client = TestClient(app)
    payload = {
        "hydrogen_count": 10,
        "heavy_atom_mass": 40.0
    }
    response = client.post("/solve/materials", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "predicted_tc" in data

def test_api_background_simulation():
    client = TestClient(app)
    payload = {
        "name": "SuperconductorSearchBatchB",
        "params": {"max_pressure_gpa": 5.0}
    }
    response = client.post("/simulation", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "queued"
    assert "task_id" in data
    
    # Poll status
    task_id = data["task_id"]
    poll_response = client.get(f"/simulation/{task_id}")
    assert poll_response.status_code == 200
    poll_data = poll_response.json()
    assert poll_data["task_id"] == task_id
    assert poll_data["status"] in ["queued", "running", "completed"]
