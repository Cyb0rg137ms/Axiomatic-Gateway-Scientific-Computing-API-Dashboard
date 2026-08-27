# Axiomatic Engine Gateway — Architecture & Technical Reference

> **Full Project Name:** Axiomatic Engine Gateway — Multi-Solver FastAPI Service
> **Category:** API Design / Distributed Computing / Backend Services
> **Language:** Python 3.9+, FastAPI, Starlette, asyncio
> **Test Coverage:** 7/7 unit tests passing ✅

---

## 1. Architecture Overview

```
06_axiomatic_gateway/
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI app factory, router registration
│   │   ├── routers/
│   │   │   ├── solve.py     # POST /solve/sat, /solve/quantum, /solve/materials
│   │   │   └── sim.py       # POST /simulate, GET /simulate/{task_id}/status
│   │   ├── cache.py         # LRU result cache + telemetry counters
│   │   ├── registry.py      # Simulation task registry (in-memory)
│   │   └── solvers/
│   │       ├── sat_bridge.py       # SAT solver integration
│   │       ├── quantum_bridge.py   # Quantum simulator integration
│   │       └── materials_bridge.py # Materials screener integration
│   ├── tests/
│   │   └── test_api.py
│   └── requirements.txt
└── pyproject.toml
```

### Component Interaction

```
┌─────────────────────────────────────────────────────────────────┐
│                 AXIOMATIC ENGINE GATEWAY                       │
│                                                                │
│  Client HTTP Request                                          │
│       │                                                       │
│       ▼                                                       │
│  FastAPI Router (POST /solve/*)                               │
│       │                                                       │
│  ┌────┴──────────────────────────────────────────┐           │
│  │           LRU Cache Check                     │           │
│  │  cache hit  ──────────────────────► Response  │           │
│  │  cache miss                                   │           │
│  └────┬──────────────────────────────────────────┘           │
│       │                                                       │
│  Solver Bridge ──► SAT / Quantum / Materials engine           │
│       │                                                       │
│       ▼                                                       │
│  Store result in cache ──► Increment telemetry counters       │
│       │                                                       │
│       ▼                                                       │
│  JSON Response  (result + mass_gap + elapsed_ms + metadata)  │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Mathematical Framework

### 2.1 LRU Cache Fingerprinting

Each request is uniquely identified by hashing its payload:

```
cache_key = SHA-256( JSON.stringify( payload, sort_keys=True ) )

The cache stores the N_max most recently used entries.
When full, the Least Recently Used (oldest-accessed) entry is evicted.

Data structure: Python OrderedDict
  - get(key)  →  O(1)  (move to end = mark as recently used)
  - set(key)  →  O(1)  (evict front if over capacity)
```

### 2.2 Cache Hit Rate Telemetry

Two atomic counters track usage:

```
hit_rate  =  N_hits  /  (N_hits + N_misses)

N_hits    = requests answered from cache  (no re-computation)
N_misses  = requests that required a fresh solver call
```

These are exposed at `GET /metrics` in Prometheus-compatible format.

### 2.3 Async Background Simulation (SAGA Pattern)

Long-running solver jobs are handled without blocking the HTTP worker:

```
Step 1:  Client sends  POST /simulate  with parameters
Step 2:  Server generates  task_id = uuid4()
Step 3:  Registers task:   registry[task_id] = { status: "pending" }
Step 4:  Returns task_id immediately  (HTTP 202 Accepted)
Step 5:  Background asyncio coroutine runs the solver
Step 6:  On completion:  registry[task_id] = { status: "done", result: ... }
Step 7:  Client polls  GET /simulate/{task_id}/status  until status = "done"
```

### 2.4 Unified Response Schema

Every `/solve/*` endpoint returns:

| Field | Type | Description |
|-------|------|-------------|
| `result` | dict | Solver-specific answer (SAT assignment, Tc values, etc.) |
| `mass_gap` | float | QUBO algebraic feasibility bound |
| `elapsed_ms` | float | Wall-clock time of the computation |
| `cache_hit` | bool | True if result came from LRU cache |
| `metadata` | dict | Solver version, parameter echo, timestamp |

---

## 3. Workflow

```
POST /solve/sat  with  { clauses: [[1,-2,3], ...], num_vars: 10 }
        │
        ▼
Router: validate request schema  (Pydantic model)
        │
        ▼
Cache: compute SHA-256 fingerprint of payload
        │
        ├── cache hit?  →  return cached response immediately
        │
        └── cache miss  →  call sat_bridge.solve(clauses, num_vars)
                                │
                                ▼
                          Collect result, mass_gap, elapsed_ms
                                │
                                ▼
                          Store in LRU cache
                          Increment hit/miss counters
                                │
                                ▼
                          Return JSON response


POST /simulate  (long-running job)
        │
        ▼
Generate UUID task_id,  register as pending
Return task_id (202 Accepted) immediately
        │
        ▼  (background coroutine)
Run solver pipeline
Update registry[task_id] = done + result
        │
Client polls:  GET /simulate/{task_id}/status
Until status = "done",  then reads result
```

---

## 4. System Design

| Component | Module | Responsibility |
|-----------|--------|----------------|
| **App Factory** | `main.py` | FastAPI instantiation, router mounting, lifespan hooks |
| **Solve Routers** | `routers/solve.py` | SAT / quantum / materials endpoints |
| **Sim Router** | `routers/sim.py` | Async job submission + status polling |
| **Cache** | `cache.py` | LRU OrderedDict cache + telemetry counters |
| **Registry** | `registry.py` | In-memory task status + result store |
| **Bridges** | `solvers/*.py` | Thin adapters calling solver modules |
| **Tests** | `test_api.py` | Full stack API tests via `TestClient` |

---

## 5. Key Advantages

| Advantage | Description |
|-----------|-------------|
| **Unified API** | Single gateway for three fundamentally different solver types |
| **LRU caching** | Repeated queries return instantly without re-solving |
| **Async-first** | Non-blocking long jobs via asyncio background tasks |
| **SAGA pattern** | Fire-and-poll for durability without blocking workers |
| **Telemetry built-in** | Cache hit rates, latencies tracked without external APM |

---

## 6. Test Results

```
tests/test_api.py::test_cache_telemetry              PASSED
tests/test_api.py::test_simulation_registry          PASSED
tests/test_api.py::test_api_health_endpoint          PASSED
tests/test_api.py::test_api_solve_sat                PASSED
tests/test_api.py::test_api_solve_quantum            PASSED
tests/test_api.py::test_api_solve_materials          PASSED
tests/test_api.py::test_api_background_simulation    PASSED
────────────────────────────────────────────────────
7 passed in 0.41s
```

---

## 7. Quick Start

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
# Docs: http://localhost:8000/docs

pytest tests/test_api.py -v
```

<div align="center">
  <a href="https://q.com"><img src="../../assets/https_q_com.png" width="80" /></a>
</div>
