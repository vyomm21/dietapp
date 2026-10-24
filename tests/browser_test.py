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
