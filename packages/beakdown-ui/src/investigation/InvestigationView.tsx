import { useEffect, useMemo, useState, useRef } from "react";
import {
  ReactFlow,
  ReactFlowProvider,
  Background,
  Controls,
  Handle,
  Position,
  MarkerType,
  useReactFlow,
  useStore,
  useNodesInitialized,
  useNodesState,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import type {
  Confidence,
  Finding,
  InvestigationSession,
  Screen,
} from "../types";
import AnalysisPanel from "../analysis/AnalysisPanel";
import {
  ArrowLeft,
  ArrowRight,
  ArrowUpRight,
  PanelsTopLeft,
  GitBranch,
  Columns2,
} from "lucide-react";
import "./investigation.css";
import "./starchy.css";

type Props = {
  session: InvestigationSession;
  base: string;
  token: string;
  busy: boolean;
  error: string;
  action: (path: string, body: object) => Promise<void>;
};
type ScreenData = {
  screen: Screen;
  image?: string;
  selected: boolean;
  findings: Finding[];
  select: () => void;
  open: () => void;
};
function ScreenNode({ data }: { data: Record<string, unknown> }) {
  const d = data as unknown as ScreenData;
  return (
    <article
      className={`screen-card ${d.selected ? "is-selected" : ""}`}
      aria-label={d.screen.title}
    >
      <Handle type="target" position={Position.Left} />
      <div className="screen-caption">
        <span className="capture-mark" />
        <span>{d.screen.title}</span>
        <span className="screen-size">
          {d.screen.width} × {d.screen.height}
        </span>
      </div>
      <button
        className="screenshot-button nodrag"
        onClick={d.open}
        aria-label={`Enlarge ${d.screen.title}`}
      >
        {d.image ? (
          <img
            src={d.image}
            alt={`${d.screen.title} screenshot`}
            draggable={false}
          />
        ) : (
          <span className="image-placeholder">Loading capture…</span>
        )}
        {d.findings
          .filter((f) => f.region)
          .map((f, i) => (
            <span
              className={`region-mark ${f.confidence}`}
              key={f.id}
              style={{
                left: `${f.region!.x * 100}%`,
                top: `${f.region!.y * 100}%`,
                width: `${f.region!.width * 100}%`,
                height: `${f.region!.height * 100}%`,
              }}
            >
              <span>{i + 1}</span>
            </span>
          ))}
      </button>
      <button className="screen-card-summary nodrag" onClick={d.select}>
        <span>{d.screen.description || "Captured application state"}</span>
        <b>
          {d.findings.length} finding{d.findings.length === 1 ? "" : "s"}
        </b>
      </button>
      <Handle type="source" position={Position.Right} />
    </article>
  );
}
const nodeTypes = { screen: ScreenNode };
function ScreenCanvas({
  screens,
  connections,
  findings,
  images,
  selected,
  overview,
  onSelect,
  onOpen,
}: {
  screens: Screen[];
  connections: InvestigationSession["investigation"]["connections"];
  findings: Finding[];
  images: Record<string, string>;
  selected: string;
  overview: boolean;
  onSelect: (s: string) => void;
  onOpen: (s: string) => void;
}) {
  const flow = useReactFlow();
  const width = useStore((s) => s.width),
    height = useStore((s) => s.height),
    initialized = useNodesInitialized();
  const measuredHeight = useStore(s => s.nodeLookup.get(selected)?.measured.height ?? 0);
  const measuredWidth = useStore(s => s.nodeLookup.get(selected)?.measured.width ?? 0);
  const mappedNodes = useMemo(
    () =>
      screens.map((screen, i) => ({
        id: screen.id,
        type: "screen",
        position: {
          x: (i % 3) * 590,
          y: Math.floor(i / 3) * 510 + (i % 3 === 1 ? 55 : 0),
        },
        data: {
          screen,
          image: images[screen.image_id],
          selected: screen.id === selected,
          findings: findings.filter((f) => f.screen_id === screen.id),
          select: () => onSelect(screen.id),
          open: () => {
            onSelect(screen.id);
            onOpen(screen.id);
          },
        },
      })),
    [screens, images, selected, findings],
  );
  const [nodes, setNodes, onNodesChange] = useNodesState(mappedNodes);
  useEffect(() => setNodes(mappedNodes), [mappedNodes, setNodes]);
  const edges = connections.map((c, i) => ({
    id: `edge-${i}`,
    source: c.source,
    target: c.target,
    label: c.label,
    style: {
      stroke: c.confidence === "inferred" ? "#a78641" : "#75949a",
      strokeWidth: 1.5,
      strokeDasharray: c.confidence === "inferred" ? "6 5" : undefined,
    },
    labelStyle: { fill: "#50676c", fontSize: 12 },
    labelBgStyle: { fill: "#f3f6f5" },
    labelBgPadding: [8, 5] as [number, number],
    markerEnd: { type: MarkerType.ArrowClosed, color: "#75949a" },
  }));
  useEffect(() => {
    if (initialized && width && height)
      flow.fitView({
        nodes: overview ? undefined : [{ id: selected }],
        duration: 0,
        padding: 0.2,
        maxZoom: 0.95,
      });
  }, [selected, width, height, measuredHeight, measuredWidth, initialized, overview]);
  return (
    <ReactFlow
      nodes={nodes}
      onNodesChange={onNodesChange}
      edges={edges}
      nodeTypes={nodeTypes}
      fitView
      fitViewOptions={{ padding: 0.18, maxZoom: 1 }}
      nodesDraggable={false}
      nodesConnectable={false}
      onNodeClick={(_, n) => onSelect(n.id)}
      minZoom={0.12}
      maxZoom={1.6}
    >
      <Background gap={24} size={1} color="#c5d3d0" />
      <Controls showInteractive={false} />
      <div className="canvas-legend">
        <span className="legend-line" />
        Observed journey
        <span className="legend-line inferred" />
        Inferred link
      </div>
    </ReactFlow>
  );
}
function Provenance({ screen }: { screen: Screen }) {
  return (
    <details className="provenance">
      <summary>Capture evidence</summary>
      <dl>
        <dt>Provider</dt>
        <dd>{screen.evidence.provider}</dd>
        <dt>Operation</dt>
        <dd>{screen.evidence.operation}</dd>
        <dt>Evidence ID</dt>
        <dd>{screen.evidence.evidence_id}</dd>
        <dt>Image SHA-256</dt>
        <dd>{screen.source_sha256}</dd>
        <dt>Recorded</dt>
        <dd>{screen.captured_at}</dd>
      </dl>
      {screen.evidence.limitations.map((l, i) => (
        <p key={i}>{l}</p>
      ))}
    </details>
  );
}
function ReviewEditor({
  finding,
  disabled,
  save,
}: {
  finding: Finding;
  disabled: boolean;
  save: (review: string, note: string) => void;
}) {
  const [note, setNote] = useState(finding.reviewer_note);
  useEffect(
    () => setNote(finding.reviewer_note),
    [finding.id, finding.reviewer_note],
  );
  return (
    <div className="review-editor">
      <label htmlFor={`note-${finding.id}`}>Your correction or note</label>
      <textarea
        id={`note-${finding.id}`}
        maxLength={5000}
        disabled={disabled}
        value={note}
        onChange={(e) => setNote(e.target.value)}
        placeholder="What should the agent reconsider?"
      />
      <div className="review-actions">
        <button disabled={disabled} onClick={() => save("confirmed", note)}>
          Confirm
        </button>
        <button disabled={disabled} onClick={() => save("disputed", note)}>
          Dispute
        </button>
        <button disabled={disabled} onClick={() => save(finding.review, note)}>
          Save note
        </button>
      </div>
    </div>
  );
}
function ScreenshotDialog({
  screen,
  image,
  findings,
  onClose,
}: {
  screen: Screen;
  image?: string;
  findings: Finding[];
  onClose: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const before = document.activeElement as HTMLElement;
    dialog.current?.showModal();
    const handle = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handle);
    return () => {
      window.removeEventListener("keydown", handle);
      before?.focus();
    };
  }, []);
  return (
    <dialog
      ref={dialog}
      className="screenshot-dialog"
      aria-label={`${screen.title} enlarged screenshot`}
      onKeyDown={(e) => {
        if (e.key === "Tab") {
          const items = e.currentTarget.querySelectorAll<HTMLElement>(
            "button,[href],input,textarea,select",
          );
          if (items.length) {
            e.preventDefault();
            items[0].focus();
          }
        }
      }}
    >
      <header>
        <div>
          <h2>{screen.title}</h2>
          <p>{screen.url || "Native application capture"}</p>
        </div>
        <button autoFocus onClick={onClose}>
          Close screenshot
        </button>
      </header>
      <div className="full-capture">
        <div className="annotated-image">
          {image && <img src={image} alt={`${screen.title} full screenshot`} />}{" "}
          {findings
            .filter((f) => f.region)
            .map((f, i) => (
              <span
                key={f.id}
                title={f.title}
                className={`region-mark ${f.confidence}`}
                style={{
                  left: `${f.region!.x * 100}%`,
                  top: `${f.region!.y * 100}%`,
                  width: `${f.region!.width * 100}%`,
                  height: `${f.region!.height * 100}%`,
                }}
              >
                <span>{i + 1}</span>
              </span>
            ))}
        </div>
      </div>
      <div className="dialog-findings">
        {findings.map((f) => (
          <p key={f.id}>
            <b>{f.title}</b> · {f.confidence}
            <br />
            {f.detail}
          </p>
        ))}
      </div>
    </dialog>
  );
}
export default function InvestigationView({
  session,
  base,
  token,
  busy,
  error,
  action,
}: Props) {
  const report = session.investigation;
  const [selected, setSelected] = useState(report.screens[0].id);
  const [images, setImages] = useState<Record<string, string>>({});
  const [assetError, setAssetError] = useState("");
  const [filter, setFilter] = useState<Confidence | "all">("all");
  const [search, setSearch] = useState("");
  const [expanded, setExpanded] = useState<string | null>(null);
  const [showOverview, setShowOverview] = useState(false);
  const [mode, setMode] = useState<"evidence" | "both" | "pipeline">("both");
  const [exporting, setExporting] = useState(false);
  const imageIds = report.screens.map((s) => s.image_id).join(",");
  useEffect(() => {
    let active = true;
    const urls: string[] = [];
    setAssetError("");
    Promise.all(
      [...new Set(report.screens.map((s) => s.image_id))].map(async (id) => {
        const response = await fetch(`${base}/assets/${id}`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!response.ok)
          throw new Error(
            "A screenshot could not be loaded. Reopen the session link or recreate an expired session.",
          );
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        urls.push(url);
        return [id, url];
      }),
    )
      .then((items) => {
        if (active) setImages(Object.fromEntries(items));
        else urls.forEach(URL.revokeObjectURL);
      })
      .catch((e) => {
        if (active) setAssetError(String(e));
      });
    return () => {
      active = false;
      urls.forEach(URL.revokeObjectURL);
    };
  }, [base, token, imageIds]);
  const screen =
    report.screens.find((s) => s.id === selected) ?? report.screens[0];
  const findings = report.findings.filter((f) => f.screen_id === screen.id);
  const visible = findings.filter(
    (f) =>
      (filter === "all" || f.confidence === filter) &&
      `${f.title} ${f.detail}`.toLowerCase().includes(search.toLowerCase()),
  );
  const index = report.screens.findIndex((s) => s.id === screen.id);
  const counts = {
    observed: report.findings.filter((f) => f.confidence === "observed").length,
    inferred: report.findings.filter((f) => f.confidence === "inferred").length,
    unknown: report.findings.filter((f) => f.confidence === "unknown").length,
  };
  const disabled =
    busy || session.state !== "ready" || report.status !== "pending_approval";
  async function exportReport() {
    setExporting(true);
    try {
      const r = await fetch(`${base}/export`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!r.ok) throw new Error("Could not export report");
      const url = URL.createObjectURL(await r.blob());
      const a = document.createElement("a");
      a.href = url;
      a.download = "beakdown-report.zip";
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (e) {
      setAssetError(String(e));
    } finally {
      setExporting(false);
    }
  }
  return (
    <div
      className={`investigation-app mode-${report.analysis ? mode : "evidence"}`}
    >
      <svg className="material-filters" aria-hidden="true">
        <defs>
          <filter id="gooey-switch">
            <feGaussianBlur in="SourceGraphic" stdDeviation="5" result="blur" />
            <feColorMatrix
              in="blur"
              mode="matrix"
              values="1 0 0 0 0 0 1 0 0 0 0 0 1 0 0 0 0 0 20 -8"
            />
          </filter>
        </defs>
      </svg>
      <header className="investigation-header">
        <a
          className="investigation-brand"
          href="#"
          onClick={(e) => {
            e.preventDefault();
            setShowOverview(true);
          }}
          aria-label="Beakdown investigation overview"
        >
          <svg
            width="26"
            height="26"
            viewBox="0 0 28 28"
            fill="none"
            aria-hidden="true"
          >
            <path d="M4 7h13l7 7-7 7H4l8-7-8-7Z" fill="currentColor" />
          </svg>
          Beakdown
        </a>
        <div className="report-heading">
          <h1>{report.title}</h1>
          <p>{report.target}</p>
        </div>
        <span className={`report-status ${report.status}`}>
          {report.status === "pending_approval"
            ? session.state === "running"
              ? "Computing analysis…"
              : session.state === "error"
                ? "Analysis needs attention"
                : "Ready for review"
            : report.status === "approved"
              ? "Review approved"
              : "Review rejected"}
        </span>
        <button
          className="export-button"
          onClick={exportReport}
          disabled={exporting}
        >
          {exporting ? "Exporting…" : "Export report"}
        </button>
      </header>
      {(error || assetError) && (
        <div className="investigation-error" role="alert">
          {error || assetError}
        </div>
      )}
      {report.analysis && (
        <nav className="workspace-switcher" aria-label="Workspace view">
          <span className="workspace-instruction">
            Evidence and execution, connected.
          </span>
          <div
            className="gooey-switch"
            style={
              {
                "--active-index": ["evidence", "both", "pipeline"].indexOf(
                  mode,
                ),
              } as React.CSSProperties
            }
          >
            <span className="gooey-track" aria-hidden="true">
              <span />
              <i />
            </span>
            {(
              [
                ["evidence", "Screens", PanelsTopLeft],
                ["both", "Both", Columns2],
                ["pipeline", "Data flow", GitBranch],
              ] as const
            ).map(([value, label, Icon]) => (
              <button
                key={value}
                aria-pressed={mode === value}
                onClick={() => setMode(value)}
              >
                <Icon size={14} />
                {label}
              </button>
            ))}
          </div>
          <span className="workspace-revision">
            Revision {session.revision}
          </span>
        </nav>
      )}
      <div className="investigation-workspace">
        <aside className="screen-sidebar" aria-label="Captured screens">
          <div className="sidebar-heading">
            <h2>Screen journey</h2>
            <span>{report.screens.length} captures</span>
          </div>
          <button
            className={`overview-button ${showOverview ? "active" : ""}`}
            onClick={() => setShowOverview(true)}
          >
            Investigation overview<span>{report.findings.length} findings</span>
          </button>
          <ol>
            {report.screens.map((s, i) => (
              <li key={s.id}>
                <button
                  className={`screen-nav ${selected === s.id && !showOverview ? "active" : ""}`}
                  onClick={() => {
                    setSelected(s.id);
                    setShowOverview(false);
                  }}
                  aria-current={
                    selected === s.id && !showOverview ? "step" : undefined
                  }
                >
                  <span className="screen-order">
                    {String(i + 1).padStart(2, "0")}
                  </span>
                  <div>
                    {images[s.image_id] && (
                      <img src={images[s.image_id]} alt="" />
                    )}
                    <strong>{s.title}</strong>
                    <small>
                      {
                        report.findings.filter((f) => f.screen_id === s.id)
                          .length
                      }{" "}
                      findings
                    </small>
                  </div>
                </button>
              </li>
            ))}
          </ol>
          <div className="capture-footer">
            <span className="live-dot" />
            Evidence captured locally
            <p>
              {report.screens.some((s) =>
                s.evidence.operation.startsWith("capture_"),
              )
                ? "REA evidence linked"
                : "Local screenshot evidence"}
            </p>
          </div>
        </aside>
        <div className="connected-stage">
          <section
            className="investigation-stage"
            aria-label="Screenshot canvas"
          >
            <div className="stage-toolbar">
              <div>
                <span className="stage-label">Screen evidence</span>
                <span className="stage-count">
                  {report.screens.length} screens / {report.connections.length}{" "}
                  connections
                </span>
              </div>
              <div className="stage-actions">
                <button onClick={() => setShowOverview(true)}>
                  Fit all screens
                </button>
                <button onClick={() => setExpanded(screen.id)}>
                  Inspect screenshot
                </button>
              </div>
            </div>
            <div className="screenshot-canvas">
              <ReactFlowProvider>
                <ScreenCanvas
                  screens={report.screens}
                  findings={report.findings}
                  connections={report.connections}
                  images={images}
                  selected={selected}
                  overview={showOverview}
                  onSelect={(s) => {
                    setSelected(s);
                    setShowOverview(false);
                  }}
                  onOpen={setExpanded}
                />
              </ReactFlowProvider>
            </div>
            <div className="journey-scrubber">
              <button
                aria-label="Previous screen"
                disabled={index === 0}
                onClick={() => {
                  setSelected(report.screens[index - 1].id);
                  setShowOverview(false);
                }}
              >
                <ArrowLeft size={14} />
              </button>
              <label>
                Journey
                <input
                  type="range"
                  aria-label="Screen journey"
                  min={0}
                  max={report.screens.length - 1}
                  value={index}
                  onChange={(e) => {
                    setSelected(report.screens[Number(e.target.value)].id);
                    setShowOverview(false);
                  }}
                />
              </label>
              <span>
                {index + 1} of {report.screens.length}
              </span>
              <button
                aria-label="Next screen"
                disabled={index === report.screens.length - 1}
                onClick={() => {
                  setSelected(report.screens[index + 1].id);
                  setShowOverview(false);
                }}
              >
                <ArrowRight size={14} />
              </button>
            </div>
          </section>
          {report.analysis && mode !== "evidence" && (
            <AnalysisPanel
              session={session}
              screenId={selected}
              busy={busy}
              action={action}
              onScreen={(id) => {
                setSelected(id);
                setShowOverview(false);
              }}
            />
          )}
        </div>
        <aside
          className="findings-inspector"
          aria-label="Investigation findings"
        >
          {showOverview ? (
            <>
              <div className="inspector-heading">
                <h2>What we learned</h2>
              </div>
              <p className="investigation-summary">
                {report.summary ||
                  "Inspect the captured screens and their evidence-linked findings."}
              </p>
              <div className="confidence-counts">
                <div>
                  <b>{counts.observed}</b>
                  <span>Observed</span>
                </div>
                <div>
                  <b>{counts.inferred}</b>
                  <span>Inferred</span>
                </div>
                <div>
                  <b>{counts.unknown}</b>
                  <span>Unknown</span>
                </div>
              </div>
              <h3>Coverage & limitations</h3>
              {report.limitations.length ? (
                report.limitations.map((l, i) => (
                  <p className="limitation" key={i}>
                    {l}
                  </p>
                ))
              ) : (
                <p className="limitation">
                  No additional coverage limitations supplied. Captured states
                  do not establish complete application behavior.
                </p>
              )}
              <h3>Human review</h3>
              <p>
                {report.findings.filter((f) => f.review === "confirmed").length}{" "}
                confirmed ·{" "}
                {report.findings.filter((f) => f.review === "disputed").length}{" "}
                disputed ·{" "}
                {
                  report.findings.filter((f) => f.review === "unreviewed")
                    .length
                }{" "}
                unreviewed
              </p>
              <p className="muted-note">
                Review approval records your assessment of this report. It does
                not execute changes in the application.
              </p>
            </>
          ) : (
            <>
              <div className="inspector-heading">
                <h2>{screen.title}</h2>
                <p>{screen.description}</p>
              </div>
              <div
                className="finding-filters"
                role="group"
                aria-label="Filter findings"
              >
                {(["all", "observed", "inferred", "unknown"] as const).map(
                  (c) => (
                    <button
                      key={c}
                      aria-pressed={filter === c}
                      onClick={() => setFilter(c)}
                    >
                      {c === "all" ? "All findings" : c}
                    </button>
                  ),
                )}
              </div>
              <label className="finding-search">
                <span className="sr-only">Search findings</span>
                <input
                  type="search"
                  placeholder="Search this screen…"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
              </label>
              <div className="finding-list">
                {visible.map((f) => (
                  <article className="finding-card" key={f.id}>
                    <div className="finding-meta">
                      <span className={`confidence ${f.confidence}`}>
                        {f.confidence}
                      </span>
                      <span>{f.category}</span>
                      {f.review !== "unreviewed" && (
                        <span className={`review-state ${f.review}`}>
                          {f.review}
                        </span>
                      )}
                    </div>
                    <h3>
                      {f.region && (
                        <span className={`finding-pin ${f.confidence}`}>
                          {findings
                            .filter((v) => v.region)
                            .findIndex((v) => v.id === f.id) + 1}
                        </span>
                      )}
                      {f.title}
                    </h3>
                    <p>{f.detail}</p>
                    {f.region && (
                      <button
                        className="text-button"
                        onClick={() => setExpanded(screen.id)}
                      >
                        Show on screenshot
                      </button>
                    )}
                    <details>
                      <summary>Evidence & review</summary>
                      <div className="finding-citations">
                        {(f.evidence_ids.length
                          ? f.evidence_ids
                          : [screen.evidence.evidence_id]
                        ).map((id) => (
                          <code key={id}>{id}</code>
                        ))}
                      </div>
                      <ReviewEditor
                        finding={f}
                        disabled={disabled}
                        save={(review, note) =>
                          action(`findings/${f.id}/review`, {
                            revision: session.revision,
                            review,
                            reviewer_note: note,
                          })
                        }
                      />
                    </details>
                  </article>
                ))}
                {visible.length === 0 && (
                  <p className="no-findings">
                    {findings.length
                      ? "No findings match this filter."
                      : "No findings recorded for this screen."}
                  </p>
                )}
              </div>
              <Provenance screen={screen} />
            </>
          )}
        </aside>
      </div>
      <footer className="investigation-dock">
        <div className="review-count">
          <span className="live-dot" />
          <span>
            {report.findings.filter((f) => f.review !== "unreviewed").length} of{" "}
            {report.findings.length} findings reviewed
          </span>
          <button className="text-button" onClick={() => setShowOverview(true)}>
            View summary
          </button>
        </div>
        {report.status === "pending_approval" ? (
          <>
            <button
              disabled={disabled}
              onClick={() => action("reject", { revision: session.revision })}
            >
              Request another pass
            </button>
            <button
              className="approve-review"
              disabled={disabled}
              onClick={() => action("approve", { revision: session.revision })}
            >
              Approve review <ArrowUpRight size={16} />
            </button>
          </>
        ) : (
          <div className="review-complete">
            <span>
              {report.status === "approved"
                ? "Review approved."
                : "Another pass requested."}
            </span>
            <button
              onClick={() =>
                navigator.clipboard.writeText(
                  `Beakdown investigation ${report.investigation_id} reviewed. Call get_session_result with its existing token. Read all corrections, disputed findings and limitations before continuing.`,
                )
              }
            >
              Copy resumption prompt
            </button>
          </div>
        )}
      </footer>
      {expanded && (
        <ScreenshotDialog
          screen={report.screens.find((s) => s.id === expanded)!}
          image={
            images[report.screens.find((s) => s.id === expanded)!.image_id]
          }
          findings={report.findings.filter((f) => f.screen_id === expanded)}
          onClose={() => setExpanded(null)}
        />
      )}
    </div>
  );
}
