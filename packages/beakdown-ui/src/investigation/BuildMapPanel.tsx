import { useEffect, useState } from "react";
import {
  BookOpen,
  Code2,
  ClipboardCheck,
  ArrowUpRight,
  RefreshCw,
  Pencil,
  Check,
} from "lucide-react";
import type {
  AppRule,
  ImplementationRef,
  InvestigationSession,
  VerificationCheck,
} from "../types";
import "./build-map.css";

function Source({ source }: { source: ImplementationRef }) {
  return (
    <article className="source-reference">
      <div className="trace-row">
        <strong>{source.title}</strong>
        <span className={`trace-state ${source.snapshot_status}`}>
          {source.snapshot_status.replaceAll("_", " ")}
        </span>
      </div>
      <p className="source-location">
        <Code2 size={13} />
        <code>
          {source.path}:{source.line_start}
          {source.line_end !== source.line_start ? `–${source.line_end}` : ""}
        </code>
      </p>
      <p>
        {source.layer.toUpperCase()}
        {source.symbol ? ` · ${source.symbol}` : ""} · Linked by the agent
      </p>
      {source.excerpt ? (
        <details>
          <summary>Inspect captured source</summary>
          <pre>
            <code>{source.excerpt}</code>
          </pre>
          <p className="source-digest">
            File SHA256 <code>{source.source_sha256}</code>
          </p>
          <p>
            A source snapshot establishes inspected code, not that the rule is
            enforced.
          </p>
        </details>
      ) : (
        <p>No local source was read. This is an unverified reference.</p>
      )}
      {source.snapshot_status === "changed" && (
        <p className="trace-warning">
          File changed since this snapshot. The agent needs to inspect and test
          the new version.
        </p>
      )}
      {source.snapshot_status === "unavailable" && (
        <p className="trace-warning">
          The linked file can no longer be read. This excerpt is the earlier
          snapshot.
        </p>
      )}
      {source.evidence_ids.length > 0 && (
        <p className="trace-citations">
          Evidence: {source.evidence_ids.join(", ")}
        </p>
      )}
    </article>
  );
}

function CheckResult({ check }: { check: VerificationCheck }) {
  return (
    <article className="verification-check">
      <div className="trace-row">
        <strong>{check.title}</strong>
        <span className={`trace-state ${check.status}`}>
          {check.status.replaceAll("_", " ")}
        </span>
      </div>
      <p>
        {check.status === "passed" || check.status === "failed"
          ? "Agent-reported outcome"
          : "Verification status"}{" "}
        · {check.method}
        {check.checked_at ? ` · ${check.checked_at}` : ""}
      </p>
      <p>{check.detail || "No result evidence supplied yet."}</p>
      {check.stale_reason && (
        <p className="trace-warning">{check.stale_reason}</p>
      )}
      {check.command && (
        <details>
          <summary>Check command & evidence</summary>
          <pre>{check.command}</pre>
          <p>This command is recorded for review. Beakdown does not run it.</p>
          <p className="trace-citations">
            Evidence: {check.evidence_ids.join(", ") || "None supplied"}
          </p>
          <p>
            Rule revisions:{" "}
            {Object.entries(check.rule_revisions)
              .map(([id, revision]) => `${id} @ ${revision}`)
              .join(", ")}
          </p>
          <p className="source-digest">
            Bound source:{" "}
            {Object.keys(check.source_hashes).join(", ") ||
              "No source hashes supplied"}
          </p>
        </details>
      )}
      {!check.command && check.evidence_ids.length > 0 && (
        <p className="trace-citations">
          Evidence: {check.evidence_ids.join(", ")}
        </p>
      )}
    </article>
  );
}

