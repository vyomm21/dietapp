# dietapp

A single-file meal planner (`index.html`). No build step, no dependencies, runs entirely in the browser. Everything lives in one `<script>` block: the `RECIPES` array, the shopping-list `CATEGORY_RULES`, the planner and the renderer.

## Adding recipes (the common request)

Each entry in `RECIPES` describes ONE portion:

    {id, name, protein, mealTypes:['lunch'|'dinner'], cookStyle:'quick'|'batch', portability:'cold'|'reheat',
     time, proteinG, fibreG, kcal, ingredients:[{name, qty, unit}], method}

Conventions:
- Quantities are per portion and metric. Allowed units: g, ml, clove, whole, slice, tin, chop, egg, rasher. The app multiplies by the number of portions and rounds to the nearest 5 g/ml.
- `protein` must match a chip in `#proteinChips`. Add a chip if a recipe needs a new protein. Beans, lentils and chickpeas are filed under `Beans`.
- `proteinG`, `fibreG` and `kcal` are rough estimates. The page shows them with a `~`. Never present them as precise.
- Reuse existing ingredient names exactly (e.g. `Rice (dry)`, `Natural yoghurt`, `Chopped tomatoes`) so shopping lists merge. Use UK spelling.
- Collapse several spices into one mix line (e.g. `Curry spice mix`, 5 g) and name the individual spices in the method.
- A recipe must be a complete plate: a protein plus a carb or veg, with nothing left open. "Serve with rice or bread" is not allowed; name the side and give an amount.
- Start `method` with `Total about N min (...)`, and keep `time` consistent with it.
- Write recipes in your own words. Do not paste text from a source. Tell the owner when a recipe is original and untested in a kitchen.
- The data uses single-quoted JS strings, so never put an apostrophe inside one.
- A new kind of ingredient needs a rule in `CATEGORY_RULES` (checked in order, first match wins). The tests fail if any ingredient lands in `Other`.
- Rice sides carry `side:true` and an id starting `side-` (the tests enforce both). They are excluded from the planner (`MEALS`) and shown in the "High-fibre rice sides" card instead, so a bowl of rice is never scheduled as a whole meal.

## Workflow

- **Recipe or data-only changes** (new recipes, ingredient names, category rules, wording inside `RECIPES`): run the tests, make one commit per request, and push straight to `main`.
- **Anything else** (planner or scoring logic, layout, form fields, new tooling, docs, this file): push a branch and tell the owner, who merges it.
- Always: the tests must pass first; never force-push or rewrite history on `main`; if you are unsure what to add, ask before building.
- Reply format: one line saying what was added, a short list of what changed, and how to undo it (`git revert <sha>`).

## Tests

    node tests/check_recipes.js       # schema, ids, units, shopping categories (no dependencies)
    python3 tests/browser_test.py     # headless Chromium; needs `pip install playwright` and its Chromium

Network failures (for example Google Fonts blocked in a sandbox) are ignored. JavaScript errors fail the run.
