# 🦅 Beakdown

**An open-source visual review canvas for application investigations and AI agent data pipelines.**

Give agent work a human checkpoint. Stage a SQL DAG, inspect bounded table previews, scrub through execution steps, edit queries, and approve the exact reviewed plan before the agent proceeds.

Pair Beakdown with **REA** to break down an app or website into captured screens, connected journeys, annotated findings and evidence. The Beakdown skill guides the agent through capture and opens a browser workbench where you can inspect, confirm, dispute and export the findings.

![Beakdown screenshot investigation](docs/investigation.png)

## Break down an app or website

1. Install [the Beakdown skill](skills/beakdown/SKILL.md) in your agent's skill directory and configure REA and Beakdown as MCP servers.
2. Ask: **“Use Beakdown with REA to break down this website: https://your-site.example. Capture its key screens and explain the main journey.”**
3. The agent uses REA to collect screenshots and supporting evidence, then calls `create_investigation_session`.
4. Open the returned canvas. Select screens, enlarge captures, inspect numbered regions, filter observations/inferences/unknowns, and confirm or dispute findings with corrections.
5. Approve the report or request another pass. The agent retrieves the reviewed findings with `get_session_result`.

REA performs the capture; the skill orchestrates the tool calls. Beakdown imports and presents evidence. This is a working agent-guided workflow, not an unattended crawler or a promise to recover every application's implementation. The skill ships in this repository; installing it does not register MCP servers.

### Screenshot investigation input

After the quick-start installation below, call `create_investigation_session` with:

```json
{
  "title": "Customer portal investigation",
  "target": "https://your-site.example",
  "summary": "What the agent learned, grounded in the captures.",
  "screens": [
    {
      "id": "home",
      "title": "Home screen",
      "description": "The starting point of the inspected journey.",
      "rea_evidence_path": "/absolute/path/to/rea-evidence.json",
      "rea_evidence_id": "ev_exact_id_from_rea",
      "capture_index": 0
    }
  ],
  "findings": [
    {
      "id": "navigation",
      "screen_id": "home",
      "title": "Persistent workspace navigation",
      "detail": "Replace this example with a conclusion supported by the actual capture.",
      "confidence": "observed",
      "category": "interface",
      "evidence_ids": ["ev_exact_id_from_rea"],
      "region": { "x": 0.01, "y": 0.1, "width": 0.15, "height": 0.3 }
    }
  ],
  "connections": [],
  "limitations": ["Only the captured routes and states were inspected."]
}
```

A screen accepts exactly one absolute `rea_evidence_path` or `screenshot_path`. Supported REA formats: web screenshot Evidence, browser/Electron scenarios, and native UI scenarios. Raw records, MCP JSON envelopes, and exported bundles are accepted. Select bundle records using `rea_evidence_id`; `capture_index` counts captured screenshots, defaulting to the last capture. Other providers can import their local PNG/JPEG/WebP screenshot files. No target HTML or scripts execute in the workbench.

For an agent without the new MCP tool loaded yet, save those arguments as an absolute JSON manifest and run:

```sh
uv run beakdown-review /absolute/path/to/investigation.json
```

This starts the local daemon, opens the canvas in your browser, and stays alive until Ctrl+C. Add `--no-open` to print the URL only. To install the skill for a compatible agent, copy `skills/beakdown` to its documented skill directory (for Codex, `~/.agents/skills/beakdown`); reconnect/restart if the client requires it.

Screenshots are authenticated, validated and normalized to inert WebP. Complete evidence JSON imports are capped at 24 MB per file. Input limits are 8 MB and 20 megapixels per screenshot, 32 MB of normalized images per session, 50 screens and 300 findings. REA-provided image digests are verified; source IDs, operation, provider and capture limitations remain visible. Export report downloads a ZIP with Markdown, JSON and normalized screenshots, excluding session credentials. The export preserves the review; reopening exported ZIPs in the canvas is not implemented yet. Sessions still expire after one hour.

Approval records the human's assessment. Disputed findings and reviewer notes are returned even when the overall report is approved; approval does not establish that every inference is true. Screenshots and source metadata may contain private content: keep evidence out of public repositories unless deliberately sharing it.

For a reproducible local test target, serve `examples/demo-site`. It is a fictional app made for testing the capture workflow. The documentation screenshot shows actual browser captures of that fictional demo.

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
      "args": [
        "--directory",
        "/absolute/path/to/beakdown",
        "run",
        "beakdown-mcp"
      ]
    }
  }
}
```

Call `create_handoff_session`:

```json
{
  "title": "Inspect active customers",
  "nodes": [
    {
      "id": "customers",
      "title": "Sample customers",
      "operation_type": "load",
      "sql_or_expr": "SELECT * FROM (VALUES (1, 'ACTIVE', 700), (2, 'INACTIVE', 20)) t(id, status, spend)"
    },
    {
      "id": "buyers",
      "title": "Active top buyers",
      "operation_type": "filter",
      "sql_or_expr": "status = 'ACTIVE' AND spend > 500"
    }
  ],
  "edges": [{ "source": "customers", "target": "buyers" }]
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

## Evidence and data investigations

Investigations open in **Both** view: captured screen journeys above, an executable SQL DAG and bounded results below, and evidence-linked findings alongside. Switch to Screens or Data flow for more space. The interface uses the Starchy Gooey system: neutral drafting ground, Geist typography, glass navigation and fluid selection controls.

Every investigation includes a default DuckDB analysis of its actual findings: captured findings → findings by screen / needs human review. Selecting a screen scopes the sampled results; selecting a linked table row returns to its screenshot. “All screens” broadens the sample view. Samples stay capped at 50 rows, so a missing sampled row does not establish absence from the full result.

Edit SQL and recompute to inspect a different question. Confirming or disputing a finding updates the source tables and reruns the DAG; approval waits for computation to complete. Exports include the reviewed report, queries, previews and Arrow files. Review approval does not execute production changes.

`create_investigation_session` accepts optional `analysis_pipeline` (a PipelineSpec), `analysis_links` (screen/node/finding associations), and `include_analysis` (default true). Queries can read `audit_findings`, `audit_screens`, `audit_connections` and upstream node IDs. Custom pipelines cannot read external files. Pass `include_analysis: false` for an evidence-only session. Use `create_handoff_session` for standalone SQL transformations.

The timeline reveals steps from the current execution. It does not retain previous query executions or provide persisted time travel.

## Development

```sh
uv run pytest
pnpm build
pnpm dev
# In another terminal, after a production build (requires Chrome):
uv run --with playwright python tests/browser_smoke.py
```

`pnpm dev` starts an isolated UI development server on a dynamic port. Use the built UI served by the daemon for authenticated end-to-end sessions.

Monorepo packages: `beakdown-core` (schemas, DuckDB, Arrow, FastAPI), `beakdown-ui` (React Flow, Vite, Tailwind), and `beakdown-mcp` (MCP Python SDK v1 stdio and the review CLI). This initial release supports DuckDB SQL; Polars and persistent historical snapshots remain future work.

## License

MIT.
