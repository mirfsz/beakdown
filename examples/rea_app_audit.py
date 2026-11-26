"""Agent-mediated REA findings, using illustrative evidence rather than live capture."""

import json
from beakdown_mcp.tools import create_handoff_session

if __name__ == "__main__":
    result = create_handoff_session(
        title="Application behavior audit · REA companion",
        description="Illustrative observations; replace source references with real REA evidence.",
        nodes=[
            {
                "id": "observations",
                "title": "Observed application requests",
                "operation_type": "evidence",
                "sql_or_expr": "SELECT * FROM (VALUES ('login', '/api/session', 200, 'observed'), ('export', '/api/export', 403, 'observed')) t(feature, endpoint, status, confidence)",
                "evidence": [
                    {
                        "source": "example://rea/network-capture",
                        "summary": "Illustrative network records, not a real capture.",
                        "confidence": "example",
                    }
                ],
            },
            {
                "id": "restricted",
                "title": "Inspect access restrictions",
                "operation_type": "filter",
                "sql_or_expr": "status = 403",
                "evidence": [
                    {
                        "source": "example://rea/network-capture",
                        "summary": "403 suggests a restriction; it does not establish the authorization implementation.",
                        "confidence": "inference",
                    }
                ],
            },
        ],
        edges=[{"source": "observations", "target": "restricted"}],
    )
    print(json.dumps(result, indent=2))
    input("Press Enter to end the inspection session. ")
