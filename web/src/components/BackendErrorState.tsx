import React from 'react';
import { AlertCircle, RefreshCw, Terminal } from 'lucide-react';
import { API_BASE } from '../lib/api';

interface BackendErrorStateProps {
  onRetry: () => void;
  isRetrying: boolean;
}

export function BackendErrorState({ onRetry, isRetrying }: BackendErrorStateProps) {
  return (
    <main
      role="main"
      aria-label="Lỗi kết nối máy chủ"
      className="min-h-screen w-full bg-bg flex items-center justify-center p-6"
    >
      <div className="max-w-2xl w-full bg-surface border border-line rounded-card p-8 flex flex-col gap-6">
        <div className="flex items-center gap-3 text-no">
          <AlertCircle className="w-8 h-8 shrink-0 text-no" aria-hidden="true" />
          <h1 className="text-2xl font-semibold text-ink">
            Không thể kết nối với máy chủ backend
          </h1>
        </div>

        <p className="text-base text-ink-2 leading-relaxed">
          Giao diện không nhận được phản hồi từ backend tại địa chỉ{' '}
          <code className="px-2 py-1 bg-bg border border-line rounded font-mono text-sm text-ink">
            {API_BASE}
          </code>
          . Vui lòng đảm bảo tiến trình backend đang chạy.
        </p>

        <div className="bg-bg border border-line rounded-card p-4 flex flex-col gap-2">
          <div className="flex items-center gap-2 text-sm font-semibold text-ink-2">
            <Terminal className="w-4 h-4" aria-hidden="true" />
            <span>Lệnh khởi chạy máy chủ:</span>
          </div>
          <pre className="font-mono text-sm bg-surface p-3 border border-line rounded text-ink overflow-x-auto">
            python -m demo run
          </pre>
          <span className="text-xs text-ink-2">
            Hoặc để chạy máy chủ giả lập trong lúc phát triển giao diện:
          </span>
          <pre className="font-mono text-sm bg-surface p-3 border border-line rounded text-ink overflow-x-auto">
            PORT=8000 node web/mock/server.mjs
          </pre>
        </div>

        <div className="flex items-center justify-end gap-3 pt-2">
          <button
            type="button"
            onClick={onRetry}
            disabled={isRetrying}
            className="min-h-[44px] px-6 py-2.5 bg-ink text-surface rounded-card font-semibold text-base flex items-center gap-2 hover:bg-ink/90 disabled:opacity-50 transition-colors focus-visible:outline-none"
          >
            <RefreshCw
              className={`w-4 h-4 ${isRetrying ? 'animate-spin' : ''}`}
              aria-hidden="true"
            />
            <span>{isRetrying ? 'Đang thử lại...' : 'Thử kết nối lại'}</span>
          </button>
        </div>
      </div>
    </main>
  );
}
