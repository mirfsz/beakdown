"""Page → intent → source → check traceability, with bounded source snapshots.

Links and check outcomes are supplied by the investigating agent. Snapshotting
establishes what source was inspected; it does not prove that it enforces a rule.
No application code or test command is executed by this module.
"""

import hashlib
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator

Identifier = Annotated[str, Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")]
Digest = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]


class AppRule(BaseModel):
    id: Identifier
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=5000)
    screen_ids: list[str] = Field(min_length=1, max_length=50)
    origin: Literal["requirement", "observed", "inferred"] = "requirement"
    rationale: str = Field(default="", max_length=3000)
    evidence_ids: list[str] = Field(default_factory=list, max_length=50)
    revision: int = Field(default=1, ge=1)
    review: Literal["unreviewed", "confirmed", "disputed"] = "unreviewed"
    reviewer_note: str = Field(default="", max_length=5000)


class ImplementationRef(BaseModel):
    id: Identifier
    title: str = Field(min_length=1, max_length=200)
    path: str = Field(min_length=1, max_length=500)
    line_start: int = Field(default=1, ge=1)
    line_end: int = Field(default=1, ge=1)
    symbol: str = Field(default="", max_length=200)
    layer: Literal["ui", "api", "data", "test", "config"] = "ui"
    rule_ids: list[str] = Field(default_factory=list, max_length=200)
    screen_ids: list[str] = Field(default_factory=list, max_length=50)
    evidence_ids: list[str] = Field(default_factory=list, max_length=50)
    excerpt: str = Field(default="", max_length=12000)
    source_sha256: str = ""
    snapshot_status: Literal["captured", "reference_only", "changed", "unavailable"] = (
        "reference_only"
    )

    @model_validator(mode="after")
    def safe_path(self):
        path = PurePosixPath(self.path)
        if (
            path.is_absolute()
            or ".." in path.parts
            or "\\" in self.path
            or ":" in self.path
        ):
            raise ValueError(
                "Source paths must be repository-relative without traversal"
            )
        if self.line_end < self.line_start or self.line_end - self.line_start >= 100:
            raise ValueError("Source references must span 1–100 lines")
        if not self.rule_ids and not self.screen_ids:
            raise ValueError("Implementation references need a page or rule link")
        return self


class VerificationCheck(BaseModel):
    id: Identifier
    title: str = Field(min_length=1, max_length=200)
    rule_ids: list[str] = Field(min_length=1, max_length=200)
    implementation_ids: list[str] = Field(default_factory=list, max_length=300)
    status: Literal["not_run", "passed", "failed", "blocked", "stale"] = "not_run"
    method: Literal["automated", "manual"] = "automated"
    command: str = Field(default="", max_length=2000)
    detail: str = Field(default="", max_length=5000)
    evidence_ids: list[str] = Field(default_factory=list, max_length=50)
    checked_at: str = Field(default="", max_length=100)
    rule_revisions: dict[str, int] = Field(default_factory=dict, max_length=200)
    source_hashes: dict[str, Digest] = Field(default_factory=dict, max_length=300)
    stale_reason: str = Field(default="", max_length=1000)

    @model_validator(mode="after")
    def outcome_needs_evidence(self):
        if self.checked_at:
            try:
                parsed = datetime.fromisoformat(self.checked_at)
                if parsed.tzinfo is None:
                    raise ValueError("A timezone is required")
            except ValueError as exc:
                raise ValueError(
                    "checked_at must be an ISO timestamp with timezone"
                ) from exc
        if self.status in ("passed", "failed") and (
            not self.evidence_ids or not self.detail.strip() or not self.checked_at
        ):
            raise ValueError(
                "Reported pass/fail needs evidence IDs, a result detail and checked_at"
            )
        return self


