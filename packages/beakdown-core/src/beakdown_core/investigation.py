"""Screenshot evidence contracts and bounded, inert image ingestion."""

import base64
import hashlib
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from PIL import Image
from pydantic import BaseModel, Field, model_validator

from .models import PipelineSpec

MAX_IMAGE_BYTES = 8_000_000
MAX_SESSION_BYTES = 32_000_000
MAX_RECORD_BYTES = 24_000_000
Image.MAX_IMAGE_PIXELS = 20_000_000
Identifier = str


class Region(BaseModel):
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    width: float = Field(gt=0, le=1)
    height: float = Field(gt=0, le=1)

    @model_validator(mode="after")
    def bounds(self):
        if self.x + self.width > 1.000001 or self.y + self.height > 1.000001:
            raise ValueError("Annotation must fit inside the screenshot")
        return self


class EvidenceSource(BaseModel):
    evidence_id: str = Field(max_length=200)
    operation: str = Field(default="manual_capture", max_length=200)
    provider: str = Field(default="agent", max_length=200)
    confidence: Literal["observed", "derived", "inferred"] = "observed"
    limitations: list[str] = Field(default_factory=list, max_length=50)


class Screen(BaseModel):
    id: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
    title: str = Field(min_length=1, max_length=200)
    url: str = Field(default="", max_length=2000)
    description: str = Field(default="", max_length=5000)
    image_id: str
    width: int
    height: int
    captured_at: str
    source_sha256: str
    evidence: EvidenceSource


class Finding(BaseModel):
    id: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
    screen_id: str
    title: str = Field(min_length=1, max_length=200)
    detail: str = Field(min_length=1, max_length=10000)
    confidence: Literal["observed", "inferred", "unknown"]
    category: Literal[
        "interface", "behavior", "data", "architecture", "accessibility"
    ] = "interface"
    evidence_ids: list[str] = Field(default_factory=list, max_length=50)
    region: Region | None = None
    review: Literal["unreviewed", "confirmed", "disputed"] = "unreviewed"
    reviewer_note: str = Field(default="", max_length=5000)


class Connection(BaseModel):
    source: str
    target: str
    label: str = Field(default="Next screen", max_length=200)
    confidence: Literal["observed", "inferred"] = "observed"
    evidence_ids: list[str] = Field(default_factory=list, max_length=50)


class AnalysisLink(BaseModel):
    screen_id: str
    node_id: str
    finding_ids: list[str] = Field(default_factory=list, max_length=300)


class Investigation(BaseModel):
    investigation_id: str
    title: str = Field(min_length=1, max_length=200)
    target: str = Field(max_length=2000)
    summary: str = Field(default="", max_length=20000)
    screens: list[Screen] = Field(min_length=1, max_length=50)
    findings: list[Finding] = Field(default_factory=list, max_length=300)
    connections: list[Connection] = Field(default_factory=list, max_length=200)
    limitations: list[str] = Field(default_factory=list, max_length=100)
    status: Literal["pending_approval", "approved", "rejected"] = "pending_approval"

    analysis: PipelineSpec | None = None
    analysis_links: list[AnalysisLink] = Field(default_factory=list, max_length=500)

    @model_validator(mode="after")
    def references(self):
        ids = {screen.id for screen in self.screens}
        if len(ids) != len(self.screens) or len({f.id for f in self.findings}) != len(
            self.findings
        ):
            raise ValueError("Screen and finding IDs must be unique")
        if any(f.screen_id not in ids for f in self.findings):
            raise ValueError("Finding references an unknown screen")
        if any(c.source not in ids or c.target not in ids for c in self.connections):
            raise ValueError("Connection references an unknown screen")
        node_ids = {n.id for n in self.analysis.nodes} if self.analysis else set()
        finding_screens = {f.id: f.screen_id for f in self.findings}
        if any(
            link.screen_id not in ids
            or link.node_id not in node_ids
            or any(finding_screens.get(f) != link.screen_id for f in link.finding_ids)
            for link in self.analysis_links
        ):
            raise ValueError(
                "Analysis links must reference existing screens, nodes and findings"
            )
        if self.analysis and any(
            n.id in {"audit_findings", "audit_screens", "audit_connections"}
            for n in self.analysis.nodes
        ):
            raise ValueError("Pipeline node IDs cannot shadow the audit input tables")
        return self


def read_json(path):
    file = Path(path).expanduser()
    if not file.is_absolute():
        raise ValueError("Evidence paths must be absolute")
    with file.open("rb") as stream:
        content = stream.read(MAX_RECORD_BYTES + 1)
    if len(content) > MAX_RECORD_BYTES:
        raise ValueError("Evidence file exceeds 24 MB")
    return json.loads(content)


def unwrap_record(record, evidence_id=None):
    # Accept a raw Evidence record, MCP structuredContent, or a text envelope.
    if "structuredContent" in record:
        record = record["structuredContent"]
    elif "content" in record:
        blocks = [c["text"] for c in record["content"] if c.get("type") == "text"]
        if len(blocks) != 1:
            raise ValueError("Expected one complete JSON Evidence record")
        record = json.loads(blocks[0])
    if "result" in record and isinstance(record["result"], dict):
        record = record["result"]
    if "records" in record:
        matches = [
            r
            for r in record["records"]
            if evidence_id is None or r.get("evidence_id") == evidence_id
        ]
        if len(matches) != 1:
            raise ValueError("Select exactly one REA record with rea_evidence_id")
        record = matches[0]
    if evidence_id and record.get("evidence_id") != evidence_id:
        raise ValueError("REA evidence ID not found in record")
    if "normalized_result" not in record or "evidence_id" not in record:
        raise ValueError("Expected a complete REA Evidence record, not a summary")
    return record


