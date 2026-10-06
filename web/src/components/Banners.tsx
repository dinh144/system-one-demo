import React from 'react';

interface BannersProps {
  isMock: boolean;
  isReplay: boolean;
  recordedOn?: string;
}

export function Banners({ isMock, isReplay, recordedOn }: BannersProps) {
  return (
    <div className="w-full flex flex-col gap-1">
      {isMock && (
        <aside
          role="status"
          aria-label="Thông báo máy chủ giả lập"
          className="w-full px-6 py-3 border-b border-replay/30 bg-replay-tint text-replay font-semibold text-center text-base tracking-wide flex items-center justify-center gap-2"
        >
          <span className="inline-block w-2.5 h-2.5 rounded-full bg-replay" aria-hidden="true" />
          <span>MÁY CHỦ GIẢ LẬP, số liệu không thật</span>
        </aside>
      )}

      {isReplay && (
        <aside
          role="status"
          aria-label="Thông báo phát lại đo đạc"
          className="w-full px-6 py-3 border-b border-replay/30 bg-replay-tint text-replay font-semibold text-center text-base tracking-wide flex items-center justify-center gap-2"
        >
          <span className="inline-block w-2.5 h-2.5 rounded-full bg-replay" aria-hidden="true" />
          <span>{`Phát lại: đo trên ${recordedOn || 'mock'}, không phải máy này`}</span>
        </aside>
      )}
    </div>
  );
}
