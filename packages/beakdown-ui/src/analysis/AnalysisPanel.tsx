import { useEffect, useMemo, useState } from "react";
import { Database, GitBranch, Play, ArrowUpRight } from "lucide-react";
import {
  ReactFlow,
  ReactFlowProvider,
  Handle,
  Position,
  useNodesState,
  Background,
  Controls,
  useReactFlow,
  useStore,
  useNodesInitialized,
} from "@xyflow/react";
import type { FlowNode, InvestigationSession } from "../types";

function AnalysisNode({ data }: { data: Record<string, unknown> }) {
  const node = data.node as FlowNode;
  return (
    <button
      className={`analysis-node ${data.active ? "active" : ""} ${data.linked ? "linked" : ""}`}
      onClick={data.select as () => void}
      aria-pressed={Boolean(data.active)}
    >
      <Handle type="target" position={Position.Left} />
      <span className="analysis-operation">
        <Database size={13} />
        {node.operation_type.replaceAll("_", " ")}
      </span>
      <strong>{node.title}</strong>
      <span className="analysis-measure">
        {node.preview
          ? `${node.preview.total_rows.toLocaleString()} rows · ${node.preview.execution_time_ms.toFixed(1)} ms`
          : "Awaiting execution"}
      </span>
      <Handle type="source" position={Position.Right} />
    </button>
  );
}
const nodeTypes = { analysis: AnalysisNode };

function DataGraph({
  pipeline,
  selected,
  links,
  select,
}: {
  pipeline: NonNullable<InvestigationSession["investigation"]["analysis"]>;
  selected: string;
  links: string[];
  select: (id: string) => void;
}) {
  const flow = useReactFlow();
  const width = useStore((s) => s.width),
    height = useStore((s) => s.height);
  const initialized = useNodesInitialized();
  useEffect(() => {
    if (initialized && width && height)
      flow.fitView({ padding: 0.08, minZoom: 0.85, maxZoom: 1, duration: 0 });
  }, [width, height, initialized]);
  const initial = useMemo(() => {
    const depths = new Map<string, number>();
    const depth = (id: string, trail = new Set<string>()): number => {
      if (trail.has(id)) return 0;
      if (depths.has(id)) return depths.get(id)!;
      const next = new Set(trail).add(id);
      const parents = pipeline.edges.filter((e) => e.target === id);
      const value = parents.length
        ? Math.max(...parents.map((e) => depth(e.source, next))) + 1
        : 0;
      depths.set(id, value);
      return value;
    };
    const slots = new Map<number, number>();
    return pipeline.nodes.map((node) => {
      const x = depth(node.id),
        y = slots.get(x) ?? 0;
      slots.set(x, y + 1);
      return {
        id: node.id,
        type: "analysis",
        position: { x: x * 250, y: y * 96 },
        data: {
          node,
          active: selected === node.id,
          linked: links.includes(node.id),
          select: () => select(node.id),
        },
      };
    });
  }, [pipeline, selected, links, select]);
  const [nodes, setNodes, onNodesChange] = useNodesState(initial);
  useEffect(() => setNodes(initial), [initial, setNodes]);
  return (
    <ReactFlow
      nodes={nodes}
      onNodesChange={onNodesChange}
      edges={pipeline.edges.map((e, i) => ({
        ...e,
        id: `analysis-${i}`,
        type: "smoothstep",
        style: { stroke: "#6e6e6e", strokeWidth: 1.2 },
      }))}
      nodeTypes={nodeTypes}
      fitView
      fitViewOptions={{ padding: 0.08, minZoom: 0.85, maxZoom: 1 }}
      minZoom={0.25}
      maxZoom={1.2}
      nodesDraggable={false}
      nodesConnectable={false}
      aria-label="Executable evidence data flow"
    >
      <Background color="#bcbcbc" gap={24} size={0.6} />
      <Controls showInteractive={false} />
    </ReactFlow>
  );
}

