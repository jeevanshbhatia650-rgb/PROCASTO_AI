"""End-to-end smoke test in a real browser (the Edge or Chrome already installed; no download).

Covers what a first-time visitor does. It never creates an account or signs in: those flows are unit-tested
with mocks and checked by hand against the real Supabase project.

    uv run --no-project --with playwright python e2e/smoke.py http://localhost:8000
"""

import asyncio
import os
import re
import sys

from playwright.async_api import Page, async_playwright, expect

STEPS: list[str] = []


def step(name: str) -> None:
    STEPS.append(name)
    print(f"  ok  {name}")


async def fits_the_screen(page: Page) -> None:
    """Nothing pushes the page sideways (a wide chart once did, by 11 px on a phone)."""
    wide = await page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
    assert wide <= 0, f"{page.url} is {wide}px wider than the screen"


async def landing(page: Page, base: str) -> None:
    response = await page.goto(base + "/")
    assert response is not None
    await expect(page.get_by_role("heading", name="Your home, explained.")).to_be_visible()
    step("landing page shows the headline")
    if base.endswith(":8000"):  # the production server adds security headers; the dev server doesn't
        headers = response.headers
        assert "script-src 'self'" in headers.get("content-security-policy", ""), headers
        assert headers.get("x-frame-options") == "DENY"
        step("security headers are on the page")
    if page.viewport_size and page.viewport_size["width"] >= 768:  # phones scroll; the section links are desktop-only
        await page.get_by_role("navigation", name="Main").get_by_role("link", name="What's different").click()
        await expect(page.get_by_role("heading", name="Not another dashboard.")).to_be_in_viewport()
        step("nav link scrolls to its section")


async def demo_fault_to_answer(page: Page, base: str) -> None:
    await page.goto(base + "/")
    await page.get_by_role("link", name="Try the live demo").first.click()
    await expect(page).to_have_url(base + "/demo")
    await expect(page.get_by_text("3 simulated devices")).to_be_visible(timeout=15000)
    await expect(page.get_by_role("region", name="Laundry room")).to_be_visible()
    await page.get_by_role("button", name=re.compile("Living room")).click()
    await expect(page.get_by_role("region", name="Living room")).to_be_visible()
    await page.get_by_role("button", name=re.compile("Laundry room")).click()
    await expect(page.get_by_role("region", name="Power right now")).to_be_visible()
    await fits_the_screen(page)
    if shots := os.environ.get("PROCASTO_E2E_SHOTS"):
        await page.screenshot(path=os.path.join(shots, f"home-{page.viewport_size['width']}.png"), full_page=True)
    step("demo home focuses one room at a time, with live power under it")

    await page.keyboard.press("1")  # washer E3, same as the rail button
    attention = page.get_by_role("region", name="Home insight")
    await expect(attention.get_by_text("1 device needs attention")).to_be_visible(timeout=10000)
    step("breaking the washer brings a fault into Worth knowing")
    await expect(page.get_by_text("Washer stopped · error E3")).to_be_visible()
    step("a followed device that breaks raises an alert")

    await page.get_by_role("region", name="Laundry room").get_by_role("link").first.click()
    await expect(page).to_have_url(base + "/demo/assistant")
    await expect(page.get_by_role("button", name="Talk")).to_be_visible()
    if shots := os.environ.get("PROCASTO_E2E_SHOTS"):
        await page.screenshot(path=os.path.join(shots, f"assistant-{page.viewport_size['width']}.png"), full_page=True)
    problem = page.get_by_text("E3 · Water not draining")
    await expect(problem.first).to_be_visible(timeout=20000)
    await expect(page.get_by_text("WW90T sample manual §E3 p.41").first).to_be_visible()
    step("Ask why answers with the manual page it came from")

    await page.get_by_role("switch", name="Under the hood").click()
    await expect(page.get_by_text("Head start")).to_be_visible()
    heard = page.get_by_role("complementary", name="Under the hood").get_by_role("region", name="What it heard")
    await expect(heard.get_by_text("E3", exact=False)).to_be_visible()
    await fits_the_screen(page)
    step("the engine view opens, with the words it heard")


async def guards(page: Page, base: str) -> None:
    await page.goto(base + "/app")
    await expect(page).to_have_url(base + "/login?next=%2Fapp", timeout=15000)
    await expect(page.get_by_role("heading", name="Welcome back")).to_be_visible()
    step("signed-out visitors are sent to sign in")

    await page.get_by_label("Email").fill("not-an-email")
    await page.get_by_role("button", name="Sign in").click()
    await expect(page.get_by_text("Enter a valid email address.")).to_be_visible()
    step("the sign-in form checks input before sending anything")

    await page.goto(base + "/no-such-page")
    await expect(page.get_by_role("heading", name="Nothing here")).to_be_visible()
    step("unknown pages get the 404 page")


async def main(base: str) -> None:
    errors: list[str] = []
    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(channel="msedge")
        except Exception:
            browser = await p.chromium.launch(channel="chrome")
        for width, height in ((1440, 900), (390, 844)):
            print(f"viewport {width}x{height}")
            context = await browser.new_context(viewport={"width": width, "height": height})
            page = await context.new_page()
            page.on("pageerror", lambda e: errors.append(str(e)))
            await landing(page, base)
            await demo_fault_to_answer(page, base)
            await guards(page, base)
            await context.close()
        await browser.close()
    if errors:
        raise SystemExit(f"page errors: {errors[:5]}")
    print(f"PASS: {len(STEPS)} checks")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://localhost:8000"))
