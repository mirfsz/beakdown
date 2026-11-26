export type FlowNode = {
  id: string;
  title: string;
  operation_type: string;
  sql_or_expr?: string;
  evidence: { source?: string; summary?: string; confidence?: string }[];
  preview?: {
    total_rows: number;
    column_count: number;
    execution_time_ms: number;
    columns: { name: string; data_type: string; null_count: number }[];
    sample_data: Record<string, unknown>[];
  };
};
export type Session = {
  state: string;
  error?: string;
  revision: number;
  approved: boolean;
  pipeline: {
    pipeline_id: string;
    title: string;
    description?: string;
    status: string;
    nodes: FlowNode[];
    edges: { source: string; target: string }[];
  };
};
