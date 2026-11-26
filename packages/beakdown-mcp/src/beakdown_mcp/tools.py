import uuid
from beakdown_core.models import PipelineSpec
from beakdown_core.daemon import SessionManager

_manager = None


def manager():
    global _manager
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
    """Return approval and exact reviewed pipeline. Approval never executes production changes."""
    service = manager()
    return service.result(service.authorize(session_id, token))
