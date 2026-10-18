"use client";

import { useState, useRef, useEffect } from "react";
import {
  Send,
  Bot,
  User,
  ShieldCheck,
  AlertTriangle,
  Sparkles,
  ChevronDown,
  ChevronUp,
  RefreshCw,
  CheckCircle2,
  XCircle,
  HelpCircle,
  MessageSquareCode,
} from "lucide-react";
import { askQuestion } from "@/lib/api";
import { ChatMessage, AskResponse } from "@/types";

const SUGGESTED_PROMPTS = [
  "Which database does GraphMind use?",
  "What is GraphMind built with?",
  "Who works on GraphMind?",
  "Where is GraphMind hosted?",
];

export default function MemoryChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [openDetails, setOpenDetails] = useState<Record<string, boolean>>({});
  const [activeTab, setActiveTab] = useState<Record<string, "evidence" | "claims" | "conflicts" | "trace">>({});
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading]);

  const handleSubmit = async (e?: React.FormEvent, customPrompt?: string) => {
    if (e) e.preventDefault();
    const query = (customPrompt || input).trim();
    if (!query || loading) return;

    const userMessageId = `user-${Date.now()}`;
    const assistantMessageId = `asst-${Date.now() + 1}`;

    const newMessages: ChatMessage[] = [
      ...messages,
      {
        id: userMessageId,
        role: "user",
        content: query,
        timestamp: new Date().toLocaleTimeString(),
      },
      {
        id: assistantMessageId,
        role: "assistant",
        content: "",
        timestamp: new Date().toLocaleTimeString(),
        isLoading: true,
      },
    ];

    setMessages(newMessages);
    setInput("");
    setLoading(true);

    try {
      const response: AskResponse = await askQuestion(query);

      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantMessageId
            ? {
                ...m,
                content: response.answer,
                response,
                isLoading: false,
                error: response.ok ? undefined : response.error || "Reasoning error",
              }
            : m
        )
      );

      // Default expand details if there is evidence or conflicts
      setOpenDetails((prev) => ({
        ...prev,
        [assistantMessageId]: true,
      }));
      setActiveTab((prev) => ({
        ...prev,
        [assistantMessageId]:
          (response.conflicts && response.conflicts.length > 0)
            ? "conflicts"
            : (response.evidence && response.evidence.length > 0)
            ? "evidence"
            : "claims",
      }));
    } catch (err: unknown) {
      const errorMsg =
        err instanceof Error ? err.message : "Failed to query GraphMind backend.";
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantMessageId
            ? {
                ...m,
                content: "Unable to process question due to a backend connection or agent error.",
                isLoading: false,
                error: errorMsg,
              }
            : m
        )
      );
    } finally {
      setLoading(false);
    }
  };

  const toggleDetails = (id: string) => {
    setOpenDetails((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const getStatusBadge = (status?: string | null, _sufficient?: boolean) => {
    if (status === "SUPPORTED") {
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-950/80 border border-emerald-700/60 text-emerald-400">
          <CheckCircle2 size={13} />
          <span>Verified: Supported</span>
        </span>
      );
    }
    if (status === "PARTIALLY_SUPPORTED") {
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-950/80 border border-amber-700/60 text-amber-400">
          <AlertTriangle size={13} />
          <span>Partially Supported</span>
        </span>
      );
    }
    if (status === "CONFLICTING") {
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-rose-950/80 border border-rose-700/60 text-rose-400">
          <AlertTriangle size={13} />
          <span>Conflicting Evidence</span>
        </span>
      );
    }
    if (status === "UNSUPPORTED") {
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-slate-800 border border-slate-700 text-slate-300">
          <XCircle size={13} className="text-rose-400" />
          <span>Insufficient Evidence</span>
        </span>
      );
    }
    if (status === "ERROR") {
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-rose-950/80 border border-rose-700/60 text-rose-400">
          <AlertTriangle size={13} />
          <span>Verification Error</span>
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-slate-800 text-slate-400">
        <HelpCircle size={13} />
        <span>Unverified</span>
      </span>
    );
  };

  return (
    <div className="flex flex-col h-[calc(100vh-5rem)] max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between pb-4 border-b border-slate-800/80 mb-4 shrink-0">
        <div>
          <h1 className="text-xl md:text-2xl font-bold text-slate-100 flex items-center gap-2">
            <MessageSquareCode className="text-blue-400" size={24} />
            Memory Reasoning & Verification Chat
          </h1>
          <p className="text-xs text-slate-400 mt-0.5">
            Answers generated strictly from graph facts and validated by the Verification Agent.
          </p>
        </div>

        {messages.length > 0 && (
          <button
            onClick={() => setMessages([])}
            className="text-xs px-3 py-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-400 hover:text-slate-200 transition-colors"
          >
            Clear Session
          </button>
        )}
      </div>

      {/* Messages Container */}
      <div className="flex-1 overflow-y-auto space-y-5 pr-1 pb-4">
        {messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center p-6 rounded-2xl bg-slate-900/20 border border-dashed border-slate-800/80 my-auto">
            <div className="w-12 h-12 rounded-xl bg-blue-950/60 border border-blue-800/40 text-blue-400 flex items-center justify-center mb-3 shadow-lg shadow-blue-500/10">
              <Bot size={24} />
            </div>
            <h2 className="text-base font-semibold text-slate-200">
              Ask GraphMind Memory
            </h2>
            <p className="text-xs text-slate-400 max-w-md mt-1 mb-6">
              Ask anything about your stored knowledge. The Reasoning Agent traverses multi-hop graph paths and the Verification Agent checks claim integrity.
            </p>

            <div className="w-full max-w-md space-y-2">
              <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider block text-left mb-1.5">
                Try asking:
              </span>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-left">
                {SUGGESTED_PROMPTS.map((prompt) => (
                  <button
                    key={prompt}
                    onClick={() => handleSubmit(undefined, prompt)}
                    className="p-2.5 rounded-lg bg-slate-900/80 hover:bg-slate-800 border border-slate-800 hover:border-slate-700 text-xs text-slate-300 hover:text-white transition-colors flex items-center justify-between group"
                  >
                    <span className="truncate pr-1">{prompt}</span>
                    <Sparkles size={12} className="text-blue-400 opacity-60 group-hover:opacity-100 shrink-0" />
                  </button>
                ))}
              </div>
            </div>
          </div>
        ) : (
          messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex flex-col ${
                msg.role === "user" ? "items-end" : "items-start"
              }`}
            >
              {/* Message Header */}
              <div className="flex items-center space-x-2 mb-1.5 px-1">
                {msg.role === "user" ? (
                  <>
                    <span className="text-[11px] text-slate-400">{msg.timestamp}</span>
                    <span className="text-xs font-semibold text-slate-300">You</span>
                    <div className="w-5 h-5 rounded-full bg-blue-600 flex items-center justify-center text-white text-[10px]">
                      <User size={12} />
                    </div>
                  </>
                ) : (
                  <>
                    <div className="w-5 h-5 rounded-full bg-gradient-to-tr from-blue-600 to-violet-600 flex items-center justify-center text-white text-[10px]">
                      <Bot size={12} />
                    </div>
                    <span className="text-xs font-semibold text-slate-300">GraphMind</span>
                    <span className="text-[11px] text-slate-400">{msg.timestamp}</span>
                  </>
                )}
              </div>

              {/* Message Bubble */}
              <div
                className={`max-w-[90%] md:max-w-[85%] rounded-2xl p-4 text-sm leading-relaxed ${
                  msg.role === "user"
                    ? "bg-blue-600 text-white rounded-tr-none shadow-md shadow-blue-600/10"
                    : "bg-slate-900/90 text-slate-100 border border-slate-800 rounded-tl-none shadow-md"
                }`}
              >
                {msg.isLoading ? (
                  <div className="flex items-center space-x-3 py-2 text-slate-400 text-xs">
                    <RefreshCw size={16} className="animate-spin text-blue-400" />
                    <span>Multi-agent reasoning & verification in progress...</span>
                  </div>
                ) : (
                  <>
                    {/* Status badge if assistant */}
                    {msg.role === "assistant" && msg.response && (
                      <div className="flex flex-wrap items-center gap-2 mb-3 pb-2.5 border-b border-slate-800/80">
                        {getStatusBadge(
                          msg.response.verification_status,
                          msg.response.sufficient_evidence
                        )}
                        {msg.response.facts_used?.length ? (
                          <span className="text-[11px] text-slate-400 bg-slate-800/80 px-2 py-0.5 rounded border border-slate-700/60 font-mono">
                            {msg.response.facts_used.length} fact(s) retrieved
                          </span>
                        ) : null}
                      </div>
                    )}

                    {/* Content */}
                    <div className="whitespace-pre-wrap">{msg.content}</div>

                    {/* Error Notice */}
                    {msg.error && (
                      <div className="mt-3 p-3 rounded-lg bg-rose-950/40 border border-rose-800/60 text-rose-300 text-xs">
                        <div className="font-semibold flex items-center gap-1.5">
                          <AlertTriangle size={14} /> Agent / Pipeline Error
                        </div>
                        <div className="mt-1 text-rose-400/90 font-mono text-[11px]">
                          {msg.error}
                        </div>
                      </div>
                    )}

                    {/* Inspection Details Section */}
                    {msg.role === "assistant" && msg.response && (
                      <div className="mt-4 pt-3 border-t border-slate-800">
                        <button
                          onClick={() => toggleDetails(msg.id)}
                          className="flex items-center justify-between w-full text-xs font-medium text-slate-400 hover:text-slate-200 transition-colors py-1"
                        >
                          <span className="flex items-center gap-1.5">
                            <ShieldCheck size={14} className="text-blue-400" />
                            <span>Verification & Evidence Details</span>
                          </span>
                          {openDetails[msg.id] ? (
                            <ChevronUp size={14} />
                          ) : (
                            <ChevronDown size={14} />
                          )}
                        </button>

                        {openDetails[msg.id] && (
                          <div className="mt-3 space-y-3 text-xs bg-slate-950/60 rounded-xl p-3 border border-slate-800/80">
                            {/* Tabs */}
                            <div className="flex space-x-1 border-b border-slate-800/80 pb-2">
                              <button
                                onClick={() =>
                                  setActiveTab((p) => ({ ...p, [msg.id]: "claims" }))
                                }
                                className={`px-2.5 py-1 rounded text-[11px] font-medium transition-colors ${
                                  (activeTab[msg.id] || "claims") === "claims"
                                    ? "bg-blue-950 text-blue-400 border border-blue-800/50"
                                    : "text-slate-400 hover:text-slate-200"
                                }`}
                              >
                                Claims ({msg.response.verified_claims?.length || 0}/
                                {(msg.response.verified_claims?.length || 0) +
                                  (msg.response.unsupported_claims?.length || 0)}
                                )
                              </button>
                              <button
                                onClick={() =>
                                  setActiveTab((p) => ({ ...p, [msg.id]: "evidence" }))
                                }
                                className={`px-2.5 py-1 rounded text-[11px] font-medium transition-colors ${
                                  activeTab[msg.id] === "evidence"
                                    ? "bg-blue-950 text-blue-400 border border-blue-800/50"
                                    : "text-slate-400 hover:text-slate-200"
                                }`}
                              >
                                Evidence ({msg.response.evidence?.length || 0})
                              </button>
                              {msg.response.conflicts && msg.response.conflicts.length > 0 && (
                                <button
                                  onClick={() =>
                                    setActiveTab((p) => ({ ...p, [msg.id]: "conflicts" }))
                                  }
                                  className={`px-2.5 py-1 rounded text-[11px] font-medium transition-colors ${
                                    activeTab[msg.id] === "conflicts"
                                      ? "bg-rose-950 text-rose-400 border border-rose-800/50"
                                      : "text-rose-400/80 hover:text-rose-300"
                                  }`}
                                >
                                  Conflicts ({msg.response.conflicts.length})
                                </button>
                              )}
                              <button
                                onClick={() =>
                                  setActiveTab((p) => ({ ...p, [msg.id]: "trace" }))
                                }
                                className={`px-2.5 py-1 rounded text-[11px] font-medium transition-colors ${
                                  activeTab[msg.id] === "trace"
                                    ? "bg-purple-950 text-purple-400 border border-purple-800/50"
                                    : "text-slate-400 hover:text-slate-200"
                                }`}
                              >
                                Agent Trace
                              </button>
                            </div>

                            {/* Claims Tab */}
                            {(activeTab[msg.id] || "claims") === "claims" && (
                              <div className="space-y-2 pt-1">
                                {msg.response.verification_explanation && (
                                  <p className="text-[11px] text-slate-300 italic mb-2 pb-1.5 border-b border-slate-900">
                                    "{msg.response.verification_explanation}"
                                  </p>
                                )}

                                {msg.response.verified_claims?.length ? (
                                  <div>
                                    <span className="text-[10px] font-semibold text-emerald-400 uppercase tracking-wider block mb-1">
                                      Supported Claims
                                    </span>
                                    <ul className="space-y-1">
                                      {msg.response.verified_claims.map((claim, idx) => (
                                        <li
                                          key={idx}
                                          className="flex items-start gap-1.5 text-slate-200 text-xs bg-emerald-950/20 p-2 rounded border border-emerald-900/40"
                                        >
                                          <CheckCircle2
                                            size={14}
                                            className="text-emerald-400 shrink-0 mt-0.5"
                                          />
                                          <span>{claim}</span>
                                        </li>
                                      ))}
                                    </ul>
                                  </div>
                                ) : null}

                                {msg.response.unsupported_claims?.length ? (
                                  <div className="mt-2">
                                    <span className="text-[10px] font-semibold text-rose-400 uppercase tracking-wider block mb-1">
                                      Unsupported Claims
                                    </span>
                                    <ul className="space-y-1">
                                      {msg.response.unsupported_claims.map((claim, idx) => (
                                        <li
                                          key={idx}
                                          className="flex items-start gap-1.5 text-slate-300 text-xs bg-rose-950/20 p-2 rounded border border-rose-900/40"
                                        >
                                          <XCircle
                                            size={14}
                                            className="text-rose-400 shrink-0 mt-0.5"
                                          />
                                          <span>{claim}</span>
                                        </li>
                                      ))}
                                    </ul>
                                  </div>
                                ) : null}
                              </div>
                            )}

                            {/* Evidence Tab */}
                            {activeTab[msg.id] === "evidence" && (
                              <div className="space-y-2 pt-1">
                                {msg.response.evidence?.length ? (
                                  msg.response.evidence.map((ev, i) => (
                                    <div
                                      key={i}
                                      className="p-2.5 rounded-lg bg-slate-900/90 border border-slate-800"
                                    >
                                      <div className="flex items-center justify-between text-[10px] font-mono text-slate-400 mb-1">
                                        <span>Fact ID: {ev.fact_id}</span>
                                      </div>
                                      <div className="font-medium text-slate-200 text-xs">
                                        {ev.statement || "Triple evidence"}
                                      </div>
                                      {ev.source_text && (
                                        <div className="mt-1.5 pt-1.5 border-t border-slate-800/80 text-[11px] text-slate-400 italic">
                                          <span className="font-semibold text-slate-500 not-italic">
                                            Source:{" "}
                                          </span>
                                          "{ev.source_text}"
                                        </div>
                                      )}
                                    </div>
                                  ))
                                ) : (
                                  <div className="text-slate-500 text-center py-2 text-xs">
                                    No direct fact evidence attached.
                                  </div>
                                )}
                              </div>
                            )}

                            {/* Conflicts Tab */}
                            {activeTab[msg.id] === "conflicts" && (
                              <div className="space-y-2 pt-1">
                                {msg.response.conflicts?.map((conf, i) => (
                                  <div
                                    key={i}
                                    className="p-2.5 rounded-lg bg-rose-950/30 border border-rose-800/50 text-rose-300"
                                  >
                                    <div className="text-[10px] uppercase font-bold text-rose-400">
                                      {conf.conflict_type}
                                    </div>
                                    <p className="text-xs text-rose-200 mt-0.5">
                                      {conf.description}
                                    </p>
                                  </div>
                                ))}
                              </div>
                            )}

                            {/* Agent Trace Tab */}
                            {activeTab[msg.id] === "trace" && (
                              <div className="space-y-2 pt-1">
                                {msg.response.agent_trace?.length ? (
                                  msg.response.agent_trace.map((trace, i) => (
                                    <div
                                      key={i}
                                      className="flex items-start space-x-2 text-xs p-2 rounded bg-slate-900 border border-slate-800"
                                    >
                                      <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-slate-800 text-blue-400 uppercase">
                                        {trace.agent}
                                      </span>
                                      <div className="flex-1 min-w-0">
                                        <div className="flex items-center justify-between">
                                          <span className="font-medium text-slate-200 text-[11px]">
                                            {trace.action}
                                          </span>
                                          {trace.duration_ms !== undefined && (
                                            <span className="text-[10px] text-slate-500 font-mono">
                                              {trace.duration_ms} ms
                                            </span>
                                          )}
                                        </div>
                                        {trace.details && (
                                          <div className="text-[11px] text-slate-400 mt-0.5">
                                            {trace.details}
                                          </div>
                                        )}
                                      </div>
                                    </div>
                                  ))
                                ) : (
                                  <div className="text-[11px] text-slate-400 font-mono">
                                    {msg.response.reasoning_path || "Path trace unavailable."}
                                  </div>
                                )}
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    )}
                  </>
                )}
              </div>
            </div>
          ))
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Form */}
      <form
        onSubmit={handleSubmit}
        className="pt-2 border-t border-slate-800/80 shrink-0"
      >
        <div className="relative flex items-center">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask a question grounded in knowledge graph memory..."
            disabled={loading}
            className="w-full bg-slate-900 border border-slate-800 focus:border-blue-500 rounded-xl px-4 py-3 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-blue-500 transition-colors pr-12 disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={!input.trim() || loading}
            className="absolute right-2 p-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white disabled:opacity-40 disabled:hover:bg-blue-600 transition-colors"
          >
            {loading ? <RefreshCw size={16} className="animate-spin" /> : <Send size={16} />}
          </button>
        </div>
        <div className="flex items-center justify-between text-[11px] text-slate-500 px-2 mt-1.5">
          <span>Answers are substantiated against FalkorDB graph evidence.</span>
          <span>Press Enter to send</span>
        </div>
      </form>
    </div>
  );
}
