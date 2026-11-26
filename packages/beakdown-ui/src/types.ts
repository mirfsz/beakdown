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
  kind?: "pipeline";
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

export type Confidence = "observed" | "inferred" | "unknown";
export type Region = { x: number; y: number; width: number; height: number };
export type EvidenceSource = {
  evidence_id: string;
  operation: string;
  provider: string;
  confidence: string;
  limitations: string[];
};
export type Screen = {
  id: string;
  title: string;
  url: string;
  description: string;
  image_id: string;
  width: number;
  height: number;
  captured_at: string;
  source_sha256: string;
  evidence: EvidenceSource;
};
export type Finding = {
  id: string;
  screen_id: string;
  title: string;
  detail: string;
  confidence: Confidence;
  category: string;
  evidence_ids: string[];
  region: Region | null;
  review: "unreviewed" | "confirmed" | "disputed";
  reviewer_note: string;
};
export type InvestigationSession = {
  kind: "investigation";
  state: string;
  error?: string;
  revision: number;
  approved: boolean;
  investigation: {
    investigation_id: string;
    title: string;
    target: string;
    summary: string;
    screens: Screen[];
    findings: Finding[];
    connections: {
      source: string;
      target: string;
      label: string;
      confidence: string;
      evidence_ids: string[];
    }[];
    limitations: string[];
    analysis?: Session["pipeline"] | null;
    analysis_links: {
      screen_id: string;
      node_id: string;
      finding_ids: string[];
    }[];
    status: string;
  };
};
export type AnySession = Session | InvestigationSession;
