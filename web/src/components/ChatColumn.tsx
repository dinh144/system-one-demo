import React, { useState, useRef, useEffect } from 'react';
import { Play, Send, RotateCcw, MessageSquare } from 'lucide-react';
import { ScenarioTurn } from '../lib/types';

interface ChatColumnProps {
  scenarioTurns: ScenarioTurn[];
  onRunScenario: () => void;
  onSendTurn: (text: string) => void;
  onResetSession: () => void;
  isRunning: boolean;
  messages: Array<{ id: string | number; text: string; speaker: string; source?: string }>;
  currentTurnIndex: number;
}

export function ChatColumn({
  scenarioTurns,
  onRunScenario,
  onSendTurn,
  onResetSession,
  isRunning,
  messages,
  currentTurnIndex,
}: ChatColumnProps) {
  const [inputText, setInputText] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages.length]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputText.trim() || isRunning) return;
    onSendTurn(inputText.trim());
    setInputText('');
  };

  return (
    <div className="w-full lg:w-[320px] xl:w-[360px] 2xl:w-[400px] shrink-0 flex flex-col gap-4 bg-surface border border-line rounded-card p-4">
      {/* Header and Controls */}
      <div className="flex flex-col gap-3 border-b border-line pb-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <MessageSquare className="w-5 h-5 text-ink-2" aria-hidden="true" />
            <h2 className="text-xl font-semibold text-ink tracking-tight">
              Hội thoại {messages.length > 0 && (
                <span className="text-sm font-mono font-normal text-ink-2">
                  ({messages.length} lượt)
                </span>
              )}
            </h2>
          </div>

          <button
            type="button"
            onClick={onResetSession}
            disabled={isRunning}
            title="Làm mới bộ nhớ các mô hình và xóa lịch sử"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-card text-sm text-ink-2 border border-line hover:bg-bg disabled:opacity-50 transition-colors focus-visible:outline-none"
          >
            <RotateCcw className="w-4 h-4" aria-hidden="true" />
            <span>Làm mới</span>
          </button>
        </div>

        {/* Prominent starter button */}
        <button
          type="button"
          onClick={onRunScenario}
          disabled={isRunning}
          data-testid="run-scenario-btn"
          className="w-full min-h-[48px] px-4 py-3 bg-ink text-surface rounded-card font-semibold text-base flex items-center justify-center gap-2 hover:bg-ink/90 disabled:opacity-50 transition-all focus-visible:outline-none"
        >
          <Play className="w-5 h-5 fill-current" aria-hidden="true" />
          <span>
            {isRunning
              ? `Đang chạy kịch bản (${currentTurnIndex}/10)...`
              : 'Chạy kịch bản 10 lượt'}
          </span>
        </button>

        {/* Secondary free-text box */}
        <form onSubmit={handleSubmit} className="flex gap-2">
          <label htmlFor="user-turn-input" className="sr-only">
            Nhập tin nhắn người dùng
          </label>
          <input
            id="user-turn-input"
            type="text"
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            disabled={isRunning}
            placeholder="Nhập phát ngôn tự do..."
            className="flex-1 min-h-[44px] px-3 py-2 bg-bg border border-line rounded-card text-base text-ink placeholder:text-ink-2/60 focus-visible:outline-none"
          />
          <button
            type="submit"
            disabled={!inputText.trim() || isRunning}
            title="Gửi phát ngôn"
            className="min-h-[44px] px-4 bg-surface border border-line rounded-card text-ink font-semibold flex items-center justify-center hover:bg-bg disabled:opacity-50 transition-colors focus-visible:outline-none"
          >
            <Send className="w-5 h-5" aria-hidden="true" />
            <span className="sr-only">Gửi</span>
          </button>
        </form>
      </div>

      {/* Message History */}
      <div
        className="flex-1 flex flex-col gap-2.5 overflow-y-auto max-h-[560px] p-1"
        aria-label="Lịch sử hội thoại"
      >
        {messages.length === 0 ? (
          <div className="py-8 text-center text-ink-2 text-sm italic">
            Chưa có tin nhắn nào. Bấm &quot;Chạy kịch bản 10 lượt&quot; hoặc gõ tin nhắn vào ô trên để bắt đầu.
          </div>
        ) : (
          messages.map((msg, idx) => (
            <div
              key={msg.id || idx}
              data-testid="chat-message"
              data-turn-number={idx + 1}
              className="p-2.5 bg-bg border border-line rounded-card flex flex-col gap-1 text-ink"
            >
              <div className="flex items-center justify-between text-xs text-ink-2 font-mono">
                <span className="font-semibold text-ink uppercase">
                  Lượt #{idx + 1} ({msg.speaker})
                </span>
                {msg.source && <span>{msg.source}</span>}
              </div>
              <p className="text-base leading-relaxed break-words">{msg.text}</p>
            </div>
          ))
        )}
        <div ref={messagesEndRef} />
      </div>
    </div>
  );
}
