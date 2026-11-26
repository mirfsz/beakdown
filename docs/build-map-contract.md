# Page → rule → implementation → check

Add `build_map` and optionally `project_root` to `create_investigation_session` or the review CLI manifest. Screens still use the existing screenshot/REA contract. A build map opens alongside screenshots by default; the data-analysis view remains available.

```json
{
  "title": "Event app build review",
  "target": "Local event app",
  "project_root": "/absolute/path/to/event-app",
  "screens": [
    {"id":"registration","title":"Registration","screenshot_path":"/absolute/path/to/registration.png"},
    {"id":"confirmation","title":"Confirmation","screenshot_path":"/absolute/path/to/confirmation.png"}
  ],
  "build_map": {
    "rules": [
      {
        "id":"capacity",
        "title":"Respect event capacity",
        "description":"Stop accepting registrations at the configured event capacity.",
        "screen_ids":["registration","confirmation"],
        "origin":"requirement",
        "rationale":"Requirement supplied in the product specification.",
        "evidence_ids":["requirement-source-id"]
      }
    ],
    "implementation": [
      {
        "id":"capacity_handler",
        "title":"Registration capacity check",
        "path":"src/api/register.ts",
        "line_start":20,
        "line_end":45,
        "symbol":"registerAttendee",
        "layer":"api",
        "rule_ids":["capacity"],
        "screen_ids":["registration","confirmation"],
        "evidence_ids":["source-inspection-id"]
      }
    ],
    "checks": [
      {
        "id":"capacity_boundary",
        "title":"Registration rejects a full event",
        "rule_ids":["capacity"],
        "implementation_ids":["capacity_handler"],
        "status":"not_run",
        "method":"automated",
        "command":"pnpm test -- capacity",
        "detail":"No test result supplied yet."
      }
    ]
  }
}
```

These are schema examples, not evidence about an existing app. Replace every path, range, symbol, requirement and evidence ID with inspected facts. A code link is an agent-declared relationship, not proof of enforcement.

## Objects

| Object | Purpose | Important fields |
|---|---|---|
| Rule | Intent or behavior associated with pages | `screen_ids`, `origin` (`requirement`, `observed`, `inferred`), `description`, `rationale`, `evidence_ids` |
| Implementation | Declared source location associated with rules or pages | Repository-relative `path`, `line_start`, `line_end`, `symbol`, `layer` (`ui`, `api`, `data`, `test`, `config`), `rule_ids`, `screen_ids` |
| Check | Agent-reported verification of one or more rules | `rule_ids`, optional `implementation_ids`, `status`, `method`, `command`, `detail`, `evidence_ids`, `checked_at`, `source_hashes` |

IDs must be unique in each collection. All page/rule/source links must resolve. Limits: 200 rules, 300 implementation references, 300 checks, 50 pages. Each source range spans at most 100 lines and 12,000 characters; each source file must be UTF-8 text, at most 512 KB. Read source paths are relative to an explicitly granted absolute `project_root`. Traversal, escaped symlinks, hidden paths, credential files and common generated directories are rejected. Without a root, no source is read, and references are labeled `reference_only`.

Beakdown replaces caller-provided excerpts/hashes with actual source snapshots when reads are granted. It resets rule reviews and revisions on creation; agents cannot pre-accept a rule for the human. Absolute project roots stay server-side and are not included in report output.

## Check evidence and freshness

Statuses are `not_run`, `passed`, `failed`, `blocked`, `stale`. A pass or failure requires a concrete `detail`, nonempty `evidence_ids`, and an ISO `checked_at` timestamp with timezone. Outcomes remain agent-reported. Beakdown does not execute the recorded command, ingest raw test logs or independently establish that an evidence ID proves the claim; the agent retains complete original evidence.

For granted local source, bind each check to exact file digests:

```json
{
  "status":"passed",
  "detail":"The capacity boundary test rejected a registration with HTTP 409 when the event was full.",
  "evidence_ids":["actual-test-run-id"],
  "checked_at":"2026-11-26T12:00:00Z",
  "source_hashes":{"capacity_handler":"<actual 64-character lowercase SHA256>"}
}
```

The placeholder is not accepted as a digest. Hash files after the relevant checks and ensure they did not change during the run. Every captured source linked to a checked rule, plus explicitly linked implementation IDs, needs a matching digest. Missing or mismatched bindings make pass/fail results stale. Hash binding identifies the declared tested source version; it does not independently certify test coverage or execution.

## Human review and change requests

The UI follows page → applicable rules → source/checks and can navigate other pages sharing a rule. Its impact list uses the supplied links; it is not an exhaustive dependency analysis.

`POST /api/session/{id}/rules/{rule_id}/review` accepts the current session `revision`, optional `title`, `description`, `rationale`, `review` (`unreviewed`, `confirmed`, `disputed`) and `reviewer_note`. Changes to rule intent increment its own revision and stale previous pass/fail outcomes. Accepting unchanged intent does not stale checks. Requests do not edit application source or execute commands.

`refresh_build_evidence(session_id, token)` and the UI’s Refresh source action compare declared files with their original snapshots. Changed/unavailable files stale linked results. Earlier excerpts and hashes remain inspectable. Approval rechecks source and rejects the old session revision if it detects a change. Edits and refresh require a pending, non-computing report. Decided reports remain immutable.

Approval records assessment of the report, including known failures and stale/untested behavior; it is not an app release certification. After a change request, the agent reads `get_session_result`, implements the authorized app change, reruns checks and creates a fresh session with current captures and evidence. No automatic code-change or test-execution service is provided.

## Export and analysis

Report JSON preserves the complete build map, reviews, source snapshots, source/check hash bindings and stale reasons. Markdown includes readable rules, source excerpts and outcomes. Original test logs remain in the agent’s evidence store; exports include their identifiers and reported summaries.

The existing read-only SQL engine also exposes `audit_rules` (one row per rule/page), `audit_implementation` and `audit_checks` (one row per check/rule). Human changes recompute attached analysis. These input names are reserved against node-name collisions. Screenshots, SQL preview bounds, authentication and session expiry retain their existing contracts.
