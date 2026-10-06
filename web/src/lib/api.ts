import {
  HealthResponse,
  HardwareInfo,
  ModelInfo,
  ScenarioData,
  DecisionData,
  BenchmarkResult,
  ReplayData,
} from './types';

// The API origin is fixed at build time and never taken from the page URL: a link carrying an override would let
// another server feed this page its own decisions, hardware and replay data. Empty means same origin.
export function getApiBase(): string {
  return process.env.NEXT_PUBLIC_API_BASE || '';
}

export const API_BASE = getApiBase();

export async function fetchHealth(): Promise<HealthResponse> {
  const base = getApiBase();
  const res = await fetch(`${base}/api/health`, { cache: 'no-store' });
  if (!res.ok) {
    throw new Error(`Health check failed with status ${res.status}`);
  }
  return res.json();
}

export async function fetchHardware(): Promise<HardwareInfo> {
  const base = getApiBase();
  const res = await fetch(`${base}/api/hardware`, { cache: 'no-store' });
  if (!res.ok) {
    throw new Error(`Lỗi khi lấy thông tin phần cứng (${res.status})`);
  }
  return res.json();
}

export async function fetchModels(): Promise<ModelInfo[]> {
  const base = getApiBase();
  const res = await fetch(`${base}/api/models`, { cache: 'no-store' });
  if (!res.ok) {
    throw new Error(`Lỗi khi tải danh sách mô hình (${res.status})`);
  }
  const data = await res.json();
  if (Array.isArray(data)) return data;
  if (data && Array.isArray(data.models)) return data.models;
  return [];
}

export async function fetchScenario(): Promise<ScenarioData> {
  const base = getApiBase();
  const res = await fetch(`${base}/api/scenario`, { cache: 'no-store' });
  if (!res.ok) {
    throw new Error(`Lỗi khi tải kịch bản (${res.status})`);
  }
  return res.json();
}

export async function createSession(engines: string[]): Promise<string> {
  const base = getApiBase();
  const res = await fetch(`${base}/api/session`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ engines }),
  });
  if (!res.ok) {
    throw new Error(`Lỗi khởi tạo phiên (${res.status})`);
  }
  const data = await res.json();
  return data.session_id;
}

export async function resetSession(sessionId: string): Promise<boolean> {
  const base = getApiBase();
  const res = await fetch(`${base}/api/session/${sessionId}/reset`, {
    method: 'POST',
  });
  if (!res.ok) {
    throw new Error(`Lỗi làm mới phiên (${res.status})`);
  }
  const data = await res.json();
  return !!data.ok;
}

export async function fetchReplay(): Promise<ReplayData | null> {
  const base = getApiBase();
  try {
    const res = await fetch(`${base}/api/replay`, { cache: 'no-store' });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export interface StreamTurnCallbacks {
  onTurn?: (data: { i: number; text: string }) => void;
  onDecision?: (data: DecisionData) => void;
  onEngineError?: (data: { engine: string; message: string }) => void;
  onEngineStart?: (data: { engine: string }) => void;
  onDone?: () => void;
  onError?: (err: Error) => void;
}

export async function streamTurn(
  sessionId: string,
  text: string,
  callbacks: StreamTurnCallbacks
): Promise<void> {
  const base = getApiBase();
  const res = await fetch(`${base}/api/session/${sessionId}/turn`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
  });

  if (!res.ok || !res.body) {
    const err = new Error(`Gửi lượt hội thoại thất bại (${res.status})`);
    callbacks.onError?.(err);
    throw err;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder('utf-8');
  let buffer = '';

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      const events = buffer.split('\n\n');
      buffer = events.pop() || '';

      for (const rawEvent of events) {
        if (!rawEvent.trim()) continue;
        const lines = rawEvent.split('\n');
        let eventType = 'message';
        let dataStr = '';

        for (const line of lines) {
          if (line.startsWith('event:')) {
            eventType = line.slice(6).trim();
          } else if (line.startsWith('data:')) {
            dataStr = line.slice(5).trim();
          }
        }

        if (!dataStr) continue;

        try {
          const parsed = JSON.parse(dataStr);
          if (eventType === 'turn') {
            callbacks.onTurn?.(parsed);
          } else if (eventType === 'decision') {
            callbacks.onDecision?.(parsed);
          } else if (eventType === 'engine_error') {
            callbacks.onEngineError?.(parsed);
          } else if (eventType === 'engine_start') {
            callbacks.onEngineStart?.(parsed);
          } else if (eventType === 'done') {
            callbacks.onDone?.();
          }
        } catch (e) {
          console.warn('Lỗi phân tích SSE data:', e, dataStr);
        }
      }
    }
    callbacks.onDone?.();
  } catch (err: any) {
    callbacks.onError?.(err);
    throw err;
  }
}

export interface StreamBenchmarkCallbacks {
  onProgress?: (data: { engine: string; current: number; total: number }) => void;
  onResult?: (data: BenchmarkResult) => void;
  onError?: (err: Error) => void;
}

export async function streamBenchmark(
  engines: string[],
  callbacks: StreamBenchmarkCallbacks
): Promise<void> {
  const base = getApiBase();
  const res = await fetch(`${base}/api/benchmark`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ engines, case_ids: null, warmup: 3 }),
  });

  if (!res.ok || !res.body) {
    const err = new Error(`Chạy đo thất bại (${res.status})`);
    callbacks.onError?.(err);
    throw err;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder('utf-8');
  let buffer = '';

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      const events = buffer.split('\n\n');
      buffer = events.pop() || '';

      for (const rawEvent of events) {
        if (!rawEvent.trim()) continue;
        const lines = rawEvent.split('\n');
        let eventType = 'message';
        let dataStr = '';

        for (const line of lines) {
          if (line.startsWith('event:')) {
            eventType = line.slice(6).trim();
          } else if (line.startsWith('data:')) {
            dataStr = line.slice(5).trim();
          }
        }

        if (!dataStr) continue;

        try {
          const parsed = JSON.parse(dataStr);
          if (eventType === 'progress') {
            callbacks.onProgress?.(parsed);
          } else if (eventType === 'result') {
            const normalized: BenchmarkResult = parsed.engines
              ? parsed
              : { engines: parsed };
            callbacks.onResult?.(normalized);
          }
        } catch (e) {
          console.warn('Lỗi phân tích SSE benchmark data:', e, dataStr);
        }
      }
    }
  } catch (err: any) {
    callbacks.onError?.(err);
    throw err;
  }
}
