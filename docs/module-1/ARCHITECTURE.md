# Module 1 Architecture

## System architecture

```mermaid
flowchart TB
    subgraph UI[Frontend]
        B[Browser]
        N[Next.js / React / TypeScript]
        B --> N
    end

    subgraph API[Application layer]
        F[FastAPI]
        SSE[SSE event stream]
        R1[Investigations API]
        R2[History / Replay / Compare]
        R3[FinOps API]
        R4[Project Health API]
        R5[Optimize API]
    end

    subgraph AGENT[Agentic layer]
        LG[LangGraph]
        MC[MCP Client]
        LLM[OpenAI Responses API]
    end

    subgraph MCP[MCP boundary]
        MS[MCP Server]
        T1[get_application]
        T2[get_reload_history]
        T3[get_reload_logs]
        T4[get_incident]
        T5[get_jira_ticket]
        T6[check_dependencies]
    end

    subgraph DATA[Data layer]
        PG[(PostgreSQL 18)]
        OPS[(ops schema)]
        OBS[(observability schema)]
        FIN[(finops schema)]
        DEL[(delivery schema)]
        VEC[pgvector 0.8.6]
    end

    N --> F
    F --> R1
    F --> R2
    F --> R3
    F --> R4
    F --> R5
    R1 --> LG
    LG --> MC
    MC --> MS
    MS --> T1
    MS --> T2
    MS --> T3
    MS --> T4
    MS --> T5
    MS --> T6
    T1 --> OPS
    T2 --> OPS
    T3 --> OPS
    T4 --> OPS
    T5 --> OPS
    T6 --> OPS
    LG --> LLM
    LG --> OBS
    R2 --> OBS
    R3 --> FIN
    R4 --> DEL
    R5 --> FIN
    F --> SSE
    SSE --> N
    OPS --> PG
    OBS --> PG
    FIN --> PG
    DEL --> PG
    VEC --> PG
```

---

## LangGraph execution

```mermaid
flowchart LR
    START((START))
    SC[select_candidate]
    APP[load_application]
    RH[inspect_reload_history]
    RL[inspect_reload_logs]
    INC[lookup_incident]
    COND{incident?}
    JIRA[lookup_jira]
    DEP[inspect_dependencies]
    SUM[build_summary]
    LLM[generate_llm_diagnosis]
    END((END))

    START --> SC --> APP --> RH --> RL --> INC --> COND
    COND -- yes --> JIRA --> DEP
    COND -- no --> DEP
    DEP --> SUM --> LLM --> END
```

---

## MCP request path

```mermaid
sequenceDiagram
    participant G as LangGraph node
    participant C as MCP Client
    participant S as MCP Server
    participant T as Tool
    participant D as PostgreSQL

    G->>C: call tool(name, arguments)
    C->>C: timeout / retry / circuit check
    C->>S: Streamable HTTP MCP
    S->>T: dispatch read-only tool
    T->>D: parameterized SQL
    D-->>T: rows
    T-->>S: structured result
    S-->>C: MCP response
    C-->>G: normalized result
```

---

## Resilience architecture

```mermaid
flowchart TD
    CALL[MCP call] --> TIMEOUT{success before timeout?}
    TIMEOUT -- yes --> OK[Return result]
    TIMEOUT -- no --> FAIL[Record transport failure]
    FAIL --> OPEN{failure threshold reached?}
    OPEN -- yes --> CIRCUIT[Open circuit]
    OPEN -- no --> RETRY{attempts left?}
    RETRY -- yes --> BACKOFF[Exponential backoff]
    BACKOFF --> CALL
    RETRY -- no --> ERR[Controlled error]

    LLM[LLM call] --> LPASS{success?}
    LPASS -- yes --> DIAG[LLM diagnosis]
    LPASS -- no --> FB[Deterministic fallback]
```

---

## Observability model

```mermaid
erDiagram
    TRACE ||--o{ SPAN : contains
    TRACE ||--o{ EVENT : emits
    SPAN ||--o{ EVENT : emits

    TRACE {
        uuid trace_id
        text status
        text prompt
        text provider
        text model
        int duration_ms
        int input_tokens
        int output_tokens
        decimal estimated_cost_usd
    }

    SPAN {
        uuid span_id
        uuid trace_id
        uuid parent_span_id
        text span_type
        text name
        text status
        int duration_ms
    }

    EVENT {
        uuid event_id
        uuid trace_id
        uuid span_id
        text event_type
        jsonb event_data
        int sequence_no
    }
```

---

## FinOps model

```mermaid
erDiagram
    BUSINESS_UNIT ||--o{ TEAM : contains
    TEAM ||--o{ USER : contains
    USER ||--o{ USAGE_EVENT : generates
    TEAM ||--o{ USAGE_EVENT : owns
    BUSINESS_UNIT ||--o{ USAGE_EVENT : owns
    USE_CASE ||--o{ USAGE_EVENT : classifies
    MODEL ||--o{ USAGE_EVENT : serves

    BUSINESS_UNIT {
        int business_unit_id
        text business_unit_name
        decimal monthly_budget_usd
    }

    TEAM {
        int team_id
        int business_unit_id
        text team_name
        decimal monthly_budget_usd
    }

    USER {
        int user_id
        int team_id
        text display_name
    }

    USE_CASE {
        int use_case_id
        text use_case_name
        decimal monthly_budget_usd
    }

    MODEL {
        int model_id
        text model_name
        text model_tier
        decimal input_cost_per_million
        decimal output_cost_per_million
    }

    USAGE_EVENT {
        timestamptz occurred_at
        int user_id
        int team_id
        int business_unit_id
        int use_case_id
        int model_id
        int input_tokens
        int output_tokens
        int latency_ms
        int retry_count
        boolean success
        decimal estimated_cost_usd
    }
```

---

## CI/CD flow

```mermaid
flowchart LR
    DEV[Local development]
    QG[Local quality gate]
    COMMIT[Git commit]
    PUSH[Git push]
    GA[GitHub Actions]
    PG[(Fresh PostgreSQL + pgvector)]
    PY[Python quality]
    FE[Frontend quality]
    PASS{All green?}
    READY[Ready for review / merge]

    DEV --> QG --> COMMIT --> PUSH --> GA
    GA --> PG
    PG --> PY
    GA --> FE
    PY --> PASS
    FE --> PASS
    PASS -- yes --> READY
    PASS -- no --> DEV
```

The first remote Module 1 run followed the `no` path because pgvector had not been activated inside the fresh CI database. The missing dependency was converted into an explicit migration, then the pipeline passed.
