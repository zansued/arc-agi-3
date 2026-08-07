#!/usr/bin/env python3
import os, time
os.environ['PLAYWRIGHT_BROWSERS_PATH'] = '/a0/usr/workdir/.venv/ms-playwright'
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
    page = browser.new_page(viewport={'width': 1280, 'height': 900})
    print('1. Navegando para SP80...')
    page.goto('https://arcprize.org/tasks/sp80', timeout=30000)
    time.sleep(1)
    page.screenshot(path='/a0/usr/workdir/sp80_pw_1.png')
    print('   Screenshot 1 OK')
    
    print('2. Clicando START...')
    try:
        starter = page.get_by_role('button', name='START')
        if starter.count():
            starter.click()
            print('   START clicked by role!')
        else:
            page.locator('text=START').first.click()
            print('   START clicked by text!')
    except Exception as e:
        print(f'   START error: {e}')
        try:
            page.evaluate("document.querySelector('button').click()")
        except:
            pass
    time.sleep(1)
    page.screenshot(path='/a0/usr/workdir/sp80_pw_2.png')
    print('   Screenshot 2 OK')
    
    print('3. Focando e enviando teclas...')
    page.mouse.click(420, 350)
    time.sleep(0.2)
    
    for k in ['ArrowRight','ArrowRight','ArrowRight',' ']:
        page.keyboard.press(k)
        time.sleep(0.05)
    time.sleep(1)
    
    page.screenshot(path='/a0/usr/workdir/sp80_pw_3.png')
    print('   Screenshot 3 OK')
    
    body = page.text_content('body') or ''
    if 'Level 2' in body:
        print('\n*** LEVEL 1 COMPLETO! ***')
    else:
        for ln in body.split('\n'):
            if 'Level' in ln and '/' in ln:
                print(f'   Level state: {ln.strip()}')
    
    browser.close()
    print('\nDone!')
