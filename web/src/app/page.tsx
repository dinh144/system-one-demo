'use client';

import React, { useEffect, useState, useCallback, useMemo } from 'react';
import {
  HealthResponse,
  HardwareInfo,
  ModelInfo,
  ScenarioData,
  ReplayData,
  TurnDecisionEvent,
  MemoryItem,
  BenchmarkResult,
} from '../lib/types';
import {
  fetchHealth,
  fetchHardware,
  fetchModels,
  fetchScenario,
  fetchReplay,
  createSession,
  resetSession,
  streamTurn,
} from '../lib/api';
import { Header } from '../components/Header';
import { Banners } from '../components/Banners';
import { Tabs, TabKey } from '../components/Tabs';
import { ChatColumn } from '../components/ChatColumn';
import { EngineColumn } from '../components/EngineColumn';
import { BenchmarkTab } from '../components/BenchmarkTab';
import { ReplayTab } from '../components/ReplayTab';
import { Footer } from '../components/Footer';
import { BackendErrorState } from '../components/BackendErrorState';

export default function Home() {
  // Global & system state
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [hardware, setHardware] = useState<HardwareInfo | null>(null);
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [scenario, setScenario] = useState<ScenarioData | null>(null);
  const [replay, setReplay] = useState<ReplayData | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);

  const [isLoadingInitial, setIsLoadingInitial] = useState(true);
  const [isBackendUnreachable, setIsBackendUnreachable] = useState(false);
  const [isRetrying, setIsRetrying] = useState(false);

  // Active navigation tab
  const [activeTab, setActiveTab] = useState<TabKey>('live');

  // Selected LLM model tag
  const [selectedLlmTag, setSelectedLlmTag] = useState<string>('llm:qwen2.5:0.5b');

  // Chat and Turns state
  const [turnEvents, setTurnEvents] = useState<TurnDecisionEvent[]>([]);
  const [messages, setMessages] = useState<
    Array<{ id: string | number; text: string; speaker: string; source?: string }>
  >([]);
  const [memories, setMemories] = useState<Record<string, MemoryItem[]>>({
    laya: [],
    'kev-0.8b': [],
  });
  const [isRunning, setIsRunning] = useState(false);
  const [currentScenarioTurnIndex, setCurrentScenarioTurnIndex] = useState(0);

  // Benchmark results cache
  const [benchmarkData, setBenchmarkData] = useState<BenchmarkResult | null>(null);

  // Active engines list
  const activeEngineIds = useMemo(() => {
    return ['laya', 'kev-0.8b', selectedLlmTag];
  }, [selectedLlmTag]);

  // Initial data loading
  const loadInitialData = useCallback(async () => {
    setIsRetrying(true);
    try {
      const [healthData, hwData, modelsData, scData, repData] = await Promise.all([
        fetchHealth(),
        fetchHardware().catch(() => null),
        fetchModels().catch(() => []),
        fetchScenario().catch(() => null),
        fetchReplay().catch(() => null),
      ]);

      setHealth(healthData);
      setHardware(hwData);
      setModels(modelsData);
      setScenario(scData);
      setReplay(repData);

      // Pick default LLM model
      const llmModels = modelsData.filter((m) => m.kind === 'llm');
      const firstReadyLlm = llmModels.find((m) => m.status === 'ready');
      if (firstReadyLlm) {
        setSelectedLlmTag(firstReadyLlm.id);
      } else if (llmModels.length > 0) {
        setSelectedLlmTag(llmModels[0].id);
      }

      // Create session
      const targetEngines = [
        'laya',
        'kev-0.8b',
        firstReadyLlm ? firstReadyLlm.id : 'llm:qwen2.5:0.5b',
      ];
      const sid = await createSession(targetEngines);
      setSessionId(sid);

      setIsBackendUnreachable(false);
    } catch (err) {
      console.error('Lỗi kết nối backend:', err);
      setIsBackendUnreachable(true);
    } finally {
      setIsLoadingInitial(false);
      setIsRetrying(false);
    }
  }, []);

  useEffect(() => {
    loadInitialData();
  }, [loadInitialData]);

  // Update session when LLM selection changes
  const handleSelectLlmTag = async (newTag: string) => {
    setSelectedLlmTag(newTag);
    try {
      const sid = await createSession(['laya', 'kev-0.8b', newTag]);
      setSessionId(sid);
      // Reset memories for the new configuration
      setMemories((prev) => ({
        ...prev,
        [newTag]: prev[newTag] || [],
      }));
    } catch (e) {
      console.warn('Lỗi khi cập nhật phiên với mô hình mới:', e);
    }
  };

  // Reset session
  const handleResetSession = async () => {
    if (sessionId) {
      try {
        await resetSession(sessionId);
      } catch (e) {
        console.warn('Reset error:', e);
      }
    }
    setTurnEvents([]);
    setMessages([]);
    setMemories({
      laya: [],
      'kev-0.8b': [],
      [selectedLlmTag]: [],
    });
    setCurrentScenarioTurnIndex(0);
  };

  // Run a single turn
  const runTurn = useCallback(
    async (text: string, sourceAttribution?: string, turnNumberOverride?: number) => {
      let currentSid = sessionId;
      if (!currentSid) {
        try {
          currentSid = await createSession(activeEngineIds);
          setSessionId(currentSid);
        } catch {
          setIsBackendUnreachable(true);
          return;
        }
      }

      const nextTurnNum = turnNumberOverride ?? (turnEvents.length + 1);

      // Add user message to chat
      setMessages((prev) => [
        ...prev,
        {
          id: nextTurnNum,
          speaker: 'Người dùng',
          text,
          source: sourceAttribution,
        },
      ]);

      // Initialize pending state for each engine
      const pendingMap: Record<string, boolean> = {};
      for (const id of activeEngineIds) {
        pendingMap[id] = true;
      }

      const newTurnEvent: TurnDecisionEvent = {
        turnIndex: nextTurnNum,
        turnText: text,
        decisions: {},
        errors: {},
        isPending: pendingMap,
      };

      setTurnEvents((prev) => [...prev, newTurnEvent]);

      try {
        await streamTurn(currentSid, text, {
          onDecision: (dec) => {
            setTurnEvents((prev) =>
              prev.map((item) => {
                if (item.turnIndex !== nextTurnNum) return item;
                return {
                  ...item,
                  decisions: {
                    ...item.decisions,
                    [dec.engine]: dec,
                  },
                  isPending: {
                    ...item.isPending,
                    [dec.engine]: false,
                  },
                };
              })
            );

            // Update memory store for engine
            if (dec.memory) {
              setMemories((prev) => ({
                ...prev,
                [dec.engine]: dec.memory,
              }));
            }
          },
          onEngineStart: ({ engine }) => {
            setTurnEvents((prev) =>
              prev.map((item) => {
                if (item.turnIndex !== nextTurnNum) return item;
                const base: Record<string, boolean> = item.isRunning ?? Object.fromEntries(Object.keys(item.isPending).map((k) => [k, false]));
                return { ...item, isRunning: { ...base, [engine]: true } };
              })
            );
          },
          onEngineError: ({ engine, message }) => {
            setTurnEvents((prev) =>
              prev.map((item) => {
                if (item.turnIndex !== nextTurnNum) return item;
                return {
                  ...item,
                  errors: {
                    ...item.errors,
                    [engine]: message,
                  },
                  isPending: {
                    ...item.isPending,
                    [engine]: false,
                  },
                };
              })
            );
          },
          onDone: () => {
            // Ensure all pending flags are cleared
            setTurnEvents((prev) =>
              prev.map((item) => {
                if (item.turnIndex !== nextTurnNum) return item;
                const clearedPending: Record<string, boolean> = {};
                for (const key of Object.keys(item.isPending)) {
                  clearedPending[key] = false;
                }
                return {
                  ...item,
                  isPending: clearedPending,
                };
              })
            );
          },
          onError: (err) => {
            console.error('Lỗi lượt SSE:', err);
          },
        });
      } catch (err) {
        console.error('Lỗi khi gửi lượt:', err);
      }
    },
    [sessionId, activeEngineIds, turnEvents.length]
  );

  // Run the full 10-turn scenario sequentially
  const handleRunScenario = async () => {
    if (!scenario || !scenario.turns || scenario.turns.length === 0 || isRunning) {
      return;
    }

    setIsRunning(true);
    await handleResetSession();

    const turns = scenario.turns;
    for (let i = 0; i < turns.length; i++) {
      const scTurn = turns[i];
      setCurrentScenarioTurnIndex(i + 1);
      await runTurn(scTurn.text, scTurn.source, i + 1);
      // Small pause between turns
      await new Promise((r) => setTimeout(r, 250));
    }

    setIsRunning(false);
  };

  // Free text turn submit
  const handleSendFreeText = async (text: string) => {
    if (isRunning) return;
    setIsRunning(true);
    await runTurn(text);
    setIsRunning(false);
  };

  // Determine if decisions differ across engines per turn
  const differsPerTurn = useMemo(() => {
    const map: Record<number, boolean> = {};

    turnEvents.forEach((t) => {
      const decs = Object.values(t.decisions);
      if (decs.length < 2) {
        map[t.turnIndex] = false;
        return;
      }

      let hasDiff = false;
      const first = decs[0];

      for (let i = 1; i < decs.length; i++) {
        const cur = decs[i];
        if (cur.action !== first.action) {
          hasDiff = true;
          break;
        }
        if (
          cur.answers.should_store.label !== first.answers.should_store.label ||
          cur.answers.redundant.label !== first.answers.redundant.label ||
          cur.answers.obsolete.label !== first.answers.obsolete.label
        ) {
          hasDiff = true;
          break;
        }
      }

      map[t.turnIndex] = hasDiff;
    });

    return map;
  }, [turnEvents]);

  // Loading initial screen
  if (isLoadingInitial) {
    return (
      <main
        role="main"
        aria-label="Đang khởi tạo giao diện"
        className="min-h-screen w-full bg-bg flex items-center justify-center p-6"
      >
        <div className="flex flex-col items-center gap-4 text-ink">
          <div className="w-8 h-8 rounded-full border-4 border-ink/20 border-t-ink animate-spin" />
          <p className="font-semibold text-lg">Đang kết nối với hệ thống System-One...</p>
        </div>
      </main>
    );
  }

  // Backend unreachable full-page screen
  if (isBackendUnreachable) {
    return (
      <BackendErrorState
        onRetry={loadInitialData}
        isRetrying={isRetrying}
      />
    );
  }

  const isMock = Boolean(health?.mock);
  const isReplayMode = activeTab === 'replay';
  const ollamaReachable = Boolean(hardware?.ollama?.reachable);

  const layaInfo = models.find((m) => m.id === 'laya');
  const kevInfo = models.find((m) => m.id === 'kev-0.8b');
  const selectedLlmInfo = models.find((m) => m.id === selectedLlmTag);

  return (
    <div className="min-h-screen flex flex-col bg-bg text-ink">
      {/* 1. Header with Title and Hardware Info */}
      <Header hardware={hardware} />

      {/* 2. Full-width Banners (Mock and Replay) */}
      <Banners
        isMock={isMock}
        isReplay={isReplayMode}
        recordedOn={replay?.recorded_on}
      />

      {/* 3. Navigation Tabs: Trực tiếp | Bảng đo | Phát lại */}
      <Tabs
        activeTab={activeTab}
        onTabChange={setActiveTab}
        hasReplay={Boolean(replay && replay.turns && replay.turns.length > 0)}
      />

      {/* Main Container */}
      <main className="flex-1 w-full max-w-[1840px] mx-auto px-4 md:px-6 py-6">
        {/* Tab 1: Trực tiếp (Live) */}
        {activeTab === 'live' && (
          <div
            id="panel-live"
            role="tabpanel"
            aria-labelledby="tab-live"
            className="w-full flex flex-col lg:flex-row gap-6 items-start"
          >
            {/* Left Column: Chat (≈ 28%) */}
            <ChatColumn
              scenarioTurns={scenario?.turns || []}
              onRunScenario={handleRunScenario}
              onSendTurn={handleSendFreeText}
              onResetSession={handleResetSession}
              isRunning={isRunning}
              messages={messages}
              currentTurnIndex={currentScenarioTurnIndex}
            />

            {/* Right Area: Three Engine Columns (each ≈ 24%) */}
            <div className="flex-1 w-full grid grid-cols-1 md:grid-cols-2 min-[1000px]:grid-cols-3 gap-4 items-start">
              {/* Column 1: Laya */}
              <EngineColumn
                engineId="laya"
                engineInfo={layaInfo}
                allModels={models}
                memories={memories['laya'] || []}
                turns={turnEvents}
                differsPerTurn={differsPerTurn}
              />

              {/* Column 2: Kev-0.8B */}
              <EngineColumn
                engineId="kev-0.8b"
                engineInfo={kevInfo}
                allModels={models}
                memories={memories['kev-0.8b'] || []}
                turns={turnEvents}
                differsPerTurn={differsPerTurn}
              />

              {/* Column 3: LLM with dropdown */}
              <EngineColumn
                engineId={selectedLlmTag}
                engineInfo={selectedLlmInfo}
                allModels={models}
                isLlmColumn={true}
                selectedLlmTag={selectedLlmTag}
                onSelectLlmTag={handleSelectLlmTag}
                ollamaReachable={ollamaReachable}
                memories={memories[selectedLlmTag] || []}
                turns={turnEvents}
                differsPerTurn={differsPerTurn}
              />
            </div>
          </div>
        )}

        {/* Tab 2: Bảng đo (Benchmark) */}
        {activeTab === 'benchmark' && (
          <div
            id="panel-benchmark"
            role="tabpanel"
            aria-labelledby="tab-benchmark"
            className="w-full"
          >
            <BenchmarkTab
              models={models}
              benchmarkData={benchmarkData}
              onBenchmarkComplete={setBenchmarkData}
            />
          </div>
        )}

        {/* Tab 3: Phát lại (Replay) */}
        {activeTab === 'replay' && (
          <div
            id="panel-replay"
            role="tabpanel"
            aria-labelledby="tab-replay"
            className="w-full"
          >
            <ReplayTab replayData={replay} models={models} />
          </div>
        )}
      </main>

      {/* 4. Footer */}
      <Footer hardware={hardware} />
    </div>
  );
}
