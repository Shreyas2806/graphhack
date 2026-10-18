"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import {
  Database,
  Share2,
  BrainCircuit,
  ShieldCheck,
  PlusCircle,
  MessageSquareCode,
  ArrowRight,
  RefreshCw,
  CheckCircle2,
  AlertTriangle,
  Sparkles,
  Layers,
} from "lucide-react";
import { listMemories, getGraphData, getHealth } from "@/lib/api";
import { StoredFact, HealthResponse } from "@/types";

export default function OverviewPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [facts, setFacts] = useState<StoredFact[]>([]);
  const [totalFacts, setTotalFacts] = useState<number>(0);
  const [graphStats, setGraphStats] = useState<{
    entities: number;
    facts: number;
    sources: number;
    edges: number;
  }>({ entities: 0, facts: 0, sources: 0, edges: 0 });

  const loadDashboardData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [healthRes, memoryRes, graphRes] = await Promise.allSettled([
        getHealth(),
        listMemories(1, 8),
        getGraphData(500),
      ]);

      if (healthRes.status === "fulfilled") {
        setHealth(healthRes.value);
      }

      if (memoryRes.status === "fulfilled") {
        setFacts(memoryRes.value.facts || []);
        setTotalFacts(memoryRes.value.total || 0);
      }

      if (graphRes.status === "fulfilled" && graphRes.value.ok) {
        const nodes = graphRes.value.nodes || [];
        const edges = graphRes.value.edges || [];
        const entityCount = nodes.filter((n) => n.label === "Entity").length;
        const factCount = nodes.filter((n) => n.label === "Fact").length;
        const sourceCount = nodes.filter((n) => n.label === "Source").length;
        setGraphStats({
          entities: entityCount,
          facts: factCount,
          sources: sourceCount,
          edges: edges.length,
        });
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load dashboard data");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadDashboardData();
  }, [loadDashboardData]);

  const falkorDbOk = health?.falkordb?.ok === true;

  return (
    <div className="space-y-8 animate-fadeIn">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-6 border-b border-slate-800/80">
        <div>
          <div className="flex items-center space-x-2 mb-1">
            <h1 className="text-2xl md:text-3xl font-extrabold text-slate-100 tracking-tight">
              Knowledge Overview
            </h1>
            <span className="text-xs px-2 py-0.5 rounded-full bg-blue-950/80 border border-blue-800/60 text-blue-400 font-medium">
              Live Graph
            </span>
          </div>
          <p className="text-sm text-slate-400">
            Real-time multi-agent memory statistics, stored graph triples, and engine status.
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <button
            onClick={loadDashboardData}
            disabled={loading}
            className="flex items-center space-x-2 px-3.5 py-2 rounded-lg bg-slate-900 hover:bg-slate-800 border border-slate-700/80 text-xs font-medium text-slate-300 transition-colors disabled:opacity-50"
          >
            <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
            <span>Refresh</span>
          </button>
          <Link
            href="/chat"
            className="flex items-center space-x-2 px-4 py-2 rounded-lg bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-xs font-semibold text-white shadow-md shadow-blue-500/20 transition-all"
          >
            <MessageSquareCode size={14} />
            <span>Ask Memory</span>
          </Link>
          <Link
            href="/memory"
            className="flex items-center space-x-2 px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-xs font-semibold text-slate-200 transition-all"
          >
            <PlusCircle size={14} />
            <span>Add Memory</span>
          </Link>
        </div>
      </div>

      {/* Error alert if backend unreachable */}
      {error && (
        <div className="p-4 rounded-xl bg-rose-950/30 border border-rose-800/50 flex items-start space-x-3">
          <AlertTriangle size={18} className="text-rose-400 mt-0.5 shrink-0" />
          <div className="text-sm">
            <div className="font-semibold text-rose-300">Backend Communication Notice</div>
            <div className="text-rose-400/90 text-xs mt-0.5">{error}</div>
          </div>
        </div>
      )}

      {/* Key Stats Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Total Facts */}
        <div className="p-5 rounded-xl bg-slate-900/60 border border-slate-800/80 relative overflow-hidden">
          <div className="flex items-center justify-between text-slate-400 mb-3">
            <span className="text-xs font-medium uppercase tracking-wider">Stored Facts</span>
            <div className="p-2 rounded-lg bg-blue-950/50 text-blue-400 border border-blue-800/30">
              <Database size={16} />
            </div>
          </div>
          <div className="text-3xl font-extrabold text-slate-100">
            {loading ? "..." : totalFacts}
          </div>
          <p className="text-[11px] text-slate-400 mt-1 flex items-center gap-1">
            <span className="text-blue-400 font-medium">Persisted</span> in FalkorDB graph
          </p>
        </div>

        {/* Entities */}
        <div className="p-5 rounded-xl bg-slate-900/60 border border-slate-800/80 relative overflow-hidden">
          <div className="flex items-center justify-between text-slate-400 mb-3">
            <span className="text-xs font-medium uppercase tracking-wider">Unique Entities</span>
            <div className="p-2 rounded-lg bg-violet-950/50 text-violet-400 border border-violet-800/30">
              <BrainCircuit size={16} />
            </div>
          </div>
          <div className="text-3xl font-extrabold text-slate-100">
            {loading ? "..." : graphStats.entities}
          </div>
          <p className="text-[11px] text-slate-400 mt-1 flex items-center gap-1">
            <span className="text-violet-400 font-medium">Nodes</span> linked across knowledge
          </p>
        </div>

        {/* Relationships */}
        <div className="p-5 rounded-xl bg-slate-900/60 border border-slate-800/80 relative overflow-hidden">
          <div className="flex items-center justify-between text-slate-400 mb-3">
            <span className="text-xs font-medium uppercase tracking-wider">Relationships</span>
            <div className="p-2 rounded-lg bg-emerald-950/50 text-emerald-400 border border-emerald-800/30">
              <Share2 size={16} />
            </div>
          </div>
          <div className="text-3xl font-extrabold text-slate-100">
            {loading ? "..." : graphStats.edges}
          </div>
          <p className="text-[11px] text-slate-400 mt-1 flex items-center gap-1">
            <span className="text-emerald-400 font-medium">Edges</span> connecting entities & facts
          </p>
        </div>

        {/* Engine Connectivity */}
        <div className="p-5 rounded-xl bg-slate-900/60 border border-slate-800/80 relative overflow-hidden">
          <div className="flex items-center justify-between text-slate-400 mb-3">
            <span className="text-xs font-medium uppercase tracking-wider">Engine Health</span>
            <div className="p-2 rounded-lg bg-indigo-950/50 text-indigo-400 border border-indigo-800/30">
              <ShieldCheck size={16} />
            </div>
          </div>
          <div className="text-xl font-bold flex items-center gap-2 text-slate-100">
            {loading ? (
              "Checking..."
            ) : falkorDbOk ? (
              <span className="text-emerald-400 flex items-center gap-1.5 text-lg">
                <CheckCircle2 size={18} /> FalkorDB Connected
              </span>
            ) : (
              <span className="text-rose-400 flex items-center gap-1.5 text-lg">
                <AlertTriangle size={18} /> Degraded
              </span>
            )}
          </div>
          <p className="text-[11px] text-slate-400 mt-1 truncate">
          {loading ? "Connecting to backend..." : `Graph: 'graphmind' via ${process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000"}`}
          </p>
        </div>
      </div>

      {/* Multi-Agent Architecture Status */}
      <div className="p-5 rounded-xl bg-slate-900/40 border border-slate-800/80">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center space-x-2">
            <Layers size={18} className="text-blue-400" />
            <h2 className="text-sm font-semibold text-slate-200">
              Autonomous Agent Workflow Pipeline
            </h2>
          </div>
          <Link
            href="/workflow"
            className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1 font-medium transition-colors"
          >
            <span>Inspect Traces</span>
            <ArrowRight size={13} />
          </Link>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
          <div className="p-3.5 rounded-lg bg-slate-950/80 border border-slate-800/80">
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-xs font-bold text-slate-200">Coordinator Agent</span>
              <span className="text-[10px] text-blue-400 px-1.5 py-0.5 rounded bg-blue-950/60 border border-blue-800/40">
                ACTIVE
              </span>
            </div>
            <p className="text-[11px] text-slate-400 leading-relaxed">
              Dispatches queries, oversees reasoning and verification, synthesizes final responses.
            </p>
          </div>

          <div className="p-3.5 rounded-lg bg-slate-950/80 border border-slate-800/80">
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-xs font-bold text-slate-200">Memory Agent</span>
              <span className="text-[10px] text-emerald-400 px-1.5 py-0.5 rounded bg-emerald-950/60 border border-emerald-800/40">
                READY
              </span>
            </div>
            <p className="text-[11px] text-slate-400 leading-relaxed">
              Extracts (S, P, O) triples via Gemini with stable IDs and persists to FalkorDB.
            </p>
          </div>

          <div className="p-3.5 rounded-lg bg-slate-950/80 border border-slate-800/80">
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-xs font-bold text-slate-200">Reasoning Agent</span>
              <span className="text-[10px] text-indigo-400 px-1.5 py-0.5 rounded bg-indigo-950/60 border border-indigo-800/40">
                READY
              </span>
            </div>
            <p className="text-[11px] text-slate-400 leading-relaxed">
              Performs multi-hop graph retrieval and grounds answers strictly in active facts.
            </p>
          </div>

          <div className="p-3.5 rounded-lg bg-slate-950/80 border border-slate-800/80">
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-xs font-bold text-slate-200">Verification Agent</span>
              <span className="text-[10px] text-purple-400 px-1.5 py-0.5 rounded bg-purple-950/60 border border-purple-800/40">
                READY
              </span>
            </div>
            <p className="text-[11px] text-slate-400 leading-relaxed">
              Enforces evidence integrity, detects staleness/conflicts, and verifies claims.
            </p>
          </div>
        </div>
      </div>

      {/* Recent Stored Memories */}
      <div className="p-5 rounded-xl bg-slate-900/40 border border-slate-800/80">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-base font-semibold text-slate-100 flex items-center gap-2">
              <Sparkles size={16} className="text-violet-400" />
              Recent Stored Facts
            </h2>
            <p className="text-xs text-slate-400 mt-0.5">
              Most recent subject-predicate-object facts extracted and persisted in FalkorDB.
            </p>
          </div>
          <Link
            href="/memory"
            className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1 font-medium transition-colors"
          >
            <span>View All & Add</span>
            <ArrowRight size={13} />
          </Link>
        </div>

        {loading ? (
          <div className="py-12 text-center text-slate-400 text-sm">
            <RefreshCw size={24} className="animate-spin mx-auto mb-2 text-slate-500" />
            Loading facts from knowledge base...
          </div>
        ) : facts.length === 0 ? (
          <div className="py-12 text-center rounded-xl border border-dashed border-slate-800 bg-slate-950/40">
            <Database size={28} className="mx-auto text-slate-600 mb-2" />
            <h3 className="text-sm font-semibold text-slate-300">No facts stored yet</h3>
            <p className="text-xs text-slate-400 max-w-sm mx-auto mt-1 mb-4">
              Add your first natural-language statement to extract structured knowledge graph facts.
            </p>
            <Link
              href="/memory"
              className="inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-xs font-semibold text-white shadow"
            >
              <PlusCircle size={14} />
              <span>Add Memory</span>
            </Link>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400 uppercase text-[10px] tracking-wider">
                  <th className="py-2.5 px-3">Subject</th>
                  <th className="py-2.5 px-3">Predicate</th>
                  <th className="py-2.5 px-3">Object Value</th>
                  <th className="py-2.5 px-3">Status</th>
                  <th className="py-2.5 px-3">Confidence</th>
                  <th className="py-2.5 px-3">Fact ID</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 text-slate-300">
                {facts.map((fact) => (
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
                    <td className="py-3 px-3">
                      <div className="flex items-center gap-1.5">
                        <div className="w-12 h-1.5 bg-slate-800 rounded-full overflow-hidden">
                          <div
                            className="h-full bg-blue-500 rounded-full"
                            style={{ width: `${Math.round((fact.confidence || 0.8) * 100)}%` }}
                          />
                        </div>
                        <span className="text-[10px] text-slate-400">
                          {Math.round((fact.confidence || 0.8) * 100)}%
                        </span>
                      </div>
                    </td>
                    <td className="py-3 px-3 font-mono text-[10px] text-slate-400">
                      {fact.fact_id.substring(0, 8)}...
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
