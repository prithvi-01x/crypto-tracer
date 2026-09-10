"""
Tier 1 Feature Coverage: Cytoscape Graph Canvas & Toolbar (R2)
Verifies canvas initialization, multi-hop rendering, floating toolbar
controls (zoom, fit, center, layout), and forensic legend indicators.
"""
import pytest
from playwright.async_api import Page


@pytest.mark.asyncio
async def test_canvas_container_mounts(case_page: Page):
    """TC-T1-GC-01: Cytoscape container and canvas layers mount successfully in Trace Graph view."""
    page = case_page
    # Verify graph header banner
    graph_header = page.locator("h3:has-text('Forensic Transaction Graph')")
    assert await graph_header.count() > 0, "Forensic Transaction Graph heading should be visible"

    # Verify canvas elements rendered
    canvases = page.locator("canvas")
    canvas_count = await canvases.count()
    assert canvas_count >= 1, f"Expected at least 1 canvas element, got {canvas_count}"


@pytest.mark.asyncio
async def test_canvas_renders_multi_hop_elements(case_page: Page):
    """TC-T1-GC-02: Canvas element has active dimensions and renders non-zero drawing surface."""
    page = case_page
    top_canvas = page.locator("canvas").last
    box = await top_canvas.bounding_box()
    assert box is not None, "Canvas bounding box must be defined"
    assert box["width"] > 300, f"Canvas width ({box['width']}) should exceed 300px"
    assert box["height"] > 300, f"Canvas height ({box['height']}) should exceed 300px"

    # Verify subtitle indicator for multi-hop
    subtitle = page.locator("span:has-text('TRC-20 USDT Flow')")
    assert await subtitle.count() > 0, "Multi-hop TRC-20 USDT Flow badge should be visible"


@pytest.mark.asyncio
async def test_graph_toolbar_controls_present(case_page: Page):
    """TC-T1-GC-03: Floating toolbar controls (Zoom In, Zoom Out, Fit, Center, Reset, Tag) are present."""
    page = case_page
    expected_buttons = [
        "Zoom In",
        "Zoom Out",
        "Fit to Screen",
        "Center on Root Suspect",
        "Re-run Directed Layout",
    ]
    for title in expected_buttons:
        btn = page.locator(f"button[title='{title}']")
        assert await btn.count() > 0, f"Toolbar button with title '{title}' must be present"


@pytest.mark.asyncio
async def test_graph_toolbar_zoom_and_fit_actions(case_page: Page):
    """TC-T1-GC-04: Clicking Zoom In, Zoom Out, and Fit to Screen functions without error."""
    page = case_page
    zoom_in = page.locator("button[title='Zoom In']")
    zoom_out = page.locator("button[title='Zoom Out']")
    fit_btn = page.locator("button[title='Fit to Screen']")

    # Click zoom in twice
    await zoom_in.click()
    await page.wait_for_timeout(200)
    await zoom_in.click()
    await page.wait_for_timeout(200)

    # Click zoom out
    await zoom_out.click()
    await page.wait_for_timeout(200)

    # Click fit to screen
    await fit_btn.click()
    await page.wait_for_timeout(300)

    # Ensure canvas is still intact
    canvases = page.locator("canvas")
    assert await canvases.count() >= 1, "Canvas must remain mounted and functional after zoom actions"


@pytest.mark.asyncio
async def test_graph_legend_indicators_rendered(case_page: Page):
    """TC-T1-GC-05: Legend bar renders Suspect, Intermediate, and Endpoint/Deposit categories."""
    page = case_page
    suspect_legend = page.locator("span:has-text('Suspect')")
    assert await suspect_legend.count() > 0, "Legend should display 'Suspect' category"

    intermediate_legend = page.locator("span:has-text('Intermediate')")
    assert await intermediate_legend.count() > 0, "Legend should display 'Intermediate' category"

    endpoint_legend = page.locator("span:has-text('Endpoint')")
    assert await endpoint_legend.count() > 0, "Legend should display 'Endpoint' category"


@pytest.mark.asyncio
async def test_graph_amount_label_toggle(case_page: Page):
    """TC-T1-GC-06: Tag button toggles amount label visibility and title."""
    page = case_page
    tag_btn = page.locator("button[title*='Amount Labels']")
    assert await tag_btn.count() > 0, "Amount label toggle button must exist"

    initial_title = await tag_btn.get_attribute("title")
    # Click to toggle
    await tag_btn.click()
    await page.wait_for_timeout(300)
    new_title = await tag_btn.get_attribute("title")
    assert initial_title != new_title, "Toggle button title must alternate between Hide and Show Amount Labels"

    # Restore initial state
    await tag_btn.click()
    await page.wait_for_timeout(200)
