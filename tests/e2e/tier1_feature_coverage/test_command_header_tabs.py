"""
Tier 1 Feature Coverage: Command Header & Navigation Tabs (R4)
Verifies FIR context, victim reference, dual currency loss metrics (INR/USDT),
chain indicator, 5 primary workspace tabs, and active tab transitions.
"""
import pytest
from playwright.async_api import Page
from tests.e2e.helpers import select_tab


@pytest.mark.asyncio
async def test_case_context_header_fir_and_victim(case_page: Page):
    """TC-T1-CH-01: Command header renders FIR reference, victim name, and case number."""
    page = case_page
    fir_elem = page.locator("span:has-text('FIR-2026-DEL-CY-0812')")
    assert await fir_elem.count() > 0, "FIR number must be displayed in command header"

    victim_elem = page.locator("span:has-text('Ramesh Kumar')")
    assert await victim_elem.count() > 0, "Victim reference must be displayed in command header"


@pytest.mark.asyncio
async def test_case_context_header_dual_currency_loss(case_page: Page):
    """TC-T1-CH-02: Loss amount is displayed in both INR and USDT denominations."""
    page = case_page
    # Check INR representation (formatted Indian currency, contains ₹)
    inr_elem = page.locator("span:has-text('₹')")
    assert await inr_elem.count() > 0, "Loss amount in INR with ₹ symbol must be visible"

    # Check USDT representation
    usdt_elem = page.locator("span:has-text('USDT')")
    assert await usdt_elem.count() > 0, "Loss amount in USDT must be visible"


@pytest.mark.asyncio
async def test_case_context_header_chain_indicator(case_page: Page):
    """TC-T1-CH-03: Blockchain network and token standard badge (TRON / TRC-20) are displayed."""
    page = case_page
    chain_badge = page.locator("span:has-text('TRON')")
    assert await chain_badge.count() > 0, "Chain indicator (TRON) must be visible in header"


@pytest.mark.asyncio
async def test_all_five_workspace_tabs_rendered(case_page: Page):
    """TC-T1-CH-04: All 5 primary investigation workspace tabs are rendered."""
    page = case_page
    expected_tabs = [
        "Trace Graph",
        "VASP Attribution",
        "Forensic Findings",
        "Evidence Vault",
        "Reports & Legal Draft",
    ]
    for tab in expected_tabs:
        btn = page.locator(f"button:has-text('{tab}')")
        assert await btn.count() > 0, f"Workspace tab '{tab}' must be present"


@pytest.mark.asyncio
async def test_forensic_findings_alert_counter_badge(case_page: Page):
    """TC-T1-CH-05: Forensic Findings tab displays a numerical badge representing open alerts."""
    page = case_page
    findings_tab = page.locator("button:has-text('Forensic Findings')")
    # Inside the tab, check for a number badge
    badge = findings_tab.locator("span.font-mono, span.font-bold")
    assert await badge.count() > 0, "Findings tab must contain a numerical count badge"
    badge_text = await badge.first.text_content()
    assert badge_text.strip().isdigit(), f"Alert badge text '{badge_text}' must be numeric"


@pytest.mark.asyncio
async def test_tab_navigation_switches_active_view(case_page: Page):
    """TC-T1-CH-06: Clicking workspace tabs switches the active panel content."""
    page = case_page
    # 1. Switch to VASP Attribution
    await select_tab(page, "VASP Attribution")
    assert await page.locator("text=Attribution Finding").count() > 0, "Attribution view must mount"

    # 2. Switch to Forensic Findings
    await select_tab(page, "Forensic Findings")
    assert await page.locator("text=Forensic Findings & Alerts").count() > 0, "Findings panel must mount"

    # 3. Switch to Evidence Vault
    await select_tab(page, "Evidence Vault")
    assert await page.locator("text=Filters & Classification").count() > 0, "Evidence workstation must mount"

    # 4. Switch to Reports & Legal Draft
    await select_tab(page, "Reports & Legal Draft")
    assert await page.locator("text=Complete Evidence Dossier (PDF)").count() > 0, "Reports view must mount"

    # 5. Switch back to Trace Graph
    await select_tab(page, "Trace Graph")
    assert await page.locator("text=Forensic Transaction Graph").count() > 0, "Graph canvas must mount"
