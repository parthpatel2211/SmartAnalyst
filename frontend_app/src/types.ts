/**
 * Mirrors backend_app/models.py field for field.
 * A rename there is a breaking change here.
 */

export type SemanticType =
  | "id"
  | "categorical"
  | "numeric"
  | "datetime"
  | "boolean"
  | "text";

export type ChartKind = "bar" | "line" | "area" | "scatter" | "histogram" | "table";

export type Severity = "high" | "medium" | "low";

export interface ColumnSchema {
  name: string;
  dtype: string;
  semantic_type: SemanticType;
  null_pct: number;
  distinct_count: number;
}

export interface TopValue {
  value: string;
  count: number;
}

export interface ColumnProfile {
  name: string;
  dtype: string;
  semantic_type: SemanticType;
  non_null_count: number;
  null_pct: number;
  distinct_count: number;
  cardinality_ratio: number;
  top_values: TopValue[];
  min: number | null;
  q1: number | null;
  median: number | null;
  mean: number | null;
  q3: number | null;
  max: number | null;
  std: number | null;
  skew: number | null;
  outlier_count: number | null;
  /** Datetime columns only: the span the column covers, ISO formatted. */
  min_label: string | null;
  max_label: string | null;
}

export interface DatasetProfile {
  row_count: number;
  column_count: number;
  duplicate_rows: number;
  memory_bytes: number;
  columns: ColumnProfile[];
}

export interface CorrelationPair {
  x: string;
  y: string;
  value: number;
}

export interface CorrelationMatrix {
  columns: string[];
  matrix: (number | null)[][];
  pairs: CorrelationPair[];
}

export interface Insight {
  kind: string;
  severity: Severity;
  title: string;
  detail: string;
  columns: string[];
}

export interface ChartSpec {
  kind: ChartKind;
  x: string | null;
  y: string[];
  series: string | null;
  title: string;
}

export interface UploadResponse {
  session_id: string;
  name: string;
  row_count: number;
  column_count: number;
  columns: ColumnSchema[];
}

export interface AskResponse {
  question: string;
  sql: string;
  explanation: string;
  columns: string[];
  rows: Record<string, unknown>[];
  row_count: number;
  truncated: boolean;
  chart: ChartSpec;
}

/** A conversation turn as the UI holds it. */
export interface Turn {
  id: string;
  question: string;
  answer: AskResponse | null;
  error: string | null;
}
