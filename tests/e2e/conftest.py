"""
Pytest configuration and shared fixtures for Playwright E2E tests.
"""
import os
import sys

# Ensure repository root is in sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import pytest
import pytest_asyncio
from playwright.async_api import async_playwright, Page, Browser, BrowserContext
from tests.e2e.helpers import get_base_url, navigate_to_case, ensure_theme


@pytest.fixture(scope="session")
def base_url() -> str:
    """Fixture returning the active base URL."""
    return get_base_url()


@pytest_asyncio.fixture
async def page(base_url: str):
    """Fixture providing an isolated Playwright page with standard 1440x900 viewport."""
    async with async_playwright() as p:
        browser: Browser = await p.chromium.launch(headless=True)
        context: BrowserContext = await browser.new_context(
            viewport={"width": 1440, "height": 900},
            ignore_https_errors=True,
        )
        page_instance: Page = await context.new_page()
        try:
            yield page_instance
        finally:
            await context.close()
            await browser.close()


@pytest_asyncio.fixture
async def case_page(page: Page, base_url: str):
    """Fixture that pre-navigates into the primary seeded investigation case."""
    await navigate_to_case(page, "FIR-2026-DEL-CY-0812", base_url)
    # Ensure starting in light mode
    await ensure_theme(page, dark=False)
    return page
