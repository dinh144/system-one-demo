export type ModelStatus = 'ready' | 'loading' | 'unavailable';

export interface ModelInfo {
  id: string;
  label: string;
  params: string;
  kind: 'system-one' | 'llm';
  device: string;
  status: ModelStatus;
  reason: string | null;
}

export interface HardwareInfo {
  os: string;
  cpu: string;
  ram_gb: number;
  gpu: {
    name: string;
    vram_gb: number;
    cuda: boolean;
  } | null;
  python: string;
  torch: string;
  ollama: {
    reachable: boolean;
    models: string[];
  };
}

export interface ScenarioTurn {
  i: number;
  speaker: 'user' | 'assistant';
  text: string;
  source?: string;
}

export interface ScenarioData {
  id: string;
  title: string;
  turns: ScenarioTurn[];
  attribution?: string;
}

export interface AnswerItem {
  p: number;
  label: 'yes' | 'no' | 'unsure';
  probability_source: 'model' | 'logprob' | 'hard_label';
}

export type MemoryAction = 'add' | 'replace' | 'skip' | 'ask';

export interface MemoryItem {
  id: string;
  text: string;
  status: 'active' | 'replaced';
  replaced_by?: string;
}

export interface DecisionData {
  engine: string;
  source: 'live' | 'replay';
  latency_ms: number;
  device: string;
  answers: {
    should_store: AnswerItem;
    redundant: AnswerItem;
    obsolete: AnswerItem;
  };
  action: MemoryAction;
  memory: MemoryItem[];
  gen_tokens: number | null;
}

export interface TurnDecisionEvent {
  turnIndex: number;
  turnText: string;
  decisions: Record<string, DecisionData>;
  errors: Record<string, string>;
  isPending: Record<string, boolean>;
  // Set only when the backend sends engine_start events; undefined means the backend starts every engine at once.
  isRunning?: Record<string, boolean>;
}

export interface BenchmarkAccuracy {
  value: number;
  n: number;
  note: string;
}

export interface BenchmarkStat {
  p50_ms: number;
  p95_ms: number;
  n: number;
  accuracy: BenchmarkAccuracy;
  breakdown?: {
    should_store?: { accuracy: number; positives: number; total: number };
    redundant?: { accuracy: number; positives: number; total: number };
    obsolete?: { accuracy: number; positives: number; total: number };
  };
}

export interface BenchmarkResult {
  engines: Record<string, BenchmarkStat>;
}

export interface ReplayTurn {
  turn: {
    i: number;
    text: string;
  };
  decisions: DecisionData[];
}

export interface ReplayData {
  source: 'replay';
  recorded_on: string;
  recorded_at: string;
  turns: ReplayTurn[];
}

export interface HealthResponse {
  ok: boolean;
  mock: boolean;
}
