from time import perf_counter
import duckdb
from .arrow_extractor import extract
from .models import PipelineSpec


def ordered_nodes(pipeline):
    done = set()
    remaining = list(pipeline.nodes)
    while remaining:
        ready = [
            n
            for n in remaining
            if all(e.source in done for e in pipeline.edges if e.target == n.id)
        ]
        if not ready:
            raise ValueError("Pipeline must be acyclic")
        for node in ready:
            yield node
            done.add(node.id)
            remaining.remove(node)


def run_pipeline(pipeline: PipelineSpec, allowed_paths=()):
    pipeline = pipeline.model_copy(deep=True)
    arrows = {}
    with duckdb.connect(
        config={
            "allow_unsigned_extensions": False,
            "autoinstall_known_extensions": False,
            "autoload_known_extensions": False,
            "memory_limit": "256MB",
            "threads": 2,
        }
    ) as db:
        db.execute("SET allowed_paths = ?", [list(allowed_paths)])
        db.execute("SET enable_external_access = false")
        db.execute("SET lock_configuration = true")
        for node in ordered_nodes(pipeline):
            start = perf_counter()
            query = node.sql_or_expr or "SELECT NULL AS empty WHERE false"
            parents = [e.source for e in pipeline.edges if e.target == node.id]
            if node.operation_type == "filter":
                if len(parents) != 1:
                    raise ValueError("Filters require exactly one input")
                query = f'SELECT * FROM "{parents[0]}" WHERE ({query})'
            statements = db.extract_statements(query)
            if (
                len(statements) != 1
                or statements[0].type != duckdb.StatementType.SELECT
            ):
                raise ValueError("Only one read-only SELECT is allowed per node")
            db.execute(f'CREATE TEMP TABLE "{node.id}" AS {query}')
            node.preview, arrows[node.id] = extract(
                db, node.id, (perf_counter() - start) * 1000
            )
    return pipeline, arrows
