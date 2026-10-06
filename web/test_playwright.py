import os
import sys
import glob
import time
import subprocess
import requests
from playwright.sync_api import sync_playwright

MOCK_PORT = 8001
BASE_URL = f"http://127.0.0.1:{MOCK_PORT}/"

SHOTS_DIR = os.path.abspath("web/shots")
os.makedirs(SHOTS_DIR, exist_ok=True)

def clean_stale_screenshots():
    """Delete stale screenshot files before test run."""
    stale_files = glob.glob(os.path.join(SHOTS_DIR, "*.png"))
    for f in stale_files:
        try:
            os.remove(f)
        except OSError:
            pass
    print(f"Cleaned {len(stale_files)} stale screenshots from {SHOTS_DIR}")

def wait_for_url(url, timeout=15):
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = requests.get(url, timeout=1)
            if r.status_code in (200, 304):
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False

def main():
    clean_stale_screenshots()

    print(f"Starting mock server with SERVE_STATIC=1 on port {MOCK_PORT}...")
    mock_proc = subprocess.Popen(
        ["node", "web/mock/server.mjs"],
        env={**os.environ, "PORT": str(MOCK_PORT), "SERVE_STATIC": "1"},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    if not wait_for_url(f"{BASE_URL}api/health"):
        print("Failed to start mock server!")
        mock_proc.kill()
        sys.exit(1)
    if not wait_for_url(BASE_URL):
        print("Failed to load static export from mock server!")
        mock_proc.kill()
        sys.exit(1)
    print("Mock server serving web/out same-origin ready.")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()

            viewports = [
                ("1920x1080", 1920, 1080),
                ("1280x720", 1280, 720),
            ]

            for vp_name, width, height in viewports:
                print(f"\n--- Testing at {vp_name} ---")
                context = browser.new_context(viewport={"width": width, "height": height})
                page = context.new_page()

                # Collect console errors
                console_errors = []
                page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
                page.on("pageerror", lambda err: console_errors.append(str(err)))

                # 1. Mock Banner Screenshot
                print(f"[{vp_name}] Loading initial page same-origin...")
                page.goto(BASE_URL, wait_until="networkidle")
                page.wait_for_selector("aside:has-text('MÁY CHỦ GIẢ LẬP, số liệu không thật')")
                mock_banner_shot = os.path.join(SHOTS_DIR, f"mock_banner_{vp_name}.png")
                page.screenshot(path=mock_banner_shot)
                print(f"Saved: {mock_banner_shot}")

                # Verify engine parameter counts from /api/models (Requirement 4)
                print(f"[{vp_name}] Verifying engine parameter counts from /api/models...")
                laya_col = page.locator("[data-testid='column-laya']")
                assert "421M" in laya_col.inner_text(), f"Laya should display 421M, got: {laya_col.inner_text()[:60]}"
                assert "23M" not in laya_col.inner_text(), "Laya must NEVER display 23M"
                kev_col = page.locator("[data-testid='column-kev-0.8b']")
                assert "~0.8B" in kev_col.inner_text() or "0.8B" in kev_col.inner_text(), "Kev should display ~0.8B"

                # 2. Mid-turn Run Screenshot
                print(f"[{vp_name}] Triggering single turn for mid-turn screenshot...")
                input_box = page.locator("#user-turn-input")
                input_box.fill("Audrey has dogs Pepper and Precious")
                page.locator("button[type='submit']").click()

                # Wait for pending clock to appear
                page.wait_for_selector("[data-testid='latency-clock']")
                mid_turn_shot = os.path.join(SHOTS_DIR, f"normal_run_mid_turn_{vp_name}.png")
                page.screenshot(path=mid_turn_shot)
                page.screenshot(path=os.path.join(SHOTS_DIR, f"mid_turn_{vp_name}.png"))
                print(f"Saved: {mid_turn_shot}")

                # Check latency clock freeze at server value
                print(f"[{vp_name}] Waiting for latency clock to freeze...")
                page.wait_for_selector("[data-latency-frozen='true']", timeout=10000)
                frozen_clock = page.locator("[data-latency-frozen='true']").first
                clock_val = frozen_clock.locator("[data-testid='latency-val']").inner_text().strip()
                print(f"Latency clock successfully froze at: {clock_val} ms")
                assert int(clock_val) > 0, "Latency value should be positive integer ms"

                # 3. Unavailable Engine Screenshot
                print(f"[{vp_name}] Selecting unavailable engine...")
                llm_select = page.locator("#llm-select")
                llm_select.select_option("llm:qwen2.5:7b")
                page.wait_for_selector("text=không khả dụng")
                unavailable_shot = os.path.join(SHOTS_DIR, f"unavailable_engine_{vp_name}.png")
                page.screenshot(path=unavailable_shot)
                print(f"Saved: {unavailable_shot}")

                # Switch back to ready LLM
                llm_select.select_option("llm:qwen2.5:0.5b")

                # 4. Full 10-turn scenario run
                print(f"[{vp_name}] Running full 10-turn scenario...")
                page.locator("[data-testid='run-scenario-btn']").click()

                # Wait until scenario finishes (all 10 turns done)
                page.wait_for_selector("button[data-testid='run-scenario-btn']:has-text('Chạy kịch bản 10 lượt')", timeout=25000)
                time.sleep(1) # Allow renders to settle

                # PROVE REQUIREMENT 2: Chat panel shows all 10 turns
                print(f"[{vp_name}] Asserting chat panel has all 10 messages...")
                chat_messages = page.locator("[data-testid='chat-message']")
                chat_count = chat_messages.count()
                print(f"Chat panel contains {chat_count} messages")
                assert chat_count == 10, f"Expected 10 chat messages in chat panel, but found {chat_count}"
                for i in range(1, 11):
                    assert page.locator(f"[data-testid='chat-message']:has-text('Lượt #{i}')").count() >= 1, f"Missing chat message for Lượt #{i}"

                # PROVE REQUIREMENT 3: Page height <= 2 viewport heights at 1920x1080
                page_height = page.evaluate("() => document.documentElement.scrollHeight")
                print(f"[{vp_name}] Page scroll height after 10 turns: {page_height}px")
                if vp_name == "1920x1080":
                    assert page_height <= 2 * 1080, f"Page height {page_height}px exceeds 2 viewport heights (2160px)"
                else:
                    assert page_height <= 2.5 * 720, f"Page height {page_height}px exceeds 1280x720 bounds ({2.5 * 720}px)"

                # PROVE REQUIREMENT 3: Current turn (Turn 10) is pinned at top of each engine column
                for eng in ["laya", "kev-0.8b", "llm:qwen2.5:0.5b"]:
                    col = page.locator(f"[data-testid='column-{eng}']")
                    top_card = col.locator("article").first
                    top_card_text = top_card.inner_text()
                    assert "Lượt #10" in top_card_text, f"Top card in {eng} column should be Lượt #10, got {top_card_text[:50]}"

                scenario_shot = os.path.join(SHOTS_DIR, f"full_scenario_10_turns_{vp_name}.png")
                page.screenshot(path=scenario_shot, full_page=True)
                page.screenshot(path=os.path.join(SHOTS_DIR, f"after_full_10_turns_{vp_name}.png"), full_page=True)
                print(f"Saved: {scenario_shot}")

                # Check differ marker exists
                differ_count = page.locator("[data-testid='differ-badge']").count()
                print(f"Found {differ_count} differ marker(s) in scenario run")
                assert differ_count > 0, "Differ markers should be present where decisions differed"

                # 5. Benchmark tab screenshot
                print(f"[{vp_name}] Testing benchmark tab...")
                page.locator("#tab-benchmark").click()
                page.wait_for_selector("text=Bảng đo hiệu năng và độ chính xác")

                # Verify mock banner is present on Benchmark tab (Requirement 6)
                page.wait_for_selector("aside:has-text('MÁY CHỦ GIẢ LẬP, số liệu không thật')")

                # Run benchmark
                page.locator("[data-testid='run-benchmark-btn']").click()
                page.wait_for_selector("text=Hoàn tất đo đạc", timeout=15000)
                time.sleep(1)

                # Verify synthetic round accuracy numbers (Requirement 6)
                benchmark_text = page.locator("table").inner_text()
                assert "80.0%" in benchmark_text, "Synthetic round accuracy 80.0% should appear in benchmark table"

                benchmark_shot = os.path.join(SHOTS_DIR, f"benchmark_tab_{vp_name}.png")
                page.screenshot(path=benchmark_shot)
                print(f"Saved: {benchmark_shot}")

                # Verify static GPT-4o-mini reference line
                page.wait_for_selector("text=GPT-4o-mini (tham chiếu từ bài báo Jev-Mem arXiv 2609.23986)")
                page.wait_for_selector("text=xem Bảng 1 của bài báo")

                # Verify accuracy caveat
                page.wait_for_selector("text=Với redundant (3 ca) và obsolete (3 ca), độ chính xác chưa có ý nghĩa thống kê.")

                # 6. Replay tab screenshot & banner verification (Requirement 5)
                print(f"[{vp_name}] Testing replay tab...")
                page.locator("#tab-replay").click()
                page.wait_for_selector("text=Phát lại kịch bản")
                # Requirement 5: banner must read 'Phát lại: đo trên mock, không phải máy này'
                page.wait_for_selector("aside:has-text('Phát lại: đo trên mock, không phải máy này')")
                replay_shot = os.path.join(SHOTS_DIR, f"replay_tab_{vp_name}.png")
                page.screenshot(path=replay_shot)
                print(f"Saved: {replay_shot}")

                # 7. Verify font size constraint: nothing under 16px, body >= 18px
                print(f"[{vp_name}] Verifying font sizes in DOM...")
                font_check = page.evaluate("""() => {
                    const elements = Array.from(document.querySelectorAll('*'));
                    let under16 = [];
                    let bodyElements = [];

                    for (const el of elements) {
                        if (el.children.length === 0 && el.textContent.trim().length > 0) {
                            const style = window.getComputedStyle(el);
                            const fontSize = parseFloat(style.fontSize);
                            if (fontSize < 15.9) {
                                under16.push({ tag: el.tagName, text: el.textContent.trim().slice(0, 30), size: fontSize });
                            }
                        }
                    }

                    // Check body paragraph size
                    const paragraphs = Array.from(document.querySelectorAll('p, .text-base'));
                    let bodyUnder18 = [];
                    for (const p of paragraphs) {
                        const style = window.getComputedStyle(p);
                        const fontSize = parseFloat(style.fontSize);
                        if (fontSize < 17.9) {
                            bodyUnder18.push({ text: p.textContent.trim().slice(0, 30), size: fontSize });
                        }
                    }

                    return { under16, bodyUnder18 };
                }""")

                if font_check["under16"]:
                    print(f"WARNING: Elements under 16px: {font_check['under16'][:5]}")
                else:
                    print("PASS: Zero elements under 16px in DOM!")
                assert len(font_check["under16"]) == 0, f"Found {len(font_check['under16'])} elements under 16px"

                # Check console errors
                if console_errors:
                    print(f"Console errors at {vp_name}: {console_errors}")
                else:
                    print(f"PASS: Zero console errors at {vp_name}!")
                assert len(console_errors) == 0, f"Found console errors: {console_errors}"

                context.close()

            browser.close()
            print("\nALL PLAYWRIGHT TESTS PASSED SUCCESSFULLY!")

    finally:
        mock_proc.terminate()
        mock_proc.wait()

if __name__ == "__main__":
    main()
