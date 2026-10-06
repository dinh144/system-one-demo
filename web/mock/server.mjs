import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const PORT = parseInt(process.env.PORT || '8000', 10);
const DATA_DIR = path.resolve(__dirname, '../../data');
const SERVE_STATIC = process.env.SERVE_STATIC === '1';
const STATIC_DIR = path.resolve(__dirname, '../out');

const MIME_TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.mjs': 'application/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.gif': 'image/gif',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon',
  '.txt': 'text/plain; charset=utf-8',
  '.woff': 'font/woff',
  '.woff2': 'font/woff2',
  '.ttf': 'font/ttf',
};

function tryServeStatic(req, res, pathname) {
  if (!SERVE_STATIC) return false;
  if (!fs.existsSync(STATIC_DIR)) return false;

  const safePath = path.normalize(decodeURIComponent(pathname)).replace(/^(\.\.[/\\])+/, '');
  let filePath = path.join(STATIC_DIR, safePath);

  if (fs.existsSync(filePath) && fs.statSync(filePath).isDirectory()) {
    filePath = path.join(filePath, 'index.html');
  } else if (!fs.existsSync(filePath)) {
    if (fs.existsSync(filePath + '.html')) {
      filePath = filePath + '.html';
    } else if (fs.existsSync(path.join(STATIC_DIR, 'index.html'))) {
      filePath = path.join(STATIC_DIR, 'index.html');
    }
  }

  if (fs.existsSync(filePath) && fs.statSync(filePath).isFile()) {
    const ext = path.extname(filePath).toLowerCase();
    const contentType = MIME_TYPES[ext] || 'application/octet-stream';
    setCors(res);
    res.writeHead(200, { 'Content-Type': contentType });
    fs.createReadStream(filePath).pipe(res);
    return true;
  }
  return false;
}

// Load cases and scenario from ../data/
const casesPath = path.join(DATA_DIR, 'cases.json');
const scenarioPath = path.join(DATA_DIR, 'scenario.json');

const casesData = JSON.parse(fs.readFileSync(casesPath, 'utf8'));
const scenarioData = JSON.parse(fs.readFileSync(scenarioPath, 'utf8'));

// Mock state sessions
const sessions = new Map();

// Helper to set CORS headers
function setCors(res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
}

function sendJson(res, statusCode, data) {
  setCors(res);
  res.writeHead(statusCode, { 'Content-Type': 'application/json; charset=utf-8' });
  res.end(JSON.stringify(data));
}

