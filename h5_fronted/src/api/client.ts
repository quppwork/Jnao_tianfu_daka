// API client — talent test & AI chat

import type { JnaoReportData } from "./types";

const BASE = "/api";
const LOG = import.meta.env.DEV;

function log(method: string, path: string, body?: unknown) {
  if (!LOG) return;
  console.log(
    `%c[API] %c${method} %c${path}`,
    "color:#6C5CE7;font-weight:bold",
    "color:#333",
    "color:#666",
    body ? body : "",
  );
}

function logRes(path: string, ok: boolean, data?: unknown) {
  if (!LOG) return;
  const style = ok ? "color:#10b981" : "color:#ef4444";
  console.log(`%c[API] %c${ok ? "OK" : "ERR"} %c${path}`, "color:#6C5CE7;font-weight:bold", style, "color:#666", data ?? "");
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  log("POST", path, body);
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    const msg = (err as { detail?: string }).detail || `HTTP ${res.status}`;
    logRes(path, false, { status: res.status, detail: msg });
    throw new Error(msg);
  }
  const json = await res.json();
  logRes(path, true, json);
  return json;
}

// ── JNAO Report ──

export async function fetchReport(answer: string, uid: number, type: number): Promise<JnaoReportData> {
  const res = await post<{ code: number; data: JnaoReportData }>("/talent/report", { answer, uid, type });
  return res.data;
}

// ── AI Chat ──

export interface ChatResponse {
  answer: string;
  sources?: { title: string; url?: string }[];
  answer_mode?: string;
}

export async function sendChat(message: string, context?: string): Promise<ChatResponse> {
  const body: Record<string, unknown> = {
    message,
    user_id: "report_user",
    user_department: "技术部",
  };
  if (context) {
    body.message = `${message}\n\n[报告背景]\n${context}`;
  }
  const res = await post<{ code: number; data: ChatResponse }>("/chat", body);
  return res.data;
}
