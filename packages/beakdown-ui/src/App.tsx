import { useEffect, useState } from "react";
import Canvas from "./components/Canvas";
import TimeScrubber from "./components/TimeScrubber";
import ApproveBar from "./components/ApproveBar";
import { loadArrow } from "./lib/arrow_loader";
import type { AnySession } from "./types";
import InvestigationView from "./investigation/InvestigationView";
import { credentialsForTab } from "./lib/credentials";
export default function App() {
  const [credentials] = useState(credentialsForTab);
  const [session, setSession] = useState<AnySession>();
  const [step, setStep] = useState(99);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [edit, setEdit] = useState("");
  const [query, setQuery] = useState("");
  const [arrowRows, setArrowRows] = useState<
    Record<string, Record<string, unknown>[]>
  >({});
  const base = `/api/session/${credentials.id}`;
  async function request(path = "", body?: object) {
    const r = await fetch(base + path, {
      method: body ? "POST" : "GET",
      headers: {
        Authorization: `Bearer ${credentials.token}`,
        "Content-Type": "application/json",
      },
      body: body ? JSON.stringify(body) : undefined,
    });
    if (!r.ok) throw new Error((await r.text()) || "Request failed");
    const data = await r.json();
    setSession(data);
    return data;
  }
  useEffect(() => {
    if (!credentials.id || !credentials.token) return;
    let active = true;
    const poll = () =>
      request().catch((e) => {
        if (active) setError(e.message);
      });
    poll();
    const timer = setInterval(poll, 1000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, []);
  useEffect(() => {
    if (
      !session ||
      session.kind === "investigation" ||
      session.state !== "ready"
    )
      return;
    let active = true;
    Promise.all(
      session.pipeline.nodes.map(async (n) => {
        const table = await loadArrow(
          `${base}/arrow/${n.id}`,
          credentials.token!,
        );
        return [
          n.id,
          table
            .toArray()
            .map((r) =>
              JSON.parse(
                JSON.stringify(r.toJSON(), (_, v) =>
                  typeof v === "bigint" ? String(v) : v,
                ),
              ),
            ),
        ] as const;
      }),
    )
      .then((rows) => {
        if (active) setArrowRows(Object.fromEntries(rows));
      })
      .catch((e) => {
        if (active) setError(String(e));
      });
    return () => {
      active = false;
    };
  }, [session?.state, session?.revision]);
  async function action(path: string, body: object) {
    setBusy(true);
    setError("");
    try {
      await request("/" + path, body);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }
  if (!credentials.id || !credentials.token)
    return (
      <main className="empty">
        <h1>Beakdown</h1>
        <p>A visual checkpoint for your agent.</p>
        <p>
          Create a handoff session with the MCP tool, then open its inspection
          link.
        </p>
      </main>
    );
  if (!session)
    return (
      <main className="empty">
        <h1>Opening your inspection…</h1>
        <p role="alert">{error}</p>
      </main>
    );
  if (session.kind === "investigation")
    return (
      <InvestigationView
        session={session}
        base={base}
        token={credentials.token!}
        busy={busy}
        error={error}
        action={action}
      />
    );
  const current = Math.min(step, session.pipeline.nodes.length - 1);
  return (
    <div className="app">
      <header className="topbar">
        <div>
          <b className="brand">◈ Beakdown</b>
          <h1>{session.pipeline.title}</h1>
          <p>
            {session.pipeline.description ||
              "Inspect the data before your agent proceeds."}
          </p>
        </div>
        <span className="badge">{session.state}</span>
      </header>
      {(error || session.error) && (
        <p className="error" role="alert">
          {error || session.error}
        </p>
      )}
      <section className="toolbar">
        <TimeScrubber
          step={current}
          count={session.pipeline.nodes.length}
          onChange={setStep}
        />
        <button
          disabled={
            session.state !== "ready" ||
            session.pipeline.status !== "pending_approval"
          }
          onClick={() => {
            const n = session.pipeline.nodes[current];
            setEdit(n.id);
            setQuery(n.sql_or_expr || "");
          }}
        >
          Edit this step
        </button>
      </section>
      <main className="canvas">
        <Canvas
          session={{
            ...session,
            pipeline: {
              ...session.pipeline,
              nodes: session.pipeline.nodes.map((n) => ({
                ...n,
                preview: n.preview
                  ? {
                      ...n.preview,
                      sample_data: arrowRows[n.id] ?? n.preview.sample_data,
                    }
                  : undefined,
              })),
            },
          }}
          step={current}
        />
      </main>
      {edit && (
        <section className="editor">
          <label>
            SQL for {edit}
            <textarea
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </label>
          <button
            disabled={busy}
            onClick={() => {
              action("edit", {
                node_id: edit,
                sql_or_expr: query,
                revision: session.revision,
              });
              setEdit("");
            }}
          >
            Recompute previews
          </button>
          <button onClick={() => setEdit("")}>Cancel</button>
        </section>
      )}
      <ApproveBar
        session={session}
        busy={busy}
        act={(a) => action(a, { revision: session.revision })}
      />
    </div>
  );
}
