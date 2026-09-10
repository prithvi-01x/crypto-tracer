"""
Tier 1 Feature Coverage: Case Notes & Dossier Export Modals (R4)
Verifies Add Note modal opening, dual mode tabs (append/edit),
quick template chips, author inputs, cancellation, and export quick actions.
"""
import pytest
from playwright.async_api import Page


@pytest.mark.asyncio
async def test_add_note_button_opens_modal(case_page: Page):
    """TC-T1-MD-01: Clicking 'Add Note' in header opens the Investigation Notes modal."""
    page = case_page
    add_note_btn = page.locator("header button:has-text('Add Note'), div button:has-text('Add Note')").first
    assert await add_note_btn.count() > 0, "Add Note button must be present"

    await add_note_btn.click()
    await page.wait_for_timeout(400)

    modal_heading = page.locator("text=Investigation Notes & Observations")
    assert await modal_heading.count() > 0, "Investigation Notes modal must be visible"

    # Close modal
    await page.locator("button:has-text('Cancel')").click()
    await page.wait_for_timeout(300)


@pytest.mark.asyncio
async def test_notes_modal_has_dual_modes(case_page: Page):
    """TC-T1-MD-02: Notes modal renders both 'Append Timestamped Entry' and 'Edit Full Case Notes' modes."""
    page = case_page
    await page.locator("button:has-text('Add Note')").first.click()
    await page.wait_for_timeout(400)

    append_tab = page.locator("button:has-text('Append Timestamped Entry')")
    assert await append_tab.count() > 0, "'Append Timestamped Entry' tab must exist"

    edit_tab = page.locator("button:has-text('Edit Full Case Notes')")
    assert await edit_tab.count() > 0, "'Edit Full Case Notes' tab must exist"

    # Switch to edit tab
    await edit_tab.click()
    await page.wait_for_timeout(300)
    full_notes_label = page.locator("text=Full Case Notes & Modus Operandi")
    assert await full_notes_label.count() > 0, "Full Case Notes editor should be displayed"

    # Close modal
    await page.locator("button:has-text('Cancel')").click()
    await page.wait_for_timeout(300)


@pytest.mark.asyncio
async def test_notes_modal_quick_template_chips(case_page: Page):
    """TC-T1-MD-03: Clicking a quick template chip inserts standard legal text into the note textarea."""
    page = case_page
    await page.locator("button:has-text('Add Note')").first.click()
    await page.wait_for_timeout(400)

    # Click first template chip (e.g. Section 91 CrPC notice or Section 94 BNSS)
    chip = page.locator("button:has-text('Section 91 CrPC'), button:has-text('Section 94 BNSS')").first
    assert await chip.count() > 0, "Quick template chip must exist"
    await chip.click()
    await page.wait_for_timeout(200)

    # Verify textarea contains inserted template text
    textarea = page.locator("textarea[placeholder*='investigation updates']")
    text_val = await textarea.input_value()
    assert len(text_val.strip()) > 10, f"Textarea should be populated with template text, got: '{text_val}'"

    # Clean up
    await page.locator("button:has-text('Cancel')").click()
    await page.wait_for_timeout(300)


@pytest.mark.asyncio
async def test_notes_modal_author_input_field(case_page: Page):
    """TC-T1-MD-04: Notes modal allows modifying the Officer / Source input."""
    page = case_page
    await page.locator("button:has-text('Add Note')").first.click()
    await page.wait_for_timeout(400)

    author_input = page.locator("input[placeholder*='Insp. Sharma']")
    assert await author_input.count() > 0, "Author input field should be present"

    await author_input.fill("Cyber Cell IO Inspector Rao")
    val = await author_input.input_value()
    assert val == "Cyber Cell IO Inspector Rao", "Author input should accept custom text"

    # Clean up
    await page.locator("button:has-text('Cancel')").click()
    await page.wait_for_timeout(300)


@pytest.mark.asyncio
async def test_notes_modal_close_via_x_button(case_page: Page):
    """TC-T1-MD-05: Clicking the top-right 'X' icon dismisses the modal."""
    page = case_page
    await page.locator("button:has-text('Add Note')").first.click()
    await page.wait_for_timeout(400)

    # Find X close button inside modal
    modal_container = page.locator("div.fixed.inset-0")
    x_btn = modal_container.locator("button:has(svg.lucide-x)").first
    assert await x_btn.count() > 0, "Modal X button must exist"

    await x_btn.click()
    await page.wait_for_timeout(300)

    modal_heading = page.locator("text=Investigation Notes & Observations")
    assert await modal_heading.count() == 0, "Modal should be closed after clicking X button"


@pytest.mark.asyncio
async def test_export_dossier_quick_action(case_page: Page):
    """TC-T1-MD-06: Clicking 'Export Trace Dossier' in header navigates to the Reports & Legal Draft tab."""
    page = case_page
    export_btn = page.locator("button:has-text('Export Trace Dossier')").first
    assert await export_btn.count() > 0, "Export Trace Dossier button must be present"

    await export_btn.click()
    await page.wait_for_timeout(500)

    # Verify Reports tab is now active and displays Evidence Dossier
    dossier_card = page.locator("text=Complete Evidence Dossier (PDF)")
    assert await dossier_card.count() > 0, "Clicking Export Trace Dossier should navigate to Reports tab"
