#!/usr/bin/env python3
"""SP80 Browser Automation - Playwright"""
import sys, os, time, json
sys.path.insert(0, '/a0/usr/workdir/.venv/lib/python3.13/site-packages')

from playwright.sync_api import sync_playwright

URL = "https://arcprize.org/tasks/sp80"
LEVELS_L1 = [
    ("3xRIGHT+spill", ["ArrowRight"]*3 + [" "]),
]

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=["--no-sandbox", "--disable-gpu"])
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        
        print(f"1. Navegando para {URL}...")
        page.goto(URL, wait_until="networkidle")
        time.sleep(1)
        
        print("2. Verificando estado...")
        page.screenshot(path="/a0/usr/workdir/sp80_playwright_1.png")
        
        # Find START button via text
        print("3. Clicando START...")
        start_btn = page.get_by_role("button", name="START")
        if start_btn.count() > 0:
            start_btn.click()
            time.sleep(0.5)
        else:
            print("   START button not found, trying text...")
            start_btn = page.locator("text=START").first
            if start_btn.count() > 0:
                start_btn.click()
                time.sleep(0.5)
        
        page.screenshot(path="/a0/usr/workdir/sp80_playwright_2_started.png")
        
        # Focus on the game area - try finding iframe, then canvas
        print("4. Procurando iframe/canvas para foco...")
        
        # Try to find and focus the iframe first
        iframe_elem = page.query_selector("iframe")
        if iframe_elem:
            print("   Iframe encontrado! Tentando foco...")
            iframe_elem.focus()
            time.sleep(0.2)
            # Press Tab to focus inner content
            page.keyboard.press("Tab")
            time.sleep(0.2)
            page.keyboard.press("Tab")
            time.sleep(0.2)
        
        # Try clicking center of game area
        print("5. Clicando no centro do canvas...")
        page.mouse.click(420, 350)
        time.sleep(0.3)
        
        print("6. Enviando ArrowRight x3 + Space...")
        page.keyboard.press("ArrowRight")
        time.sleep(0.15)
        page.keyboard.press("ArrowRight")
        time.sleep(0.15)
        page.keyboard.press("ArrowRight")
        time.sleep(0.15)
        page.keyboard.press(" ")
        time.sleep(1)
        
        print("7. Screenshot pós-ação...")
        page.screenshot(path="/a0/usr/workdir/sp80_playwright_3_after_spill.png")
        
        # Check if level advanced
        body = page.locator("body").text_content()
        if "Level 2" in body:
            print("✅ LEVEL 1 COMPLETO! Avançou para Level 2!")
        else:
            print("⚠️ Level 1 pode não ter completado")
        
        # Try selecting Level 5 via SELECT
        print("8. Tentando SELECT para pular para Level 5...")
        select_btn = page.get_by_role("button", name="SELECT")
        if select_btn.count() > 0:
            select_btn.click()
            time.sleep(0.5)
            page.screenshot(path="/a0/usr/workdir/sp80_playwright_4_select.png")
            # Try clicking level 5 in selector
            lvl5 = page.locator("text=Level 5")
            if lvl5.count() > 0:
                lvl5.click()
                time.sleep(0.3)
                page.screenshot(path="/a0/usr/workdir/sp80_playwright_5_level5.png")
        
        browser.close()
        print("
Pronto! Verifique screenshots em /a0/usr/workdir/sp80_playwright_*.png")

if __name__ == "__main__":
    main()
