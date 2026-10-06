import React, { useState } from 'react';
import { ModelInfo, BenchmarkResult } from '../lib/types';
import { streamBenchmark } from '../lib/api';
import { Gauge, Play, CheckCircle2, AlertCircle } from 'lucide-react';

interface BenchmarkTabProps {
  models: ModelInfo[];
  benchmarkData: BenchmarkResult | null;
  onBenchmarkComplete: (result: BenchmarkResult) => void;
}

export function BenchmarkTab({
  models,
  benchmarkData,
  onBenchmarkComplete,
}: BenchmarkTabProps) {
  const [isRunning, setIsRunning] = useState(false);
  const [progressMsg, setProgressMsg] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const readyEngines = models
    .filter((m) => m.status === 'ready')
    .map((m) => m.id);

  const handleRunBenchmark = async () => {
    if (isRunning || readyEngines.length === 0) return;
    setIsRunning(true);
    setProgressMsg('Bắt đầu đo đạc trên máy này...');
    setErrorMsg(null);

    try {
      await streamBenchmark(readyEngines, {
        onProgress: (p) => {
          setProgressMsg(
            `Đang đo ${p.engine}: ${p.current}/${p.total} ca...`
          );
        },
        onResult: (result) => {
          onBenchmarkComplete(result);
          setProgressMsg('Hoàn tất đo đạc.');
        },
        onError: (err) => {
          setErrorMsg(err.message || 'Lỗi trong quá trình chạy kiểm chuẩn.');
        },
      });
    } catch (err: any) {
      setErrorMsg(err.message || 'Lỗi kết nối khi chạy đo.');
    } finally {
      setIsRunning(false);
    }
  };

  return (
    <div className="w-full flex flex-col gap-6 p-2">
      {/* Tab Header & Action */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-surface p-6 border border-line rounded-card">
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2">
            <Gauge className="w-6 h-6 text-ink-2" aria-hidden="true" />
            <h2 className="text-xl font-semibold text-ink tracking-tight">
              Bảng đo hiệu năng và độ chính xác
            </h2>
          </div>
          <p className="text-base text-ink-2">
            nhãn tham chiếu (n = 30), chưa kiểm định độc lập
          </p>
        </div>

        <button
          type="button"
          onClick={handleRunBenchmark}
          disabled={isRunning || readyEngines.length === 0}
          data-testid="run-benchmark-btn"
          className="min-h-[48px] px-6 py-3 bg-ink text-surface rounded-card font-semibold text-base flex items-center justify-center gap-2 hover:bg-ink/90 disabled:opacity-50 transition-all focus-visible:outline-none"
        >
          <Play className="w-5 h-5 fill-current" aria-hidden="true" />
          <span>
            {isRunning ? 'Đang đo đạc...' : 'Chạy đo trên máy này'}
          </span>
        </button>
      </div>

      {/* Progress status */}
      {progressMsg && (
        <div
          role="status"
          className="p-4 bg-bg border border-line rounded-card text-sm text-ink font-mono flex items-center gap-2"
        >
          <span className="inline-block w-2.5 h-2.5 rounded-full bg-ink animate-pulse" />
          <span>{progressMsg}</span>
        </div>
      )}

      {errorMsg && (
        <div
          role="alert"
          className="p-4 bg-bg border border-no/40 rounded-card text-sm text-no flex items-center gap-2"
        >
          <AlertCircle className="w-5 h-5 shrink-0 text-no" aria-hidden="true" />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* Benchmark Table */}
      <div className="overflow-x-auto bg-surface border border-line rounded-card">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="border-b border-line bg-bg text-sm font-semibold text-ink-2">
              <th scope="col" className="p-4">Mô hình</th>
              <th scope="col" className="p-4 font-mono text-right">p50 (ms)</th>
              <th scope="col" className="p-4 font-mono text-right">p95 (ms)</th>
              <th scope="col" className="p-4 font-mono text-right">n</th>
              <th scope="col" className="p-4 font-mono text-right">
                should_store
                <span className="block text-xs font-normal text-ink-2">
                  (20 ca dương tính / 30)
                </span>
              </th>
              <th scope="col" className="p-4 font-mono text-right">
                redundant
                <span className="block text-xs font-normal text-ink-2">
                  (3 ca dương tính / 30)
                </span>
              </th>
              <th scope="col" className="p-4 font-mono text-right">
                obsolete
                <span className="block text-xs font-normal text-ink-2">
                  (3 ca dương tính / 30)
                </span>
              </th>
              <th scope="col" className="p-4 font-mono text-right">
                Độ chính xác chung
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line text-sm text-ink font-mono">
            {models.map((model) => {
              const stat = benchmarkData?.engines?.[model.id];
              return (
                <tr key={model.id} className="hover:bg-bg/40 transition-colors">
                  <td className="p-4 font-sans font-medium text-base text-ink">
                    <div className="flex items-center gap-2">
                      <span>{model.label}</span>
                      <span className="text-xs text-ink-2 font-mono">
                        ({model.params})
                      </span>
                    </div>
                  </td>
                  <td className="p-4 text-right tabular-nums">
                    {stat ? Math.round(stat.p50_ms) : '—'}
                  </td>
                  <td className="p-4 text-right tabular-nums">
                    {stat ? Math.round(stat.p95_ms) : '—'}
                  </td>
                  <td className="p-4 text-right tabular-nums">
                    {stat ? stat.n : '—'}
                  </td>
                  <td className="p-4 text-right tabular-nums">
                    {stat?.breakdown?.should_store
                      ? `${(stat.breakdown.should_store.accuracy * 100).toFixed(1)}%`
                      : '—'}
                  </td>
                  <td className="p-4 text-right tabular-nums">
                    {stat?.breakdown?.redundant
                      ? `${(stat.breakdown.redundant.accuracy * 100).toFixed(1)}%`
                      : '—'}
                  </td>
                  <td className="p-4 text-right tabular-nums">
                    {stat?.breakdown?.obsolete
                      ? `${(stat.breakdown.obsolete.accuracy * 100).toFixed(1)}%`
                      : '—'}
                  </td>
                  <td className="p-4 text-right tabular-nums font-semibold">
                    {stat?.accuracy
                      ? `${(stat.accuracy.value * 100).toFixed(1)}%`
                      : '—'}
                  </td>
                </tr>
              );
            })}

            {/* Static GPT-4o-mini Reference Row (Citing Jev-Mem arXiv 2609.23986) */}
            <tr className="bg-bg/60 text-ink-2 italic border-t-2 border-line">
              <td className="p-4 font-sans text-base">
                GPT-4o-mini (tham chiếu từ bài báo Jev-Mem arXiv 2609.23986)
              </td>
              <td colSpan={7} className="p-4 text-right font-sans not-italic text-sm">
                xem Bảng 1 của bài báo
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      {/* Accuracy Caveat Box */}
      <div className="p-4 bg-bg border border-line rounded-card flex flex-col gap-2">
        <p className="text-base text-ink font-medium">
          Với redundant (3 ca) và obsolete (3 ca), độ chính xác chưa có ý nghĩa thống kê.
        </p>
        <p className="text-base text-ink-2">
          Số ca tham chiếu trong tập dữ liệu (n = 30) tập trung vào phân loại should_store (20 ca dương tính). Kết quả redundant và obsolete chỉ mang tính chất tham khảo định tính sơ bộ.
        </p>
      </div>
    </div>
  );
}
