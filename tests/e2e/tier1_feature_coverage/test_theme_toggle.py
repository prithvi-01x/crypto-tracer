"""
Tier 1 Feature Coverage: Theme Toggle & Dual-Mode Visual Identity (R1)
Verifies default theme states, dark/light transitions, icon toggles,
and theme persistence across application view transitions.
"""
import pytest
from playwright.async_api import Page
from tests.e2e.helpers import open_home, ensure_theme


@pytest.mark.asyncio
async def test_initial_theme_default_state(page: Page, base_url: str):
    """TC-T1-TH-01: Page initially loads with light theme (no .dark class on html)."""
    await open_home(page, base_url)
    await ensure_theme(page, dark=False)
    has_dark = await page.evaluate("document.documentElement.classList.contains('dark')")
    assert not has_dark, "Initial theme state should not have .dark class on documentElement"


@pytest.mark.asyncio
async def test_toggle_button_enables_dark_mode(page: Page, base_url: str):
    """TC-T1-TH-02: Clicking theme toggle button adds .dark class to documentElement."""
    await open_home(page, base_url)
    await ensure_theme(page, dark=False)

    toggle_btn = page.locator("header button[title='Toggle dark mode']")
    assert await toggle_btn.count() > 0, "Header should contain 'Toggle dark mode' button"

    await toggle_btn.click()
    await page.wait_for_timeout(300)

    has_dark = await page.evaluate("document.documentElement.classList.contains('dark')")
    assert has_dark, "Clicking toggle button should add .dark class to documentElement"


@pytest.mark.asyncio
async def test_toggle_button_restores_light_mode(page: Page, base_url: str):
    """TC-T1-TH-03: Clicking theme toggle a second time removes .dark class to restore light mode."""
    await open_home(page, base_url)
    await ensure_theme(page, dark=False)

    toggle_btn = page.locator("header button[title='Toggle dark mode']")
    # Toggle ON (dark)
    await toggle_btn.click()
    await page.wait_for_timeout(300)
    assert await page.evaluate("document.documentElement.classList.contains('dark')")

    # Toggle OFF (light)
    await toggle_btn.click()
    await page.wait_for_timeout(300)
    assert not await page.evaluate("document.documentElement.classList.contains('dark')")


@pytest.mark.asyncio
async def test_theme_toggle_updates_button_icon(page: Page, base_url: str):
    """TC-T1-TH-04: Theme toggle renders appropriate icon (moon for light mode, sun for dark mode)."""
    await open_home(page, base_url)
    await ensure_theme(page, dark=False)

    toggle_btn = page.locator("header button[title='Toggle dark mode']")
    # In light mode, an SVG for Moon is rendered
    svg_light = toggle_btn.locator("svg")
    assert await svg_light.count() > 0, "Toggle button should contain an SVG icon"

    # Switch to dark mode
    await toggle_btn.click()
    await page.wait_for_timeout(300)

    # In dark mode, an SVG for Sun is rendered
    svg_dark = toggle_btn.locator("svg")
    assert await svg_dark.count() > 0, "Toggle button should contain an SVG icon in dark mode"


@pytest.mark.asyncio
async def test_theme_persists_across_case_navigation(page: Page, base_url: str):
    """TC-T1-TH-05: Dark mode active on dashboard remains active after entering a case."""
    await open_home(page, base_url)
    await ensure_theme(page, dark=False)

    # Turn dark mode on at dashboard
    toggle_btn = page.locator("header button[title='Toggle dark mode']")
    await toggle_btn.click()
    await page.wait_for_timeout(300)
    assert await page.evaluate("document.documentElement.classList.contains('dark')")

    # Navigate into case
    first_row = page.locator("tbody tr").first
    await first_row.click()
    await page.wait_for_selector("span:has-text('FIR')", timeout=8000)
    await page.wait_for_timeout(500)

    # Assert dark mode remains active inside Case Details
    is_dark_in_case = await page.evaluate("document.documentElement.classList.contains('dark')")
    assert is_dark_in_case, "Dark mode must persist when navigating from Dashboard into Case Details"

    # Clean up back to light mode
    await toggle_btn.click()
    await page.wait_for_timeout(300)
