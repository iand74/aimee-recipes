"""End-to-end tests for Aimee's Recipes.

Run:  python3 -m http.server 8765   (from the repo root, in another terminal)
      python3 tests/test_app.py
"""
import asyncio, json, os, sys, tempfile, traceback
from datetime import date
from playwright.async_api import async_playwright

URL = os.environ.get('APP_URL', 'http://localhost:8765/')
PHONE = dict(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True)
results = []


def check(name, cond, detail=''):
    results.append((name, bool(cond), detail))
    print(('  PASS ' if cond else '  FAIL ') + name + (f'  [{detail}]' if detail and not cond else ''))


async def new_phone(browser, **kw):
    ctx = await browser.new_context(**PHONE, accept_downloads=True, **kw)
    page = await ctx.new_page()
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.on('dialog', lambda d: asyncio.ensure_future(d.accept()))
    await page.goto(URL)
    await page.evaluate('localStorage.clear()')
    await page.reload()
    return ctx, page, errors


async def stored(page):
    return await page.evaluate("JSON.parse(localStorage.getItem('aimee-recipes.v1') || '[]')")


async def add_recipe(page, title, **f):
    await page.click('.tab[data-tab="recipes"]')
    await page.click('#addBtn')
    if title is not None:
        await page.fill('#fTitle', title)
    if f.get('type') == 'baking':
        await page.click('#fType [data-type="baking"]')
    if f.get('for') == 'aimee-dad':
        await page.click('#fFor [data-for="aimee-dad"]')
    if 'hours' in f: await page.fill('#fHours', str(f['hours']))
    if 'mins' in f: await page.fill('#fMins', str(f['mins']))
    for _ in range(f.get('serves', 0)): await page.click('#servesPlus')
    if 'ingredients' in f: await page.fill('#fIngredients', f['ingredients'])
    if 'method' in f: await page.fill('#fMethod', f['method'])
    if 'score' in f: await page.click(f'#fScore [data-score="{f["score"]}"]')
    await page.click('#recipeForm button[type=submit]')
    await page.wait_for_timeout(150)


async def search_count(page):
    t = await page.text_content('#resultCount')
    return int(t.split()[0]) if t and t[0].isdigit() else 0