function RuleDetail({
  rule,
  session,
  disabled,
  onScreen,
  action,
}: {
  rule: AppRule;
  session: InvestigationSession;
  disabled: boolean;
  onScreen: (id: string) => void;
  action: (path: string, body: object) => Promise<void>;
}) {
  const [tab, setTab] = useState<"intent" | "code" | "checks">("intent");
  const [editing, setEditing] = useState(false);
  const [description, setDescription] = useState(rule.description);
  const [note, setNote] = useState(rule.reviewer_note);
  const [copied, setCopied] = useState(false);
  const [copyBlocked, setCopyBlocked] = useState(false);
  useEffect(() => {
    setDescription(rule.description);
    setNote(rule.reviewer_note);
    setEditing(false);
    setCopied(false);
    setCopyBlocked(false);
  }, [rule.id, rule.revision, rule.reviewer_note]);
  const build = session.investigation.build_map!;
  const sources = build.implementation.filter((s) =>
    s.rule_ids.includes(rule.id),
  );
  const checks = build.checks.filter((c) => c.rule_ids.includes(rule.id));
  const save = (review: AppRule["review"], change = false) =>
    action(`rules/${rule.id}/review`, {
      revision: session.revision,
      review,
      reviewer_note: note,
      ...(change ? { description } : {}),
    });
  const changeRequest = `Beakdown rule ${rule.id} (revision ${rule.revision}) needs a change. Required behavior: ${rule.description}\nReviewer note: ${rule.reviewer_note}\nAffected pages: ${rule.screen_ids.join(", ")}\nLinked source: ${sources.map((s) => `${s.path}:${s.line_start}`).join(", ")}\nFetch get_session_result for the full reviewed intent, implement the change, rerun affected checks, and create a fresh build map with new evidence. Do not treat stale checks as passing.`;
  return (
    <div className="rule-detail">
      <header className="rule-heading">
        <div>
          <h3>{rule.title}</h3>
          <p>
            {rule.origin === "requirement"
              ? "Intended requirement"
              : rule.origin === "observed"
                ? "Observed behavior"
                : "Inferred rule"}{" "}
            · revision {rule.revision}
          </p>
        </div>
        <div className="rule-heading-actions">
          <button
            disabled={disabled}
            onClick={() => {
              setTab("intent");
              setEditing(true);
            }}
          >
            <Pencil size={13} />
            Edit rule
          </button>
          <span className={`trace-state ${rule.review}`}>
            {rule.review === "confirmed"
              ? "accepted"
              : rule.review === "disputed"
                ? "change requested"
                : "needs review"}
          </span>
        </div>
      </header>
      <nav className="rule-tabs" aria-label="Rule details">
        {(
          [
            ["intent", "Intent", BookOpen],
            ["code", `Code (${sources.length})`, Code2],
            ["checks", `Checks (${checks.length})`, ClipboardCheck],
          ] as const
        ).map(([value, label, Icon]) => (
          <button
            key={value}
            aria-pressed={tab === value}
            onClick={() => setTab(value)}
          >
            <Icon size={13} />
            {label}
          </button>
        ))}
      </nav>
      <div className="rule-content">
        {tab === "intent" && editing && (
          <form
            className="rule-editor"
            onSubmit={(e) => {
              e.preventDefault();
              void save("disputed", true);
            }}
          >
            <label>
              Required behavior
              <textarea
                autoFocus
                aria-label="Required behavior"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                maxLength={5000}
                required
              />
            </label>
            <label>
              Note for the agent
              <textarea
                aria-label="Note for the agent"
                value={note}
                onChange={(e) => setNote(e.target.value)}
                maxLength={5000}
              />
            </label>
            <p>
              This records your intent. It marks earlier check results stale and
              does not change application code.
            </p>
            <div>
              <button
                className="primary"
                disabled={disabled || !description.trim()}
              >
                Save change request
              </button>
              <button type="button" onClick={() => setEditing(false)}>
                Cancel
              </button>
            </div>
          </form>
        )}
        {tab === "intent" && !editing && (
          <>
            <p className="rule-description">{rule.description}</p>
            {rule.rationale && <p>{rule.rationale}</p>}
            <h4>Where this rule applies</h4>
            <div className="rule-pages">
              {rule.screen_ids.map((id) => (
                <button key={id} onClick={() => onScreen(id)}>
                  {
                    session.investigation.screens.find((s) => s.id === id)
                      ?.title
                  }
                  <ArrowUpRight size={12} />
                </button>
              ))}
            </div>
            <p className="rule-impact">
              Changing this rule affects {rule.screen_ids.length} page
              {rule.screen_ids.length === 1 ? "" : "s"}, {sources.length} code
              reference{sources.length === 1 ? "" : "s"}, and {checks.length}{" "}
              check{checks.length === 1 ? "" : "s"}.
            </p>
            <div className="rule-coverage">
              <button onClick={() => setTab("code")}>
                <Code2 size={15} />
                {sources.length
                  ? `Inspect ${sources.length} source links`
                  : "No implementation linked"}
                <ArrowUpRight size={13} />
              </button>
              <button onClick={() => setTab("checks")}>
                <ClipboardCheck size={15} />
                {checks.length
                  ? `${checks.filter((c) => c.status === "passed").length} passed · ${checks.filter((c) => c.status === "stale").length} stale · ${checks.filter((c) => c.status === "failed").length} failed`
                  : "No verification supplied"}
                <ArrowUpRight size={13} />
              </button>
            </div>
            {rule.evidence_ids.length > 0 && (
              <p className="trace-citations">
                Rule evidence: {rule.evidence_ids.join(", ")}
              </p>
            )}
            {rule.reviewer_note && !editing && (
              <p className="rule-review-note">
                Your note: {rule.reviewer_note}
              </p>
            )}
            <div className="rule-actions">
              <button
                disabled={disabled || rule.review === "confirmed"}
                onClick={() => void save("confirmed")}
              >
                <Check size={14} />
                Accept rule
              </button>
            </div>
            {rule.review === "disputed" && (
              <button
                className="copy-rule-change"
                onClick={async () => {
                  try {
                    await navigator.clipboard.writeText(changeRequest);
                    setCopied(true);
                    setCopyBlocked(false);
                  } catch {
                    setCopied(false);
                    setCopyBlocked(true);
                  }
                }}
              >
                {copied
                  ? "Change request copied"
                  : "Copy change request for agent"}
              </button>
            )}
            {copyBlocked && (
              <div className="copy-fallback">
                <p role="status">
                  Clipboard access is blocked. Select the change request below
                  and copy it manually.
                </p>
                <textarea
                  aria-label="Change request text"
                  readOnly
                  value={changeRequest}
                  onFocus={(event) => event.currentTarget.select()}
                />
              </div>
            )}
          </>
        )}
        {tab === "code" && (
          <>
            {sources.map((source) => (
              <Source key={source.id} source={source} />
            ))}
            {!sources.length && (
              <p className="trace-empty">
                No code is linked to this rule. Ask the agent to locate its
                implementation; a screenshot alone cannot establish enforcement.
              </p>
            )}
          </>
        )}
        {tab === "checks" && (
          <>
            {checks.map((check) => (
              <CheckResult key={check.id} check={check} />
            ))}
            {!checks.length && (
              <p className="trace-empty">
                This rule has no recorded checks. Its implementation is
                unverified.
              </p>
            )}
          </>
        )}
      </div>
    </div>
  );
}

