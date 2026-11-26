import threading
import uuid

from beakdown_core.daemon import SessionManager
from beakdown_core.models import PipelineSpec

_manager = None
_manager_lock = threading.Lock()


def manager():
    global _manager
    with _manager_lock:
        if _manager is None:
            _manager = SessionManager()
    return _manager


def create_handoff_session(
    title: str,
    nodes: list[dict],
    edges: list[dict],
    description: str = "",
    allowed_paths: list[str] | None = None,
) -> dict:
    """Stage read-only SQL for human inspection. Evidence nodes may include REA source references.

    SQL references upstream tables by node ID. Filters accept SQL predicates.
    allowed_paths explicitly grants local file read access. No production writes occur.
    """
    pipeline = PipelineSpec(
        pipeline_id="sess_" + uuid.uuid4().hex,
        title=title,
        description=description,
        nodes=nodes,
        edges=edges,
    )
    for node in pipeline.nodes:
        node.preview = None
    result = manager().create(pipeline, allowed_paths or [])
    result["message"] = (
        f"Inspect and approve: {result['url']} . Return here after approval, then call get_session_result."
    )
    return result


def get_session_result(session_id: str, token: str) -> dict:
    """Return a pipeline or investigation, its approval, reviewer corrections and limitations."""
    service = manager()
    return service.result(service.authorize(session_id, token))


def create_investigation_session(
    title: str,
    target: str,
    screens: list[dict],
    findings: list[dict] | None = None,
    connections: list[dict] | None = None,
    summary: str = "",
    limitations: list[str] | None = None,
    analysis_pipeline: dict | None = None,
    analysis_links: list[dict] | None = None,
    include_analysis: bool = True,
) -> dict:
    """Present an application/website investigation as a screenshot evidence canvas.

    Capture first with REA. Each screen needs id/title and exactly one absolute
    screenshot_path (PNG/JPEG/WebP) or rea_evidence_path (complete REA JSON).
    capture_index selects a captured screenshot within REA scenarios (default last).
    Evidence IDs, provenance and coverage limitations from REA are preserved.
    Findings have id, screen_id, title, detail, confidence (observed/inferred/unknown),
    optional category, evidence_ids and region {x,y,width,height} normalized to 0..1.
    Connections have source/target/label/confidence/evidence_ids. No remote fetching,
    app control or HTML execution occurs here; the Beakdown skill orchestrates REA.
    Analysis is included by default: executable SQL over audit_findings, audit_screens
    and audit_connections, built from this report. Supply analysis_pipeline and
    analysis_links to customize it, or include_analysis=false for evidence only.
    """
    from beakdown_core.investigation import AnalysisLink, Investigation, load_screens

    if not 1 <= len(screens) <= 50:
        raise ValueError("An investigation requires 1–50 screens")
    loaded, assets = load_screens(screens)
    # Agent input cannot pre-confirm findings or pre-approve a report.
    cleaned = [
        {**f, "review": "unreviewed", "reviewer_note": ""} for f in findings or []
    ]
    investigation = Investigation(
        investigation_id="inv_" + uuid.uuid4().hex,
        title=title,
        target=target,
        summary=summary,
        screens=loaded,
        findings=cleaned,
        connections=connections or [],
        limitations=limitations or [],
    )
    if include_analysis:
        from beakdown_core.analysis import default_analysis
        from beakdown_core.models import PipelineSpec

        if analysis_pipeline is not None:
            pipeline = PipelineSpec.model_validate(
                {
                    **analysis_pipeline,
                    "pipeline_id": investigation.investigation_id + "_analysis",
                    "status": "pending_approval",
                }
            )
            for node in pipeline.nodes:
                node.preview = None
            investigation.analysis = pipeline
            investigation.analysis_links = [
                AnalysisLink.model_validate(link) for link in analysis_links or []
            ]
        else:
            investigation.analysis, investigation.analysis_links = default_analysis(
                investigation
            )
        investigation = Investigation.model_validate(investigation.model_dump())
    result = manager().create_investigation(investigation, assets)
    result["message"] = (
        f"Inspect the screenshot canvas: {result['url']} . Review findings, export the report, and return here when ready."
    )
    return result
