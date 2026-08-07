import asyncio
from playwright.async_api import async_playwright

async def run_test():
    print("=" * 60)
    print("PLAYWRIGHT MOVEMENT TEST - LS20 Level 1")
    print("=" * 60)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        print("\n🌐 Opening LS20...")
        await page.goto("https://arcprize.org/tasks/ls20", wait_until="networkidle")
        await page.wait_for_timeout(2000)
        print("✅ Page loaded")
        
        canvas = await page.query_selector("canvas")
        if not canvas:
            print("❌ No canvas found")
            await browser.close()
            return
        print("✅ Canvas found")
        
        # Click START
        start_button = await page.query_selector("text=START")
        if start_button:
            await start_button.click()
            print("✅ START clicked")
            await page.wait_for_timeout(1000)
        
        # Screenshot before movement
        await page.screenshot(path="test_pw_before.png", full_page=False)
        print("📸 Screenshot BEFORE saved")
        
        # Test movement
        print("\n🎮 Testing ArrowDown...")
        await page.keyboard.press("ArrowDown")
        await page.wait_for_timeout(400)
        await page.screenshot(path="test_pw_arrowdown.png", full_page=False)
        print("📸 Screenshot AFTER ArrowDown saved")
        
        print("\n🎮 Testing ArrowRight...")
        await page.keyboard.press("ArrowRight")
        await page.wait_for_timeout(400)
        await page.screenshot(path="test_pw_arrowright.png", full_page=False)
        print("📸 Screenshot AFTER ArrowRight saved")
        
        # Multiple arrows
        print("\n🎮 Sending 5x ArrowDown...")
        for i in range(5):
            await page.keyboard.press("ArrowDown")
            await page.wait_for_timeout(100)
        await page.wait_for_timeout(500)
        await page.screenshot(path="test_pw_5down.png", full_page=False)
        print(f"📸 Screenshot AFTER 5x ArrowDown saved")
        
        # Canvas data
        print("\n🔬 Scanning canvas pixels for player detection...")
        canvas_data = await page.evaluate("""() => {
            const canvas = document.querySelector('canvas');
            if (!canvas) return null;
            const ctx = canvas.getContext('2d');
            const scan = ctx.getImageData(0, 0, canvas.width, canvas.height);
            
            const results = {};
            
            // Detect blue pixels (player color: r<60, g<100, b>200)
            results.blue_pixels = [];
            for (let y = 0; y < canvas.height; y += 1) {
                for (let x = 0; x < canvas.width; x += 1) {
                    const i = (y * canvas.width + x) * 4;
                    const r = scan.data[i], g = scan.data[i+1], b = scan.data[i+2];
                    if (r < 60 && g < 100 && b > 200) {
                        results.blue_pixels.push({x, y});
                    }
                }
            }
            
            // Group into connected clusters (simple: just find bounding box)
            if (results.blue_pixels.length > 0) {
                const xs = results.blue_pixels.map(p => p.x);
                const ys = results.blue_pixels.map(p => p.y);
                results.player_bbox = {
                    x_min: Math.min(...xs),
                    x_max: Math.max(...xs),
                    y_min: Math.min(...ys),
                    y_max: Math.max(...ys),
                    center_x: Math.round((Math.min(...xs) + Math.max(...xs)) / 2),
                    center_y: Math.round((Math.min(...ys) + Math.max(...ys)) / 2),
                    pixel_count: results.blue_pixels.length
                };
            }
            
            results.canvas_dim = {w: canvas.width, h: canvas.height};
            
            return results;
        }""")
        
        print(f"\nCanvas: {canvas_data['canvas_dim']['w']}x{canvas_data['canvas_dim']['h']}")
        if 'player_bbox' in canvas_data:
            pb = canvas_data['player_bbox']
            print(f"🔵 Player detected at center=({pb['center_x']}, {pb['center_y']})")
            print(f"   BBox: x=[{pb['x_min']},{pb['x_max']}] y=[{pb['y_min']},{pb['y_max']}]")
            print(f"   Blue pixels: {pb['pixel_count']}")
        else:
            print(f"🔴 No blue pixels found. Blue pixel count: {len(canvas_data.get('blue_pixels', []))}")
        
        print("\n" + "=" * 60)
        print("✅ TEST COMPLETE")
        print("=" * 60)
        
        await browser.close()
        print("\n📁 Screenshots saved:")
        for f in ["test_pw_before.png", "test_pw_arrowdown.png", "test_pw_arrowright.png", "test_pw_5down.png"]:
            print(f"  - {f}")

if __name__ == "__main__":
    asyncio.run(run_test())
