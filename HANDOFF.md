# Windows handoff

Not tested on Windows by the authors.

Run every command from the repository root in PowerShell. Follow the numbered steps in order. For any FAIL, send the failed command and its complete output.

## Windows setup and run

1. Install Python 3.11, uv, and Ollama. Node.js is not required to run the demo.

   ```powershell
   winget install --exact --id Python.Python.3.11
   winget install --exact --id astral-sh.uv
   winget install --exact --id Ollama.Ollama
   python --version
   uv --version
   ollama --version
   ```

   PASS: the installs exit 0; Python reports 3.11.x, and uv and Ollama each print a version. FAIL: send the failed command and output.

2. Download the four offered Ollama models.

   ```powershell
   ollama pull qwen2.5:0.5b
   ollama pull qwen2.5:1.5b
   ollama pull qwen2.5:3b
   ollama pull qwen2.5:7b
   ollama list
   ```

   PASS: each pull exits 0 and `ollama list` contains all four exact tags. FAIL: send the failed pull output and `ollama list` output.

3. Install the Python environment, model weights, and LoCoMo excerpts.

   ```powershell
   python -m demo setup
   ```

   PASS: exit code 0; output ends with `Laya, Kev, and Kev base weights are available in the Hugging Face cache.` FAIL: send the full setup output.

4. Install the CUDA-enabled PyTorch wheel for the RTX 30xx machine, then verify CUDA.

   ```powershell
   uv pip install --python .\backend\.venv\Scripts\python.exe torch==2.8.0 --index-url https://download.pytorch.org/whl/cu128
   .\backend\.venv\Scripts\python.exe -c "import torch; print(torch.__version__, torch.cuda.is_available())"
   ```

   PASS: install exits 0 and the Python command prints a torch 2.8.0 version followed by `True`. If CUDA setup fails, use the CPU fallback below; the demo still works on CPU.

   CPU fallback:

   ```powershell
   uv pip install --python .\backend\.venv\Scripts\python.exe torch==2.8.0 --index-url https://download.pytorch.org/whl/cpu
   .\backend\.venv\Scripts\python.exe -c "import torch; print(torch.__version__, torch.cuda.is_available())"
   ```

   PASS: install exits 0 and the Python command prints `False`. CUDA wheel files are listed at the [official PyTorch CUDA 12.8 wheel index](https://download.pytorch.org/whl/cu128/).

5. Collect the machine and dependency report.

   ```powershell
   python -m demo doctor
   ```

   PASS: exit code 0 and output contains `System-One backend doctor`, `torch_runtime`, `acceleration_optional`, and `Missing or unavailable:`. Missing optional engines and acceleration-package import failures are reported but do not fail this step. FAIL: save the complete output.

6. Start the demo.

   ```powershell
   python -m demo run
   ```

   PASS: output prints the URL selected by the launcher, the browser opens that URL, and the page shows live backend data. The launcher uses `http://127.0.0.1:8000` when available and automatically selects and prints another free port when needed; do not stop another service. In a second PowerShell window, request `/api/health` at the exact printed URL.

   ```powershell
   Invoke-RestMethod http://127.0.0.1:8000/api/health
   ```

   If the launcher printed another port, replace `8000` with that port. PASS: the response contains `ok : True` and `mock : False`. Stop the demo with Ctrl+C in the original window. FAIL: send the launcher output and health response.

7. Send the report back.

   ```powershell
   python -m demo doctor | Tee-Object doctor-output.txt
   ```

   PASS: send `doctor-output.txt` and the complete error output for any failed command. FAIL: if doctor cannot start, send its full console output and command.

## Linux author check

Run these commands from a clean source copy's root. The commands do not require Node.js.

1. Install the Python environment, model weights, and data excerpts.

   ```sh
   python -m demo setup
   ```

   PASS: exit code 0 and output reports that Laya, Kev, and Kev base weights are available in the Hugging Face cache. FAIL: save the complete output.

2. Inspect the machine report.

   ```sh
   python -m demo doctor
   ```

   PASS: exit code 0 and output contains the hardware, torch runtime, optional acceleration import, and missing-component sections. FAIL: save the complete output.

3. Start the demo.

   ```sh
   python -m demo run
   ```

   PASS: output prints the selected URL, the browser opens it, the static page loads, and `/api/health` at that same URL returns `ok: true` and `mock: false`. If port 8000 is occupied, the launcher reports the next available URL and leaves the existing service running. Stop the demo with Ctrl+C. FAIL: save the launcher output and health response.

## Measurement notes (read before trusting any number on screen)

- Latencies are measured by the backend while it runs, on this machine. Engines run one after another by default, so each latency is one engine alone. Setting the environment variable `SYSTEM_ONE_ENGINE_WORKERS` to 2 or 3 runs engines at the same time; on a CPU that makes every latency several times larger because the engines compete for cores, and the numbers then include that contention.
- Close other heavy programs (browsers with many tabs, other servers, other model runners) before measuring. On the authors' laptop, background load changed the same engine's latency by two to five times between runs.
- Latency grows with the length of the state (the memories already stored), so later turns of the scenario are slower than the first ones.
- The first call of each engine is a warm-up whose time is not reported.
- The replay tab shows a recording made on the authors' ThinkPad (CPU only). To record a replay on this machine instead, with the demo running in another window, run `python scripts/record_replay.py --recorded-on "describe this machine honestly, for example Legion 5, RTX 3060 6 GB"`. It overwrites `data/replay.json`. Do not put another machine's name there.
- A recorded video of a real run on the ThinkPad is `data/video/demo-thinkpad.mp4`. If the demo does not run on the presenter's machine, play that video and say it was recorded on a different machine.

## Network exposure

The demo answers only requests addressed to `localhost`, `127.0.0.1` or `::1`, and rejects state-changing requests that come from another origin. That stops a web page open in the same browser from driving it. Do not expose the port to a network. If you must reach it by another hostname on purpose, set `SYSTEM_ONE_ALLOWED_HOSTS` to a comma-separated list of those hostnames before `python -m demo run`.

## Optional appendix: rebuild the static UI

The repository includes the built UI in `web/out/`, so these Node.js steps are only needed when changing the web source or restoring a missing export. Keep `NEXT_PUBLIC_API_BASE` unset so the exported UI uses same-origin API requests.

In PowerShell:

```powershell
winget install --exact --id OpenJS.NodeJS.LTS
Remove-Item Env:NEXT_PUBLIC_API_BASE -ErrorAction SilentlyContinue
npm ci --prefix web
npm run build --prefix web
```

PASS: the build exits 0 and `web/out/index.html` exists. FAIL: send the complete npm output.

What to say if asked about labels:

They are reference labels for this demo.
There are 30 case turns.
The labels were proposed by the author.
They have not been independently verified.
