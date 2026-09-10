"""
E2E Playwright Tests for Judge-Critical Gaps:
- P0: New Case Trace Execution from Empty-State Workspace
- P1: Execution Mode Visibility (DEMO REPLAY FIXTURE vs LIVE TRON RPC)
- P2: Header Controls (Bell System Telemetry popover & Help Operating Manual modal)
- Global Search: Cmd/Ctrl+K keyboard shortcut focus
"""
import uuid
import pytest
from playwright.async_api import Page, expect
from tests.e2e.helpers import select_tab


@pytest.mark.asyncio
async def test_global_search_cmd_k_shortcut(page: Page, base_url: str):
    """TC-GAP-01: Cmd/Ctrl+K keyboard shortcut focuses the global search input."""
    await page.goto(base_url, wait_until="networkidle")
    
    # Press Control+k
    await page.keyboard.press("Control+k")
    await page.wait_for_timeout(200)

    # Verify search input is focused
    is_focused = await page.evaluate(
        """() => {
            const active = document.activeElement;
            return active && active.tagName === 'INPUT' && active.getAttribute('placeholder')?.includes('Search address');
        }"""
    )
    assert is_focused, "Control+K must focus the global search bar"


@pytest.mark.asyncio
async def test_bell_telemetry_popover(page: Page, base_url: str):
    """TC-GAP-02: Bell icon opens real System Telemetry & Forensic Alerts popover."""
    await page.goto(base_url, wait_until="networkidle")

    # Click the Bell notifications button
    bell_btn = page.locator("button[aria-label='Notifications']")
    await expect(bell_btn).to_be_visible()
    await bell_btn.click()

    # Verify popover content
    telemetry_heading = page.locator("text=System Telemetry & Alerts")
    await expect(telemetry_heading).to_be_visible()

    # Check database and services health lines
    assert await page.locator("text=PostgreSQL 18").count() > 0, "PostgreSQL 18 status must be shown"
    assert await page.locator("text=Redis Cache").count() > 0, "Redis Cache status must be shown"
    assert await page.locator("text=FastAPI Engine").count() > 0, "FastAPI status must be shown"
    assert await page.locator("text=SHA-256 Merkle Ledger active").count() > 0, "Merkle ledger status must be shown"

    # Close with Esc
    await page.keyboard.press("Escape")
    await page.wait_for_timeout(200)
    assert await page.locator("text=System Telemetry & Alerts").count() == 0, "Escape must dismiss popover"


@pytest.mark.asyncio
async def test_help_operating_manual_modal(page: Page, base_url: str):
    """TC-GAP-03: Help icon opens comprehensive Forensic Operating Manual modal."""
    await page.goto(base_url, wait_until="networkidle")

    # Click Help button
    help_btn = page.locator("button[aria-label='Help']")
    await expect(help_btn).to_be_visible()
    await help_btn.click()

    # Verify Modal title and contents
    modal_title = page.locator("text=Forensic Investigation Operating Manual")
    await expect(modal_title).to_be_visible()

    # Verify standard operational procedure
    assert await page.locator("text=Standard Operational Procedure").count() > 0
    assert await page.locator("text=1. Case Registration").count() > 0
    assert await page.locator("text=2. Multi-Hop Trace Execution").count() > 0
    assert await page.locator("text=3. VASP Attribution & Findings").count() > 0
    assert await page.locator("text=4. Evidence Vault & Legal Export").count() > 0

    # Verify engine modes explained
    assert await page.locator("text=DEMO REPLAY FIXTURE").count() > 0
    assert await page.locator("text=LIVE TRON RPC").count() > 0

    # Verify statutory compliance
    assert await page.get_by_text("Bharatiya Sakshya Adhiniyam", exact=False).count() > 0

    # Dismiss modal with Esc
    await page.keyboard.press("Escape")
    await page.wait_for_timeout(200)
    assert await page.locator("text=Forensic Investigation Operating Manual").count() == 0


