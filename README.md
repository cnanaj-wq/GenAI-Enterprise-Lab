# GenAI Enterprise Lab

Production-oriented **GenAI Data Engineering** lab designed to build, evaluate and industrialize enterprise Generative AI applications.

The project progressively covers:

- Agentic AI
- Retrieval-Augmented Generation (RAG)
- LLM evaluation
- PromptOps
- MCP
- AI observability
- Enterprise Data / AI integration

---

## Core Stack

### Application & Backend

- **Python** — Main backend and AI engineering language. Used for API services, data processing, synthetic data generation, agent orchestration, RAG pipelines and evaluation workflows.
- **FastAPI** — High-performance API framework used to expose the GenAI platform services, health endpoints, agents, RAG pipelines and future AI capabilities.
- **Pydantic** — Provides strongly typed data validation, configuration management and structured outputs through explicit schemas.

### Frontend

- **TypeScript** — Adds static typing to the application layer and improves reliability when building frontend components, API contracts and AI interfaces.
- **Next.js** — React-based framework used to build the GenAI Enterprise Lab interface, dashboards and server-side integrations with FastAPI.

### Generative AI & Agentic Systems

- **OpenAI / Anthropic** — LLM providers used for reasoning, structured generation, tool calling and agentic workflows.
- **LangGraph** — Framework used to build stateful AI agents and controlled workflows with routing, tool execution, retries and human-in-the-loop capabilities.
- **MCP — Model Context Protocol** — Standard protocol used to expose enterprise tools, APIs and data sources to AI agents through a consistent interface.

### Data & RAG

- **PostgreSQL** — Primary relational database used to store structured business data, application data and large synthetic datasets for realistic enterprise scenarios.
- **pgvector** — PostgreSQL extension used to store embeddings and perform vector similarity searches for Retrieval-Augmented Generation.

### Infrastructure & DevOps

- **Docker** — Provides reproducible infrastructure and isolated services. PostgreSQL and pgvector currently run inside Docker containers.
- **GitHub Actions** — CI/CD automation used to validate the project through linting, automated tests and production builds.

### AI Observability

- **Langfuse** — LLM observability platform used to trace prompts, model calls, agents, latency, token usage, cost and evaluation results.
- **OpenTelemetry** — Vendor-neutral observability standard used to collect distributed traces, metrics and logs across the application.

---

## Current Architecture

```text
Browser
   │
   ▼
Next.js / TypeScript
   │
   ▼
FastAPI / Python
   │
   ▼
SQLAlchemy / psycopg
   │
   ▼
PostgreSQL 18
   │
   └── pgvector
```

---

## Implementation Status

| Component | Status |
|---|---|
| Python 3.12 | ✅ Implemented |
| FastAPI | ✅ Implemented |
| Pydantic | ✅ Implemented |
| PostgreSQL 18 | ✅ Implemented |
| pgvector | ✅ Implemented |
| Docker | ✅ Implemented |
| TypeScript | ✅ Implemented |
| Next.js | ✅ Implemented |
| Ruff | ✅ Implemented |
| Pytest | ✅ Implemented |
| Frontend production build | ✅ Implemented |
| GitHub Actions | 🔜 Module 0 |
| OpenAI / Anthropic | 🔜 Module 1 |
| LangGraph | 🔜 Module 1 |
| MCP | 🔜 Module 1 |
| Langfuse | 🔜 Module 3 |
| OpenTelemetry | 🔜 Module 3 |

---

## Roadmap

### Module 0 — Enterprise GenAI Technical Foundation

Build the production-oriented technical foundation that will support every future GenAI module.

**You will learn to:**

- Structure a professional monorepo for Python and TypeScript applications
- Manage source code and incremental development with Git
- Build isolated Python environments with `venv`
- Create REST APIs with FastAPI
- Validate configuration and data with Pydantic
- Connect Python applications to PostgreSQL with SQLAlchemy and psycopg
- Run PostgreSQL and pgvector inside Docker
- Build a frontend with TypeScript and Next.js
- Connect Next.js to a FastAPI backend
- Implement health checks across application and database layers
- Write automated tests with Pytest
- Enforce Python code quality with Ruff
- Validate frontend code with ESLint and TypeScript
- Build production-ready Next.js applications
- Manage secrets securely with environment variables
- Prepare automated CI validation with GitHub Actions

**Final deliverable:**  
A working GenAI Enterprise Lab foundation with Next.js, FastAPI, PostgreSQL, pgvector, Docker, automated tests and CI-ready architecture.

---

### Module 1 — Agentic AI & MCP

Move from traditional LLM calls to systems capable of selecting tools, executing actions and managing multi-step workflows.

**You will learn to:**

