import React from 'react';
import { HardwareInfo } from '../lib/types';

interface HeaderProps {
  hardware: HardwareInfo | null;
}

export function Header({ hardware }: HeaderProps) {
  const hardwareSummary = hardware ? (
    <>
      <span>
        {hardware.gpu
          ? `Thiết bị: GPU (${hardware.gpu.name || 'NVIDIA'})`
          : `Thiết bị: CPU (${hardware.cpu.split('@')[0].trim() || 'Hệ thống'})`}
      </span>
      <span>·</span>
      <span>
        CUDA: {hardware.gpu?.cuda ? 'Có' : 'Không'}
      </span>
      <span>·</span>
      <span>Python {hardware.python}</span>
      <span>·</span>
      <span>PyTorch: {hardware.torch}</span>
      <span>·</span>
      <span>
        Ollama:{' '}
        {hardware.ollama?.reachable
          ? `Sẵn sàng (${hardware.ollama.models?.length || 0} mô hình)`
          : 'Không kết nối'}
      </span>
    </>
  ) : (
    <span>Đang tải thông tin phần cứng...</span>
  );

  return (
    <header className="w-full border-b border-line bg-surface px-6 py-4">
      <div className="max-w-[1840px] mx-auto flex flex-col md:flex-row md:items-baseline justify-between gap-3">
        <div className="flex items-baseline gap-4">
          <h1 className="text-xl font-semibold text-ink tracking-tight">
            System-One
          </h1>
          <span className="text-sm text-ink-2 hidden sm:inline">
            Công cụ đo lường kiểm soát ký ức agent AI
          </span>
        </div>

        <div
          className="text-sm text-ink-2 font-mono flex flex-wrap items-center gap-x-2 gap-y-1"
          aria-label="Thông số môi trường chạy"
        >
          {hardwareSummary}
        </div>
      </div>
    </header>
  );
}
