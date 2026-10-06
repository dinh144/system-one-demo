import React, { useState } from 'react';
import { ReplayData, ModelInfo } from '../lib/types';
import { Play, SkipBack, SkipForward, RotateCcw } from 'lucide-react';
import { DecisionCard } from './DecisionCard';
import { MemoryStore } from './MemoryStore';

interface ReplayTabProps {
  replayData: ReplayData | null;
  models: ModelInfo[];
}

export function ReplayTab({ replayData, models }: ReplayTabProps) {
  const [currentStep, setCurrentStep] = useState<number>(0);

  if (!replayData || !replayData.turns || replayData.turns.length === 0) {
    return (
      <div className="w-full p-8 text-center bg-surface border border-line rounded-card text-ink">
        <h2 className="text-xl font-semibold mb-2">Chưa có dữ liệu phát lại</h2>
        <p className="text-base text-ink-2">
          Hệ thống không tìm thấy tập tin ghi phát lại (`data/replay.json`). Hãy chạy thu thập dữ liệu phát lại trên máy đo chuẩn để hiển thị tab này.
        </p>
      </div>
    );
  }

  const turns = replayData.turns;
  // Steps from 1 to turns.length
  const displayedTurns = currentStep === 0 ? turns : turns.slice(0, currentStep);
  const latestTurn = displayedTurns[displayedTurns.length - 1];

  const engineIds = ['laya', 'kev-0.8b', 'llm:qwen2.5:0.5b'];

  return (
    <div className="w-full flex flex-col gap-6 p-2">
      {/* Replay Controls Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-surface p-4 border border-line rounded-card">
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2">
            <span className="font-semibold text-lg text-ink">
              Phát lại kịch bản ({turns.length} lượt)
            </span>
            <span className="text-xs font-mono text-ink-2 bg-bg px-2 py-0.5 rounded-chip border border-line">
              {replayData.recorded_on}
            </span>
          </div>
          <p className="text-base text-ink-2">
            Thời điểm ghi: {replayData.recorded_at}
          </p>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          <button
            type="button"
            onClick={() => setCurrentStep(1)}
            disabled={currentStep <= 1 && currentStep !== 0}
            title="Về lượt đầu"
            className="min-h-[44px] px-3 bg-surface border border-line rounded-card text-ink hover:bg-bg disabled:opacity-50 transition-colors"
          >
            <RotateCcw className="w-4 h-4" aria-hidden="true" />
            <span className="sr-only">Lượt đầu</span>
          </button>
          <button
            type="button"
            onClick={() => setCurrentStep((prev) => Math.max(1, (prev || turns.length) - 1))}
            disabled={currentStep === 1}
            title="Lượt trước"
            className="min-h-[44px] px-3 bg-surface border border-line rounded-card text-ink hover:bg-bg disabled:opacity-50 transition-colors"
          >
            <SkipBack className="w-4 h-4" aria-hidden="true" />
            <span className="sr-only">Lượt trước</span>
          </button>
          <span className="font-mono text-sm px-3 py-1 bg-bg rounded-card border border-line">
            Lượt {currentStep === 0 ? turns.length : currentStep} / {turns.length}
          </span>
          <button
            type="button"
            onClick={() => setCurrentStep((prev) => Math.min(turns.length, (prev || 1) + 1))}
            disabled={currentStep === turns.length || currentStep === 0}
            title="Lượt sau"
            className="min-h-[44px] px-3 bg-surface border border-line rounded-card text-ink hover:bg-bg disabled:opacity-50 transition-colors"
          >
            <SkipForward className="w-4 h-4" aria-hidden="true" />
            <span className="sr-only">Lượt sau</span>
          </button>
          <button
            type="button"
            onClick={() => setCurrentStep(0)}
            title="Hiển thị tất cả"
            className="min-h-[44px] px-4 bg-ink text-surface rounded-card font-semibold text-sm hover:bg-ink/90 transition-colors"
          >
            Xem tất cả
          </button>
        </div>
      </div>

      {/* Latest Observation Banner */}
      {latestTurn && (
        <div className="p-4 bg-bg border border-line rounded-card flex flex-col gap-1 text-ink">
          <span className="text-xs font-mono text-ink-2 uppercase font-semibold">
            Quan sát lượt #{latestTurn.turn.i}
          </span>
          <p className="text-base font-medium">&quot;{latestTurn.turn.text}&quot;</p>
        </div>
      )}

      {/* Columns for Engines */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {engineIds.map((engId) => {
          const modelInfo = models.find((m) => m.id === engId);
          // Find latest memory from the displayed turns
          const lastDecision = latestTurn?.decisions.find((d) => d.engine === engId);
          const memories = lastDecision?.memory || [];

          return (
            <div
              key={engId}
              className="flex flex-col gap-4 bg-surface border border-line rounded-card p-4"
            >
              <div className="border-b border-line pb-2 flex items-center justify-between">
                <div>
                  <h3 className="text-xl font-semibold text-ink">
                    {modelInfo?.label || engId}
                  </h3>
                  <span className="text-xs text-ink-2 font-mono">
                    {modelInfo?.params || '—'} · {replayData.recorded_on}
                  </span>
                </div>
                <span className="px-2.5 py-0.5 rounded-chip text-xs font-semibold uppercase bg-no/10 text-no border border-no/30">
                  phát lại
                </span>
              </div>

              <MemoryStore engineId={engId} memories={memories} />

              <div className="flex flex-col gap-2.5 overflow-y-auto max-h-[640px] pr-1">
                {[...displayedTurns].reverse().map((t) => {
                  const dec = t.decisions.find((d) => d.engine === engId);
                  if (!dec) return null;
                  return (
                    <DecisionCard
                      key={t.turn.i}
                      turnIndex={t.turn.i}
                      engineId={engId}
                      decision={dec}
                      isPending={false}
                    />
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