class BuildMap(BaseModel):
    rules: list[AppRule] = Field(default_factory=list, max_length=200)
    implementation: list[ImplementationRef] = Field(
        default_factory=list, max_length=300
    )
    checks: list[VerificationCheck] = Field(default_factory=list, max_length=300)

    @model_validator(mode="after")
    def references(self):
        for values in (self.rules, self.implementation, self.checks):
            if len({item.id for item in values}) != len(values):
                raise ValueError("Build map IDs must be unique within each collection")
        rules = {r.id for r in self.rules}
        refs = {r.id for r in self.implementation}
        if any(set(r.rule_ids) - rules for r in self.implementation) or any(
            set(c.rule_ids) - rules or set(c.implementation_ids) - refs
            for c in self.checks
        ):
            raise ValueError(
                "Build map links must reference existing rules and implementation"
            )
        return self


def snapshot_reference(ref, project_root):
    """Only inspect declared relative files within an explicitly granted root."""
    root = Path(project_root).resolve()
    path = (root / ref.path).resolve()
    if not path.is_relative_to(root):
        raise ValueError("Source reference escapes the granted project root")
    # Avoid accidental credentials/vendor imports even when they are linked by an agent.
    if any(
        part.startswith(".") or part in {"node_modules", "dist", "venv", "__pycache__"}
        for part in (*Path(ref.path).parts, *path.relative_to(root).parts)
    ) or path.suffix.lower() in {".pem", ".key", ".p12", ".pfx"}:
        raise ValueError(
            "Hidden, generated and credential files cannot be source references"
        )
    if not path.is_file():
        raise ValueError("Source reference must be a regular file")
    with path.open("rb") as stream:
        data = stream.read(512_001)
    if len(data) > 512_000 or b"\x00" in data:
        raise ValueError("Source files must be text and at most 512 KB")
    lines = data.decode("utf-8").splitlines()
    if ref.line_end > len(lines):
        raise ValueError("Source line range is outside the file")
    excerpt = "\n".join(lines[ref.line_start - 1 : ref.line_end])
    if len(excerpt) > 12000:
        raise ValueError("Source excerpt exceeds 12,000 characters")
    return hashlib.sha256(data).hexdigest(), excerpt


def stage_build_map(payload, project_root):
    build = BuildMap.model_validate(payload)
    for rule in build.rules:
        rule.review, rule.reviewer_note, rule.revision = "unreviewed", "", 1
    for ref in build.implementation:
        ref.excerpt, ref.source_sha256, ref.snapshot_status = "", "", "reference_only"
        if project_root:
            ref.source_sha256, ref.excerpt = snapshot_reference(ref, project_root)
            ref.snapshot_status = "captured"
    for check in build.checks:
        check.rule_revisions = {
            r.id: r.revision for r in build.rules if r.id in check.rule_ids
        }
        expected = {
            r.id: r.source_sha256
            for r in build.implementation
            if r.source_sha256
            and (
                r.id in check.implementation_ids
                or set(r.rule_ids) & set(check.rule_ids)
            )
        }
        if check.status in ("passed", "failed") and any(
            check.source_hashes.get(key) != value for key, value in expected.items()
        ):
            check.status = "stale"
            check.stale_reason = "Check evidence is not bound to the current linked source hashes; test and capture again."
    return build


def invalidate_checks(build, rule_ids, reason):
    for check in build.checks:
        if set(check.rule_ids) & set(rule_ids) and check.status in (
            "passed",
            "failed",
            "stale",
        ):
            check.status, check.stale_reason = "stale", reason


def refresh_sources(build, project_root):
    """Keep the inspected snapshot immutable; flag differences for re-investigation."""
    changed = False
    if not project_root:
        return False
    for ref in build.implementation:
        try:
            digest, _ = snapshot_reference(ref, project_root)
            status = "captured" if digest == ref.source_sha256 else "changed"
        except (OSError, ValueError, UnicodeError):
            status = "unavailable"
        if status != ref.snapshot_status:
            ref.snapshot_status = status
            changed = True
        if status != "captured":
            affected = set(ref.rule_ids)
            affected.update(
                r
                for c in build.checks
                if ref.id in c.implementation_ids
                for r in c.rule_ids
            )
            invalidate_checks(
                build,
                affected,
                f"Linked source {ref.path} changed or is unavailable; capture and test again.",
            )
    return changed
