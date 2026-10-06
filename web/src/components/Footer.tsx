import React from 'react';
import { HardwareInfo } from '../lib/types';

interface FooterProps {
  hardware: HardwareInfo | null;
}

export function Footer({ hardware }: FooterProps) {
  return (
    <footer className="w-full border-t border-line bg-surface mt-6 py-4 px-6 text-sm text-ink-2">
      <div className="max-w-[1840px] mx-auto flex flex-col gap-3">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-2 border-b border-line/60 pb-3">
          <p className="font-mono text-base text-ink">
            <strong>Quy tắc trích xuất candidate:</strong> trong trò chuyện trực tiếp, candidate là ký ức gần nhất có tiền tố 4 ký tự viết thường trùng nhiều nhất với quan sát hiện tại (ví dụ: &quot;hike&quot; khớp &quot;hiking&quot;); để trống nếu độ trùng bằng 0.
          </p>
          <span className="shrink-0 italic text-base">
            nhãn tham chiếu (n = 30), chưa kiểm định độc lập
          </span>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-4 text-xs font-mono">
          <div>
            Hệ điều hành: {hardware?.os || 'Đang kiểm tra'} · CPU: {hardware?.cpu || 'Chưa rõ'} · RAM: {hardware?.ram_gb ? `${hardware.ram_gb} GB` : '—'}
          </div>
          <div>
            Thực nghiệm phi thương mại cho đề cương nghiên cứu Hệ Thống 1 (System-One)
          </div>
        </div>
      </div>
    </footer>
  );
}
