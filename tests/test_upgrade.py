"""Simulates a live upgrade: install the version currently on GitHub Pages,
add recipes, then deploy the new version over it and reopen the app.
Usage: python3 tests/test_upgrade.py <served_dir> <new_version_dir>   (served_dir is served on :8767)"""
import asyncio, os, shutil, subprocess, sys, time
from playwright.async_api import async_playwright
served, new = sys.argv[1], sys.argv[2]
FILES = ['index.html', 'app.js', 'sw.js', 'styles.css', 'manifest.webmanifest']
ok_all = True
def check(n, c, d=''):
    global ok_all; ok_all &= bool(c); print(('  PASS ' if c else '  FAIL ') + n + (f'  [{d}]' if d and not c else ''))
async def main():
    srv = subprocess.Popen([sys.executable, '-m', 'http.server', '8767'], cwd=served, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1)
    try:
        async with async_playwright() as p:
            b = await p.chromium.launch()
            ctx = await b.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True)
            pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
            await pg.goto('http://localhost:8767/'); await pg.evaluate('navigator.serviceWorker.ready'); await pg.reload(); await pg.wait_for_timeout(400)
            v_old = await pg.text_content('#appVersion')
            for t in ['Live Lasagne', 'Live Flapjacks', 'Live Curry']:
                await pg.click('.tab[data-tab="recipes"]'); await pg.click('#addBtn'); await pg.fill('#fTitle', t)
                await pg.click('#fScore [data-score="8"]'); await pg.click('#recipeForm button[type=submit]'); await pg.wait_for_timeout(150)
            before = await pg.evaluate("JSON.parse(localStorage.getItem('aimee-recipes.v1'))")
            check(f'Installed live version {v_old} with 3 recipes', len(before) == 3)
            for f in FILES: shutil.copy(os.path.join(new, f), os.path.join(served, f))   # "git push"
            await pg.goto('http://localhost:8767/'); await pg.wait_for_timeout(2500)    # she reopens the app
            v_new = await pg.text_content('#appVersion')
            after = await pg.evaluate("JSON.parse(localStorage.getItem('aimee-recipes.v1'))")
            check(f'App updated itself {v_old} → {v_new}', v_new != v_old, v_new)
            check('"Updated" message shown', 'Updated to' in (await pg.text_content('#toast')))
            check('All 3 live recipes still there', len(after) == 3 and [r['id'] for r in after] == [r['id'] for r in before])
            check('Live recipes untouched apart from new Cooking label', all({k: v for k, v in a.items() if k != 'type'} == o and a['type'] == 'cooking' for a, o in zip(after, before)))
            check('Cooking/Baking buttons now on the form', await pg.locator('#fType').count() == 1)
            await pg.click('.tab[data-tab="recipes"]'); await pg.click('#addBtn'); await pg.fill('#fTitle', 'New Cupcakes')
            await pg.click('#fType [data-type="baking"]'); await pg.click('#recipeForm button[type=submit]'); await pg.wait_for_timeout(150)
            await pg.click('.tab[data-tab="search"]'); await pg.click('#searchType [data-type="baking"]')
            check('Baking search finds the new recipe', 'New Cupcakes' in await pg.text_content('#searchResults'))
            await ctx.set_offline(True); await pg.reload(); await pg.wait_for_timeout(500)
            check('New version works offline', await pg.text_content('#appVersion') == v_new and await pg.locator('#recipeList .recipe-card').count() == 4)
            check('No script errors', not errs, '; '.join(errs))
            await b.close()
    finally:
        srv.terminate()
    print('\nUPGRADE TEST', 'PASSED' if ok_all else 'FAILED'); return 0 if ok_all else 1
sys.exit(asyncio.run(main()))
