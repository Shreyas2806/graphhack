"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import {
  LayoutDashboard,
  MessageSquareCode,
  PlusCircle,
  Share2,
  Workflow,
  Menu,
  X,
  Database,
  ExternalLink,
} from "lucide-react";
import { getHealth, API_BASE_URL } from "@/lib/api";
import { HealthResponse } from "@/types";

const NAV_ITEMS = [
  {
    name: "Overview",
    href: "/",
    icon: LayoutDashboard,
    description: "System stats & recent activity",
  },
  {
    name: "Memory Chat",
    href: "/chat",
    icon: MessageSquareCode,
    description: "Grounded Q&A with Verification",
  },
  {
    name: "Add Memory",
    href: "/memory",
    icon: PlusCircle,
    description: "Extract & persist graph triples",
  },
  {
    name: "Graph Explorer",
    href: "/graph",
    icon: Share2,
    description: "Interactive React Flow graph",
  },
  {
    name: "Agent Workflow",
    href: "/workflow",
    icon: Workflow,
    description: "Multi-agent execution traces",
  },
];

export function Navigation() {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [loadingHealth, setLoadingHealth] = useState(true);

  useEffect(() => {
    let mounted = true;
    async function check() {
      try {
        const res = await getHealth();
        if (mounted) {
          setHealth(res);
          setLoadingHealth(false);
        }
      } catch {
        if (mounted) {
          setHealth({
            status: "disconnected",
            falkordb: { ok: false },
          });
          setLoadingHealth(false);
        }
      }
    }
    check();
    const interval = setInterval(check, 10000);
    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, []);

  const isConnected = health?.falkordb?.ok === true;

  return (
    <>
      {/* Mobile Top Bar */}
      <div className="lg:hidden flex items-center justify-between px-4 py-3 bg-slate-900/90 border-b border-slate-800 backdrop-blur sticky top-0 z-50">
        <Link href="/" className="flex items-center space-x-2.5">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-blue-600 to-violet-600 flex items-center justify-center text-white font-bold text-sm shadow-md shadow-blue-500/20">
            GM
          </div>
          <div>
            <span className="font-bold text-slate-100 text-base">GraphMind</span>
            <span className="text-[10px] text-blue-400 font-mono ml-2 px-1.5 py-0.5 rounded bg-blue-950/60 border border-blue-800/40">
              v0.1.0
            </span>
          </div>
        </Link>
        <button
          onClick={() => setMobileOpen(!mobileOpen)}
          className="p-1.5 rounded-lg text-slate-400 hover:text-slate-100 hover:bg-slate-800 focus:outline-none"
        >
          {mobileOpen ? <X size={20} /> : <Menu size={20} />}
        </button>
      </div>

      {/* Sidebar for Desktop & Mobile Overlay */}
      <aside
        className={`fixed inset-y-0 left-0 z-40 w-64 bg-slate-950/95 border-r border-slate-800/80 flex flex-col transition-transform duration-200 ease-in-out lg:translate-x-0 ${
          mobileOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        {/* Brand Header */}
        <div className="p-5 border-b border-slate-800/80 flex items-center justify-between">
          <Link href="/" className="flex items-center space-x-3 group">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-blue-600 via-indigo-600 to-violet-600 flex items-center justify-center text-white font-bold text-base shadow-lg shadow-blue-500/20 group-hover:scale-105 transition-transform">
              <Share2 size={18} />
            </div>
            <div>
              <div className="flex items-center space-x-1.5">
                <span className="font-bold text-slate-100 text-lg tracking-tight">GraphMind</span>
                <span className="text-[9px] text-violet-300 font-mono px-1 py-0.2 rounded bg-violet-950/60 border border-violet-800/50">
                  AI
                </span>
              </div>
              <p className="text-[11px] text-slate-400">Memory & Decision System</p>
            </div>
          </Link>
          <button
            onClick={() => setMobileOpen(false)}
            className="lg:hidden text-slate-400 hover:text-slate-200"
          >
            <X size={18} />
          </button>
        </div>

        {/* Navigation Links */}
        <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
          <div className="px-3 pb-2 text-[10px] font-semibold tracking-wider text-slate-400 uppercase">
            Workspaces
          </div>
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const active = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setMobileOpen(false)}
                className={`flex items-center space-x-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                  active
                    ? "bg-blue-600/15 text-blue-400 border border-blue-500/30"
                    : "text-slate-300 hover:text-slate-100 hover:bg-slate-900 border border-transparent"
                }`}
              >
                <Icon
                  size={18}
                  className={active ? "text-blue-400" : "text-slate-400"}
                />
                <div className="flex-1 min-w-0">
                  <div className="leading-snug">{item.name}</div>
                  <div className="text-[11px] text-slate-400 truncate font-normal">
                    {item.description}
                  </div>
                </div>
              </Link>
            );
          })}
        </nav>

        {/* Backend & DB Health Card */}
        <div className="p-3 m-3 rounded-xl bg-slate-900/90 border border-slate-800/80">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[11px] font-medium text-slate-400 flex items-center gap-1.5">
              <Database size={13} className="text-slate-400" /> FalkorDB Engine
            </span>
            {loadingHealth ? (
              <span className="flex h-2 w-2 relative">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-slate-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-slate-500"></span>
              </span>
            ) : isConnected ? (
              <span className="flex items-center gap-1 text-[10px] font-medium text-emerald-400">
                <span className="h-2 w-2 rounded-full bg-emerald-500"></span> Live
              </span>
            ) : (
              <span className="flex items-center gap-1 text-[10px] font-medium text-rose-400">
                <span className="h-2 w-2 rounded-full bg-rose-500"></span> Offline
              </span>
            )}
          </div>
          <div className="text-[11px] font-mono text-slate-300 truncate">
            {API_BASE_URL}
          </div>
          <a
            href={`${API_BASE_URL}/docs`}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-2.5 flex items-center justify-between text-[11px] text-blue-400 hover:text-blue-300 transition-colors pt-2 border-t border-slate-800"
          >
            <span>FastAPI Docs (Swagger)</span>
            <ExternalLink size={12} />
          </a>
        </div>
      </aside>

      {/* Backdrop for mobile */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/60 backdrop-blur-sm lg:hidden"
          onClick={() => setMobileOpen(false)}
        />
      )}
    </>
  );
}
