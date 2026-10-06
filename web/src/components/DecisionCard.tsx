import React from 'react';
import { Check, Minus, HelpCircle, Plus, RefreshCw, XCircle, AlertTriangle } from 'lucide-react';
import { DecisionData, AnswerItem } from '../lib/types';
import { LatencyClock } from './LatencyClock';

interface DecisionCardProps {
  turnIndex: number;
  engineId: string;
  decision?: DecisionData;
  errorMessage?: string;
  isPending: boolean;
  isRunning?: boolean;
  differs?: boolean;
}

export function DecisionCard({
  turnIndex,
  engineId,
  decision,
  errorMessage,
  isPending,
  isRunning = true,
  differs,
}: DecisionCardProps) {
  // If mid-turn error
  if (errorMessage) {
    return (
      <article
        aria-label={`Lỗi lượt ${turnIndex} trên mô hình ${engineId}`}
        className="w-full bg-surface border border-line rounded-card p-3 flex flex-col gap-2 shadow-none"
      >
        <div className="flex items-center justify-between border-b border-line pb-1.5">
          <span className="font-mono text-sm text-ink-2 font-medium">
            Lượt #{turnIndex}
          </span>
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-chip text-xs font-semibold tracking-wide uppercase bg-no/10 text-no">
            <XCircle className="w-3.5 h-3.5" aria-hidden="true" />
            LỖI LƯỢT
          </span>
        </div>
        <div className="p-2.5 bg-bg border border-line rounded-card text-ink text-sm">
          <p className="font-semibold text-no flex items-center gap-1.5 text-sm">
            <AlertTriangle className="w-4 h-4 text-no shrink-0" aria-hidden="true" />
            Đã xảy ra lỗi khi xử lý lượt này
          </p>
          <p className="mt-0.5 text-ink-2 break-words text-sm">{errorMessage}</p>
        </div>
      </article>
    );
  }

  // Pending placeholder state
  if (isPending && !decision) {
    return (
      <article
        aria-label={`Đang xử lý lượt ${turnIndex} trên mô hình ${engineId}`}
        className="w-full bg-surface border border-line rounded-card p-3 flex flex-col gap-2 shadow-none transition-all"
      >
        <div className="flex items-center justify-between border-b border-line pb-1.5">
          <span className="font-mono text-sm text-ink-2 font-medium">
            Lượt #{turnIndex}
          </span>
          <span className="text-xs font-semibold text-ink-2 uppercase tracking-wide">
            Đang đánh giá
          </span>
        </div>

        <div className="space-y-2 py-1">
          <div className="h-4 bg-line/50 rounded animate-pulse w-3/4" />
          <div className="h-4 bg-line/40 rounded animate-pulse w-5/6" />
          <div className="h-4 bg-line/40 rounded animate-pulse w-2/3" />
        </div>

        <div className="flex justify-end pt-1.5 border-t border-line/50">
          {isRunning ? (
            <LatencyClock isPending={true} />
          ) : (
            <span data-testid="queued-label" className="text-ink-2 text-base">đang chờ đến lượt</span>
          )}
        </div>
      </article>
    );
  }

  if (!decision) {
    return null;
  }

  // Render Action Chip
  const renderActionChip = (action: string) => {
    switch (action) {
      case 'add':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-chip text-xs font-semibold tracking-wide uppercase bg-yes/15 text-yes border border-yes/30">
            <Plus className="w-3.5 h-3.5 stroke-[2.5]" aria-hidden="true" />
            LƯU MỚI (add)
          </span>
        );
      case 'replace':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-chip text-xs font-semibold tracking-wide uppercase bg-ink/10 text-ink border border-ink/20">
            <RefreshCw className="w-3.5 h-3.5 stroke-[2.5]" aria-hidden="true" />
            THAY THẾ (replace)
          </span>
        );
      case 'ask':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-chip text-xs font-semibold tracking-wide uppercase bg-unsure/15 text-unsure border border-unsure/30">
            <HelpCircle className="w-3.5 h-3.5 stroke-[2.5]" aria-hidden="true" />
            không chắc, nên hỏi lại (ask)
          </span>
        );
      case 'skip':
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-chip text-xs font-semibold tracking-wide uppercase bg-no/10 text-no border border-no/20">
            <Minus className="w-3.5 h-3.5 stroke-[2.5]" aria-hidden="true" />
            BỎ QUA (skip)
          </span>
        );
    }
  };

  // Render Label Chip (Never conveyed by colour alone: always icon + text)
  const renderLabelChip = (label: 'yes' | 'no' | 'unsure') => {
    if (label === 'yes') {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-chip text-xs font-semibold tracking-[0.04em] uppercase bg-yes/15 text-yes border border-yes/25">
          <Check className="w-3.5 h-3.5 stroke-[2.5]" aria-hidden="true" />
          <span>CÓ</span>
        </span>
      );
    }
    if (label === 'unsure') {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-chip text-xs font-semibold tracking-[0.04em] uppercase bg-unsure/15 text-unsure border border-unsure/25">
          <HelpCircle className="w-3.5 h-3.5 stroke-[2.5]" aria-hidden="true" />
          <span>KHÔNG CHẮC</span>
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-chip text-xs font-semibold tracking-[0.04em] uppercase bg-no/10 text-no border border-no/20">
        <Minus className="w-3.5 h-3.5 stroke-[2.5]" aria-hidden="true" />
        <span>KHÔNG</span>
      </span>
    );
  };

  // Render Question Row
  const renderRow = (
    key: 'should_store' | 'redundant' | 'obsolete',
    labelEn: string,
    glossVi: string,
    item: AnswerItem
  ) => {
    const rawVal = Number.isFinite(item.p) ? item.p.toFixed(2) : '—';
    const percent = Math.max(0, Math.min(100, Math.round(item.p * 100)));

    let barColor = 'bg-no';
    if (item.label === 'yes') barColor = 'bg-yes';
    else if (item.label === 'unsure') barColor = 'bg-unsure';

    return (
      <div className="flex flex-col gap-1 py-1.5 border-b border-line/40 last:border-b-0">
        <div className="flex items-center justify-between gap-1 flex-wrap">
          <div className="flex items-center gap-1.5">
            <span className="font-mono font-medium text-sm text-ink">
              {labelEn}
            </span>
            <span className="text-sm text-ink-2">({glossVi})</span>
            {item.probability_source === 'hard_label' && (
              <span
                title="Xác suất từ nhãn cứng (không có logprob)"
                className="px-1.5 py-0.2 rounded-chip text-xs font-semibold uppercase bg-unsure/15 text-unsure border border-unsure/30"
              >
                nhãn cứng
              </span>
            )}
          </div>
          {renderLabelChip(item.label)}
        </div>

        {/* Probability bar with ticks at 0.35 and 0.65 */}
        <div className="flex items-center gap-2">
          <div
            className="relative flex-1 h-2.5 bg-line/40 rounded-bar overflow-hidden border border-line"
            role="progressbar"
            aria-valuenow={percent}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label={`Xác suất ${labelEn}`}
          >
            {/* Unsure band highlight between 35% and 65% */}
            <div
              className="absolute top-0 bottom-0 left-[35%] w-[30%] bg-unsure/15 pointer-events-none"
              title="Vùng không chắc (0.35 - 0.65)"
            />
            {/* Tick at 0.35 */}
            <div
              className="absolute top-0 bottom-0 left-[35%] w-px bg-ink/40 z-10 pointer-events-none"
              title="Ngưỡng 0.35"
            />
            {/* Tick at 0.65 */}
            <div
              className="absolute top-0 bottom-0 left-[65%] w-px bg-ink/40 z-10 pointer-events-none"
              title="Ngưỡng 0.65"
            />
            {/* Filled bar */}
            <div
              className={`h-full ${barColor} transition-all`}
              style={{ width: `${percent}%` }}
            />
          </div>

          <span className="w-14 text-right font-mono tabular-nums text-xl lg:text-2xl font-semibold text-ink">
            {rawVal}
          </span>
        </div>
      </div>
    );
  };

  return (
    <article
      aria-label={`Quyết định lượt ${turnIndex} của ${engineId}`}
      className={`w-full bg-surface rounded-card p-3 flex flex-col gap-2 shadow-none transition-all ${
        differs
          ? 'border-2 border-differ'
          : 'border border-line'
      }`}
    >
      <div className="flex items-center justify-between border-b border-line pb-1.5">
        <div className="flex items-center gap-2">
          <span className="font-mono text-sm font-semibold text-ink">
            Lượt #{turnIndex}
          </span>
          {differs && (
            <span
              data-testid="differ-badge"
              className="px-2 py-0.5 rounded-chip text-xs font-semibold uppercase tracking-wider text-differ border border-differ bg-differ/10"
            >
              khác nhau
            </span>
          )}
        </div>
        <div>{renderActionChip(decision.action)}</div>
      </div>

      <div className="flex flex-col">
        {renderRow(
          'should_store',
          'should_store',
          'có nên lưu không',
          decision.answers.should_store
        )}
        {renderRow(
          'redundant',
          'redundant',
          'đã có chưa',
          decision.answers.redundant
        )}
        {renderRow(
          'obsolete',
          'obsolete',
          'đã cũ chưa',
          decision.answers.obsolete
        )}
      </div>

      <div className="flex items-center justify-between pt-1.5 border-t border-line/60">
        <span className="text-xs text-ink-2 font-mono">
          {decision.gen_tokens ? `${decision.gen_tokens} tokens` : 'không sinh văn bản'}
        </span>
        <LatencyClock
          isPending={isPending}
          serverLatencyMs={decision.latency_ms}
        />
      </div>
    </article>
  );
}
