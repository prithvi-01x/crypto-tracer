"""
Tier 1 Feature Coverage: Entity Profiler Workstation (R3)
Verifies wallet entity card, risk badges, TronScan link,
address clipboard copy action, financial volume metrics, and forensic seal.
"""
import pytest
from playwright.async_api import Page


async def _select_node_for_test(page: Page):
    """Helper to select a node and open the Entity Profiler drawer."""
    alerts_btn = page.locator("button:has-text('Alerts')").first
    await alerts_btn.click()
    await page.wait_for_timeout(500)
    await page.locator("button:has-text('View on Graph')").first.click()
    await page.wait_for_timeout(600)


@pytest.mark.asyncio
async def test_entity_drawer_renders_node_type_badge(case_page: Page):
    """TC-T1-EP-01: Entity drawer renders node classification badge (Root Suspect / Intermediate / Endpoint)."""
    page = case_page
    await _select_node_for_test(page)

    badge = page.locator("span:has-text('Root Suspect'), span:has-text('Intermediate Hop'), span:has-text('Endpoint')")
    assert await badge.count() > 0, "Drawer should render a node type classification badge"


@pytest.mark.asyncio
async def test_entity_drawer_displays_wallet_address(case_page: Page):
    """TC-T1-EP-02: Entity drawer displays full Base58 wallet address in monospace font."""
    page = case_page
    await _select_node_for_test(page)

    addr_header = page.locator("text=Wallet Address")
    assert await addr_header.count() > 0, "Wallet Address heading must be present"

    # Verify wallet address starts with 'T' (TRON standard address)
    addr_elem = page.locator("div.font-mono.text-base.text-emerald-300, div:has-text('TBinance'), div:has-text('TSuspect'), div:has-text('TLayering')")
    assert await addr_elem.count() > 0, "A valid TRON address string should be visible in drawer"


@pytest.mark.asyncio
async def test_entity_drawer_copy_address_button(case_page: Page):
    """TC-T1-EP-03: Clicking Copy Address triggers visual 'Copied' confirmation."""
    page = case_page
    await _select_node_for_test(page)

    copy_btn = page.locator("button:has-text('Copy Address')")
    assert await copy_btn.count() > 0, "Copy Address button should exist"

    await copy_btn.click()
    await page.wait_for_timeout(300)

    copied_indicator = page.locator("span:has-text('Copied')")
    assert await copied_indicator.count() > 0, "Button should display 'Copied' state upon click"


@pytest.mark.asyncio
async def test_entity_drawer_tronscan_link(case_page: Page):
    """TC-T1-EP-04: Drawer provides external link to TronScan block explorer."""
    page = case_page
    await _select_node_for_test(page)

    tronscan_link = page.locator("a:has-text('TronScan')")
    assert await tronscan_link.count() > 0, "TronScan external link must be rendered"

    href = await tronscan_link.get_attribute("href")
    assert href is not None and "tronscan.org/#/address/" in href, f"Invalid TronScan href: {href}"
    assert await tronscan_link.get_attribute("target") == "_blank", "TronScan link must open in new tab"


@pytest.mark.asyncio
async def test_entity_drawer_financial_volume_metrics(case_page: Page):
    """TC-T1-EP-05: Entity drawer renders financial summary metrics (Total Received, Sent, Tx count)."""
    page = case_page
    await _select_node_for_test(page)

    received_metric = page.locator("text=Total Received")
    assert await received_metric.count() > 0, "Total Received metric header should be present"

    sent_metric = page.locator("text=Total Sent Out")
    assert await sent_metric.count() > 0, "Total Sent Out metric header should be present"

    tx_count = page.locator("text=Observed Transactions:")
    assert await tx_count.count() > 0, "Observed Transactions counter should be present"


@pytest.mark.asyncio
async def test_entity_drawer_footer_integrity_badge(case_page: Page):
    """TC-T1-EP-06: Drawer footer displays forensic seal badge."""
    page = case_page
    await _select_node_for_test(page)

    footer_seal = page.locator("text=Forensic Integrity Sealed")
    assert await footer_seal.count() > 0, "Forensic Integrity Sealed badge must be present in drawer footer"
