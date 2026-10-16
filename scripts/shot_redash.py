"""Screenshot dashboardu Redasha do dokumentacji (utility deweloperskie).

Wymaga działającego stacku (docker compose up -d) i playwright na systemowym Chrome:
    uv venv /tmp/pwenv && uv pip install --python /tmp/pwenv/bin/python playwright

Użycie:
    /tmp/pwenv/bin/python scripts/shot_redash.py <url> <output.png>
"""

import sys

from playwright.sync_api import sync_playwright

BASE_URL = "http://localhost:5000"
EMAIL = "demo@av.local"
PASSWORD = "av-demo-2026"


def main() -> None:
    target_url, output_path = sys.argv[1], sys.argv[2]
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        page = browser.new_page(viewport={"width": 1600, "height": 1100})
        page.goto(f"{BASE_URL}/login", wait_until="networkidle")
        page.fill('input[name="email"]', EMAIL)
        page.fill('input[name="password"]', PASSWORD)
        page.click('button[type="submit"]')
        page.wait_for_url(f"{BASE_URL}/", timeout=15000)
        page.goto(target_url, wait_until="networkidle")
        page.wait_for_timeout(6000)  # wykresy renderują się chwilę po danych
        page.screenshot(path=output_path, full_page=True)
        browser.close()
    print(f"ok: {output_path}")


if __name__ == "__main__":
    main()
