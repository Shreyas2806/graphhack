"use client";

import { useState, useEffect, useCallback } from "react";
import {
  PlusCircle,
  Sparkles,
  Database,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  ChevronLeft,
  ChevronRight,
  Send,
} from "lucide-react";
import { storeMemory, listMemories } from "@/lib/api";
import { MemoryResponse, MemoryListResponse } from "@/types";

const SAMPLE_STATEMENTS = [
  "I am building GraphMind using Python and FalkorDB.",
  "GraphMind uses Gemini 2.5 Flash for multi-agent reasoning.",
  "Alice works on the GraphMind project with Python.",
  "GraphMind stores knowledge as subject, predicate, and object triples.",
  "GraphMind uses FastAPI for backend API endpoints.",
];

export default function AddMemoryPage() {
  const [statement, setStatement] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<MemoryResponse | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);

  // Stored memories pagination state
  const [page, setPage] = useState(1);
  const pageSize = 10;
  const [memoryList, setMemoryList] = useState<MemoryListResponse | null>(null);
  const [loadingList, setLoadingList] = useState(true);

  const fetchMemories = useCallback(async (pageNum: number) => {
    setLoadingList(true);
    try {
      const data = await listMemories(pageNum, pageSize);
      setMemoryList(data);
    } catch (err: unknown) {
      console.error("Failed to load stored memories:", err);
    } finally {
      setLoadingList(false);
    }
  }, [pageSize]);

  useEffect(() => {
    fetchMemories(page);
  }, [fetchMemories, page]);

  const handleSubmit = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    const text = statement.trim();
    if (!text || submitting) return;

    setSubmitting(true);
    setSubmitError(null);
    setResult(null);

    try {
      const res = await storeMemory(text);
      setResult(res);
      setStatement("");
      // Refresh memory list
      fetchMemories(1);
      setPage(1);
    } catch (err: unknown) {
      setSubmitError(
        err instanceof Error ? err.message : "Failed to store memory in FalkorDB."
      );
    } finally {
      setSubmitting(false);
    }
  };

  const handleUseSample = (sample: string) => {
    setStatement(sample);
  };

  const totalPages = memoryList ? Math.ceil(memoryList.total / pageSize) : 1;

  return (
    <div className="space-y-8 animate-fadeIn max-w-5xl mx-auto">
      {/* Header */}
      <div className="pb-4 border-b border-slate-800/80">
        <h1 className="text-xl md:text-2xl font-bold text-slate-100 flex items-center gap-2">
          <PlusCircle className="text-emerald-400" size={24} />
          Add Knowledge Memory
        </h1>
        <p className="text-xs text-slate-400 mt-0.5">
          Submit natural-language statements. The Memory Agent extracts structured triples and persists them to FalkorDB.
        </p>
      </div>

      {/* Input Form Card */}
      <div className="p-6 rounded-2xl bg-slate-900/60 border border-slate-800/80 shadow-lg">
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
                <Sparkles size={14} className="text-blue-400" />
                Natural Language Statement
              </label>
              <span className="text-[11px] text-slate-500 font-mono">
                {statement.length} / 4000 characters
              </span>
            </div>
            <textarea
              value={statement}
              onChange={(e) => setStatement(e.target.value)}
              placeholder="e.g. I am building GraphMind using Python and FalkorDB."
              rows={3}
              disabled={submitting}
              className="w-full bg-slate-950 border border-slate-800 focus:border-blue-500 rounded-xl p-3.5 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-blue-500 transition-colors disabled:opacity-50"
            />
          </div>

          {/* Quick Sample Prompts */}
          <div>
            <span className="text-[11px] font-medium text-slate-400 block mb-1.5">
              Or pick an example statement:
            </span>
            <div className="flex flex-wrap gap-2">
              {SAMPLE_STATEMENTS.map((sample, idx) => (
                <button
                  type="button"
                  key={idx}
                  onClick={() => handleUseSample(sample)}
                  disabled={submitting}
                  className="px-2.5 py-1 rounded-lg bg-slate-950 hover:bg-slate-800 border border-slate-800 text-[11px] text-slate-300 hover:text-white transition-colors truncate max-w-xs text-left"
                >
                  "{sample}"
                </button>
              ))}
            </div>
          </div>

          <div className="flex items-center justify-end pt-2">
            <button
              type="submit"
              disabled={!statement.trim() || submitting}
              className="flex items-center space-x-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-xs font-semibold text-white shadow-md shadow-emerald-600/20 disabled:opacity-50 transition-all"
            >
              {submitting ? (
                <>
                  <RefreshCw size={14} className="animate-spin" />
                  <span>Extracting Triples & Storing...</span>
                </>
              ) : (
                <>
                  <Send size={14} />
                  <span>Store in Knowledge Graph</span>
                </>
              )}
            </button>
          </div>
        </form>

        {/* Submit Error */}
        {submitError && (
          <div className="mt-4 p-3.5 rounded-xl bg-rose-950/40 border border-rose-800/60 text-rose-300 text-xs flex items-start space-x-2.5">
            <AlertTriangle size={16} className="text-rose-400 shrink-0 mt-0.5" />
            <div>
              <div className="font-semibold">Memory Storage Error</div>
              <div className="text-rose-400/90 text-[11px] mt-0.5 font-mono">
                {submitError}
              </div>
            </div>
          </div>
        )}

        {/* Successful Extraction Result Card */}
        {result && (
          <div className="mt-6 p-4 rounded-xl bg-slate-950/90 border border-emerald-800/50 space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800/80">
              <div className="flex items-center space-x-2">
                <CheckCircle2 size={18} className="text-emerald-400" />
                <span className="text-xs font-bold text-slate-100 uppercase tracking-wider">
                  Memory Persisted Successfully
                </span>
              </div>
              <div className="flex items-center space-x-2 text-[11px] font-mono">
                <span className="text-emerald-400 font-semibold">
                  {result.facts_stored} Stored
                </span>
                <span className="text-slate-500">|</span>
                <span className="text-blue-400">
                  {result.facts_extracted} Extracted
                </span>
              </div>
            </div>

            {/* Extracted Facts List */}
            <div className="space-y-2">
              <span className="text-[11px] font-medium text-slate-400 uppercase tracking-wider block">
                Extracted Knowledge Graph Triples
              </span>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
                {result.facts.map((fact, i) => (
                  <div
                    key={i}
                    className="p-3 rounded-lg bg-slate-900 border border-slate-800 hover:border-slate-700 transition-colors"
                  >
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="text-[10px] font-mono text-slate-500">
                        ID: {fact.fact_id?.substring(0, 10)}...
                      </span>
                      {fact.duplicate ? (
                        <span className="text-[10px] px-1.5 py-0.2 rounded bg-amber-950/80 text-amber-400 border border-amber-800/40">
                          Duplicate (Merged)
                        </span>
                      ) : fact.updated ? (
                        <span className="text-[10px] px-1.5 py-0.2 rounded bg-purple-950/80 text-purple-400 border border-purple-800/40">
                          Superseded Old
                        </span>
                      ) : (
                        <span className="text-[10px] px-1.5 py-0.2 rounded bg-emerald-950/80 text-emerald-400 border border-emerald-800/40">
                          New Stored
                        </span>
                      )}
                    </div>

                    <div className="text-xs font-medium text-slate-200">
                      <span className="text-blue-400 font-semibold">{fact.subject}</span>{" "}
                      <span className="text-slate-400 font-mono text-[11px]">
                        [{fact.predicate}]
                      </span>{" "}
                      <span className="text-emerald-300 font-semibold">{fact.object_value}</span>
                    </div>

                    <div className="mt-2 flex items-center justify-between text-[10px] text-slate-500">
                      <span>Type: {fact.object_type || "entity"}</span>
                      <span>Confidence: {Math.round((fact.confidence || 0.9) * 100)}%</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Source Provenance Node */}
            {result.source_id && (
              <div className="pt-2 text-[11px] text-slate-400 font-mono flex items-center gap-1.5">
                <Database size={13} className="text-slate-500" />
                <span>Source Provenance ID:</span>
                <span className="text-slate-300">{result.source_id}</span>
              </div>
            )}

            {/* Agent Workflow Trace */}
            {result.agent_trace && result.agent_trace.length > 0 && (
              <div className="pt-2 border-t border-slate-900 space-y-1">
                <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider block">
                  Agent Execution Sequence
                </span>
                <div className="space-y-1">
                  {result.agent_trace.map((tr, idx) => (
                    <div
                      key={idx}
                      className="flex items-center justify-between text-[11px] text-slate-400 bg-slate-900/60 px-2.5 py-1.5 rounded"
                    >
                      <span className="text-slate-300 font-medium">
                        [{tr.agent}] {tr.action}
                      </span>
                      <span className="font-mono text-slate-500">{tr.duration_ms} ms</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Stored Facts Table */}
      <div className="p-6 rounded-2xl bg-slate-900/40 border border-slate-800/80">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
          <div>
            <h2 className="text-base font-bold text-slate-100 flex items-center gap-2">
              <Database size={16} className="text-blue-400" />
              All Persisted Facts in FalkorDB
            </h2>
            <p className="text-xs text-slate-400 mt-0.5">
              Total {memoryList?.total || 0} fact(s) stored in the current graph database.
            </p>
          </div>

          <button
            onClick={() => fetchMemories(page)}
            disabled={loadingList}
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 border border-slate-700/80 text-xs text-slate-300 transition-colors w-fit"
          >
            <RefreshCw size={12} className={loadingList ? "animate-spin" : ""} />
            <span>Refresh Table</span>
          </button>
        </div>

        {loadingList ? (
          <div className="py-12 text-center text-slate-500 text-xs">
            <RefreshCw size={20} className="animate-spin mx-auto mb-2 text-slate-600" />
            Loading facts from FalkorDB...
          </div>
        ) : !memoryList || memoryList.facts.length === 0 ? (
          <div className="py-10 text-center text-slate-500 text-xs border border-dashed border-slate-800 rounded-xl">
            No memories stored yet. Submit a statement above to populate the knowledge base.
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-slate-800 text-slate-400 uppercase text-[10px] tracking-wider">
                    <th className="py-2.5 px-3">Subject</th>
                    <th className="py-2.5 px-3">Predicate</th>
                    <th className="py-2.5 px-3">Object Value</th>
                    <th className="py-2.5 px-3">Type</th>
                    <th className="py-2.5 px-3">Status</th>
                    <th className="py-2.5 px-3">Fact ID</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 text-slate-300">
                  {memoryList.facts.map((fact) => (
                    <tr key={fact.fact_id} className="hover:bg-slate-800/30 transition-colors">
                      <td className="py-3 px-3 font-semibold text-slate-100">
                        {fact.subject}
                      </td>
                      <td className="py-3 px-3 text-blue-400 font-mono text-[11px]">
                        {fact.predicate}
                      </td>
                      <td className="py-3 px-3 text-slate-200">
                        {fact.object_value}
                      </td>
                      <td className="py-3 px-3 text-slate-400 text-[11px]">
                        {fact.object_type || "entity"}
                      </td>
                      <td className="py-3 px-3">
                        <span
                          className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-medium ${
                            fact.status === "active"
                              ? "bg-emerald-950/60 text-emerald-400 border border-emerald-800/40"
                              : "bg-amber-950/60 text-amber-400 border border-amber-800/40"
                          }`}
                        >
                          {fact.status}
                        </span>
                      </td>
                      <td className="py-3 px-3 font-mono text-[10px] text-slate-500">
                        {fact.fact_id.substring(0, 10)}...
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination Controls */}
            {totalPages > 1 && (
              <div className="flex items-center justify-between pt-4 border-t border-slate-800 mt-4 text-xs text-slate-400">
                <span>
                  Showing page {page} of {totalPages} ({memoryList.total} facts)
                </span>
                <div className="flex items-center space-x-2">
                  <button
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                    disabled={page <= 1}
                    className="p-1.5 rounded-lg bg-slate-900 border border-slate-800 hover:bg-slate-800 text-slate-300 disabled:opacity-30 disabled:hover:bg-slate-900"
                  >
                    <ChevronLeft size={16} />
                  </button>
                  <button
                    onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                    disabled={page >= totalPages}
                    className="p-1.5 rounded-lg bg-slate-900 border border-slate-800 hover:bg-slate-800 text-slate-300 disabled:opacity-30 disabled:hover:bg-slate-900"
                  >
                    <ChevronRight size={16} />
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