def rea_images(record, evidence_id=None):
    """Return supported REA screenshots without interpreting target HTML or scripts."""
    record = unwrap_record(record, evidence_id)
    result = record["normalized_result"]
    operation = record.get("operation")
    captures = []
    if operation == "capture_web_screenshot":
        captures.append(
            (
                "viewport",
                result["artifact"],
                result.get("target", {}).get("url", ""),
                result.get("captured_at"),
            )
        )
    elif operation in ("capture_browser_scenario", "capture_electron_scenario"):
        for step in result.get("steps", []):
            artifact = step.get("artifacts", {}).get("screenshot", {})
            if artifact.get("state") == "captured":
                url = step.get("after_url") or {}
                captures.append(
                    (
                        str(step.get("step_id", step.get("step_index"))),
                        artifact["value"],
                        url.get("url", ""),
                        None,
                    )
                )
    elif operation == "capture_native_ui_scenario":
        states = [("initial", result.get("initial"))]
        states.extend(
            (str(s.get("index")), s.get("after")) for s in result.get("steps", [])
        )
        for name, state in states:
            if state and state.get("screenshot"):
                captures.append((name, state["screenshot"], "", None))
    else:
        raise ValueError(f"Unsupported REA screenshot operation: {operation}")
    if not captures:
        raise ValueError(
            "REA returned no captured screenshots; request screenshot artifacts"
        )
    return record, captures


def normalize_image(data):
    if len(data) > MAX_IMAGE_BYTES:
        raise ValueError("Screenshot exceeds 8 MB")
    with Image.open(io.BytesIO(data)) as image:
        if image.format not in ("PNG", "JPEG", "WEBP"):
            raise ValueError("Only PNG, JPEG, and WebP screenshots are supported")
        if image.width * image.height > 20_000_000:
            raise ValueError("Screenshot exceeds 20 megapixels")
        image.load()
        width, height = image.size
        output = io.BytesIO()
        image.convert("RGB").save(output, format="WEBP", quality=88)
    payload = output.getvalue()
    if len(payload) > MAX_IMAGE_BYTES:
        raise ValueError("Normalized screenshot exceeds 8 MB")
    return hashlib.sha256(payload).hexdigest(), payload, width, height


def load_screens(specs):
    screens, assets = [], {}
    for spec in specs:
        spec = dict(spec)
        evidence_path = spec.pop("rea_evidence_path", None)
        screenshot_path = spec.pop("screenshot_path", None)
        index = spec.pop("capture_index", -1)
        evidence_id = spec.pop("rea_evidence_id", None)
        if bool(evidence_path) == bool(screenshot_path):
            raise ValueError(
                "Each screen needs exactly one screenshot_path or rea_evidence_path"
            )
        if evidence_path:
            record, captures = rea_images(read_json(evidence_path), evidence_id)
            try:
                _, artifact, url, captured_at = captures[index]
            except (IndexError, TypeError):
                raise ValueError(
                    "capture_index is outside the available screenshots"
                ) from None
            encoded = artifact.get("data_base64", artifact.get("base64", ""))
            if len(encoded) > MAX_IMAGE_BYTES * 4 // 3 + 4:
                raise ValueError("Screenshot exceeds 8 MB")
            data = base64.b64decode(encoded, validate=True)
            digest = hashlib.sha256(data).hexdigest()
            if artifact.get("sha256") != digest:
                raise ValueError("REA screenshot digest mismatch")
            spec.setdefault("url", url)
            spec["evidence"] = EvidenceSource(
                evidence_id=record["evidence_id"],
                operation=record["operation"],
                provider=(record.get("provider") or {}).get("name", "REA"),
                confidence=record.get("confidence", "observed"),
                limitations=[
                    str(v)[:2000]
                    for v in [
                        *record.get("limitations", []),
                        *record["normalized_result"].get("limitations", []),
                    ]
                ][:50],
            )
            completeness = record["normalized_result"].get("completeness", {})
            if completeness.get("status") not in (
                None,
                "complete",
                "complete_within_window",
            ):
                spec["evidence"].limitations.append(
                    f"REA capture coverage: {completeness['status']}"
                )
            spec.setdefault(
                "captured_at", captured_at or datetime.now(timezone.utc).isoformat()
            )
        else:
            file = Path(screenshot_path).expanduser()
            if not file.is_absolute():
                raise ValueError("Screenshot paths must be absolute")
            with file.open("rb") as stream:
                data = stream.read(MAX_IMAGE_BYTES + 1)
            digest = hashlib.sha256(data).hexdigest()
            spec.setdefault("captured_at", datetime.now(timezone.utc).isoformat())
            spec.setdefault(
                "evidence",
                {
                    "evidence_id": "image_" + digest,
                    "provider": "local screenshot",
                    "limitations": [
                        "File import time is not proof of original capture time."
                    ],
                },
            )
        image_id, payload, width, height = normalize_image(data)
        assets[image_id] = payload
        if sum(map(len, assets.values())) > MAX_SESSION_BYTES:
            raise ValueError("Screenshots exceed 32 MB session budget")
        screens.append(
            Screen(
                **spec,
                image_id=image_id,
                width=width,
                height=height,
                source_sha256=digest,
            )
        )
    return screens, assets
