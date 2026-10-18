"use client";

import { useEffect, useState, useMemo, useCallback } from "react";
import Link from "next/link";
import {
  ReactFlow,
  MiniMap,
  Controls,
  Background,
  useNodesState,
  useEdgesState,
  Node,
  Edge,
  MarkerType,
  BackgroundVariant,
} from "@xyflow/react";
import {
  Share2,
  RefreshCw,
  PlusCircle,
  Database,
  Info,
  X,
  Tag,
} from "lucide-react";
import { getGraphData } from "@/lib/api";
import { GraphNodeRaw } from "@/types";

// Custom node data types
interface CustomNodeData extends Record<string, unknown> {
  raw: GraphNodeRaw;
  label: string;
  sublabel?: string;
  badge?: string;
  status?: string;
  nodeType: "Entity" | "Fact" | "Source";
}

// Custom Node Component
function KnowledgeGraphNode({ data, selected }: { data: CustomNodeData; selected?: boolean }) {
  const isEntity = data.nodeType === "Entity";
  const isFact = data.nodeType === "Fact";

  return (
    <div
      className={`px-3.5 py-2.5 rounded-xl border shadow-lg transition-all min-w-[150px] max-w-[220px] ${
        selected
          ? "ring-2 ring-blue-400 border-blue-400 scale-105"
          : "hover:border-slate-500"
      } ${
        isEntity
          ? "bg-gradient-to-b from-violet-950/90 to-slate-900 border-violet-700/60 text-violet-100"
          : isFact
          ? data.status === "superseded"
            ? "bg-gradient-to-b from-amber-950/80 to-slate-900 border-amber-800/60 text-amber-100"
            : "bg-gradient-to-b from-emerald-950/90 to-slate-900 border-emerald-700/60 text-emerald-100"
          : "bg-gradient-to-b from-slate-900 to-slate-950 border-slate-700/80 text-slate-200"
      }`}
    >
      <div className="flex items-center justify-between gap-1 mb-1">
        <span
          className={`text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.2 rounded ${
            isEntity
              ? "bg-violet-900/60 text-violet-300 border border-violet-700/40"
              : isFact
              ? "bg-emerald-900/60 text-emerald-300 border border-emerald-700/40"
              : "bg-slate-800 text-slate-400 border border-slate-700/50"
          }`}
        >
          {data.nodeType}
        </span>
        {data.status && (
          <span
            className={`text-[9px] px-1 py-0.2 rounded font-medium ${
              data.status === "active"
                ? "text-emerald-400 bg-emerald-950/80"
                : "text-amber-400 bg-amber-950/80"
            }`}
          >
            {data.status}
          </span>
        )}
      </div>

      <div className="font-bold text-xs truncate" title={data.label}>
        {data.label}
      </div>

      {data.sublabel && (
        <div className="text-[10px] text-slate-400 truncate mt-0.5" title={data.sublabel}>
          {data.sublabel}
        </div>
      )}
    </div>
  );
}