- Understand the difference between an LLM, tool calling, workflow and AI agent
- Design stateful agent workflows with LangGraph
- Create specialized tools for agents
- Implement routing and conditional execution
- Manage agent state and execution context
- Implement retries, error handling and fallback strategies
- Use structured outputs for reliable agent responses
- Add human-in-the-loop validation
- Understand when to use one agent versus multiple agents
- Build MCP servers and MCP clients
- Expose enterprise APIs, databases and services through MCP
- Secure tool execution and reduce agent permissions
- Trace agent decisions and tool executions
- Design deterministic boundaries around non-deterministic LLM behavior

**Final deliverable:**  
**AI Ops Investigator** — an agent capable of investigating an enterprise incident using logs, PostgreSQL, documentation and tools before producing a structured diagnosis.

---

### Module 2 — Enterprise RAG

Build a production-oriented Retrieval-Augmented Generation system capable of answering questions from enterprise knowledge.

**You will learn to:**

- Understand embeddings and vector representations
- Generate and store embeddings with pgvector
- Design document ingestion pipelines
- Parse PDF, Markdown and structured documents
- Implement chunking strategies
- Measure the impact of chunk size and overlap
- Perform semantic vector search
- Implement keyword and full-text search
- Build hybrid retrieval systems
- Apply metadata filtering
- Implement Top-K retrieval
- Add reranking
- Perform query rewriting
- Manage context windows and token budgets
- Generate answers grounded in retrieved evidence
- Add source citations
- Detect insufficient evidence and refuse unsupported answers
- Evaluate retrieval quality

**Final deliverable:**  
**Enterprise Knowledge Copilot** — a hybrid RAG application with semantic search, keyword search, reranking, metadata filtering and source citations.

---

### Module 3 — LLM Evaluation & Observability

Learn how to determine whether a GenAI system is actually improving instead of relying on subjective impressions.

**You will learn to:**

- Build evaluation datasets
- Define ground-truth test cases
- Measure answer correctness
- Measure faithfulness
- Measure context precision
- Measure context recall
- Detect hallucinations
- Evaluate retrieval quality independently from generation quality
- Compare prompts and models
- Track input and output tokens
- Measure inference latency
- Calculate cost per request
- Measure P50 and P95 latency
- Trace LLM calls and agent executions
- Instrument applications with Langfuse
- Understand OpenTelemetry traces, metrics and logs
- Detect regressions after application changes
- Build repeatable evaluation pipelines
- Compare architectures using measurable KPIs

**Final deliverable:**  
**LLM Quality Observatory** — a monitoring and evaluation cockpit for quality, latency, tokens, cost, retrieval performance and LLM traces.

---

### Module 4 — PromptOps

Move beyond basic prompt engineering and manage prompts as production software assets.

**You will learn to:**

- Design system prompts
- Separate system, user and business instructions
- Implement few-shot prompting
- Build reusable prompt templates
- Manage dynamic prompt variables
- Use structured outputs
- Validate LLM responses with Pydantic and JSON Schema
- Implement function and tool calling
- Control context composition
- Optimize token usage
- Compress large contexts
- Version prompts with Git
- Compare prompt versions
- Build automated prompt regression tests
- Perform A/B testing
- Detect prompt injection
- Protect tools and retrieved context
- Implement guardrails
- Measure prompt quality, cost and latency

**Final deliverable:**  
**PromptOps Workbench** — a platform for versioning, testing, comparing and evaluating production prompts.

---

### Module 5 — End-to-End AI Data Analyst Platform

Combine everything learned in the previous modules into a complete enterprise GenAI application.

**You will learn to:**

- Design an end-to-end GenAI architecture
- Connect LLMs to structured enterprise data
- Build SQL tools for AI agents
- Allow agents to query PostgreSQL safely
- Integrate RAG with structured data analysis
- Orchestrate multiple tools through LangGraph
- Use MCP to expose external capabilities
- Generate business-oriented analytical answers
- Validate AI-generated calculations
- Implement agent guardrails
- Implement application-level security boundaries
- Manage asynchronous processing
- Build resilient API services
- Integrate FastAPI and Next.js
- Stream AI responses to the frontend
- Containerize the complete application
- Automate testing with GitHub Actions
- Add LLM observability
- Monitor performance, cost and quality
- Prepare the application for deployment

**Final deliverable:**  
**AI Data Analyst Platform** — a production-oriented GenAI application capable of querying business data, retrieving enterprise knowledge, using tools, validating results and explaining its conclusions.

---

## Portfolio Outcome

At the end of the roadmap, the repository will contain complete GenAI systems rather than isolated notebooks or proofs of concept.

Each module will include:

- Production-oriented source code
- Architecture diagrams
- Automated tests
- Docker configuration
- Documented SQL queries
- Versioned prompts
- Evaluation results
- Technical documentation
- Demo screenshots
- Short demonstration video
- LinkedIn-ready technical publication