export default function AnalysisPanel({
  session,
  screenId,
  onScreen,
  busy,
  action,
}: {
  session: InvestigationSession;
  screenId: string;
  onScreen: (id: string) => void;
  busy: boolean;
  action: (path: string, body: object) => Promise<void>;
}) {
  const pipeline = session.investigation.analysis!;
  const [selected, select] = useState(pipeline.nodes[0]?.id ?? "");
  const [scope, setScope] = useState<"screen" | "all">("screen");
  const [editing, setEditing] = useState(false);
  const node =
    pipeline.nodes.find((n) => n.id === selected) ?? pipeline.nodes[0];
  const [query, setQuery] = useState(node?.sql_or_expr ?? "");
  useEffect(() => {
    setQuery(node?.sql_or_expr ?? "");
    setEditing(false);
  }, [node?.id, node?.sql_or_expr]);
  const links = session.investigation.analysis_links
    .filter((l) => l.screen_id === screenId)
    .map((l) => l.node_id);
  const preview = node?.preview;
  const scoped = preview?.columns.some((c) => c.name === "screen_id");
  const rows = (preview?.sample_data ?? []).filter(
    (r) => scope === "all" || !scoped || r.screen_id === screenId,
  );
  const screen = session.investigation.screens.find((s) => s.id === screenId);
  const locked =
    busy ||
    session.state === "running" ||
    pipeline.status !== "pending_approval";
  if (!node)
    return (
      <section className="analysis-panel">
        <h2>Data flow</h2>
        <p>No analysis nodes supplied.</p>
      </section>
    );
  return (
    <section className="analysis-panel" aria-label="Evidence analysis">
      <div className="analysis-heading">
        <div>
          <h2>
            <GitBranch size={16} />
            Data flow
          </h2>
          <p>Read-only SQL over captured evidence</p>
        </div>
        <span className="execution-status" role="status">
          {session.state === "running"
            ? "Computing…"
            : session.state === "error"
              ? "Query needs attention"
              : "Executed locally"}
        </span>
      </div>
      <div className="analysis-graph">
        <ReactFlowProvider>
          <DataGraph
            pipeline={pipeline}
            selected={node.id}
            links={links}
            select={select}
          />
        </ReactFlowProvider>
      </div>
      <div className="analysis-result">
        <div className="result-heading">
          <strong>{node.title}</strong>
          <div className="result-actions">
            <button
              aria-pressed={scope === "screen"}
              onClick={() => setScope(scope === "all" ? "screen" : "all")}
            >
              {scope === "screen" ? "This screen" : "All screens"}
            </button>
            <button
              aria-expanded={editing}
              onClick={() => setEditing(!editing)}
            >
              Edit SQL
            </button>
          </div>
        </div>
        <p className="result-context">
          {scope === "screen" && scoped ? screen?.title + " · " : ""}
          {rows.length} sample rows / {preview?.total_rows ?? "—"} total ·
          maximum 50 sampled. Select a linked row to inspect its screen.
        </p>
        {session.error && (
          <p className="analysis-error" role="alert">
            {session.error} Edit the query and recompute.
          </p>
        )}
        {editing && (
          <form
            className="analysis-editor"
            onSubmit={async (e) => {
              e.preventDefault();
              await action("edit", {
                revision: session.revision,
                node_id: node.id,
                sql_or_expr: query,
              });
            }}
          >
            <label>
              SQL or filter expression
              <textarea
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                spellCheck={false}
              />
            </label>
            <button className="primary" disabled={locked || !query.trim()}>
              <Play size={13} />
              Recompute
            </button>
            <p>
              Available sources: audit_findings, audit_screens,
              audit_connections, and upstream nodes.
            </p>
          </form>
        )}
        <div className="analysis-table" aria-busy={session.state === "running"}>
          {preview && (
            <table>
              <thead>
                <tr>
                  {preview.columns.map((c) => (
                    <th key={c.name}>
                      {c.name}
                      <small>
                        {c.data_type} · {c.null_count} nulls
                      </small>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((row, i) => (
                  <tr key={i}>
                    {preview.columns.map((c, j) => (
                      <td key={c.name}>
                        {j === 0 &&
                        typeof row.screen_id === "string" &&
                        session.investigation.screens.some(
                          (s) => s.id === row.screen_id,
                        ) ? (
                          <button
                            className="row-evidence"
                            onClick={() => onScreen(row.screen_id as string)}
                            aria-label={`Inspect screen ${row.screen_id}`}
                          >
                            {String(row[c.name] ?? "null")}
                            <ArrowUpRight size={12} />
                          </button>
                        ) : (
                          String(row[c.name] ?? "null")
                        )}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {!rows.length && (
            <p className="analysis-empty">
              {session.state === "running"
                ? "Computing bounded previews…"
                : scope === "screen" && scoped
                  ? "No sampled rows for this screen. Show all screens or inspect another step."
                  : "This step returned no rows."}
            </p>
          )}
        </div>
        <label className="analysis-scrubber">
          Execution step
          <input
            type="range"
            aria-label="Analysis step"
            min={0}
            max={pipeline.nodes.length - 1}
            value={pipeline.nodes.findIndex((n) => n.id === node.id)}
            onChange={(e) => select(pipeline.nodes[Number(e.target.value)].id)}
          />
          <span>
            {pipeline.nodes.findIndex((n) => n.id === node.id) + 1} /{" "}
            {pipeline.nodes.length}
          </span>
        </label>
      </div>
    </section>
  );
}
