"""Headless-browser test of the meal planner.

Usage: python3 tests/browser_test.py [index.html] [screenshot_dir]
Needs: pip install playwright (and its Chromium).
Network failures (for example blocked Google Fonts) are ignored; JavaScript errors fail the run.
"""
import os
import sys

from playwright.sync_api import sync_playwright

here = os.path.dirname(os.path.abspath(__file__))
page_path = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.abspath(os.path.join(here, '..', 'index.html'))
shot_dir = sys.argv[2] if len(sys.argv) > 2 else None
NETWORK_NOISE = ('ERR_', 'Failed to load resource')

errors, failures = [], []


def check(cond, msg):
    if not cond and msg not in failures:
        failures.append(msg)


def set_chips(pg, vals):
    pg.evaluate(
        """(vals) => { document.querySelectorAll('#proteinChips input').forEach(i => {
            i.checked = vals.includes(i.value); i.dispatchEvent(new Event('change')); }); }""",
        vals,
    )


def generate(pg, days, meals, chips):
    pg.fill('#days', str(days))
    pg.fill('#mealsPerDay', str(meals))
    set_chips(pg, chips)
    pg.click('button.primary')


def meal_names(pg):
    return pg.locator('#recipeList h3').all_inner_texts()


def first_tags(pg):
    return pg.locator('#recipeList .recipe').evaluate_all("els => els.map(e => ((e.querySelector('.tag') || {}).textContent || ''))")


