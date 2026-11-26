"""Executable analysis grounded in typed investigation data, never generated SQL values."""

import pyarrow as pa

from .investigation import AnalysisLink
from .models import PipelineSpec


def evidence_tables(document):
    findings_schema = pa.schema(
        [
            ("id", pa.string()),
            ("screen_id", pa.string()),
            ("title", pa.string()),
            ("category", pa.string()),
            ("confidence", pa.string()),
            ("review", pa.string()),
            ("evidence_count", pa.int64()),
            ("reviewer_note", pa.string()),
        ]
    )
    screens_schema = pa.schema(
        [
            ("screen_id", pa.string()),
            ("title", pa.string()),
            ("url", pa.string()),
            ("width", pa.int64()),
            ("height", pa.int64()),
            ("evidence_id", pa.string()),
        ]
    )
    connections_schema = pa.schema(
        [
            ("source", pa.string()),
            ("target", pa.string()),
            ("label", pa.string()),
            ("confidence", pa.string()),
        ]
    )
    return {
        "audit_findings": pa.Table.from_pylist(
            [
                {
                    "id": f.id,
                    "screen_id": f.screen_id,
                    "title": f.title,
                    "category": f.category,
                    "confidence": f.confidence,
                    "review": f.review,
                    "evidence_count": len(f.evidence_ids),
                    "reviewer_note": f.reviewer_note,
                }
                for f in document.findings
            ],
            schema=findings_schema,
        ),
        "audit_screens": pa.Table.from_pylist(
            [
                {
                    "screen_id": s.id,
                    "title": s.title,
                    "url": s.url,
                    "width": s.width,
                    "height": s.height,
                    "evidence_id": s.evidence.evidence_id,
                }
                for s in document.screens
            ],
            schema=screens_schema,
        ),
        "audit_connections": pa.Table.from_pylist(
            [
                {
                    "source": c.source,
                    "target": c.target,
                    "label": c.label,
                    "confidence": c.confidence,
                }
                for c in document.connections
            ],
            schema=connections_schema,
        ),
    }


def default_analysis(document):
    pipeline = PipelineSpec(
        pipeline_id=document.investigation_id + "_analysis",
        title="Evidence analysis",
        description="Read-only SQL over the actual captured report. Reviews update the source tables.",
        nodes=[
            {
                "id": "findings",
                "title": "Captured findings",
                "operation_type": "load",
                "sql_or_expr": "SELECT * FROM audit_findings ORDER BY screen_id, id",
            },
            {
                "id": "screen_summary",
                "title": "Findings by screen",
                "operation_type": "sql_query",
                "sql_or_expr": "SELECT s.screen_id, s.title AS screen, count(f.id) AS findings, count(f.id) FILTER (WHERE f.confidence = 'observed') AS observed, count(f.id) FILTER (WHERE f.confidence = 'inferred') AS inferred, count(f.id) FILTER (WHERE f.confidence = 'unknown') AS unknown, count(f.id) FILTER (WHERE f.review = 'disputed') AS disputed FROM audit_screens s LEFT JOIN findings f ON s.screen_id = f.screen_id GROUP BY s.screen_id, s.title ORDER BY s.screen_id",
            },
            {
                "id": "review_queue",
                "title": "Needs human review",
                "operation_type": "filter",
                "sql_or_expr": "confidence <> 'observed' OR review = 'disputed'",
            },
        ],
        edges=[
            {"source": "findings", "target": "screen_summary"},
            {"source": "findings", "target": "review_queue"},
        ],
    )
    links = []
    for screen in document.screens:
        ids = [f.id for f in document.findings if f.screen_id == screen.id]
        links.extend(
            [
                AnalysisLink(screen_id=screen.id, node_id="findings", finding_ids=ids),
                AnalysisLink(
                    screen_id=screen.id, node_id="screen_summary", finding_ids=ids
                ),
                AnalysisLink(
                    screen_id=screen.id, node_id="review_queue", finding_ids=ids
                ),
            ]
        )
    return pipeline, links
