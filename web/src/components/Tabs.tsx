import React from 'react';

export type TabKey = 'live' | 'benchmark' | 'replay';

interface TabsProps {
  activeTab: TabKey;
  onTabChange: (tab: TabKey) => void;
  hasReplay: boolean;
}

export function Tabs({ activeTab, onTabChange, hasReplay }: TabsProps) {
  return (
    <nav aria-label="Các chế độ làm việc" className="w-full border-b border-line bg-surface px-6">
      <div
        role="tablist"
        aria-label="Chọn tab hiển thị"
        className="max-w-[1840px] mx-auto flex items-center gap-2"
      >
        <button
          role="tab"
          id="tab-live"
          aria-selected={activeTab === 'live'}
          aria-controls="panel-live"
          tabIndex={activeTab === 'live' ? 0 : -1}
          type="button"
          onClick={() => onTabChange('live')}
          className={`min-h-[48px] px-6 py-3 font-semibold text-base transition-colors border-b-2 flex items-center gap-2 focus-visible:outline-none ${
            activeTab === 'live'
              ? 'border-ink text-ink'
              : 'border-transparent text-ink-2 hover:text-ink hover:border-line'
          }`}
        >
          Trực tiếp
        </button>

        <button
          role="tab"
          id="tab-benchmark"
          aria-selected={activeTab === 'benchmark'}
          aria-controls="panel-benchmark"
          tabIndex={activeTab === 'benchmark' ? 0 : -1}
          type="button"
          onClick={() => onTabChange('benchmark')}
          className={`min-h-[48px] px-6 py-3 font-semibold text-base transition-colors border-b-2 flex items-center gap-2 focus-visible:outline-none ${
            activeTab === 'benchmark'
              ? 'border-ink text-ink'
              : 'border-transparent text-ink-2 hover:text-ink hover:border-line'
          }`}
        >
          Bảng đo
        </button>

        {hasReplay && (
          <button
            role="tab"
            id="tab-replay"
            aria-selected={activeTab === 'replay'}
            aria-controls="panel-replay"
            tabIndex={activeTab === 'replay' ? 0 : -1}
            type="button"
            onClick={() => onTabChange('replay')}
            className={`min-h-[48px] px-6 py-3 font-semibold text-base transition-colors border-b-2 flex items-center gap-2 focus-visible:outline-none ${
              activeTab === 'replay'
                ? 'border-ink text-ink'
                : 'border-transparent text-ink-2 hover:text-ink hover:border-line'
            }`}
          >
            Phát lại
          </button>
        )}
      </div>
    </nav>
  );
}
