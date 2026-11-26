from typing import Any, Literal
from pydantic import BaseModel, Field, model_validator


class ColumnSchema(BaseModel):
    name: str
    data_type: str
    null_count: int = 0


class NodePreview(BaseModel):
    total_rows: int
    column_count: int
    columns: list[ColumnSchema]
    sample_data: list[dict[str, Any]]
    execution_time_ms: float


class FlowNode(BaseModel):
    id: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_]{0,63}$")
    title: str = Field(max_length=200)
    operation_type: Literal["load", "filter", "sql_query", "transform", "evidence"]
    sql_or_expr: str | None = Field(default=None, max_length=20000)
    preview: NodePreview | None = None
    evidence: list[dict[str, str]] = Field(default_factory=list)


class FlowEdge(BaseModel):
    source: str
    target: str


class PipelineSpec(BaseModel):
    pipeline_id: str
    title: str = Field(max_length=200)
    description: str | None = None
    nodes: list[FlowNode] = Field(min_length=1, max_length=100)
    edges: list[FlowEdge] = Field(max_length=500)
    status: Literal["pending_approval", "approved", "rejected"] = "pending_approval"

    @model_validator(mode="after")
    def graph(self):
        ids = [n.id for n in self.nodes]
        if len(set(ids)) != len(ids):
            raise ValueError("Duplicate node IDs")
        if any(e.source not in ids or e.target not in ids for e in self.edges):
            raise ValueError("Unknown edge endpoint")
        return self
