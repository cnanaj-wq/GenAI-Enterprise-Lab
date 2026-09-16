type HealthStatus = {
  api: string;
  database: string;
  postgresql: string | null;
  pgvector: string | null;
};

async function getHealth(): Promise<HealthStatus | null> {
  try {
    const apiUrl =
      process.env.FASTAPI_URL ?? "http://127.0.0.1:8000";

    const response = await fetch(`${apiUrl}/health`, {
      cache: "no-store",
    });

    if (!response.ok) {
      return null;
    }

    return response.json();
  } catch {
    return null;
  }
}

function StatusBadge({ healthy }: { healthy: boolean }) {
  return (
    <span className="flex items-center gap-2 text-sm font-medium">
      <span
        className={`h-2.5 w-2.5 rounded-full ${
          healthy
            ? "bg-emerald-400 shadow-[0_0_12px_rgba(52,211,153,0.8)]"
            : "bg-rose-400"
        }`}
      />
      {healthy ? "HEALTHY" : "UNAVAILABLE"}
    </span>
  );
}

export const dynamic = "force-dynamic";

export default async function Home() {
  const health = await getHealth();

  const apiHealthy = health?.api === "healthy";
  const databaseHealthy = health?.database === "healthy";

  return (
    <main className="min-h-screen bg-[#09090b] px-6 py-14 text-zinc-100">
      <div className="mx-auto max-w-5xl">

        <header className="mb-12">
          <p className="mb-3 text-sm font-semibold uppercase tracking-[0.28em] text-emerald-400">
            GenAI Data Engineering
          </p>

          <h1 className="text-4xl font-semibold tracking-tight">
            GenAI Enterprise Lab
          </h1>

          <p className="mt-4 max-w-2xl text-zinc-400">
            Production-oriented environment for Agentic AI, RAG,
            evaluation, PromptOps and enterprise GenAI applications.
          </p>
        </header>

        <section className="grid gap-4 md:grid-cols-2">
          <article className="rounded-2xl border border-zinc-800 bg-zinc-900/70 p-6">
            <p className="text-sm text-zinc-500">API</p>

            <div className="mt-4 flex items-center justify-between">
              <p className="text-xl font-medium">FastAPI</p>
              <StatusBadge healthy={apiHealthy} />
            </div>
          </article>

          <article className="rounded-2xl border border-zinc-800 bg-zinc-900/70 p-6">
            <p className="text-sm text-zinc-500">Database</p>

            <div className="mt-4 flex items-center justify-between">
              <p className="text-xl font-medium">PostgreSQL</p>
              <StatusBadge healthy={databaseHealthy} />
            </div>
          </article>

          <article className="rounded-2xl border border-zinc-800 bg-zinc-900/70 p-6">
            <p className="text-sm text-zinc-500">PostgreSQL version</p>

            <p className="mt-4 text-2xl font-semibold">
              {health?.postgresql ?? "—"}
            </p>
          </article>

          <article className="rounded-2xl border border-zinc-800 bg-zinc-900/70 p-6">
            <p className="text-sm text-zinc-500">Vector Engine</p>

            <div className="mt-4 flex items-center justify-between">
              <p className="text-2xl font-semibold">
                pgvector {health?.pgvector ?? "—"}
              </p>

              <StatusBadge healthy={Boolean(health?.pgvector)} />
            </div>
          </article>
        </section>

        <div className="mt-8 rounded-2xl border border-zinc-800 bg-zinc-950 p-5 font-mono text-sm text-zinc-400">
          Next.js → FastAPI → SQLAlchemy → PostgreSQL → pgvector
        </div>

      </div>
    </main>
  );
}
