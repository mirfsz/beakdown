import json
import pyarrow as pa
from .models import ColumnSchema, NodePreview

MAX_BYTES = 100_000


def extract(connection, name, elapsed):
    quoted = '"' + name.replace('"', '""') + '"'
    columns = connection.execute(f"DESCRIBE SELECT * FROM {quoted}").fetchall()
    total = connection.execute(f"SELECT count(*) FROM {quoted}").fetchone()[0]
    schemas = []
    for col, dtype, *_ in columns:
        key = '"' + col.replace('"', '""') + '"'
        count = connection.execute(
            f"SELECT count(*) - count({key}) FROM {quoted}"
        ).fetchone()[0]
        schemas.append(ColumnSchema(name=col, data_type=dtype, null_count=count))
    table = connection.execute(f"SELECT * FROM {quoted} LIMIT 50").to_arrow_table()
    # JSON normalizes dates, decimals and bytes for the REST preview.
    rows = json.loads(json.dumps(table.to_pylist(), default=str))
    preview = NodePreview(
        total_rows=total,
        column_count=len(schemas),
        columns=schemas,
        sample_data=rows,
        execution_time_ms=elapsed,
    )
    while True:
        sample = (
            pa.Table.from_pylist(preview.sample_data)
            if preview.sample_data
            else table.slice(0, 0)
        )
        sink = pa.BufferOutputStream()
        with pa.ipc.new_stream(sink, sample.schema) as writer:
            writer.write_table(sample)
        data = sink.getvalue().to_pybytes()
        if len(data) + len(preview.model_dump_json().encode()) < MAX_BYTES:
            return preview, data
        if not preview.sample_data:
            raise ValueError("Node schema exceeds 100 KB preview budget")
        preview.sample_data.pop()
