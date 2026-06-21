import type { JnaoReportData } from "../api/types";

const KEY = "jnao_test_history";

export interface HistoryEntry {
  encoding: string;
  uid: number;
  type: number;
  talent: string;
  property: string;
  create_time: string;
  record_id: number;
  response: JnaoReportData;
  saved_at: string;
}

export function getHistory(): HistoryEntry[] {
  try {
    const raw = localStorage.getItem(KEY) || "[]";
    const arr = JSON.parse(raw);
    if (!Array.isArray(arr)) return [];
    return arr.sort((a, b) => (b.record_id || 0) - (a.record_id || 0));
  } catch {
    return [];
  }
}

export function removeHistory(recordId: number) {
  try {
    const list = getHistory().filter((e) => e.record_id !== recordId);
    localStorage.setItem(KEY, JSON.stringify(list));
  } catch { /* ignore */ }
}
