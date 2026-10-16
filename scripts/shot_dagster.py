"""Screenshot Dagster UI do dokumentacji (utility deweloperskie).

Wymaga działającego `dagster dev` (port 3000) i playwright na systemowym Chrome:
    uv venv /tmp/pwenv && uv pip install --python /tmp/pwenv/bin/python playwright

Użycie:
    /tmp/pwenv/bin/python scripts/shot_dagster.py <url> <output.png>
"""

import sys

from playwright.sync_api import sync_playwright


def main() -> None:
    target_url, output_path = sys.argv[1], sys.argv[2]
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        page = browser.new_page(viewport={"width": 1600, "height": 1000})
        page.goto(target_url, wait_until="networkidle")
        page.wait_for_timeout(3000)
        try:
            page.click('button:has-text("Skip")', timeout=5000)
            page.wait_for_timeout(2000)
        except Exception:
            pass  # brak modala = już zamknięty
        page.wait_for_timeout(4000)  # websocket + statusy
        page.screenshot(path=output_path)
        browser.close()
    print(f"ok: {output_path}")


if __name__ == "__main__":
    main()
