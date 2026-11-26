import type { Session } from "../types";
export default function ApproveBar({
  session,
  act,
  busy,
}: {
  session: Session;
  act: (s: string) => void;
  busy: boolean;
}) {
  const disabled =
    busy ||
    session.state !== "ready" ||
    session.pipeline.status !== "pending_approval";
  return (
    <footer>
      <div>
        <strong>{session.pipeline.status.replaceAll("_", " ")}</strong>
        <p>
          Approval records the reviewed plan. Your agent performs the final
          execution.
        </p>
      </div>
      {!session.approved && (
        <>
          <button disabled={disabled} onClick={() => act("reject")}>
            Reject
          </button>
          <button
            className="primary"
            disabled={disabled}
            onClick={() => act("approve")}
          >
            Approve & Commit
          </button>
        </>
      )}
      {session.approved && (
        <button
          onClick={() =>
            navigator.clipboard.writeText(
              `Beakdown session ${session.pipeline.pipeline_id} approved. Call get_session_result and use the exact approved pipeline.`,
            )
          }
        >
          Copy resumption prompt
        </button>
      )}
    </footer>
  );
}
