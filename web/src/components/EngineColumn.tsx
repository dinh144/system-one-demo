import React from 'react';
import { ModelInfo, MemoryItem, TurnDecisionEvent } from '../lib/types';
import { MemoryStore } from './MemoryStore';
import { DecisionCard } from './DecisionCard';
import { AlertCircle, Cpu } from 'lucide-react';

interface EngineColumnProps {
  engineId: string;
  engineInfo?: ModelInfo;
  allModels: ModelInfo[];
  isLlmColumn?: boolean;
  selectedLlmTag?: string;
  onSelectLlmTag?: (tag: string) => void;
  ollamaReachable?: boolean;
  memories: MemoryItem[];
  turns: TurnDecisionEvent[];
  differsPerTurn: Record<number, boolean>;
}

export function EngineColumn({
  engineId,
  engineInfo,
  allModels,
  isLlmColumn,
  selectedLlmTag,
  onSelectLlmTag,
  ollamaReachable = true,
  memories,
  turns,
  differsPerTurn,
}: EngineColumnProps) {
  const llmModels = allModels.filter((m) => m.kind === 'llm');
  const isUnavailable = engineInfo?.status === 'unavailable' || (isLlmColumn && !ollamaReachable);

  const getStatusChip = () => {
    if (isUnavailable) {
      return (
        <span
          data-testid={`status-${engineId}`}
          className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-chip text-sm font-semibold tracking-wide uppercase bg-no/10 text-no border border-no/30"
        >
          không khả dụng
        </span>
      );
    }
    if (engineInfo?.status === 'loading') {
      return (
        <span
          data-testid={`status-${engineId}`}
          className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-chip text-sm font-semibold tracking-wide uppercase bg-unsure/15 text-unsure border border-unsure/30"
        >
          đang tải
        </span>
      );
    }
    return (
      <span
        data-testid={`status-${engineId}`}
        className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-chip text-sm font-semibold tracking-wide uppercase bg-yes/15 text-yes border border-yes/30"
      >
        sẵn sàng
      </span>
    );
  };

  // Sort turns with newest on top
  const reversedTurns = [...turns].reverse();

  return (
    <div
      data-testid={`column-${engineId}`}
      className="flex-1 min-w-[280px] flex flex-col gap-4 bg-surface border border-line rounded-card p-4"
    >
      {/* Column Header */}
      <header className="flex flex-col gap-2 border-b border-line pb-3">
        <div className="flex items-center justify-between gap-2 flex-wrap">
          <div className="flex items-center gap-2">
            <Cpu className="w-5 h-5 text-ink-2" aria-hidden="true" />
            <h2 className="text-xl font-semibold text-ink tracking-tight">
              {engineInfo?.label || engineId}
            </h2>
          </div>
          {getStatusChip()}
        </div>

        <div className="flex items-center justify-between text-sm text-ink-2 font-mono">
          <span>
            {engineInfo?.params ? `${engineInfo.params}` : '—'} ·{' '}
            {engineInfo?.device ? engineInfo.device.toUpperCase() : 'CPU'}
          </span>
          <span className="text-xs">
            {engineInfo?.kind === 'system-one' ? 'Hệ Thống 1' : 'LLM'}
          </span>
        </div>

        {/* LLM Selector Dropdown */}
        {isLlmColumn && llmModels.length > 0 && (
          <div className="mt-1">
            <label htmlFor="llm-select" className="sr-only">
              Chọn mô hình LLM
            </label>
            <select
              id="llm-select"
              value={selectedLlmTag || engineId}
              onChange={(e) => onSelectLlmTag?.(e.target.value)}
              className="w-full min-h-[44px] px-3 py-2 bg-bg border border-line rounded-card text-sm text-ink font-mono focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
            >
              {llmModels.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.label} ({m.params}) {m.status === 'unavailable' ? '— Chưa sẵn sàng' : ''}
                </option>
              ))}
            </select>
          </div>
        )}
      </header>

      {/* Unavailable State Notice */}
      {isUnavailable && (
        <div
          role="alert"
          className="p-4 bg-bg border border-line rounded-card flex flex-col gap-2 text-ink text-sm"
        >
          <div className="flex items-center gap-2 font-semibold text-no">
            <AlertCircle className="w-5 h-5 text-no shrink-0" aria-hidden="true" />
            <span>Mô hình không khả dụng</span>
          </div>
          <p className="text-base text-ink-2">
            {isLlmColumn && !ollamaReachable
              ? 'Dịch vụ Ollama không phản hồi. Hãy khởi chạy Ollama (ollama serve) và tải mô hình.'
              : engineInfo?.reason || 'Mô hình chưa được cấu hình hoặc tải xong trên máy này.'}
          </p>
        </div>
      )}

      {/* Memory Store */}
      <MemoryStore engineId={engineId} memories={memories} />

      {/* Decision Cards List (Newest on top, independent scroll) */}
      <div className="flex flex-col gap-2.5 overflow-y-auto max-h-[560px] pr-1">
        {reversedTurns.length === 0 ? (
          <div className="py-8 text-center text-ink-2 text-sm italic">
            Chưa có quyết định nào
          </div>
        ) : (
          reversedTurns.map((turnEvent) => {
            const decision = turnEvent.decisions[engineId];
            const errorMsg = turnEvent.errors[engineId];
            const isPending = turnEvent.isPending[engineId];
            const isRunning = turnEvent.isRunning ? Boolean(turnEvent.isRunning[engineId]) : true;
            const differs = differsPerTurn[turnEvent.turnIndex];

            return (
              <DecisionCard
                key={turnEvent.turnIndex}
                turnIndex={turnEvent.turnIndex}
                engineId={engineId}
                decision={decision}
                errorMessage={errorMsg}
                isPending={isPending}
                isRunning={isRunning}
                differs={differs}
              />
            );
          })
        )}
      </div>
    </div>
  );
}
