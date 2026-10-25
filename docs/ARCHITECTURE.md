# Architecture

```mermaid
flowchart LR
  C[Client] -->|JSON| API[FastAPI app.main]
  API -->|validate| PY[Pydantic schemas]
  API --> CA[(TelemetryCache\nLRU + TTL, sha256 keys)]
  API --> PR[app.prover\ngiven-clause loop]
  PR --> L[app.logic\nunify / match / factor]
  PR -->|proof DAG| CK[app.proof.ProofChecker\nstep-by-step replay]
  API --> EN[app.engines]
  EN -->|installed| GS[graphsat CDCL]
  EN -->|fallback| DP[app.sat DPLL]
  EN -->|installed| QT[qtensor-rbm]
  EN -->|missing| E503[HTTP 503]
  API --> RG[app.registry\nThreadPool jobs]
```

## Given-clause loop (`app/prover.py`)

```mermaid
flowchart TD
  I[axioms + Skolemized negated goal] --> P[(passive heap\nweight, age)]
  P -->|pick lightest, every 5th: oldest| G[given clause]
  G -->|forward-subsumed?| P
  G --> A[(active set)]
  A --> R[binary resolvents + factors]
  R -->|tautology / duplicate / subsumed| X[discard]
  R -->|empty clause| PF[extract proof DAG -> ProofChecker]
  R --> P
  P -->|empty| SAT[saturated]
```

Every `proved` answer is replayed by `ProofChecker`. It accepts:
- an axiom step only if the clause is an exact instance of an axiom (one-way matching);
- a resolution or factor step only if a resolvent or factor subsumes the stated clause.