function readBody(req) {
  return new Promise((resolve, reject) => {
    let body = '';
    req.on('data', chunk => {
      body += chunk;
    });
    req.on('end', () => {
      try {
        resolve(body ? JSON.parse(body) : {});
      } catch (err) {
        reject(err);
      }
    });
    req.on('error', reject);
  });
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

// Generate pre-computed replay turns based on the 10 scenario turns
function generateReplayData() {
  const turns = [];
  const engines = ['laya', 'kev-0.8b', 'llm:qwen2.5:0.5b'];
  const stores = {
    'laya': [],
    'kev-0.8b': [],
    'llm:qwen2.5:0.5b': []
  };

  const scenarioTurns = scenarioData.turns || [];

  scenarioTurns.forEach((scTurn, index) => {
    const turnIndex = index + 1;
    const turnDecisions = [];

    // Realistic decision per engine
    engines.forEach(eng => {
      let latency = 300;
      let action = 'add';
      let answers = {
        should_store: { p: 0.92, label: 'yes', probability_source: 'model' },
        redundant: { p: 0.08, label: 'no', probability_source: 'model' },
        obsolete: { p: 0.04, label: 'no', probability_source: 'model' }
      };

      if (eng === 'laya') {
        latency = 780 + (index * 25) % 90;
      } else if (eng === 'kev-0.8b') {
        latency = 1240 + (index * 30) % 110;
      } else {
        latency = 294 + (index * 15) % 40;
        answers.should_store.probability_source = 'logprob';
        answers.redundant.probability_source = 'logprob';
        answers.obsolete.probability_source = 'logprob';
      }

      // Turn specific behaviors
      if (turnIndex === 3 && eng === 'kev-0.8b') {
        // unsure
        answers.should_store = { p: 0.52, label: 'unsure', probability_source: 'model' };
        action = 'ask';
      } else if (turnIndex === 4 && eng === 'llm:qwen2.5:0.5b') {
        // hard_label
        answers.should_store = { p: 1.0, label: 'yes', probability_source: 'hard_label' };
        action = 'add';
      } else if (turnIndex === 5) {
        // replace
        answers.obsolete = { p: 0.88, label: 'yes', probability_source: eng.startsWith('llm') ? 'logprob' : 'model' };
        answers.redundant = { p: 0.05, label: 'no', probability_source: eng.startsWith('llm') ? 'logprob' : 'model' };
        action = 'replace';
      } else if (turnIndex === 7) {
        // redundant / skip
        answers.should_store = { p: 0.85, label: 'yes', probability_source: eng.startsWith('llm') ? 'logprob' : 'model' };
        answers.redundant = { p: 0.91, label: 'yes', probability_source: eng.startsWith('llm') ? 'logprob' : 'model' };
        action = 'skip';
      }

      // Update engine store
      if (action === 'add') {
        stores[eng].push({
          id: `mem-${eng}-${turnIndex}`,
          text: scTurn.text.slice(0, 70),
          status: 'active'
        });
      } else if (action === 'replace') {
        if (stores[eng].length > 0) {
          stores[eng][0].status = 'replaced';
          stores[eng][0].replaced_by = scTurn.text.slice(0, 50);
        }
        stores[eng].push({
          id: `mem-${eng}-${turnIndex}`,
          text: scTurn.text.slice(0, 70),
          status: 'active'
        });
      }

      turnDecisions.push({
        engine: eng,
        source: 'replay',
        latency_ms: latency,
        device: 'cpu',
        answers,
        action,
        memory: JSON.parse(JSON.stringify(stores[eng])),
        gen_tokens: eng.startsWith('llm') ? 28 : null
      });
    });

    turns.push({
      turn: { i: turnIndex, text: scTurn.text },
      decisions: turnDecisions
    });
  });

  return {
    schema: 1,
    source: 'replay',
    recorded_on: 'mock',
    recorded_at: '2026-10-06 20:45:00',
    turns
  };
}

const replayCache = generateReplayData();

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, `http://${req.headers.host || '127.0.0.1'}`);
  const pathname = url.pathname;
  const method = req.method;

  if (method === 'OPTIONS') {
    setCors(res);
    res.writeHead(204);
    res.end();
    return;
  }

  // Serve static files when SERVE_STATIC=1 and request is GET and not an /api route
  if (method === 'GET' && !pathname.startsWith('/api')) {
    if (tryServeStatic(req, res, pathname)) {
      return;
    }
  }

  // 1. GET /api/health
  if (method === 'GET' && pathname === '/api/health') {
    sendJson(res, 200, {
      schema: 1,
      ok: true,
      mock: true
    });
    return;
  }

  // 2. GET /api/hardware
  if (method === 'GET' && pathname === '/api/hardware') {
    sendJson(res, 200, {
      schema: 1,
      os: 'Linux 6.6.0-x86_64',
      cpu: 'Intel(R) Core(TM) i7-1185G7 @ 3.00GHz (8 cores)',
      ram_gb: 16.0,
      gpu: null,
      python: '3.11.9',
      torch: '2.4.0+cpu',
      ollama: {
        reachable: true,
        models: ['qwen2.5:0.5b', 'qwen2.5:1.5b', 'qwen2.5:3b']
      }
    });
    return;
  }

  // 3. GET /api/models
  if (method === 'GET' && pathname === '/api/models') {
    sendJson(res, 200, [
      {
        id: 'laya',
        label: 'Laya',
        params: '421M',
        kind: 'system-one',
        device: 'cpu',
        status: 'ready',
        reason: null
      },
      {
        id: 'kev-0.8b',
        label: 'Kev-0.8B',
        params: '~0.8B',
        kind: 'system-one',
        device: 'cpu',
        status: 'ready',
        reason: null
      },
      {
        id: 'llm:qwen2.5:0.5b',
        label: 'Qwen 2.5 0.5B',
        params: '0.5B',
        kind: 'llm',
        device: 'cpu',
        status: 'ready',
        reason: null
      },
      {
        id: 'llm:qwen2.5:1.5b',
        label: 'Qwen 2.5 1.5B',
        params: '1.5B',
        kind: 'llm',
        device: 'cpu',
        status: 'ready',
        reason: null
      },
      {
        id: 'llm:qwen2.5:3b',
        label: 'Qwen 2.5 3B',
        params: '3B',
        kind: 'llm',
        device: 'cpu',
        status: 'ready',
        reason: null
      },
      {
        id: 'llm:qwen2.5:7b',
        label: 'Qwen 2.5 7B',
        params: '7B',
        kind: 'llm',
        device: 'cpu',
        status: 'unavailable',
        reason: 'Chưa tải trọng số qua ollama (chạy `ollama pull qwen2.5:7b`)'
      }
    ]);
    return;
  }

  // 4. GET /api/scenario
  if (method === 'GET' && pathname === '/api/scenario') {
    sendJson(res, 200, {
      schema: 1,
      ...scenarioData
    });
    return;
  }

  // 5. GET /api/cases
  if (method === 'GET' && pathname === '/api/cases') {
    sendJson(res, 200, {
      schema: 1,
      ...casesData
    });
    return;
  }

  // 6. POST /api/session
  if (method === 'POST' && pathname === '/api/session') {
    const body = await readBody(req);
    const engines = Array.isArray(body.engines) && body.engines.length > 0
      ? body.engines
      : ['laya', 'kev-0.8b', 'llm:qwen2.5:0.5b'];

    const sessionId = `mock-session-${Date.now()}`;
    const sessionStores = {};
    for (const eng of engines) {
      sessionStores[eng] = [];
    }

    sessions.set(sessionId, {
      sessionId,
      engines,
      turnIndex: 0,
      stores: sessionStores
    });

    sendJson(res, 200, {
      schema: 1,
      session_id: sessionId
    });
    return;
  }

  // 7. POST /api/session/:id/reset
  const resetMatch = pathname.match(/^\/api\/session\/([^/]+)\/reset$/);
  if (method === 'POST' && resetMatch) {
    const sessionId = resetMatch[1];
    const session = sessions.get(sessionId);
    if (session) {
      session.turnIndex = 0;
      for (const eng of session.engines) {
        session.stores[eng] = [];
      }
    }
    sendJson(res, 200, { schema: 1, ok: true });
    return;
  }

  // 8. POST /api/session/:id/turn
  const turnMatch = pathname.match(/^\/api\/session\/([^/]+)\/turn$/);
  if (method === 'POST' && turnMatch) {
    const sessionId = turnMatch[1];
    const session = sessions.get(sessionId) || {
      sessionId,
      engines: ['laya', 'kev-0.8b', 'llm:qwen2.5:0.5b'],
      turnIndex: 0,
      stores: {
        'laya': [],
        'kev-0.8b': [],
        'llm:qwen2.5:0.5b': []
      }
    };
    sessions.set(sessionId, session);

    const body = await readBody(req);
    const turnText = body.text || 'Lượt hội thoại kiểm thử';
    session.turnIndex += 1;
    const currentTurn = session.turnIndex;

    setCors(res);
    res.writeHead(200, {
      'Content-Type': 'text/event-stream; charset=utf-8',
      'Cache-Control': 'no-cache',
      'Connection': 'keep-alive'
    });

    // 1. Emit turn event
    res.write(`event: turn\ndata: ${JSON.stringify({ i: currentTurn, text: turnText })}\n\n`);

    // Prepare async decision events for engines
    // Engines finish at different times
    const promises = session.engines.map(async (eng) => {
      // Different realistic delays
      let delayMs = 300;
      let latencyMs = 294.2;

      if (eng === 'laya') {
        delayMs = 600;
        latencyMs = 784.0;
      } else if (eng === 'kev-0.8b') {
        delayMs = 950;
        latencyMs = 1245.5;
      } else if (eng.startsWith('llm')) {
        delayMs = 250;
        latencyMs = 294.0;
      }

      await sleep(delayMs);

      // Check if this engine should simulate mid-turn error
      // Requirement: "one error mid-turn"
      // Trigger error on turn 6 for kev-0.8b, or if text specifically mentions "error"
      const isError = (currentTurn === 6 && eng === 'kev-0.8b') || (turnText.toLowerCase().includes('error') && eng === 'kev-0.8b');
      if (isError) {
        res.write(`event: engine_error\ndata: ${JSON.stringify({
          engine: eng,
          message: 'Lỗi nội bộ: quá tải bộ nhớ CPU (CUDA out of memory fallback error)'
        })}\n\n`);
        return;
      }

      // Check if engine is marked unavailable
      if (eng === 'llm:qwen2.5:7b') {
        res.write(`event: engine_error\ndata: ${JSON.stringify({
          engine: eng,
          message: 'Mô hình không khả dụng: Chưa tải trọng số qua ollama'
        })}\n\n`);
        return;
      }

      // Decision construction
      let action = 'add';
      let shouldStoreP = 0.92;
      let redundantP = 0.08;
      let obsoleteP = 0.04;
      let probSource = eng.startsWith('llm') ? 'logprob' : 'model';

      // Requirement: "a unsure case" (turn 3 or text containing "unsure")
      if ((currentTurn === 3 && eng === 'kev-0.8b') || turnText.toLowerCase().includes('unsure')) {
        shouldStoreP = 0.52; // Between 0.35 and 0.65 -> unsure
        action = 'ask';
      }

      // Requirement: "a hard_label probability source" (turn 4 or text containing "hard")
      if ((currentTurn === 4 && eng.startsWith('llm')) || turnText.toLowerCase().includes('hard')) {
        probSource = 'hard_label';
        shouldStoreP = 1.0;
      }

      // Requirement: "a replace action" (turn 5 or text containing "replace")
      if ((currentTurn === 5) || turnText.toLowerCase().includes('replace')) {
        shouldStoreP = 0.94;
        redundantP = 0.05;
        obsoleteP = 0.89; // obsolete yes -> replace
        action = 'replace';
      }

      // Turn 7: redundant / skip
      if (currentTurn === 7) {
        shouldStoreP = 0.88;
        redundantP = 0.93;
        obsoleteP = 0.02;
        action = 'skip';
      }

      const getLabel = (p) => {
        if (p >= 0.65) return 'yes';
        if (p <= 0.35) return 'no';
        return 'unsure';
      };

      const answers = {
        should_store: {
          p: shouldStoreP,
          label: getLabel(shouldStoreP),
          probability_source: probSource
        },
        redundant: {
          p: redundantP,
          label: getLabel(redundantP),
          probability_source: probSource
        },
        obsolete: {
          p: obsoleteP,
          label: getLabel(obsoleteP),
          probability_source: probSource
        }
      };

      // Memory store management per engine
      const store = session.stores[eng] || [];
      if (action === 'add') {
        store.push({
          id: `mem-${eng}-${currentTurn}`,
          text: turnText.slice(0, 80),
          status: 'active'
        });
      } else if (action === 'replace') {
        if (store.length > 0) {
          const old = store[store.length - 1];
          old.status = 'replaced';
          old.replaced_by = turnText.slice(0, 50);
        }
        store.push({
          id: `mem-${eng}-${currentTurn}`,
          text: turnText.slice(0, 80),
          status: 'active'
        });
      }
      session.stores[eng] = store;

      const decisionData = {
        engine: eng,
        source: 'live',
        latency_ms: latencyMs,
        device: 'cpu',
        answers,
        action,
        memory: JSON.parse(JSON.stringify(store)),
        gen_tokens: eng.startsWith('llm') ? 28 : null
      };

      res.write(`event: decision\ndata: ${JSON.stringify(decisionData)}\n\n`);
    });

    await Promise.all(promises);
    res.write(`event: done\ndata: {}\n\n`);
    res.end();
    return;
  }

  // 9. POST /api/benchmark
  if (method === 'POST' && pathname === '/api/benchmark') {
    const body = await readBody(req);
    const engines = Array.isArray(body.engines) && body.engines.length > 0
      ? body.engines
      : ['laya', 'kev-0.8b', 'llm:qwen2.5:0.5b'];

    setCors(res);
    res.writeHead(200, {
      'Content-Type': 'text/event-stream; charset=utf-8',
      'Cache-Control': 'no-cache',
      'Connection': 'keep-alive'
    });

    const totalCases = 30;
    // Emit progress events
    for (const eng of engines) {
      for (const step of [10, 20, 30]) {
        await sleep(70);
        res.write(`event: progress\ndata: ${JSON.stringify({
          engine: eng,
          current: step,
          total: totalCases
        })}\n\n`);
      }
    }

    // Benchmark stats (obviously synthetic round numbers, identical across engines)
    const mockAccuracy = {
      value: 0.800,
      n: 30,
      note: 'nhãn tham chiếu (n = 30), chưa kiểm định độc lập'
    };
    const mockBreakdown = {
      should_store: { accuracy: 0.80, positives: 20, total: 30 },
      redundant: { accuracy: 0.80, positives: 3, total: 30 },
      obsolete: { accuracy: 0.80, positives: 3, total: 30 }
    };

    const results = {
      schema: 1,
      engines: {
        'laya': {
          p50_ms: 780.0,
          p95_ms: 1150.0,
          n: 30,
          accuracy: mockAccuracy,
          breakdown: mockBreakdown
        },
        'kev-0.8b': {
          p50_ms: 1240.0,
          p95_ms: 1420.0,
          n: 30,
          accuracy: mockAccuracy,
          breakdown: mockBreakdown
        },
        'llm:qwen2.5:0.5b': {
          p50_ms: 294.0,
          p95_ms: 380.0,
          n: 30,
          accuracy: mockAccuracy,
          breakdown: mockBreakdown
        },
        'llm:qwen2.5:1.5b': {
          p50_ms: 784.0,
          p95_ms: 920.0,
          n: 30,
          accuracy: mockAccuracy,
          breakdown: mockBreakdown
        },
        'llm:qwen2.5:3b': {
          p50_ms: 1429.0,
          p95_ms: 1680.0,
          n: 30,
          accuracy: mockAccuracy,
          breakdown: mockBreakdown
        }
      }
    };

    res.write(`event: result\ndata: ${JSON.stringify(results)}\n\n`);
    res.end();
    return;
  }

  // 10. GET /api/replay
  if (method === 'GET' && pathname === '/api/replay') {
    sendJson(res, 200, replayCache);
    return;
  }

  // 404
  sendJson(res, 404, {
    schema: 1,
    error: {
      code: 'NOT_FOUND',
      message: `Endpoint không tồn tại: ${pathname}`
    }
  });
});

server.listen(PORT, '127.0.0.1', () => {
  console.log(`Mock server running at http://127.0.0.1:${PORT}`);
});
