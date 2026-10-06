import React, { useState } from 'react';
import { ChevronDown, ChevronUp, Database } from 'lucide-react';
import { MemoryItem } from '../lib/types';

interface MemoryStoreProps {
  engineId: string;
  memories: MemoryItem[];
}

export function MemoryStore({ engineId, memories }: MemoryStoreProps) {
  const [isOpen, setIsOpen] = useState(true);

  const activeCount = memories.filter((m) => m.status === 'active').length;

  return (
    <section
      aria-label={`Bộ nhớ của ${engineId}`}
      className="w-full bg-surface border border-line rounded-card overflow-hidden"
    >
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        aria-expanded={isOpen}
        className="w-full min-h-[44px] px-4 py-3 flex items-center justify-between gap-2 text-left bg-surface hover:bg-bg/60 transition-colors focus-visible:outline-none"
      >
        <div className="flex items-center gap-2">
          <Database className="w-4 h-4 text-ink-2" aria-hidden="true" />
          <span className="font-semibold text-base text-ink">
            Ký ức đã lưu ({memories.length})
          </span>
          {activeCount > 0 && (
            <span className="text-sm text-ink-2">({activeCount} kích hoạt)</span>
          )}
        </div>
        <span className="text-ink-2">
          {isOpen ? (
            <ChevronUp className="w-5 h-5" aria-hidden="true" />
          ) : (
            <ChevronDown className="w-5 h-5" aria-hidden="true" />
          )}
        </span>
      </button>

      {isOpen && (
        <div className="p-4 border-t border-line bg-bg/40 max-h-60 overflow-y-auto space-y-2">
          {memories.length === 0 ? (
            <p className="text-base text-ink-2 italic py-2 text-center">
              chưa có ký ức nào
            </p>
          ) : (
            <ul className="space-y-2 list-none p-0 m-0">
              {memories.map((mem, idx) => {
                const isReplaced = mem.status === 'replaced';
                return (
                  <li
                    key={mem.id || idx}
                    className={`p-2.5 rounded-card text-sm border ${
                      isReplaced
                        ? 'bg-line/20 border-line/60 text-ink-2 line-through'
                        : 'bg-surface border-line text-ink'
                    }`}
                  >
                    <div className="flex flex-col gap-1">
                      <span>{mem.text}</span>
                      {isReplaced && mem.replaced_by && (
                        <span className="no-underline text-xs text-ink-2 not-italic">
                          thay bằng &quot;{mem.replaced_by}&quot;
                        </span>
                      )}
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      )}
    </section>
  );
}
