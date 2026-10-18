"use client";

import { useState } from "react";
import {
  Workflow,
  Cpu,
  Layers,
  Sparkles,
  ShieldCheck,
  BrainCircuit,
  CheckCircle2,
  AlertTriangle,
  Play,
  RefreshCw,
} from "lucide-react";
import { askQuestion, storeMemory } from "@/lib/api";
import { AgentStepTrace, AskResponse, MemoryResponse } from "@/types";

export default function AgentWorkflowPage() {
  const [activeWorkflow, setActiveWorkflow] = useState<"ask" | "memory">("ask");
  const [queryInput, setQueryInput] = useState("Which database does GraphMind use?");
  const [statementInput, setStatementInput] = useState("GraphMind is built using Python, FalkorDB, and Next.js.");
  const [running, setRunning] = useState(false);
  const [askTrace, setAskTrace] = useState<AgentStepTrace[] | null>(null);
  const [askResult, setAskResult] = useState<AskResponse | null>(null);
  const [memoryTrace, setMemoryTrace] = useState<AgentStepTrace[] | null>(null);
  const [memoryResult, setMemoryResult] = useState<MemoryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleRunAskWorkflow = async () => {
    if (!queryInput.trim() || running) return;
    setRunning(true);
    setError(null);
    setAskTrace(null);
    setAskResult(null);

    try {
      const res = await askQuestion(queryInput.trim());
      setAskResult(res);
      setAskTrace(res.agent_trace || []);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Workflow execution failed.");
    } finally {
      setRunning(false);
    }
  };

  const handleRunMemoryWorkflow = async () => {
    if (!statementInput.trim() || running) return;
    setRunning(true);
    setError(null);
    setMemoryTrace(null);
    setMemoryResult(null);

    try {
      const res = await storeMemory(statementInput.trim());
      setMemoryResult(res);
      setMemoryTrace(res.agent_trace || []);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Workflow execution failed.");
    } finally {
      setRunning(false);
    }
  };

  const getAgentColor = (agent: string) => {
    if (agent === "Coordinator") return "text-blue-400 bg-blue-950/70 border-blue-800/50";
    if (agent === "MemoryAgent") return "text-emerald-400 bg-emerald-950/70 border-emerald-800/50";
    if (agent === "ReasoningAgent") return "text-indigo-400 bg-indigo-950/70 border-indigo-800/50";
    if (agent === "VerificationAgent") return "text-purple-400 bg-purple-950/70 border-purple-800/50";
    return "text-slate-400 bg-slate-900 border-slate-800";
  };

  const getStatusBadge = (status: string) => {
    if (status === "SUCCESS" || status === "COMPLETED") {
      return (
        <span className="flex items-center gap-1 text-[10px] font-semibold text-emerald-400 bg-emerald-950/60 px-2 py-0.5 rounded border border-emerald-800/40">
          <CheckCircle2 size={11} /> {status}
        </span>
      );
    }
    if (status === "WARNING") {
      return (
        <span className="flex items-center gap-1 text-[10px] font-semibold text-amber-400 bg-amber-950/60 px-2 py-0.5 rounded border border-amber-800/40">
          <AlertTriangle size={11} /> {status}
        </span>
      );
    }
    return (
      <span className="flex items-center gap-1 text-[10px] font-semibold text-rose-400 bg-rose-950/60 px-2 py-0.5 rounded border border-rose-800/40">
        <AlertTriangle size={11} /> {status}
      </span>
    );
  };

  const totalDuration =
    activeWorkflow === "ask"
      ? askTrace?.reduce((acc, step) => acc + (step.duration_ms || 0), 0)
      : memoryTrace?.reduce((acc, step) => acc + (step.duration_ms || 0), 0);

  return (
    <div className="space-y-8 animate-fadeIn max-w-5xl mx-auto">
      {/* Header */}
      <div className="pb-4 border-b border-slate-800/80">
        <h1 className="text-xl md:text-2xl font-bold text-slate-100 flex items-center gap-2">
          <Workflow className="text-purple-400" size={24} />
          Multi-Agent Execution Workflow
        </h1>
        <p className="text-xs text-slate-400 mt-0.5">
          Real execution traces showing the Coordinator, Reasoning Agent, and Verification Agent sequence with real latencies.
        </p>
      </div>

      {/* Architecture Sequence Diagram */}
      <div className="p-6 rounded-2xl bg-slate-900/40 border border-slate-800/80">
        <h2 className="text-sm font-bold text-slate-200 uppercase tracking-wider mb-4 flex items-center gap-2">
          <Layers size={16} className="text-blue-400" />
          End-to-End Autonomous Pipeline
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 relative">
          {/* Step 1: Coordinator */}
          <div className="p-4 rounded-xl bg-slate-950/80 border border-blue-900/50 space-y-2 relative">
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-mono text-blue-400 font-bold px-1.5 py-0.5 rounded bg-blue-950">
                STAGE 1
              </span>
              <Cpu size={16} className="text-blue-400" />
            </div>
            <div className="text-sm font-bold text-slate-100">Coordinator Agent</div>
            <p className="text-[11px] text-slate-400 leading-relaxed">
              Analyzes user intent, validates schemas, and routes tasks to specialized agents.
            </p>
          </div>

          {/* Step 2: Reasoning or Memory */}
          <div className="p-4 rounded-xl bg-slate-950/80 border border-indigo-900/50 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-mono text-indigo-400 font-bold px-1.5 py-0.5 rounded bg-indigo-950">
                STAGE 2
              </span>
              <BrainCircuit size={16} className="text-indigo-400" />
            </div>
            <div className="text-sm font-bold text-slate-100">Reasoning Agent</div>
            <p className="text-[11px] text-slate-400 leading-relaxed">
              Queries FalkorDB, performs multi-hop expansion, and generates grounded answer with Gemini.
            </p>
          </div>

          {/* Step 3: Verification */}
          <div className="p-4 rounded-xl bg-slate-950/80 border border-purple-900/50 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-mono text-purple-400 font-bold px-1.5 py-0.5 rounded bg-purple-950">
                STAGE 3
              </span>
              <ShieldCheck size={16} className="text-purple-400" />
            </div>
            <div className="text-sm font-bold text-slate-100">Verification Agent</div>
            <p className="text-[11px] text-slate-400 leading-relaxed">
              Enforces evidence integrity against FalkorDB, detects staleness/conflicts, and evaluates claims.
            </p>
          </div>

          {/* Step 4: Final Synthesis */}
          <div className="p-4 rounded-xl bg-slate-950/80 border border-emerald-900/50 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-mono text-emerald-400 font-bold px-1.5 py-0.5 rounded bg-emerald-950">
                STAGE 4
              </span>
              <Sparkles size={16} className="text-emerald-400" />
            </div>
            <div className="text-sm font-bold text-slate-100">Grounded Response</div>
            <p className="text-[11px] text-slate-400 leading-relaxed">
              Synthesizes answer with verification status, supporting citations, and conflict disclosures.
            </p>
          </div>
        </div>
      </div>

      {/* Interactive Workflow Runner */}
      <div className="p-6 rounded-2xl bg-slate-900/60 border border-slate-800 shadow-xl space-y-6">
        <div className="flex items-center justify-between pb-3 border-b border-slate-800">
          <div>
            <h2 className="text-base font-bold text-slate-100 flex items-center gap-2">
              <Play size={16} className="text-emerald-400" />
              Live Pipeline Execution Inspector
            </h2>
            <p className="text-xs text-slate-400 mt-0.5">
              Execute a live workflow to inspect the exact multi-agent trace returned by the backend.
            </p>
          </div>

          {/* Workflow Toggle */}
          <div className="flex items-center bg-slate-950 border border-slate-800 rounded-lg p-0.5 text-xs">
            <button
              onClick={() => setActiveWorkflow("ask")}
              className={`px-3 py-1.5 rounded-md font-semibold transition-colors ${
                activeWorkflow === "ask"
                  ? "bg-blue-600 text-white"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              Ask Q&A Workflow
            </button>
            <button
              onClick={() => setActiveWorkflow("memory")}
              className={`px-3 py-1.5 rounded-md font-semibold transition-colors ${
                activeWorkflow === "memory"
                  ? "bg-emerald-600 text-white"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              Memory Storage Workflow
            </button>
          </div>
        </div>

        {/* Input & Run Form */}
        {activeWorkflow === "ask" ? (
          <div className="space-y-3">
            <label className="text-xs font-semibold text-slate-300">
              Query for Reasoning & Verification Agents:
            </label>
            <div className="flex gap-2">
              <input
                type="text"
                value={queryInput}
                onChange={(e) => setQueryInput(e.target.value)}
                placeholder="e.g. Which database does GraphMind use?"
                disabled={running}
                className="flex-1 bg-slate-950 border border-slate-800 focus:border-blue-500 rounded-xl px-4 py-2.5 text-sm text-slate-100 placeholder-slate-500 focus:outline-none"
              />
              <button
                onClick={handleRunAskWorkflow}
                disabled={!queryInput.trim() || running}
                className="flex items-center space-x-2 px-5 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-xs font-semibold text-white shadow-md shadow-blue-500/20 disabled:opacity-50 transition-all shrink-0"
              >
                {running ? (
                  <>
                    <RefreshCw size={14} className="animate-spin" />
                    <span>Running Agents...</span>
                  </>
                ) : (
                  <>
                    <Play size={14} />
                    <span>Execute Pipeline</span>
                  </>
                )}
              </button>
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            <label className="text-xs font-semibold text-slate-300">
              Statement for Memory Extraction Agent:
            </label>
            <div className="flex gap-2">
              <input
                type="text"
                value={statementInput}
                onChange={(e) => setStatementInput(e.target.value)}
                placeholder="e.g. GraphMind uses FalkorDB for persistent graph memory."
                disabled={running}
                className="flex-1 bg-slate-950 border border-slate-800 focus:border-emerald-500 rounded-xl px-4 py-2.5 text-sm text-slate-100 placeholder-slate-500 focus:outline-none"
              />
              <button
                onClick={handleRunMemoryWorkflow}
                disabled={!statementInput.trim() || running}
                className="flex items-center space-x-2 px-5 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-xs font-semibold text-white shadow-md shadow-emerald-500/20 disabled:opacity-50 transition-all shrink-0"
              >
                {running ? (
                  <>
                    <RefreshCw size={14} className="animate-spin" />
                    <span>Storing...</span>
                  </>
                ) : (
                  <>
                    <Play size={14} />
                    <span>Execute Pipeline</span>
                  </>
                )}
              </button>
            </div>
          </div>
        )}

        {/* Error message */}
        {error && (
          <div className="p-3.5 rounded-xl bg-rose-950/40 border border-rose-800/60 text-rose-300 text-xs flex items-center space-x-2">
            <AlertTriangle size={16} />
            <span>{error}</span>
          </div>
        )}

        {/* Execution Trace Timeline */}
        {((activeWorkflow === "ask" && askTrace) ||
          (activeWorkflow === "memory" && memoryTrace)) && (
          <div className="space-y-4 pt-2">
            <div className="flex items-center justify-between pb-2 border-b border-slate-800/80">
              <span className="text-xs font-bold text-slate-200 uppercase tracking-wider">
                Execution Trace Log ({(activeWorkflow === "ask" ? askTrace : memoryTrace)?.length} Steps)
              </span>
              {totalDuration !== undefined && (
                <span className="text-xs font-mono text-purple-400 bg-purple-950/60 px-2 py-0.5 rounded border border-purple-800/40">
                  Total Latency: {totalDuration.toFixed(1)} ms
                </span>
              )}
            </div>

            <div className="space-y-3 relative before:absolute before:inset-0 before:left-3.5 before:w-0.5 before:bg-slate-800">
              {(activeWorkflow === "ask" ? askTrace : memoryTrace)?.map((step, idx) => (
                <div key={idx} className="relative flex items-start space-x-3 text-xs pl-1">
                  <div className="w-6 h-6 rounded-full bg-slate-900 border-2 border-slate-700 flex items-center justify-center text-[10px] font-bold text-slate-400 z-10 shrink-0">
                    {idx + 1}
                  </div>
                  <div className="flex-1 p-3.5 rounded-xl bg-slate-950 border border-slate-800/80 space-y-1.5 shadow">
                    <div className="flex items-center justify-between flex-wrap gap-2">
                      <div className="flex items-center space-x-2">
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase border ${getAgentColor(
                            step.agent
                          )}`}
                        >
                          {step.agent}
                        </span>
                        <span className="font-semibold text-slate-100 text-xs">
                          {step.action}
                        </span>
                      </div>
                      <div className="flex items-center space-x-2">
                        {step.duration_ms !== undefined && (
                          <span className="text-[11px] font-mono text-slate-500">
                            {step.duration_ms} ms
                          </span>
                        )}
                        {getStatusBadge(step.status)}
                      </div>
                    </div>

                    {step.details && (
                      <p className="text-[11px] text-slate-300 leading-relaxed font-mono bg-slate-900/60 p-2 rounded border border-slate-800/50">
                        {step.details}
                      </p>
                    )}
                  </div>
                </div>
              ))}
            </div>

            {/* Answer / Memory Output Summary */}
            {activeWorkflow === "ask" && askResult && (
              <div className="mt-4 p-4 rounded-xl bg-slate-950 border border-blue-900/50 space-y-2">
                <span className="text-[10px] font-bold text-blue-400 uppercase tracking-wider block">
                  Final Grounded Output
                </span>
                <p className="text-sm text-slate-100 leading-relaxed font-medium">
                  {askResult.answer}
                </p>
                <div className="flex items-center gap-3 text-[11px] text-slate-400 pt-2 border-t border-slate-800/80">
                  <span>Verification Status: <strong className="text-slate-200">{askResult.verification_status}</strong></span>
                  <span>Facts Used: <strong className="text-slate-200">{askResult.facts_used?.length || 0}</strong></span>
                </div>
              </div>
            )}

            {activeWorkflow === "memory" && memoryResult && (
              <div className="mt-4 p-4 rounded-xl bg-slate-950 border border-emerald-900/50 space-y-2">
                <span className="text-[10px] font-bold text-emerald-400 uppercase tracking-wider block">
                  Memory Extraction & Storage Output
                </span>
                <div className="text-sm text-slate-100 leading-relaxed font-medium">
                  Persisted {memoryResult.facts_stored} of {memoryResult.facts_extracted} extracted fact(s) to FalkorDB.
                </div>
                {memoryResult.source_id && (
                  <div className="text-[11px] text-slate-400 font-mono pt-1">
                    Source Node ID: {memoryResult.source_id}
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
