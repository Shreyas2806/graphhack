/**
 * src/lib/api.ts — Reusable GraphMind backend API client.
 * Connects directly to the FastAPI server at NEXT_PUBLIC_API_BASE_URL.
 */

import {
  HealthResponse,
  RootResponse,
  MemoryRequest,
  MemoryResponse,
  AskRequest,
  AskResponse,
  MemoryListResponse,
  GraphExportResponse,
  VerifyRequest,
  VerifyResponse,
} from "@/types";

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/+$/, "") || "http://127.0.0.1:8000";

export class ApiError extends Error {
  status: number;
  data?: unknown;

  constructor(message: string, status: number, data?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.data = data;
  }
}

async function fetchJson<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  try {
    const res = await fetch(url, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...(options?.headers || {}),
      },
    });

    let data: unknown;
    const contentType = res.headers.get("content-type");
    if (contentType && contentType.includes("application/json")) {
      data = await res.json();
    } else {
      const text = await res.text();
      data = { text };
    }

    if (!res.ok) {
      const errorMsg =
        typeof data === "object" && data !== null && "detail" in data
          ? String((data as { detail: unknown }).detail)
          : typeof data === "object" && data !== null && "error" in data
          ? String((data as { error: unknown }).error)
          : `HTTP Error ${res.status}: ${res.statusText}`;
      throw new ApiError(errorMsg, res.status, data);
    }

    return data as T;
  } catch (err: unknown) {
    if (err instanceof ApiError) {
      throw err;
    }
    const message =
      err instanceof Error
        ? err.message
        : "Failed to connect to GraphMind backend. Ensure the backend server is running.";
    throw new ApiError(
      `${message} (Target: ${url})`,
      0
    );
  }
}

/** Check backend and FalkorDB connectivity */
export async function getHealth(): Promise<HealthResponse> {
  return fetchJson<HealthResponse>("/health");
}

/** Get root API metadata */
export async function getRoot(): Promise<RootResponse> {
  return fetchJson<RootResponse>("/");
}

/** Submit natural-language memory to extract and store in FalkorDB */
export async function storeMemory(text: string): Promise<MemoryResponse> {
  const body: MemoryRequest = { text };
  return fetchJson<MemoryResponse>("/memory", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

/** Ask question grounded in stored knowledge graph and verified by Verification Agent */
export async function askQuestion(question: string): Promise<AskResponse> {
  const body: AskRequest = { question };
  return fetchJson<AskResponse>("/ask", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

/** Get paginated list of stored facts */
export async function listMemories(
  page: number = 1,
  pageSize: number = 20
): Promise<MemoryListResponse> {
  return fetchJson<MemoryListResponse>(
    `/memory?page=${page}&page_size=${pageSize}`
  );
}

/** Export graph nodes and edges for explorer visualization */
export async function getGraphData(limit: number = 200): Promise<GraphExportResponse> {
  return fetchJson<GraphExportResponse>(`/graph?limit=${limit}`);
}

/** Explicitly verify an answer against evidence */
export async function verifyAnswer(req: VerifyRequest): Promise<VerifyResponse> {
  return fetchJson<VerifyResponse>("/verify", {
    method: "POST",
    body: JSON.stringify(req),
  });
}