export default function KnowledgeGraphExplorer() {
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<GraphNodeRaw | null>(null);

  // Filter state
  const [filterType, setFilterType] = useState<"ALL" | "Entity" | "Fact" | "Source">("ALL");

  const nodeTypes = useMemo(() => ({ customNode: KnowledgeGraphNode }), []);

  const loadGraph = useCallback(async () => {
    setLoading(true);
    setError(null);
    setSelectedNode(null);

    try {
      const res = await getGraphData(300);
      if (!res.ok) {
        throw new Error(res.error || "Failed to load graph data from FalkorDB");
      }

      const rawNodes = res.nodes || [];
      const rawEdges = res.edges || [];

      // Calculate positions in 3 columns:
      // Left: Entities, Center: Facts, Right: Sources
      const entityNodes = rawNodes.filter((n) => n.label === "Entity");
      const factNodes = rawNodes.filter((n) => n.label === "Fact");
      const sourceNodes = rawNodes.filter((n) => n.label === "Source");

      const positionedNodes: Node[] = [];

      entityNodes.forEach((n, idx) => {
        positionedNodes.push({
          id: n.id,
          type: "customNode",
          position: { x: 50, y: 50 + idx * 100 },
          data: {
            raw: n,
            nodeType: "Entity",
            label: n.name || n.id,
            sublabel: n.type ? `Type: ${n.type}` : undefined,
          },
        });
      });

      factNodes.forEach((n, idx) => {
        positionedNodes.push({
          id: n.id,
          type: "customNode",
          position: { x: 380, y: 50 + idx * 110 },
          data: {
            raw: n,
            nodeType: "Fact",
            label: n.predicate ? `${n.predicate}: ${n.object_value}` : n.id,
            sublabel: n.subject ? `Subject: ${n.subject}` : undefined,
            status: n.status,
          },
        });
      });

      sourceNodes.forEach((n, idx) => {
        positionedNodes.push({
          id: n.id,
          type: "customNode",
          position: { x: 740, y: 60 + idx * 120 },
          data: {
            raw: n,
            nodeType: "Source",
            label: n.text ? `"${n.text.substring(0, 30)}..."` : n.id,
            sublabel: n.source_type ? `Source: ${n.source_type}` : undefined,
          },
        });
      });

      // Transform edges with labels and colors
      const styledEdges: Edge[] = rawEdges.map((e, idx) => {
        const isSubject = e.type === "SUBJECT_OF";
        const isObject = e.type === "OBJECT_OF";
        const isSupports = e.type === "SUPPORTS";

        const strokeColor = isSubject
          ? "#8b5cf6"
          : isObject
          ? "#3b82f6"
          : isSupports
          ? "#10b981"
          : "#64748b";

        return {
          id: `edge-${idx}-${e.source}-${e.target}`,
          source: e.source,
          target: e.target,
          label: e.type,
          type: "smoothstep",
          animated: isSupports,
          style: { stroke: strokeColor, strokeWidth: 1.8 },
          markerEnd: {
            type: MarkerType.ArrowClosed,
            color: strokeColor,
            width: 16,
            height: 16,
          },
          labelStyle: { fill: "#94a3b8", fontSize: 10, fontWeight: 600 },
          labelBgStyle: { fill: "#0f172a", fillOpacity: 0.85 },
          labelBgPadding: [4, 2],
          labelBgBorderRadius: 4,
        };
      });

      setNodes(positionedNodes);
      setEdges(styledEdges);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load graph.");
    } finally {
      setLoading(false);
    }
  }, [setNodes, setEdges]);

  useEffect(() => {
    loadGraph();
  }, [loadGraph]);

  // Handle node selection
  const onNodeClick = (_: React.MouseEvent, node: Node) => {
    const raw = (node.data as CustomNodeData)?.raw;
    if (raw) {
      setSelectedNode(raw);
    }
  };

  // Filtered nodes
  const displayNodes = useMemo(() => {
    if (filterType === "ALL") return nodes;
    return nodes.filter((n) => (n.data as CustomNodeData)?.nodeType === filterType);
  }, [nodes, filterType]);

  const isEmpty = !loading && nodes.length === 0;

  return (
    <div className="space-y-4 animate-fadeIn h-[calc(100vh-5rem)] flex flex-col">
      {/* Top Controls Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-800 shrink-0">
        <div>
          <h1 className="text-xl md:text-2xl font-bold text-slate-100 flex items-center gap-2">
            <Share2 className="text-violet-400" size={24} />
            Knowledge Graph Explorer
          </h1>
          <p className="text-xs text-slate-400 mt-0.5">
            Interactive visualization of FalkorDB entities, facts, and provenance sources.
          </p>
        </div>

        <div className="flex items-center space-x-2">
          {/* Node Type Filter */}
          <div className="flex items-center bg-slate-900 border border-slate-800 rounded-lg p-0.5 text-xs text-slate-400">
            <button
              onClick={() => setFilterType("ALL")}
              className={`px-2.5 py-1 rounded font-medium transition-colors ${
                filterType === "ALL"
                  ? "bg-slate-800 text-white"
                  : "hover:text-slate-200"
              }`}
            >
              All ({nodes.length})
            </button>
            <button
              onClick={() => setFilterType("Entity")}
              className={`px-2.5 py-1 rounded font-medium transition-colors ${
                filterType === "Entity"
                  ? "bg-violet-950 text-violet-300 border border-violet-800/50"
                  : "hover:text-slate-200"
              }`}
            >
              Entities
            </button>
            <button
              onClick={() => setFilterType("Fact")}
              className={`px-2.5 py-1 rounded font-medium transition-colors ${
                filterType === "Fact"
                  ? "bg-emerald-950 text-emerald-300 border border-emerald-800/50"
                  : "hover:text-slate-200"
              }`}
            >
              Facts
            </button>
            <button
              onClick={() => setFilterType("Source")}
              className={`px-2.5 py-1 rounded font-medium transition-colors ${
                filterType === "Source"
                  ? "bg-blue-950 text-blue-300 border border-blue-800/50"
                  : "hover:text-slate-200"
              }`}
            >
              Sources
            </button>
          </div>

          <button
            onClick={loadGraph}
            disabled={loading}
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 border border-slate-700/80 text-xs font-medium text-slate-300 transition-colors disabled:opacity-50"
          >
            <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
            <span>Reload</span>
          </button>
        </div>
      </div>

      {/* Error state */}
      {error && (
        <div className="p-3.5 rounded-xl bg-rose-950/40 border border-rose-800/60 text-rose-300 text-xs flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <Info size={16} />
            <span>{error}</span>
          </div>
          <button
            onClick={loadGraph}
            className="px-2 py-1 bg-rose-900/60 rounded text-rose-200 text-xs hover:bg-rose-900"
          >
            Retry
          </button>
        </div>
      )}

      {/* Canvas & Drawer Container */}
      <div className="flex-1 relative rounded-2xl border border-slate-800 overflow-hidden bg-slate-950 shadow-inner">
        {loading ? (
          <div className="absolute inset-0 z-20 flex flex-col items-center justify-center bg-slate-950/80 backdrop-blur-sm text-slate-400 text-sm">
            <RefreshCw size={28} className="animate-spin text-blue-400 mb-2" />
            <span>Retrieving graph nodes & edges from FalkorDB...</span>
          </div>
        ) : isEmpty ? (
          <div className="absolute inset-0 z-10 flex flex-col items-center justify-center text-center p-6 my-auto">
            <div className="w-14 h-14 rounded-2xl bg-slate-900 border border-slate-800 flex items-center justify-center text-slate-500 mb-3 shadow-lg">
              <Database size={28} />
            </div>
            <h3 className="text-base font-semibold text-slate-200">
              Knowledge Graph is Empty
            </h3>
            <p className="text-xs text-slate-400 max-w-sm mt-1 mb-5">
              No entity or fact nodes exist in FalkorDB yet. Add memories to extract triples and view the interactive graph.
            </p>
            <Link
              href="/memory"
              className="flex items-center space-x-2 px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 text-xs font-semibold text-white shadow-md shadow-blue-500/20"
            >
              <PlusCircle size={15} />
              <span>Add First Memory</span>
            </Link>
          </div>
        ) : null}

        {/* React Flow Canvas */}
        <ReactFlow
          nodes={displayNodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onNodeClick={onNodeClick}
          nodeTypes={nodeTypes}
          fitView
          attributionPosition="bottom-left"
          minZoom={0.2}
          maxZoom={2.5}
        >
          <Background color="#1e293b" gap={20} size={1} variant={BackgroundVariant.Dots} />
          <Controls />
          <MiniMap
            nodeColor={(n) => {
              const type = (n.data as CustomNodeData)?.nodeType;
              if (type === "Entity") return "#8b5cf6";
              if (type === "Fact") return "#10b981";
              return "#64748b";
            }}
            maskColor="rgba(15, 23, 42, 0.7)"
          />
        </ReactFlow>

        {/* Selected Node Details Drawer */}
        {selectedNode && (
          <div className="absolute top-4 right-4 z-20 w-80 max-h-[85%] bg-slate-900/95 border border-slate-700/80 rounded-2xl p-4 shadow-2xl backdrop-blur-md flex flex-col overflow-y-auto">
            <div className="flex items-center justify-between pb-2.5 border-b border-slate-800 mb-3">
              <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                <Tag size={12} className="text-blue-400" />
                Node Properties
              </span>
              <button
                onClick={() => setSelectedNode(null)}
                className="text-slate-400 hover:text-white p-1 rounded hover:bg-slate-800"
              >
                <X size={15} />
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <div>
                <span className="text-[10px] text-slate-400 uppercase font-semibold">
                  Type / Label
                </span>
                <div className="text-sm font-bold text-slate-100 flex items-center gap-2 mt-0.5">
                  <span>{selectedNode.label}</span>
                  {selectedNode.status && (
                    <span
                      className={`text-[10px] px-2 py-0.5 rounded font-medium ${
                        selectedNode.status === "active"
                          ? "bg-emerald-950/80 text-emerald-400 border border-emerald-800/40"
                          : "bg-amber-950/80 text-amber-400 border border-amber-800/40"
                      }`}
                    >
                      {selectedNode.status}
                    </span>
                  )}
                </div>
              </div>

              <div>
                <span className="text-[10px] text-slate-400 uppercase font-semibold">
                  Internal Node ID
                </span>
                <div className="font-mono text-[11px] text-slate-300 break-all bg-slate-950 p-1.5 rounded border border-slate-800 mt-0.5">
                  {selectedNode.id}
                </div>
              </div>

              {selectedNode.label === "Entity" && (
                <>
                  <div>
                    <span className="text-[10px] text-slate-400 uppercase font-semibold">
                      Entity Name
                    </span>
                    <div className="text-slate-200 font-semibold text-sm mt-0.5">
                      {selectedNode.name}
                    </div>
                  </div>
                  {selectedNode.type && (
                    <div>
                      <span className="text-[10px] text-slate-400 uppercase font-semibold">
                        Entity Category
                      </span>
                      <div className="text-slate-300 capitalize mt-0.5">
                        {selectedNode.type}
                      </div>
                    </div>
                  )}
                </>
              )}

              {selectedNode.label === "Fact" && (
                <>
                  <div className="p-2.5 rounded-xl bg-slate-950 border border-slate-800 space-y-1.5">
                    <div>
                      <span className="text-[10px] text-slate-400">Subject:</span>{" "}
                      <span className="text-blue-400 font-semibold">
                        {selectedNode.subject}
                      </span>
                    </div>
                    <div>
                      <span className="text-[10px] text-slate-400">Predicate:</span>{" "}
                      <span className="text-purple-400 font-mono">
                        {selectedNode.predicate}
                      </span>
                    </div>
                    <div>
                      <span className="text-[10px] text-slate-400">Object:</span>{" "}
                      <span className="text-emerald-400 font-semibold">
                        {selectedNode.object_value}
                      </span>
                    </div>
                  </div>

                  {selectedNode.confidence !== undefined && (
                    <div>
                      <span className="text-[10px] text-slate-400 uppercase font-semibold">
                        Confidence Score
                      </span>
                      <div className="text-slate-200 mt-0.5">
                        {Math.round(selectedNode.confidence * 100)}%
                      </div>
                    </div>
                  )}
                </>
              )}

              {selectedNode.label === "Source" && (
                <>
                  <div>
                    <span className="text-[10px] text-slate-400 uppercase font-semibold">
                      Original Text Snippet
                    </span>
                    <div className="text-slate-300 italic bg-slate-950 p-2.5 rounded-lg border border-slate-800 mt-1 leading-relaxed">
                      "{selectedNode.text}"
                    </div>
                  </div>
                  {selectedNode.source_type && (
                    <div>
                      <span className="text-[10px] text-slate-400 uppercase font-semibold">
                        Source Provenance Type
                      </span>
                      <div className="text-slate-300 capitalize mt-0.5">
                        {selectedNode.source_type}
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
