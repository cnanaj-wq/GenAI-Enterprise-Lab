export type EventPayload = {
  trace_id: string | null;
  span_id: string | null;
  event_type: string;
  occurred_at: string | null;
  sequence_no: number | null;
  event_data: Record<string, unknown> | null;
};

export type Breakdown = {
  total_ms: number;
  total_pct: number;
  tool_execution_ms: number;
  tool_execution_pct: number;
  llm_duration_ms?: number;
  llm_pct?: number;
  unattributed_ms: number;
  unattributed_pct: number;
  note?: string;
};

export type InvestigationStart = {
  run_id: string;
  status: string;
  stream_url: string;
  state_url: string;
};

export type LLMMetric = {
  provider: string;
  model: string;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  estimated_cost_usd: number;
  duration_ms: number;
};
