// Static checks for index.html: script syntax, recipe schema, unique ids, units,
// protein chips, and shopping-list categories (no ingredient may fall into "Other").
// Usage: node tests/check_recipes.js [path/to/index.html]
const fs = require('fs');
const path = require('path');

const file = process.argv[2] || path.join(__dirname, '..', 'index.html');
const html = fs.readFileSync(file, 'utf8');
const problems = [];
const fail = (msg) => problems.push(msg);

const block = html.match(/<script>([\s\S]*?)<\/script>/);
if (!block) { console.error('no <script> block found'); process.exit(1); }
const script = block[1];
try { new Function(script); } catch (e) { console.error('SYNTAX ERROR:', e.message); process.exit(1); }

function grabArray(name) {
  const start = script.indexOf('var ' + name + ' = [');
  if (start < 0) { fail('cannot find var ' + name); return []; }
  const end = script.indexOf('\n  ];', start);
  const src = script.slice(script.indexOf('[', start), end + 4);
  return new Function('return (' + src + ')')();
}

const RECIPES = grabArray('RECIPES');
const RULES = grabArray('CATEGORY_RULES');
const categorize = (name) => {
  const lower = name.toLowerCase();
  for (const rule of RULES) if (lower.includes(rule[0])) return rule[1];
  return 'Other';
};

const chipBlock = html.match(/id="proteinChips"[\s\S]*?<\/div>/);
const chips = chipBlock ? [...chipBlock[0].matchAll(/value="([^"]+)"/g)].map((x) => x[1]) : [];
if (!chips.length) fail('no protein chips found');

const UNITS = ['g', 'ml', 'clove', 'whole', 'slice', 'tin', 'chop', 'egg', 'rasher'];
const FIELDS = ['id', 'name', 'protein', 'mealTypes', 'cookStyle', 'portability', 'time', 'proteinG', 'fibreG', 'kcal', 'ingredients', 'method'];
const ids = new Set();

for (const r of RECIPES) {
  const where = r.id || r.name || '(unnamed recipe)';
  for (const f of FIELDS) if (r[f] === undefined) fail(`${where}: missing ${f}`);
  if (ids.has(r.id)) fail(`${where}: duplicate id`);
  ids.add(r.id);
  if (!chips.includes(r.protein)) fail(`${where}: protein "${r.protein}" is not a chip`);
  if (!['quick', 'batch'].includes(r.cookStyle)) fail(`${where}: bad cookStyle "${r.cookStyle}"`);
  if (!['cold', 'reheat'].includes(r.portability)) fail(`${where}: bad portability "${r.portability}"`);
  if (!Array.isArray(r.mealTypes) || !r.mealTypes.length || r.mealTypes.some((t) => !['lunch', 'dinner'].includes(t))) {
    fail(`${where}: bad mealTypes`);
  }
  for (const f of ['time', 'proteinG', 'fibreG', 'kcal']) if (!(r[f] > 0)) fail(`${where}: ${f} must be a positive number`);
  if (r.side !== undefined && r.side !== true) fail(`${where}: side must be true or absent`);
  if (String(r.id).startsWith('side-') !== (r.side === true)) {
    fail(`${where}: ids starting "side-" must have side:true, and side:true recipes must have an id starting "side-"`);
  }
  if (!Array.isArray(r.ingredients) || !r.ingredients.length) fail(`${where}: no ingredients`);
  for (const i of r.ingredients || []) {
    if (!i.name) { fail(`${where}: ingredient without a name`); continue; }
    if (!UNITS.includes(i.unit)) fail(`${where}: ${i.name}: unit "${i.unit}" is not allowed`);
    if (!(i.qty > 0)) fail(`${where}: ${i.name}: qty must be above 0`);
    if (categorize(i.name) === 'Other') fail(`${where}: "${i.name}" falls into the Other shopping category (add a CATEGORY_RULES entry)`);
  }
}

// every protein chip needs at least one real meal, or selecting it would show other proteins
for (const c of chips) {
  if (!RECIPES.some((r) => r.protein === c && !r.side)) fail(`chip "${c}" has no meal recipe`);
}

const sides = RECIPES.filter((r) => r.side).length;
console.log(`recipes: ${RECIPES.length} (${RECIPES.length - sides} meals, ${sides} sides) | chips: ${chips.length} | category rules: ${RULES.length}`);
if (problems.length) {
  console.log('PROBLEMS:');
  problems.forEach((p) => console.log('  - ' + p));
  process.exit(1);
}
console.log('check_recipes: OK');