export default function BuildMapPanel({
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
  const build = session.investigation.build_map!;
  const [selected, setSelected] = useState(
    build.rules.find((r) => r.screen_ids.includes(screenId))?.id ?? "",
  );
  const [all, setAll] = useState(false);
  const [search, setSearch] = useState("");
  const visible = build.rules.filter(
    (r) =>
      (all || r.screen_ids.includes(screenId)) &&
      `${r.title} ${r.description}`
        .toLowerCase()
        .includes(search.toLowerCase()),
  );
  const rule = visible.find((r) => r.id === selected) ?? visible[0];
  const disabled =
    busy ||
    session.state === "running" ||
    session.investigation.status !== "pending_approval";
  return (
    <section
      className="build-map-panel"
      aria-label="Page rules and implementation"
    >
      <div className="build-map-heading">
        <div>
          <h2>
            <BookOpen size={16} />
            Rules & implementation
          </h2>
          <p>Page intent, linked code, and evidence of checks</p>
        </div>
        <button
          disabled={disabled}
          onClick={() =>
            void action("build/refresh", { revision: session.revision })
          }
          title="Recheck linked local files without running code"
        >
          <RefreshCw size={13} />
          Refresh source
        </button>
      </div>
      <div className="build-map-body">
        <aside className="rule-navigation" aria-label="Application rules">
          <div className="rule-list-tools">
            <button aria-pressed={all} onClick={() => setAll(!all)}>
              {all ? "All pages" : "This page"}
            </button>
            <input
              aria-label="Search rules"
              type="search"
              placeholder="Find a rule…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <div className="rule-list">
            {visible.map((r) => {
              const checks = build.checks.filter((c) =>
                c.rule_ids.includes(r.id),
              );
              return (
                <button
                  key={r.id}
                  className={`rule-choice ${rule?.id === r.id ? "active" : ""}`}
                  aria-pressed={rule?.id === r.id}
                  onClick={() => setSelected(r.id)}
                >
                  <strong>{r.title}</strong>
                  <span>
                    {r.origin} ·{" "}
                    {checks.length
                      ? `${checks.filter((c) => c.status === "passed").length}/${checks.length} reported passing`
                      : "No checks"}
                  </span>
                  {checks.some((c) => c.status === "stale") && (
                    <span className="stale-label">Checks need rerunning</span>
                  )}
                  {r.review === "disputed" && (
                    <span className="stale-label">Change requested</span>
                  )}
                </button>
              );
            })}
          </div>
        </aside>
        {rule ? (
          <RuleDetail
            key={rule.id}
            rule={rule}
            session={session}
            disabled={disabled}
            onScreen={onScreen}
            action={action}
          />
        ) : (
          <div className="trace-empty">
            <h3>
              {search ? "No matching rules" : "No rules linked to this page"}
            </h3>
            <p>
              {search
                ? "Try another search or show all pages."
                : "Ask the agent to map the page’s intended behavior and its implementation. Beakdown will not invent requirements from screenshots."}
            </p>
          </div>
        )}
      </div>
    </section>
  );
}
