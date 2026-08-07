import os, time, sys
os.environ['PLAYWRIGHT_BROWSERS_PATH'] = '/a0/usr/workdir/.venv/ms-playwright'
sys.path.insert(0, '/a0/usr/workdir/.venv/lib/python3.13/site-packages')
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

with sync_playwright() as p:
    b = p.chromium.launch(headless=True, args=['--no-sandbox'])
    page = b.new_page(viewport={'width':1280,'height':900})
    page.set_default_timeout(15000)
    
    try:
        page.goto('https://arcprize.org/tasks/sp80', wait_until='domcontentloaded', timeout=25000)
        print('Page loaded')
        page.screenshot(path='/a0/usr/workdir/sp80_pw_a.png')
        
        # Try all possible selectors for START
        selectors = [
            'button:has-text("START")',
            '[role="button"]:has-text("START")',
            'text=START',
            'button'  # last resort
        ]
        clicked = False
        for sel in selectors[:3]:  # try named first
            try:
                btn = page.wait_for_selector(sel, timeout=3000)
                if btn:
                    btn.click()
                    print(f'Clicked: {sel}')
                    clicked = True
                    break
            except:
                continue
        
        if not clicked:
            page.evaluate('() => { document.querySelectorAll("button").forEach(b => { if(b.textContent.includes("START")) b.click(); }) }')
            print('Clicked via evaluate')
        
        time.sleep(1)
        page.screenshot(path='/a0/usr/workdir/sp80_pw_b.png')
        
        # Try to focus game canvas via evaluate
        page.evaluate('() => { document.querySelectorAll("canvas, iframe").forEach(el => el.focus()) }')
        time.sleep(0.2)
        
        # Send keys directly
        page.keyboard.press('ArrowRight')
        time.sleep(0.1)
        page.keyboard.press('ArrowRight')
        time.sleep(0.1)
        page.keyboard.press('ArrowRight')
        time.sleep(0.1)
        page.keyboard.press(' ')
        time.sleep(0.5)
        
        page.screenshot(path='/a0/usr/workdir/sp80_pw_c.png')
        print('Keys sent, screenshots saved')
        
        # Check level
        body = page.text_content('body') or ''
        for ln in body.split('\n'):
            if 'Level' in ln:
                print(f'Level: {ln.strip()}')
        
    except Exception as e:
        print(f'Error: {e}')
        page.screenshot(path='/a0/usr/workdir/sp80_pw_error.png')
    
    b.close()
