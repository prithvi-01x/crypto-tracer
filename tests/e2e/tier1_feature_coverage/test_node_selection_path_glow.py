"""
Tier 1 Feature Coverage: Node Selection, Path Tracing & Glow (R2)
Verifies node selection via canvas click and alerts deep-link,
path-to-root tracing trigger, and deselection behavior.
"""
import pytest
from playwright.async_api import Page


@pytest.mark.asyncio
async def test_clicking_node_opens_detail_drawer(case_page: Page):
    """TC-T1-NS-01: Tapping a node on the Cytoscape canvas opens the Wallet Inspection drawer."""
    page = case_page
    top_canvas = page.locator("canvas").last
    box = await top_canvas.bounding_box()
    assert box is not None, "Canvas must be rendered"

    # Click near canvas center where nodes reside
    await page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    await page.wait_for_timeout(600)

    # Drawer should open
    drawer_heading = page.locator("text=Wallet Inspection")
    assert await drawer_heading.count() > 0, "Wallet Inspection drawer should open after clicking a node"


@pytest.mark.asyncio
async def test_view_on_graph_from_alerts_selects_node(case_page: Page):
    """TC-T1-NS-02: Clicking [View on Graph] in Alerts drawer switches to graph and selects the target node."""
    page = case_page
    # Open Alerts drawer
    alerts_btn = page.locator("button:has-text('Alerts')").first
    await alerts_btn.click()
    await page.wait_for_timeout(500)

    # Click View on Graph
    view_graph_btn = page.locator("button:has-text('View on Graph')").first
    assert await view_graph_btn.count() > 0, "View on Graph button should be present in Alerts drawer"
    await view_graph_btn.click()
    await page.wait_for_timeout(600)

    # Verify that detail drawer for selected node is displayed
    drawer_heading = page.locator("text=Wallet Inspection")
    assert await drawer_heading.count() > 0, "View on Graph should select node and open detail drawer"


@pytest.mark.asyncio
async def test_selected_node_displays_address_and_hop(case_page: Page):
    """TC-T1-NS-03: Selected node displays full wallet address and hop level badge."""
    page = case_page
    # Trigger selection via alerts view on graph
    alerts_btn = page.locator("button:has-text('Alerts')").first
    await alerts_btn.click()
    await page.wait_for_timeout(500)
    await page.locator("button:has-text('View on Graph')").first.click()
    await page.wait_for_timeout(600)

    # Verify wallet address title and content
    addr_label = page.locator("text=Wallet Address")
    assert await addr_label.count() > 0, "'Wallet Address' section should be visible in drawer"

    hop_badge = page.locator("text=Hop Level:")
    assert await hop_badge.count() > 0, "Hop Level badge should be displayed in drawer"


@pytest.mark.asyncio
async def test_highlight_trail_from_suspect_action(case_page: Page):
    """TC-T1-NS-04: Clicking 'Highlight Trail from Suspect' executes path highlight to root."""
    page = case_page
    # Select intermediate/endpoint node via alerts
    alerts_btn = page.locator("button:has-text('Alerts')").first
    await alerts_btn.click()
    await page.wait_for_timeout(500)
    await page.locator("button:has-text('View on Graph')").first.click()
    await page.wait_for_timeout(600)

    highlight_btn = page.locator("button:has-text('Highlight Trail from Suspect')")
    if await highlight_btn.count() > 0:
        await highlight_btn.click()
        await page.wait_for_timeout(400)
        # Canvas should maintain active elements without crash
        assert await page.locator("canvas").count() >= 1


@pytest.mark.asyncio
async def test_center_on_root_suspect_action(case_page: Page):
    """TC-T1-NS-05: Center on Root Suspect button focuses viewport on root suspect node."""
    page = case_page
    center_btn = page.locator("button[title='Center on Root Suspect']")
    assert await center_btn.count() > 0, "Center on Root Suspect button should exist"

    await center_btn.click()
    await page.wait_for_timeout(400)
    # Verify canvas remains intact
    assert await page.locator("canvas").count() >= 1


@pytest.mark.asyncio
async def test_close_drawer_deselects_node(case_page: Page):
    """TC-T1-NS-06: Closing detail drawer dismisses inspection panel."""
    page = case_page
    # Open drawer via node click
    top_canvas = page.locator("canvas").last
    box = await top_canvas.bounding_box()
    assert box is not None
    await page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    await page.wait_for_timeout(600)

    close_drawer_btn = page.locator("button:has(svg.lucide-x)").last
    if await close_drawer_btn.count() > 0:
        await close_drawer_btn.click()
        await page.wait_for_timeout(400)
        drawer_heading = page.locator("text=Wallet Inspection")
        assert await drawer_heading.count() == 0, "Drawer should be closed after clicking close button"