async def main():
    tmp = tempfile.mkdtemp()
    async with async_playwright() as p:
        browser = await p.chromium.launch()

        print('\n== Phone 1: adding recipes ==')
        ctx1, page, errors = await new_phone(browser, service_workers='block')
        check('Empty state shown on first open', 'No recipes yet' in await page.text_content('#recipeList'))

        await add_recipe(page, None)
        check('Saving without a title is blocked', len(await stored(page)) == 0)
        check('"Please add a title" message shows', await page.is_visible('#titleError'))
        await page.fill('#fTitle', '   ')
        await page.click('#recipeForm button[type=submit]')
        check('Title of only spaces is blocked', len(await stored(page)) == 0)

        await page.fill('#fTitle', 'Toast')
        await page.click('#recipeForm button[type=submit]')
        await page.wait_for_timeout(150)
        r = (await stored(page))[0]
        check('Title-only recipe saves', r['title'] == 'Toast')
        check('Date added is filled in automatically (today)', r['dateAdded'][:10] == date.today().isoformat(), r['dateAdded'])
        check('Defaults to "Family"', r['forWho'] == 'family')
        check('Defaults to "Cooking"', r['type'] == 'cooking')
        check('Optional fields left empty', r['score'] is None and r['timeMins'] is None and r['serves'] is None and r['ingredients'] == '' and r['method'] == '')
        check('Recipe page opens after saving', await page.is_visible('#view-detail') and 'Toast' in await page.text_content('#view-detail'))

        await add_recipe(page, 'Pancake Stack', **{'for': 'aimee-dad', 'type': 'baking'}, hours=0, mins=20, serves=2,
                         ingredients='200g flour\n1 egg\n300ml milk\nBlueberries', method='Whisk the batter.\nFry in a hot pan until golden.', score=10)
        await add_recipe(page, 'Chicken Pie', hours=1, mins=15, serves=6,
                         ingredients='500g chicken\n1 leek\nPuff pastry\n2 garlic cloves', method='Brown the chicken. Bake in the oven at 200C.', score=8)
        await add_recipe(page, 'Garlic Bread', **{'for': 'aimee-dad'}, mins=15, serves=4,
                         ingredients='1 baguette\n3 garlic cloves\nButter', method='Spread and bake in the oven.', score=6)
        data = await stored(page)
        pie = next(x for x in data if x['title'] == 'Chicken Pie')
        pan = next(x for x in data if x['title'] == 'Pancake Stack')
        check('4 recipes stored', len(data) == 4)
        check('All fields stored (pie)', pie['timeMins'] == 75 and pie['serves'] == 6 and pie['score'] == 8 and 'leek' in pie['ingredients'])
        check('"Baking" stored (pancakes)', pan['type'] == 'baking' and pie['type'] == 'cooking')
        check('"Aimee & Dad" stored (pancakes)', pan['forWho'] == 'aimee-dad' and pan['timeMins'] == 20 and pan['serves'] == 2)
        detail = await page.text_content('#view-detail')
        check('Recipe page shows time, serves, score', '1 hr 15 min' not in detail and 'Garlic Bread' in detail and '15 min' in detail and 'Serves 4' in detail and '6/10' in detail)

        # tap again to clear a score
        await page.click('#editBtn')
        await page.click('#fScore [data-score="6"]')
        await page.click('#recipeForm button[type=submit]')
        await page.wait_for_timeout(150)
        gb = next(x for x in await stored(page) if x['title'] == 'Garlic Bread')
        check('Tapping the same score again clears it', gb['score'] is None)

        print('\n== Edit, delete, undo ==')
        await page.click('.tab[data-tab="recipes"]')
        await page.click('.recipe-card:has-text("Chicken Pie")')
        await page.click('#editBtn')
        check('Edit form shows Cooking selected', await page.get_attribute('#fType [data-type="cooking"]', 'class') == 'active')
        await page.click('#fType [data-type="baking"]')
        check('Edit form is pre-filled', await page.input_value('#fTitle') == 'Chicken Pie' and await page.input_value('#fHours') == '1' and await page.input_value('#fMins') == '15' and await page.input_value('#fServes') == '6')
        await page.fill('#fTitle', "Grandma's Chicken Pie")
        await page.click('#fScore [data-score="9"]')
        await page.click('#recipeForm button[type=submit]')
        await page.wait_for_timeout(150)
        pie2 = next(x for x in await stored(page) if x['id'] == pie['id'])
        check('Edit saves changes, keeps original date', pie2['title'] == "Grandma's Chicken Pie" and pie2['score'] == 9 and pie2['dateAdded'] == pie['dateAdded'])
        check('Edit keeps the same recipe (no duplicate)', len(await stored(page)) == 4)
        check('Edit can switch Cooking → Baking', pie2['type'] == 'baking')
        check('Recipe page shows Baking', 'Baking' in await page.text_content('#view-detail'))

        await page.click('.tab[data-tab="recipes"]')
        await page.click('.recipe-card:has-text("Toast")')
        await page.click('#delBtn')
        await page.wait_for_timeout(150)
        check('Delete removes the recipe', len(await stored(page)) == 3)
        await page.click('#toast button')
        await page.wait_for_timeout(150)
        check('Undo brings it back', len(await stored(page)) == 4)

        print('\n== Recipes list ==')
        await page.click('.tab[data-tab="recipes"]')
        titles = await page.locator('#recipeList .recipe-card h3').all_text_contents()
        check('List shows all recipes, newest first', titles[0] == 'Garlic Bread' and len(titles) == 4, str(titles))
        await page.click('[data-list-filter="aimee-dad"]')
        titles = await page.locator('#recipeList .recipe-card h3').all_text_contents()
        check('"Aimee & Dad" filter', sorted(titles) == ['Garlic Bread', 'Pancake Stack'], str(titles))
        await page.click('[data-list-filter="family"]')
        check('"Family" filter', await page.locator('#recipeList .recipe-card').count() == 2)
        await page.click('[data-list-filter="all"]')
        await page.reload()
        check('Recipes still there after closing/reopening', await page.locator('#recipeList .recipe-card').count() == 4)

        print('\n== Search tab: every field ==')
        await page.click('.tab[data-tab="search"]')
        await page.click('#searchFields [data-field="title"]')
        await page.fill('#sText', 'PIE')
        check('Title search (case-insensitive)', await search_count(page) == 1 and 'Grandma' in await page.text_content('#searchResults'))
        check('Title match highlighted', await page.locator('#searchResults mark').count() >= 1)
        await page.fill('#sText', 'zzz')
        check('Title search with no match shows 0', await search_count(page) == 0 and 'Nothing matches' in await page.text_content('#searchResults'))

        await page.click('#searchFields [data-field="ingredients"]')
        await page.fill('#sText', 'garlic')
        check('Ingredients search: garlic → 2', await search_count(page) == 2)
        await page.fill('#sText', 'garlic, leek')
        check('Ingredients search: "garlic, leek" needs both → 1', await search_count(page) == 1)

        await page.click('#searchFields [data-field="method"]')
        await page.fill('#sText', 'oven')
        check('Method search: oven → 2', await search_count(page) == 2)

        await page.click('#searchFields [data-field="date"]')
        today = date.today().isoformat()
        await page.fill('#sFrom', today); await page.fill('#sTo', today)
        check('Date search: today → 4', await search_count(page) == 4)
        await page.fill('#sFrom', '2020-01-01'); await page.fill('#sTo', '2020-12-31')
        check('Date search: 2020 → 0', await search_count(page) == 0)

        await page.click('#searchFields [data-field="for"]')
        await page.click('#sFor [data-for="aimee-dad"]')
        check('For search: Aimee & Dad → 2', await search_count(page) == 2)
        await page.click('#sFor [data-for="family"]')
        check('For search: Family → 2', await search_count(page) == 2)

        await page.click('#searchFields [data-field="score"]')
        await page.click('#sScore [data-score="9"]')
        check('Score search: 9+ → 2', await search_count(page) == 2)
        await page.click('#sScore [data-score="10"]')
        check('Score search: 10 → 1', await search_count(page) == 1)

        await page.click('#searchFields [data-field="time"]')
        await page.click('#sTime [data-v="15"]')
        check('Time search: 15 min or less → 1', await search_count(page) == 1)
        await page.click('#sTime [data-v="30"]')
        check('Time search: 30 min or less → 2', await search_count(page) == 2)
        await page.click('#sTime [data-v="90"]')
        check('Time search: 1½ hr or less → 3', await search_count(page) == 3)

        await page.click('#searchFields [data-field="serves"]')
        await page.click('#sServes [data-v="4"]')
        check('Serves search: at least 4 → 2', await search_count(page) == 2)
        await page.click('#sServes [data-v="1"]')
        check('Serves search: at least 1 → 3', await search_count(page) == 3)

        print('\n== Search: Cooking / Baking ==')
        # now: Baking = Pancake Stack, Grandma's Chicken Pie ; Cooking = Toast, Garlic Bread
        await page.click('#searchFields [data-field="title"]')
        await page.fill('#sText', '')
        await page.click('#searchType [data-type="baking"]')
        check('Baking with no other filter lists all baking → 2', await search_count(page) == 2)
        await page.click('#searchType [data-type="cooking"]')
        check('Cooking with no other filter lists all cooking → 2', await search_count(page) == 2)
        await page.click('#searchType [data-type="all"]')
        check('All with empty search shows prompt', await search_count(page) == 0 and 'Pick a field' in await page.text_content('#searchResults'))
        await page.click('#searchFields [data-field="ingredients"]')
        await page.fill('#sText', 'garlic')
        check('Ingredients garlic, All → 2', await search_count(page) == 2)
        await page.click('#searchType [data-type="baking"]')
        check('Ingredients garlic, Baking only → 1 (pie)', await search_count(page) == 1 and 'Chicken Pie' in await page.text_content('#searchResults'))
        await page.click('#searchType [data-type="cooking"]')
        check('Ingredients garlic, Cooking only → 1 (garlic bread)', await search_count(page) == 1 and 'Garlic Bread' in await page.text_content('#searchResults'))
        await page.click('#searchFields [data-field="score"]')
        await page.click('#sScore [data-score="9"]')
        await page.click('#searchType [data-type="baking"]')
        check('Score 9+, Baking → 2', await search_count(page) == 2)
        await page.click('#searchType [data-type="cooking"]')
        check('Score 9+, Cooking → 0 with message', await search_count(page) == 0)
        await page.click('#searchFields [data-field="for"]')
        await page.click('#sFor [data-for="aimee-dad"]')
        await page.click('#searchType [data-type="baking"]')
        check('For Aimee & Dad, Baking → 1', await search_count(page) == 1)
        await page.click('#searchType [data-type="all"]')
        await page.click('#searchFields [data-field="title"]')
        await page.fill('#sText', 'a')

        await page.click('#searchResults .recipe-card >> nth=0')
        check('Tapping a search result opens it', await page.is_visible('#view-detail'))
        await page.click('.topbar .back')
        check('Back returns to search', await page.is_visible('#view-search'))

        print('\n== Backup ==')
        await page.click('.tab[data-tab="backup"]')
        check('Backup shows recipe count', '4 recipes' in await page.text_content('#backupStat'))
        async with page.expect_download() as dl:
            await page.click('#backupBtn')
        d = await dl.value
        backup_path = os.path.join(tmp, d.suggested_filename)
        await d.save_as(backup_path)
        b = json.load(open(backup_path))
        check('Backup file downloads with dated name', d.suggested_filename == f'aimee-recipes-backup-{today}.json', d.suggested_filename)
        check('Backup contains all 4 recipes with every field', len(b['recipes']) == 4 and all(k in b['recipes'][0] for k in ['type', 'title', 'dateAdded', 'forWho', 'ingredients', 'method', 'score', 'timeMins', 'serves']))
        check('"Last backup" date updates', 'Last backup' in await page.text_content('#lastBackup'))
        check('No script errors on phone 1', not errors, '; '.join(errors))

        print('\n== Phone 2: restore from backup ==')
        ctx2, page2, errors2 = await new_phone(browser, service_workers='block')
        check('Phone 2 starts empty', len(await stored(page2)) == 0)
        await page2.click('.tab[data-tab="restore"]')
        await page2.set_input_files('#restoreFile', backup_path)
        await page2.wait_for_timeout(200)
        d2 = await stored(page2)
        check('Restore (merge) loads all 4 recipes', len(d2) == 4)
        check('Restored recipes identical to originals', sorted(json.dumps(x, sort_keys=True) for x in d2) == sorted(json.dumps(x, sort_keys=True) for x in b['recipes']))
        check('Goes to the recipe list after restore', await page2.locator('#recipeList .recipe-card').count() == 4)

        await page2.click('.tab[data-tab="restore"]')
        await page2.set_input_files('#restoreFile', backup_path)
        await page2.wait_for_timeout(200)
        check('Restoring the same backup twice makes no duplicates', len(await stored(page2)) == 4)

        await add_recipe(page2, 'Phone 2 Soup', serves=3)
        await page2.click('.tab[data-tab="restore"]')
        await page2.set_input_files('#restoreFile', backup_path)
        await page2.wait_for_timeout(200)
        titles2 = [x['title'] for x in await stored(page2)]
        check('Merge keeps recipes only on phone 2', 'Phone 2 Soup' in titles2 and len(titles2) == 5)

        # newer edit on phone 1 should update phone 2 on merge; older should not overwrite
        await page.click('.tab[data-tab="recipes"]')
        await page.click('.recipe-card:has-text("Pancake")')
        await page.click('#editBtn')
        await page.fill('#fMethod', 'Updated method on phone 1')
        await page.click('#recipeForm button[type=submit]')
        await page.wait_for_timeout(150)
        await page.click('.tab[data-tab="backup"]')
        async with page.expect_download() as dl:
            await page.click('#backupBtn')
        newer = os.path.join(tmp, 'newer.json'); await (await dl.value).save_as(newer)
        await page2.click('.tab[data-tab="restore"]')
        await page2.set_input_files('#restoreFile', newer)
        await page2.wait_for_timeout(200)
        p2 = next(x for x in await stored(page2) if x['title'] == 'Pancake Stack')
        check('Merge updates a recipe edited more recently on the other phone', p2['method'] == 'Updated method on phone 1')
        await page2.set_input_files('#restoreFile', backup_path)
        await page2.wait_for_timeout(200)
        p2 = next(x for x in await stored(page2) if x['title'] == 'Pancake Stack')
        check('Merge does not overwrite with an older copy', p2['method'] == 'Updated method on phone 1')

        await page2.click('.tab[data-tab="restore"]')
        await page2.click('#restoreMode [data-mode="replace"]')
        await page2.set_input_files('#restoreFile', backup_path)
        await page2.wait_for_timeout(200)
        titles2 = [x['title'] for x in await stored(page2)]
        check('Replace all wipes phone 2 and loads only the backup', len(titles2) == 4 and 'Phone 2 Soup' not in titles2)

        bad = os.path.join(tmp, 'bad.json'); open(bad, 'w').write('this is not json')
        empty = os.path.join(tmp, 'empty.json'); json.dump({'recipes': [{'title': ''}]}, open(empty, 'w'))
        await page2.click('.tab[data-tab="restore"]')
        await page2.click('#restoreMode [data-mode="merge"]')
        await page2.set_input_files('#restoreFile', bad)
        await page2.wait_for_timeout(200)
        check("A non-backup file is rejected safely", len(await stored(page2)) == 4 and "isn't a recipe backup" in await page2.text_content('#toast'))
        await page2.set_input_files('#restoreFile', empty)
        await page2.wait_for_timeout(200)
        check('A backup with no valid recipes is rejected', len(await stored(page2)) == 4)
        check('No script errors on phone 2', not errors2, '; '.join(errors2))

        print('\n== Upgrading existing (pre-Cooking/Baking) data ==')
        old = [
          {'id': 'old1', 'title': 'Old Lasagne', 'dateAdded': '2026-10-10T18:00:00.000Z', 'forWho': 'family', 'ingredients': 'pasta\nmince', 'method': 'Layer and bake', 'score': 9, 'timeMins': 90, 'serves': 6, 'updated': '2026-10-10T18:00:00.000Z'},
          {'id': 'old2', 'title': 'Old Brownies', 'dateAdded': '2026-10-11T15:00:00.000Z', 'forWho': 'aimee-dad', 'ingredients': 'chocolate', 'method': 'Melt, mix, bake', 'score': None, 'timeMins': None, 'serves': None, 'updated': '2026-10-11T15:00:00.000Z'},
          {'id': 'old3', 'title': 'Very Old Soup', 'dateAdded': '2026-10-09T12:00:00.000Z', 'forWho': 'family', 'ingredients': '', 'method': '', 'score': 5, 'updated': '2026-10-09T12:00:00.000Z'},
        ]
        ctx4 = await browser.new_context(**PHONE, service_workers='block')
        page4 = await ctx4.new_page(); e4 = []; page4.on('pageerror', lambda e: e4.append(str(e)))
        await page4.goto(URL)
        await page4.evaluate("d => localStorage.setItem('aimee-recipes.v1', JSON.stringify(d))", old)
        await page4.reload(); await page4.wait_for_timeout(300)
        up = await stored(page4)
        check('Upgrade keeps every existing recipe', len(up) == 3 and sorted(x['id'] for x in up) == ['old1', 'old2', 'old3'])
        check('Upgrade labels old recipes "Cooking"', all(x['type'] == 'cooking' for x in up))
        same = all({k: v for k, v in u.items() if k != 'type'} == o for u, o in zip(sorted(up, key=lambda x: x['id']), old))
        check('Upgrade leaves every other field untouched', same)
        safety = await page4.evaluate("JSON.parse(localStorage.getItem('aimee-recipes.v1.pre-1.3') || 'null')")
        check('Safety copy of the old data is kept', safety == old)
        check('Old recipes show in the list', await page4.locator('#recipeList .recipe-card').count() == 3)
        await page4.reload(); await page4.wait_for_timeout(300)
        check('Upgrade runs once (reopen changes nothing)', await stored(page4) == up)
        await page4.click('.recipe-card:has-text("Old Brownies")')
        await page4.click('#editBtn')
        await page4.click('#fType [data-type="baking"]')
        await page4.click('#recipeForm button[type=submit]')
        await page4.wait_for_timeout(150)
        br = next(x for x in await stored(page4) if x['id'] == 'old2')
        check('Old recipe can be re-labelled Baking', br['type'] == 'baking' and br['title'] == 'Old Brownies' and br['dateAdded'] == old[1]['dateAdded'])
        oldbackup = os.path.join(tmp, 'old-backup.json')
        json.dump({'app': 'aimee-recipes', 'version': 1, 'recipes': [dict(old[0], id='bk1', title='From Old Backup')]}, open(oldbackup, 'w'))
        await page4.click('.tab[data-tab="restore"]')
        await page4.set_input_files('#restoreFile', oldbackup)
        await page4.wait_for_timeout(200)
        fb = next((x for x in await stored(page4) if x['id'] == 'bk1'), None)
        check('Restoring a backup made before this update works (→ Cooking)', fb is not None and fb['type'] == 'cooking' and len(await stored(page4)) == 4)
        check('No script errors (upgrade)', not e4, '; '.join(e4))

        print('\n== Install & offline ==')
        ctx3 = await browser.new_context(**PHONE)
        page3 = await ctx3.new_page()
        e3 = []; page3.on('pageerror', lambda e: e3.append(str(e)))
        await page3.goto(URL)
        await page3.evaluate('navigator.serviceWorker.ready')
        await page3.reload(); await page3.wait_for_timeout(500)
        has_sw = await page3.evaluate('!!navigator.serviceWorker.controller')
        check('Offline helper (service worker) installs', has_sw)
        manifest = await page3.evaluate("fetch('manifest.webmanifest').then(r=>r.json())")
        check('Install manifest has name, icons, standalone', manifest['name'] == "Aimee's Recipes" and manifest['display'] == 'standalone' and any(i['sizes'] == '512x512' for i in manifest['icons']))
        for icon in ['icons/icon-192.png', 'icons/icon-512.png', 'icons/apple-touch-icon.png', 'icons/icon-maskable-512.png']:
            st = await page3.evaluate(f"fetch('{icon}').then(r=>r.status)")
            check(f'Icon present: {icon}', st == 200)
        await add_recipe(page3, 'Offline Test')
        await ctx3.set_offline(True)
        await page3.reload(); await page3.wait_for_timeout(500)
        check('App opens with no internet', await page3.is_visible('#addBtn'))
        check('Recipes readable offline', 'Offline Test' in await page3.text_content('#recipeList'))
        await add_recipe(page3, 'Added While Offline')
        check('Can add recipes offline', len(await stored(page3)) == 2)
        await ctx3.set_offline(False)
        check('No script errors (install/offline)', not e3, '; '.join(e3))

        await browser.close()

    passed = sum(1 for _, ok, _ in results if ok)
    print(f'\n{passed}/{len(results)} checks passed')
    return 0 if passed == len(results) else 1

if __name__ == '__main__':
    try:
        sys.exit(asyncio.run(main()))
    except Exception:
        traceback.print_exc(); sys.exit(2)
