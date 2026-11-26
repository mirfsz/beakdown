import pytest
from beakdown_core.models import PipelineSpec
from beakdown_core.runner import run_pipeline
from beakdown_core.arrow_extractor import MAX_BYTES


def pipeline(query="SELECT * FROM range(100) t(id)"):
    return PipelineSpec(
        pipeline_id="test",
        title="Test",
        nodes=[
            {
                "id": "source",
                "title": "Source",
                "operation_type": "load",
                "sql_or_expr": query,
            },
            {
                "id": "filtered",
                "title": "Filter",
                "operation_type": "filter",
                "sql_or_expr": "id > 90",
            },
        ],
        edges=[{"source": "source", "target": "filtered"}],
    )


def test_dag_and_bounds():
    result, arrows = run_pipeline(pipeline())
    assert result.nodes[0].preview.total_rows == 100
    assert len(result.nodes[0].preview.sample_data) == 50
    assert result.nodes[1].preview.total_rows == 9
    assert (
        len(arrows["source"]) + len(result.nodes[0].preview.model_dump_json().encode())
        < MAX_BYTES
    )


@pytest.mark.parametrize(
    "query",
    [
        "COPY (SELECT 1) TO '/tmp/beakdown-forbidden'",
        "SELECT 1; SELECT 2",
        "SELECT * FROM read_csv('/etc/passwd')",
        "SELECT * FROM read_csv('https://example.com/data.csv')",
        "INSTALL httpfs",
    ],
)
def test_unsafe_sql_denied(query):
    with pytest.raises(Exception):
        run_pipeline(pipeline(query))


def test_cycle_rejected():
    p = pipeline()
    p.edges.append(type(p.edges[0])(source="filtered", target="source"))
    with pytest.raises(ValueError, match="acyclic"):
        run_pipeline(p)


def test_large_cells_shrink():
    p = pipeline("SELECT range AS id, repeat('a', 120000) AS big FROM range(2)")
    result, _ = run_pipeline(p)
    assert result.nodes[0].preview.sample_data == []


def test_explicit_file_grant(tmp_path):
    data = tmp_path / "data.csv"
    data.write_text("id\n1\n2\n")
    query = f"SELECT * FROM read_csv('{data}')"
    with pytest.raises(Exception):
        run_pipeline(pipeline(query))
    result, _ = run_pipeline(pipeline(query), [str(data)])
    assert result.nodes[0].preview.total_rows == 2
