export type CRStatus =
  | 'DRAFT'
  | 'BRANCHED'
  | 'BLOCKED'
  | 'CHECKS_PASSED'
  | 'READY_FOR_REVIEW'
  | 'APPROVED'
  | 'REJECTED'
  | 'MERGED'
  | 'CONFLICT';

export interface Operation {
  op_id: string;
  op_type: string;
  key?: string;
  new_value?: any;
  expected_version?: number;
  old_fact_id?: string;
  new_fact_id?: string;
  source_id?: string;
  doc_id?: string;
  before?: string;
  after?: string;
  derived?: {
    from_key: string;
    rule: string;
  };
}

export interface ChangeRequest {
  id: string;
  title: string;
  fact_key: string;
  new_value: any;
  source_id?: string;
  status: CRStatus;
  branch_graph: string;
  base_revision: number;
  ops: Operation[];
  created_by: string;
  created_at: string;
  approved_by?: string;
  merged_at?: string;
  rejected_reason?: string;
}

export interface ImpactItem {
  doc_id: string;
  title: string;
  reason: 'CITES' | 'CITES_DERIVED_FACT' | 'DERIVED_FROM_DOC';
  reasons: string[];
  path: string[];
  owner_id?: string;
  owner_name?: string;
  system_id?: string;
  system_name?: string;
}

export interface BaselineComparison {
  naive_count: number;
  graph_count: number;
  missed_by_naive: string[];
  false_positives: string[];
  correctly_flagged: string[];
  dark_dependencies: string[];
}

export interface CheckResult {
  code: string;
  severity: 'BLOCK' | 'WARN';
  passed: boolean;
  message: string;
  evidence: any[];
}

export interface ProposedEdit {
  edit_id: string;
  doc_id: string;
  doc_title: string;
  before: string;
  after: string;
  status: string;
}

export interface AgentStep {
  id: string;
  cr_id: string;
  idx: number;
  tool: string;
  args: Record<string, any>;
  result_summary: string;
  created_at: string;
}

export interface AuditEvent {
  id: string;
  cr_id: string;
  event_type: string;
  detail: Record<string, any>;
  created_at: string;
}

export interface ChangeRequestDetail {
  cr: ChangeRequest;
  diff: {
    facts: any[];
    edits: ProposedEdit[];
    doc_status_changes: any[];
    summary: Record<string, number>;
  };
  impact: ImpactItem[];
  baseline: BaselineComparison;
  checks: CheckResult[];
  steps: AgentStep[];
  audit: AuditEvent[];
}

export interface PersonEntity {
  id: string;
  name: string;
  role: string;
  email: string;
}

export interface FactEntity {
  id: string;
  key: string;
  value: any;
  unit: string;
  subject: string;
  attribute: string;
  version: number;
}

export interface SourceEntity {
  id: string;
  title: string;
  trust: number;
  valid: boolean;
  kind: string;
}

export interface DocSummary {
  id: string;
  title: string;
  status: string;
}

export interface EntityData {
  people: PersonEntity[];
  facts: FactEntity[];
  sources: SourceEntity[];
  documents: DocSummary[];
}

export interface ChatMessageItem {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  citations?: string[];
  timestamp: string;
}

export interface CatalogEntry {
  id: string;
  name: string;
  domain: string;
  description: string;
  default_graph: string;
  is_active: boolean;
  is_seeded: boolean;
}

export interface DatasetCatalogResponse {
  active_dataset: string;
  catalog: CatalogEntry[];
}

