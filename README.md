# 🦅 Beakdown

**The open-source visual audit and time-travel canvas for AI agent data pipelines.**

Give agent work a human checkpoint. Stage a SQL DAG, inspect bounded table previews, scrub through execution steps, edit queries, and approve the exact reviewed plan before the agent proceeds.

Pair Beakdown with **REA** to understand applications: REA collects static and runtime evidence; Beakdown makes the agent's analysis pipeline and conclusions inspectable. This is an evidence review companion, not a promise to recover every application's implementation.

## Quick start

Requires Python 3.11+, uv, Node 20.19+ and pnpm 10.

```sh
uv sync
pnpm install
pnpm build
uv run beakdown-mcp
```

The MCP server uses stdio. Configure your agent with:

```json
{
  "mcpServers": {
    "beakdown": {
      "command": "uv",
      "args": ["--directory", "/absolute/path/to/beakdown", "run", "beakdown-mcp"]
    }
  }
}
```

Call `create_handoff_session`:

```json
{
  "title": "Inspect active customers",
  "nodes": [
    {"id": "customers", "title": "Sample customers", "operation_type": "load", "sql_or_expr": "SELECT * FROM (VALUES (1, 'ACTIVE', 700), (2, 'INACTIVE', 20)) t(id, status, spend)"},
    {"id": "buyers", "title": "Active top buyers", "operation_type": "filter", "sql_or_expr": "status = 'ACTIVE' AND spend > 500"}
  ],
  "edges": [{"source": "customers", "target": "buyers"}]
}
```

Open the returned inspection URL. After approval, call `get_session_result` with the returned `session_id` and `token`. Only proceed if `approved` is true, using the returned pipeline. “Approve & Commit” commits the approval decision; the agent separately executes production changes.

## Execution contract

- Nodes run in topological order. Queries reference upstream tables by node ID; filter nodes take one parent and a SQL predicate.
- Only a single DuckDB SELECT is accepted. No Python expressions, exec, extensions, network access, or production writes.
- Local data files require exact absolute paths in `allowed_paths` at session creation. Treat this as an explicit read grant.
- Each node returns schema, full-table null counts, up to 50 sample rows, and Arrow IPC. Combined preview JSON and Arrow must remain below 100,000 bytes; large samples shrink and oversized schemas fail.
- The engine materializes intermediate tables under a 256 MB DuckDB limit. This preview budget is a browser transport limit, not a total process-memory guarantee. No query timeout or OS sandbox is provided yet.
- The loopback daemon binds an OS-assigned port. Credentials live in the URL fragment and Authorization headers. The UI removes the fragment from the address bar after reading it. API responses are not cached; cross-origin requests and unexpected Host headers are rejected.
- Sessions are in-memory, expire after one hour, and end with the MCP process. Capacity is 32 sessions; work uses two background threads. Creation queues execution without waiting for previews; first daemon startup has no strict 50 ms guarantee.
- Edits recompute the full DAG. Revision checks prevent stale approvals. The timeline reveals ordered node results from the current execution; persisted execution history is not implemented.

## REA companion workflow

1. Use REA on an application you can inspect: browser/network captures, bundle analysis, native or managed inspection, and static/runtime correlation.
2. Have the agent normalize relevant findings into SQL rows. Keep originals outside Beakdown and attach source references through node `evidence`.
3. Build separate nodes for observations, joins, filters, and inferred conclusions. Record confidence and unresolved questions in evidence summaries.
4. Inspect samples and queries in Beakdown. Review original artifacts before approving claims that a sample cannot establish.

See [the runnable REA example](examples/rea_app_audit.py). This integration is agent-mediated: Beakdown does not automatically invoke REA, ingest its private formats, or render arbitrary HTML from findings. Sources appear as plain text.

## Development

```sh
uv run pytest
pnpm build
pnpm dev
```

`pnpm dev` starts an isolated UI development server on a dynamic port. Use the built UI served by the daemon for authenticated end-to-end sessions.

Monorepo packages: `beakdown-core` (schemas, DuckDB, Arrow, FastAPI), `beakdown-ui` (React Flow, Vite, Tailwind), and `beakdown-mcp` (MCP Python SDK v1 stdio). This initial release supports DuckDB SQL; Polars and persistent historical snapshots remain future work.

## License

MIT.
