/**
 * src/types/index.ts — Shared TypeScript definitions for GraphMind frontend.
 * Strictly mirrors the backend Pydantic models.
 */

export interface HealthResponse {
  status: "ok" | "degraded" | "llm_unavailable" | string;
  falkordb: {
    ok?: boolean;
    error?: string;
  };
  gemini?: {
    ok?: boolean;
    error?: string;
  } | null;
}

export interface RootResponse {
  project: string;
  status: string;
  version: string;
}

export interface ExtractedFact {
  fact_id?: string | null;
  subject?: string | null;
  predicate?: string | null;
  object_value?: string | null;
  object_type?: string | null;
  confidence?: number | null;
  status?: string | null;
  stored: boolean;
  duplicate: boolean;
  updated: boolean;
  error?: string | null;
  skip_reason?: string | null;
}

export interface AgentStepTrace {
  agent: string; // Coordinator, MemoryAgent, ReasoningAgent, VerificationAgent
  status: "SUCCESS" | "COMPLETED" | "WARNING" | "ERROR" | string;
  action: string;
  duration_ms?: number | null;
  details?: string | null;
  metadata?: Record<string, unknown> | null;
}

export interface MemoryRequest {
  text: string;
}

export interface MemoryResponse {
  ok: boolean;
  facts_extracted: number;
  facts_stored: number;
  source_id?: string | null;
  facts: ExtractedFact[];
  agent_trace?: AgentStepTrace[];
  error?: string | null;
}

export interface SourceEvidence {
  source_id?: string | null;
  text?: string | null;
  source_type?: string | null;
  created_at?: string | null;
}

export interface FactUsed {
  fact_id?: string;
  subject?: string;
  predicate?: string;
  object_value?: string;
  object_type?: string | null;
  confidence?: number | null;
  status?: string | null;
  source_text?: string | null;
  statement?: string | null;
  created_at?: string | null;
}

export interface ConflictItem {
  conflict_type: string;
  description: string;
  fact_id?: string | null;
  conflicting_fact_id?: string | null;
}

export interface EvidenceDetail {
  fact_id: string;
  statement?: string | null;
  source_text?: string | null;
}

export interface AskRequest {
  question: string;
}

export interface AskResponse {
  ok: boolean;
  answer: string;
  sufficient_evidence: boolean;
  facts_used: FactUsed[];
  sources: SourceEvidence[];
  reasoning_path: string;
  verification_status?: "SUPPORTED" | "PARTIALLY_SUPPORTED" | "UNSUPPORTED" | "CONFLICTING" | "ERROR" | null;
  verified_claims: string[];
  unsupported_claims: string[];
  evidence: EvidenceDetail[];
  conflicts: ConflictItem[];
  verification_explanation?: string | null;
  agent_trace?: AgentStepTrace[];
  error?: string | null;
}

export interface StoredFact {
  fact_id: string;
  subject: string;
  predicate: string;
  object_value: string;
  object_type: string;
  confidence?: number | null;
  status: string;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface MemoryListResponse {
  ok: boolean;
  total: number;
  page: number;
  page_size: number;
  facts: StoredFact[];
  error?: string | null;
}

export interface GraphNodeRaw {
  id: string;
  label: "Entity" | "Fact" | "Source" | string;
  name?: string;
  type?: string;
  subject?: string;
  predicate?: string;
  object_value?: string;
  status?: string;
  confidence?: number;
  text?: string;
  source_type?: string;
}

export interface GraphEdgeRaw {
  source: string;
  target: string;
  type: string;
}

export interface GraphExportResponse {
  ok: boolean;
  nodes: GraphNodeRaw[];
  edges: GraphEdgeRaw[];
  error?: string | null;
}

export interface VerifyEvidenceInput {
  fact_id?: string;
  statement?: string;
  subject?: string;
  predicate?: string;
  object_value?: string;
  source_text?: string;
  status?: string;
  confidence?: number;
}

export interface VerifyRequest {
  question: string;
  answer: string;
  evidence: VerifyEvidenceInput[];
}

export interface VerifyResponse {
  ok: boolean;
  status: "SUPPORTED" | "PARTIALLY_SUPPORTED" | "UNSUPPORTED" | "CONFLICTING" | "ERROR" | string;
  verified_claims: string[];
  unsupported_claims: string[];
  evidence: EvidenceDetail[];
  conflicts: ConflictItem[];
  explanation: string;
  error?: string | null;
}

// Conversation message type for Memory Chat
export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
  response?: AskResponse;
  isLoading?: boolean;
  error?: string;
}
