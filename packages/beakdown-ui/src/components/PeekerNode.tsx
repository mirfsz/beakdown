import { Handle, Position } from "@xyflow/react";
import type { FlowNode } from "../types";
export default function PeekerNode({
  data,
}: {
  data: Record<string, unknown>;
}) {
  const node = data.node as FlowNode;
  const p = node.preview;
  return (
    <article className="peeker">
      <Handle type="target" position={Position.Left} />
      <header>
        <span className="badge">{node.operation_type}</span>
        <span>{p?.execution_time_ms.toFixed(1)} ms</span>
      </header>
      <h2>{node.title}</h2>
      <p>
        {p?.total_rows.toLocaleString() ?? "…"} rows · {p?.column_count ?? 0}{" "}
        columns
      </p>
      <details className="nodrag nowheel" open>
        <summary>Inspect sample · {p?.sample_data.length ?? 0} rows</summary>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                {p?.columns.map((c) => (
                  <th key={c.name}>
                    {c.name}
                    <small>
                      {c.data_type} · {c.null_count} nulls
                    </small>
                    <meter
                      min={0}
                      max={Math.max(1, p.total_rows)}
                      value={c.null_count}
                      aria-label={`${c.name} null count`}
                    />
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {p?.sample_data.map((r, i) => (
                <tr key={i}>
                  {p.columns.map((c) => (
                    <td key={c.name}>
                      {r[c.name] === null ? "∅" : String(r[c.name])}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
      <details className="nodrag">
        <summary>Query & evidence</summary>
        <pre>{node.sql_or_expr}</pre>
        {node.evidence.map((e, i) => (
          <p key={i}>
            {e.summary}
            <small>
              {e.source} {e.confidence}
            </small>
          </p>
        ))}
      </details>
      <Handle type="source" position={Position.Right} />
    </article>
  );
}