@pytest.mark.asyncio
async def test_execution_mode_visibility(case_page: Page):
    """TC-GAP-04: Execution mode is clearly visible in header, stats bar, and VASP banner."""
    page = case_page

    # Verify command header metadata strip mode badge
    header_badge = page.locator("text=DEMO REPLAY FIXTURE").first
    await expect(header_badge).to_be_visible()

    # Verify TraceStatsBar mode indicator
    stats_mode = page.locator("span:has-text('Engine Mode')")
    await expect(stats_mode).to_be_visible()

    # Navigate to VASP Attribution tab
    await select_tab(page, "VASP Attribution")
    banner_mode = page.locator("span:has-text('DEMO REPLAY FIXTURE')")
    assert await banner_mode.count() > 0, "VASP Attribution must display execution mode badge"


@pytest.mark.asyncio
async def test_new_case_empty_state_trace_execution(page: Page, base_url: str):
    """
    TC-GAP-05 (P0 Critical):
    Create a new case -> Verify empty-state Trace Launcher is displayed ->
    Execute Trace -> Progress through pipeline -> Observe completed graph ->
    Verify all 4 downstream tabs (Attribution, Findings, Evidence, Reports) work normally.
    """
    unique_fir = f"FIR-2026-TEST-{uuid.uuid4().hex[:6].upper()}"
    target_wallet = "TYDZSxdBzWnCuB4jF3K6j5X3qW7b9X1234"

    await page.goto(base_url, wait_until="networkidle")

    # Click Register Case button on home
    new_case_btn = page.locator("button:has-text('New Investigation Case')").first
    await expect(new_case_btn).to_be_visible()
    await new_case_btn.click()

    # Fill case intake form
    fir_input = page.locator("input[placeholder*='2026/812']").first
    await expect(fir_input).to_be_visible()
    await fir_input.fill(unique_fir)

    wallet_input = page.locator("input[placeholder*='TRON Address']").first
    await wallet_input.fill(target_wallet)

    loss_input = page.locator("input[placeholder='500000.00']").first
    await loss_input.fill("500000")

    victim_input = page.locator("input[placeholder*='Ramesh Kumar']").first
    await victim_input.fill("Deepak Verma")

    # Submit new case
    submit_btn = page.locator("button:has-text('Register Investigation Case')").first
    await submit_btn.click()

    # Wait for navigation into Case Workspace
    await page.wait_for_timeout(1000)
    await expect(page.locator(f"span:has-text('{unique_fir}')")).to_be_visible()

    # Verify Empty State Trace Launcher Card is displayed
    launcher_heading = page.locator("text='Trace Suspect Wallet'")
    await expect(launcher_heading).to_be_visible()

    # Verify target wallet is prefilled in launcher
    wallet_field = page.locator(f"input[value='{target_wallet}']").first
    await expect(wallet_field).to_be_visible()

    # Verify DEMO and LIVE options are present
    assert await page.locator("button:has-text('DEMO REPLAY')").count() > 0
    assert await page.locator("button:has-text('LIVE TRON RPC')").count() > 0

    # Click "Execute Multi-Hop Trace"
    execute_btn = page.locator("button:has-text('Execute Multi-Hop Trace')")
    await expect(execute_btn).to_be_visible()
    await execute_btn.click()

    # Wait for trace completion and graph rendering
    traversal_depth = page.locator("text='Traversal Depth'")
    await expect(traversal_depth).to_be_visible(timeout=15000)

    # Verify Active Topology is rendered
    active_topology = page.locator("text='Active Topology'")
    await expect(active_topology).to_be_visible()

    # Verify Re-Trace button is available in toolbar
    retrace_btn = page.locator("button:has-text('Re-Trace')")
    await expect(retrace_btn).to_be_visible()

    # 1. Verify VASP Attribution tab works
    await select_tab(page, "VASP Attribution")
    vasp_heading = page.locator("text=Attribution Finding:")
    await expect(vasp_heading).to_be_visible(timeout=8000)

    # 2. Verify Forensic Findings tab works
    await select_tab(page, "Forensic Findings")
    findings_panel = page.locator("h2:has-text('Forensic Findings & Alerts')")
    await expect(findings_panel).to_be_visible(timeout=8000)

    # 3. Verify Evidence Vault tab works
    await select_tab(page, "Evidence Vault")
    evidence_vault = page.locator("text=Cryptographic SHA-256 Hash")
    await expect(evidence_vault).to_be_visible(timeout=8000)

    # 4. Verify Reports tab works
    await select_tab(page, "Reports & Legal Draft")
    reports_view = page.locator("text=Complete Evidence Dossier")
    await expect(reports_view).to_be_visible(timeout=8000)
