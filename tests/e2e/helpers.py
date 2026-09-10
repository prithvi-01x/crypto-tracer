"""
E2E Test Helpers and Utilities for Crypto-Tracer Playwright Test Suite
"""
import os
import urllib.request
from typing import Optional
from playwright.async_api import Page, Locator

DEFAULT_PORTS = [5173, 5174]


def detect_active_port(preferred_port: Optional[int] = None) -> int:
    """
    Detect whether port 5173 or 5174 is actively serving the frontend.
    Allows override via TARGET_PORT or BASE_URL environment variable.
    """
    env_port = os.getenv("TARGET_PORT")
    if env_port:
        return int(env_port)

    env_url = os.getenv("BASE_URL")
    if env_url:
        import urllib.parse
        parsed = urllib.parse.urlparse(env_url)
        if parsed.port:
            return parsed.port

    ports_to_check = [preferred_port] if preferred_port else DEFAULT_PORTS
    for port in ports_to_check:
        if port is None:
            continue
        try:
            url = f"http://localhost:{port}/"
            resp = urllib.request.urlopen(url, timeout=1.5)
            if resp.getcode() == 200:
                return port
        except Exception:
            continue

    # Fallback to 5173 default
    return 5173


def get_base_url(preferred_port: Optional[int] = None) -> str:
    """Return full base URL for the active frontend."""
    env_url = os.getenv("BASE_URL")
    if env_url:
        return env_url.rstrip("/")
    port = detect_active_port(preferred_port)
    return f"http://localhost:{port}"


async def wait_for_page_ready(page: Page, timeout_ms: int = 1500) -> None:
    """Wait for page load and settle React state."""
    await page.wait_for_load_state("domcontentloaded")
    await page.wait_for_timeout(timeout_ms)


async def open_home(page: Page, base_url: Optional[str] = None) -> None:
    """Navigate to the dashboard home."""
    url = base_url or get_base_url()
    await page.goto(url, wait_until="domcontentloaded")
    await wait_for_page_ready(page, 1500)


async def navigate_to_case(page: Page, fir_or_text: str = "FIR-2026-DEL-CY-0812", base_url: Optional[str] = None) -> None:
    """Open home and navigate into a specific case by FIR or click first row."""
    await open_home(page, base_url)
    row = page.locator(f"tbody tr:has-text('{fir_or_text}')")
    if await row.count() > 0:
        await row.first.click()
    else:
        # Fallback to first available row
        await page.locator("tbody tr").first.click()
    # Wait for case details view to mount
    await page.wait_for_selector("span:has-text('FIR')", timeout=8000)
    await page.wait_for_timeout(1000)


async def ensure_theme(page: Page, dark: bool = False) -> None:
    """Ensure documentElement has or does not have .dark class."""
    is_currently_dark = await page.evaluate("document.documentElement.classList.contains('dark')")
    if is_currently_dark != dark:
        toggle_btn = page.locator("header button[title='Toggle dark mode']")
        if await toggle_btn.count() > 0:
            await toggle_btn.click()
            await page.wait_for_timeout(300)


async def select_tab(page: Page, tab_name: str) -> Locator:
    """Click a workspace tab by display text and wait for panel transition."""
    tab_btn = page.locator(f"button:has-text('{tab_name}')").first
    await tab_btn.click()
    await page.wait_for_timeout(800)
    return tab_btn
