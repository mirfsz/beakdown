import { useEffect, useState } from "react";
import { ReactFlow, Background, Controls, MiniMap } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import PeekerNode from "./PeekerNode";
import type { Session } from "../types";
const nodeTypes = { peeker: PeekerNode };
export default function Canvas({
  session,
  step,
}: {
  session: Session;
  step: number;
}) {
  const [mobile, setMobile] = useState(() => window.innerWidth < 700);
  useEffect(() => {
    const update = () => setMobile(window.innerWidth < 700);
    window.addEventListener("resize", update);
    return () => window.removeEventListener("resize", update);
  }, []);
  const nodes = session.pipeline.nodes
    .slice(0, step + 1)
    .map((n, i) => ({
      id: n.id,
      type: "peeker",
      position: { x: mobile ? 0 : i * 500, y: mobile ? i * 450 : (i % 2) * 70 },
      data: { node: n },
    }));
  const ids = new Set(nodes.map((n) => n.id));
  return (
    <ReactFlow
      key={String(mobile)}
      nodes={nodes}
      edges={session.pipeline.edges
        .filter((e) => ids.has(e.source) && ids.has(e.target))
        .map((e, i) => ({ ...e, id: String(i) }))}
      nodeTypes={nodeTypes}
      fitView
      minZoom={0.15}
    >
      <Background gap={24} color="#b5c5d5" />
      <Controls />
      <MiniMap />
    </ReactFlow>
  );
}