with sync_playwright() as p:
    browser = p.chromium.launch()
    pg = browser.new_page(viewport={'width': 430, 'height': 900})
    pg.on('pageerror', lambda e: errors.append('pageerror: ' + str(e)))
    pg.on('console', lambda m: errors.append('console.error: ' + m.text)
          if m.type == 'error' and not any(n in m.text for n in NETWORK_NOISE) else None)
    pg.goto('file://' + page_path)

    chips = pg.locator('#proteinChips input').evaluate_all('els => els.map(e => e.value)')
    print('default max cook time:', pg.input_value('#maxTime'), '| protein chips:', len(chips))

    # prime the page so the optional sides card is rendered, then remember its names
    generate(pg, 5, 2, [])
    side_names = pg.locator('#sideList h3').all_inner_texts() if pg.locator('#sideList').count() else []
    print('rice side cards:', len(side_names))

    plans, side_hits, other_hits = 0, 0, 0

    def inspect(label):
        global plans, side_hits, other_hits
        plans += 1
        shown = meal_names(pg)
        check(len(shown) > 0, f'{label}: no recipes shown')
        plan_text = pg.inner_text('#planTable')
        if any(s in shown or s in plan_text for s in side_names):
            side_hits += 1
            check(False, f'{label}: a rice side was scheduled as a meal')
        if 'Other' in [h.title() for h in pg.locator('#shopList h4').all_inner_texts()]:
            other_hits += 1
            check(False, f'{label}: shopping list has an Other group')

    # every protein chip on its own: it must show recipes for that protein only
    for chip in chips:
        generate(pg, 14, 4, [chip])
        for _ in range(6):
            inspect('chip ' + chip)
            tags = first_tags(pg)
            check(all(t == chip for t in tags), f'chip {chip}: shows other proteins (no recipe for this chip?)')
            pg.click('#regenBtn')

    # no chips and a few plan sizes
    for days, meals in [(5, 2), (14, 4), (3, 1), (7, 3)]:
        generate(pg, days, meals, [])
        for _ in range(6):
            inspect(f'{days}d x {meals} meals')
            pg.click('#regenBtn')

    # ---- recipe picker ----
    rows = pg.locator('#pickList .pick-row').evaluate_all(
        """els => els.map(e => ({id: e.querySelector('input').value,
            name: e.querySelector('.pick-name').textContent,
            side: e.querySelector('.pick-meta').textContent.startsWith('Side'),
            protein: e.querySelector('.pick-meta').textContent.split(' · ')[0]}))""")
    meals_ = [r for r in rows if not r['side']]
    sides_ = [r for r in rows if r['side']]
    print(f'picker rows: {len(rows)} ({len(meals_)} meals, {len(sides_)} sides)')
    check(len(sides_) == len(side_names) and len(meals_) > 0, 'picker does not list every meal and every rice side')

    def clear_filters():
        pg.fill('#pickSearch', '')
        pg.select_option('#pickProtein', '')

    def set_picks(ids):
        clear_filters()
        if pg.locator('#pickClear').is_visible():
            pg.click('#pickClear')
        for i in ids:
            pg.check(f'#pickList input[value="{i}"]')

    by_protein = {}
    for r in meals_:
        by_protein.setdefault(r['protein'], r)
    salmon, beans, paneer = by_protein['Salmon'], by_protein['Beans'], by_protein['Paneer']
    side = sides_[0]

    # picks are guaranteed on every shuffle, even when they clash with the protein chips
    set_picks([salmon['id'], beans['id'], side['id']])
    generate(pg, 5, 2, ['Chicken'])
    for n in range(25):
        table = pg.inner_text('#planTable')
        shown = meal_names(pg)
        check(salmon['name'] in table and beans['name'] in table, 'a picked meal is missing from the plan table')
        check(side['name'] in shown, 'a picked side is missing from the recipe list')
        check(side['name'] not in table, 'a picked side took a meal slot')
        check(any(t == 'Chicken' for t in first_tags(pg)), 'the Chicken chip lost its guaranteed recipe')
        pg.click('#regenBtn')
    side_card = pg.locator('#recipeList .recipe', has_text=side['name']).first.inner_text()
    check('×10 portions' in side_card, 'picked side should get one portion per meal (5 days x 2 = 10)')
    check('Rice (dry)' in pg.inner_text('#shopList') or 'rice' in pg.inner_text('#shopList').lower(),
          'picked side ingredients missing from the shopping list')
    check('Side with every meal' in pg.inner_text('#planSummary'), 'plan summary does not mention the picked side')

    # more picks than slots: nothing crashes and the user is told
    set_picks([salmon['id'], beans['id'], paneer['id']])
    generate(pg, 1, 1, [])
    check(pg.locator('#planWarnings').is_visible() and 'did not fit' in pg.inner_text('#planWarnings'),
          'no warning when picks do not fit the plan')

    # a pick over the time limit is kept and flagged
    set_picks([salmon['id']])
    pg.fill('#maxTime', '5')
    generate(pg, 3, 2, [])
    check(salmon['name'] in pg.inner_text('#planTable'), 'a pick over the time limit was dropped')
    check('over your 5 min limit' in pg.inner_text('#planWarnings'), 'no warning for a pick over the time limit')
    pg.fill('#maxTime', '60')

    # nothing picked: no warnings, sides never scheduled
    set_picks([])
    generate(pg, 5, 2, [])
    check(not pg.locator('#planWarnings').is_visible(), 'warning shown with no picks')

    # search and filter
    clear_filters()
    pg.fill('#pickSearch', 'paneer')
    found = pg.locator('#pickList .pick-row').count()
    check(0 < found < len(rows), 'search for paneer should narrow the list')
    pg.fill('#pickSearch', 'zzzz-nothing')
    check(pg.locator('.pick-empty').count() == 1, 'empty search should say nothing matches')
    clear_filters()
    pg.select_option('#pickProtein', 'Paneer')
    check(all(m.startswith('Paneer') for m in pg.locator('.pick-meta').all_inner_texts()), 'protein filter shows other proteins')
    pg.select_option('#pickProtein', '__side')
    check(pg.locator('#pickList .pick-row').count() == len(sides_), 'rice side filter should list only the sides')
    clear_filters()

    # pressing Enter in the search box must not generate a plan
    fresh = browser.new_page(viewport={'width': 430, 'height': 900})
    fresh.on('pageerror', lambda e: errors.append('pageerror: ' + str(e)))
    fresh.goto('file://' + page_path)
    fresh.fill('#pickSearch', 'chicken')
    fresh.press('#pickSearch', 'Enter')
    check('show' not in (fresh.get_attribute('#results', 'class') or ''), 'Enter in the search box submitted the form')
    fresh.close()

    # ---- iPhone layout ----
    iphone = {k: v for k, v in p.devices['iPhone 13'].items() if k != 'default_browser_type'}
    ctx = browser.new_context(**iphone)
    mob = ctx.new_page()
    mob.on('pageerror', lambda e: errors.append('mobile pageerror: ' + str(e)))
    mob.goto('file://' + page_path)
    check(mob.evaluate("() => (document.querySelector('meta[name=viewport]') || {}).content || ''").startswith('width=device-width'),
          'missing viewport meta tag (phones will show a zoomed-out desktop layout)')

    def overflow(label):
        w = mob.evaluate('() => [window.innerWidth, document.documentElement.scrollWidth]')
        check(w[0] <= 430 and w[1] <= w[0], f'{label}: page is wider than the phone screen ({w[1]}px in {w[0]}px)')

    small = mob.evaluate("""() => [...document.querySelectorAll('input:not([type=checkbox]):not([type=radio]),select,textarea')]
        .filter(e => e.offsetParent !== null && parseFloat(getComputedStyle(e).fontSize) < 16).map(e => e.id)""")
    check(not small, 'fields under 16px make iOS zoom in when tapped: ' + ', '.join(small))
    overflow('form')
    mob.check(f'#pickList input[value="{salmon["id"]}"]')
    mob.check(f'#pickList input[value="{side["id"]}"]')
    mob.click('button.primary')
    mob.wait_for_selector('#results.show')
    overflow('results')
    if shot_dir:
        os.makedirs(shot_dir, exist_ok=True)
        mob.screenshot(path=os.path.join(shot_dir, 'iphone_results.png'), full_page=True)
    ctx.close()

    if shot_dir:
        os.makedirs(shot_dir, exist_ok=True)
        pg.locator('#results').screenshot(path=os.path.join(shot_dir, 'results.png'))
    browser.close()

print(f'plans checked: {plans} | sides scheduled as meals: {side_hits} | plans with an "Other" shopping group: {other_hits}')
check(not errors, 'JavaScript errors: ' + '; '.join(errors))
if failures:
    print('FAILURES:')
    for f in failures:
        print('  - ' + f)
    sys.exit(1)
print('browser_test: OK')
