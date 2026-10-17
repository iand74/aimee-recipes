/* Aimee's Recipes – stored on the phone (localStorage), works offline. */
'use strict';

const APP_VERSION = '1.0.0';
const STORE_KEY = 'aimee-recipes.v1';
const META_KEY = 'aimee-recipes.meta';
const FOR_LABEL = { family: 'Family', 'aimee-dad': 'Aimee & Dad' };
const FOR_EMOJI = { family: '🏡', 'aimee-dad': '💕' };
const BADGE_BG = ['#CDEFDF', '#FFE1C7', '#E3DBFB', '#FFF1B8', '#D3EBFB', '#FFC7D6'];

/* ---------- storage ---------- */
function loadRecipes() {
  try { return JSON.parse(localStorage.getItem(STORE_KEY)) || []; } catch { return []; }
}
function saveRecipes(list) {
  try { localStorage.setItem(STORE_KEY, JSON.stringify(list)); return true; }
  catch { toast('Could not save – phone storage may be full'); return false; }
}
function loadMeta() { try { return JSON.parse(localStorage.getItem(META_KEY)) || {}; } catch { return {}; } }
function saveMeta(m) { try { localStorage.setItem(META_KEY, JSON.stringify(m)); } catch {} }

let recipes = loadRecipes();
if (navigator.storage && navigator.storage.persist) navigator.storage.persist().catch(() => {});

/* ---------- helpers ---------- */
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const uid = () => Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
const fmtDate = iso => new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
const dayKey = iso => { const d = new Date(iso); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`; };
const lines = t => String(t || '').split('\n').map(s => s.trim()).filter(Boolean);
const byNewest = (a, b) => new Date(b.dateAdded) - new Date(a.dateAdded);
function badgeColour(id) { let h = 0; for (const c of id) h = (h * 31 + c.charCodeAt(0)) >>> 0; return BADGE_BG[h % BADGE_BG.length]; }
function highlight(text, q) {
  const safe = esc(text);
  if (!q) return safe;
  const re = new RegExp('(' + q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + ')', 'ig');
  return safe.replace(re, '<mark>$1</mark>');
}
let toastTimer;
function toast(msg, actionLabel, action) {
  const t = $('#toast');
  t.innerHTML = esc(msg) + (actionLabel ? ` <button type="button">${esc(actionLabel)}</button>` : '');
  if (action) t.querySelector('button').onclick = action;
  t.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove('show'), actionLabel ? 8000 : 2600);
}

/* ---------- navigation ---------- */
let currentTab = 'recipes';
function show(viewId, title, backTo) {
  $$('.view').forEach(v => v.classList.toggle('active', v.id === 'view-' + viewId));
  $('#pageTitle').textContent = title || "Aimee's Recipes";
  const old = $('.topbar .back'); if (old) old.remove();
  if (backTo) {
    const b = document.createElement('button');
    b.className = 'back'; b.type = 'button'; b.textContent = '‹ Back';
    b.onclick = backTo; $('.topbar').appendChild(b);
  }
  window.scrollTo(0, 0);
}
function goTab(tab) {
  currentTab = tab;
  $$('.tab').forEach(t => t.classList.toggle('active', t.dataset.tab === tab));
  const titles = { recipes: "Aimee's Recipes", search: 'Search', backup: 'Backup', restore: 'Restore' };
  show(tab, titles[tab]);
  if (tab === 'recipes') renderList();
  if (tab === 'search') renderSearch();
  if (tab === 'backup') renderBackup();
}
$$('.tab').forEach(t => t.addEventListener('click', () => goTab(t.dataset.tab)));

/* ---------- recipe card ---------- */
function cardHTML(r, extra = '') {
  const score = r.score ? `<div class="score-badge">${r.score}<small>/10</small></div>` : `<div class="score-badge none">–</div>`;
  return `<button class="recipe-card" type="button" data-id="${esc(r.id)}">
    <div class="badge" style="background:${badgeColour(r.id)}">${FOR_EMOJI[r.forWho] || '🍽️'}</div>
    <div>
      <h3>${extra && extra.titleHTML ? extra.titleHTML : esc(r.title)}</h3>
      <div class="meta"><span>${fmtDate(r.dateAdded)}</span><span class="tag ${esc(r.forWho)}">${FOR_LABEL[r.forWho]}</span></div>
      ${extra && extra.snippet ? `<div class="snippet">${extra.snippet}</div>` : ''}
    </div>
    ${score}
  </button>`;
}
function bindCards(container, from) {
  $$('.recipe-card', container).forEach(c => c.addEventListener('click', () => openDetail(c.dataset.id, from)));
}

/* ---------- recipes list ---------- */
let listFilter = 'all';
$$('[data-list-filter]').forEach(p => p.addEventListener('click', () => {
  listFilter = p.dataset.listFilter;
  $$('[data-list-filter]').forEach(x => x.classList.toggle('active', x === p));
  renderList();
}));
function renderList() {
  const list = recipes.filter(r => listFilter === 'all' || r.forWho === listFilter).sort(byNewest);
  const el = $('#recipeList');
  if (!recipes.length) {
    el.innerHTML = `<div class="empty"><div class="big">🥣</div><h3>No recipes yet</h3><p>Tap “Add a recipe” to start your book.</p></div>`;
    return;
  }
  if (!list.length) { el.innerHTML = `<div class="empty"><div class="big">🔎</div><p>No recipes in this group yet.</p></div>`; return; }
  el.innerHTML = list.map(r => cardHTML(r)).join('');
  bindCards(el, 'recipes');
}

/* ---------- add / edit ---------- */
let editing = null; // recipe being edited or null
let formFor = 'family';
let formScore = null;

function buildScorePicker() {
  const p = $('#fScore');
  p.innerHTML = Array.from({ length: 10 }, (_, i) => `<button type="button" data-score="${i + 1}">${i + 1}</button>`).join('');
  $$('button', p).forEach(b => b.addEventListener('click', () => {
    const v = +b.dataset.score;
    formScore = formScore === v ? null : v; // tap again to clear
    paintScore();
  }));
}
function paintScore() {
  $$('#fScore button').forEach(b => {
    const v = +b.dataset.score;
    b.classList.toggle('on', formScore && v < formScore);
    b.classList.toggle('picked', formScore === v);
  });
  $('#scoreLabel').textContent = formScore ? `${formScore} / 10 ${scoreEmoji(formScore)}` : 'not rated';
}
function scoreEmoji(s) { return s >= 9 ? '🤩' : s >= 7 ? '😋' : s >= 5 ? '🙂' : s >= 3 ? '😐' : '😬'; }
function paintFor() { $$('#fFor button').forEach(b => b.classList.toggle('active', b.dataset.for === formFor)); }
$$('#fFor button').forEach(b => b.addEventListener('click', () => { formFor = b.dataset.for; paintFor(); }));

function openForm(recipe) {
  editing = recipe || null;
  $('#fTitle').value = recipe ? recipe.title : '';
  $('#fIngredients').value = recipe ? recipe.ingredients : '';
  $('#fMethod').value = recipe ? recipe.method : '';
  formFor = recipe ? recipe.forWho : 'family';
  formScore = recipe ? recipe.score : null;
  $('#fDate').textContent = '📅 ' + fmtDate(recipe ? recipe.dateAdded : new Date().toISOString()) + (recipe ? '' : ' (today)');
  $('#titleError').hidden = true; $('#fTitle').classList.remove('invalid');
  paintFor(); paintScore();
  const back = () => recipe ? openDetail(recipe.id, detailFrom) : goTab('recipes');
  show('edit', recipe ? 'Edit recipe' : 'New recipe', back);
  $('#cancelBtn').onclick = back;
}
$('#addBtn').addEventListener('click', () => openForm(null));

$('#recipeForm').addEventListener('submit', e => {
  e.preventDefault();
  const title = $('#fTitle').value.trim();
  if (!title) {
    $('#titleError').hidden = false; $('#fTitle').classList.add('invalid'); $('#fTitle').focus();
    return;
  }
  const now = new Date().toISOString();
  const data = {
    title,
    forWho: formFor,
    ingredients: $('#fIngredients').value.trim(),
    method: $('#fMethod').value.trim(),
    score: formScore,
    updated: now,
  };
  let id;
  if (editing) {
    Object.assign(editing, data); id = editing.id;
  } else {
    id = uid();
    recipes.push({ id, dateAdded: now, ...data });
  }
  if (saveRecipes(recipes)) {
    toast(editing ? 'Recipe updated ✨' : 'Recipe saved 🎉');
    openDetail(id, 'recipes');
  }
});

/* ---------- detail ---------- */
let detailFrom = 'recipes';
function openDetail(id, from) {
  detailFrom = from || 'recipes';
  const r = recipes.find(x => x.id === id);
  if (!r) return goTab(detailFrom);
  const ing = lines(r.ingredients);
  const stars = r.score ? '★'.repeat(r.score) + '<span style="opacity:.3">' + '★'.repeat(10 - r.score) + '</span>' : '';
  $('#view-detail').innerHTML = `
    <div class="detail-head ${esc(r.forWho)}">
      <h2>${esc(r.title)}</h2>
      <div class="meta">
        <span class="chip">📅 ${fmtDate(r.dateAdded)}</span>
        <span class="chip">${FOR_EMOJI[r.forWho]} ${FOR_LABEL[r.forWho]}</span>
        <span class="chip">${r.score ? `😋 ${r.score}/10` : 'Not rated'}</span>
      </div>
      ${stars ? `<div class="stars" style="color:#E8A93B">${stars}</div>` : ''}
    </div>
    <div class="card">
      <h3>🧺 Ingredients</h3>
      ${ing.length ? `<ul class="ingredients">${ing.map(i => `<li>${esc(i)}</li>`).join('')}</ul>` : '<p class="none-text">No ingredients added</p>'}
    </div>
    <div class="card">
      <h3>👩‍🍳 Method</h3>
      ${r.method ? `<p class="method">${esc(r.method)}</p>` : '<p class="none-text">No method added</p>'}
    </div>
    <div class="detail-actions">
      <button class="btn btn-danger" id="delBtn" type="button">Delete</button>
      <button class="btn btn-primary" id="editBtn" type="button">Edit</button>
    </div>`;
  $('#editBtn').onclick = () => openForm(r);
  $('#delBtn').onclick = () => {
    if (!confirm(`Delete “${r.title}”?`)) return;
    const idx = recipes.findIndex(x => x.id === r.id);
    const [removed] = recipes.splice(idx, 1);
    saveRecipes(recipes);
    goTab(detailFrom);
    toast('Recipe deleted', 'Undo', () => {
      recipes.push(removed); saveRecipes(recipes); goTab(currentTab);
      $('#toast').classList.remove('show');
    });
  };
  show('detail', 'Recipe', () => goTab(detailFrom));
}

/* ---------- search ---------- */
let searchField = 'title';
const searchState = { title: '', ingredients: '', method: '', from: '', to: '', for: 'family', score: 7 };
$$('#searchFields button').forEach(b => b.addEventListener('click', () => {
  searchField = b.dataset.field;
  $$('#searchFields button').forEach(x => x.classList.toggle('active', x === b));
  renderSearch(true);
}));

function renderSearch(focus) {
  const box = $('#searchInput');
  const f = searchField;
  if (f === 'title' || f === 'ingredients' || f === 'method') {
    const ph = { title: 'Type part of a title…', ingredients: 'e.g. chicken, garlic', method: 'e.g. oven, simmer' }[f];
    box.innerHTML = `<input type="search" id="sText" placeholder="${ph}" value="${esc(searchState[f])}" autocomplete="off">
      ${f === 'ingredients' ? '<p class="hint">Separate with commas to find recipes containing all of them.</p>' : ''}`;
    const inp = $('#sText');
    inp.addEventListener('input', () => { searchState[f] = inp.value; runSearch(); });
    if (focus) inp.focus();
  } else if (f === 'date') {
    box.innerHTML = `<div class="row">
      <label>From<input type="date" id="sFrom" value="${searchState.from}"></label>
      <label>To<input type="date" id="sTo" value="${searchState.to}"></label></div>
      <p class="hint">Leave one blank for “since” or “up to”.</p>`;
    $('#sFrom').addEventListener('input', e => { searchState.from = e.target.value; runSearch(); });
    $('#sTo').addEventListener('input', e => { searchState.to = e.target.value; runSearch(); });
  } else if (f === 'for') {
    box.innerHTML = `<div class="segmented" id="sFor">
      <button type="button" data-for="family">🏡 Family</button>
      <button type="button" data-for="aimee-dad">💕 Aimee &amp; Dad</button></div>`;
    $$('#sFor button').forEach(b => {
      b.classList.toggle('active', b.dataset.for === searchState.for);
      b.addEventListener('click', () => { searchState.for = b.dataset.for; renderSearch(); });
    });
  } else if (f === 'score') {
    box.innerHTML = `<span class="label">At least <small>${searchState.score}/10 ${scoreEmoji(searchState.score)}</small></span>
      <div class="score-picker" id="sScore">${Array.from({ length: 10 }, (_, i) => `<button type="button" data-score="${i + 1}">${i + 1}</button>`).join('')}</div>`;
    $$('#sScore button').forEach(b => {
      const v = +b.dataset.score;
      b.classList.toggle('on', v > searchState.score);
      b.classList.toggle('picked', v === searchState.score);
      b.addEventListener('click', () => { searchState.score = v; renderSearch(); });
    });
  }
  runSearch();
}

function runSearch() {
  const f = searchField;
  let results = [];
  let extra = () => ({});
  if (f === 'title') {
    const q = searchState.title.trim().toLowerCase();
    results = q ? recipes.filter(r => r.title.toLowerCase().includes(q)) : [];
    extra = r => ({ titleHTML: highlight(r.title, searchState.title.trim()) });
  } else if (f === 'ingredients') {
    const terms = searchState.ingredients.split(',').map(s => s.trim().toLowerCase()).filter(Boolean);
    results = terms.length ? recipes.filter(r => terms.every(t => (r.ingredients || '').toLowerCase().includes(t))) : [];
    extra = r => {
      const hits = lines(r.ingredients).filter(l => terms.some(t => l.toLowerCase().includes(t)));
      let s = hits.slice(0, 3).map(h => esc(h)).join(' · ');
      terms.forEach(t => { s = s.replace(new RegExp('(' + esc(t).replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + ')', 'ig'), '<mark>$1</mark>'); });
      return { snippet: s };
    };
  } else if (f === 'method') {
    const q = searchState.method.trim().toLowerCase();
    results = q ? recipes.filter(r => (r.method || '').toLowerCase().includes(q)) : [];
    extra = r => {
      const m = r.method || ''; const i = m.toLowerCase().indexOf(q);
      const start = Math.max(0, i - 30); const piece = (start ? '…' : '') + m.slice(start, i + q.length + 50) + '…';
      return { snippet: highlight(piece.replace(/\n/g, ' '), searchState.method.trim()) };
    };
  } else if (f === 'date') {
    const { from, to } = searchState;
    results = (from || to) ? recipes.filter(r => { const k = dayKey(r.dateAdded); return (!from || k >= from) && (!to || k <= to); }) : [];
  } else if (f === 'for') {
    results = recipes.filter(r => r.forWho === searchState.for);
  } else if (f === 'score') {
    results = recipes.filter(r => r.score && r.score >= searchState.score);
  }
  results.sort(f === 'score' ? (a, b) => b.score - a.score || byNewest(a, b) : byNewest);

  const idle = results.length === 0 && ((f === 'title' && !searchState.title.trim()) || (f === 'ingredients' && !searchState.ingredients.trim()) || (f === 'method' && !searchState.method.trim()) || (f === 'date' && !searchState.from && !searchState.to));
  $('#resultCount').textContent = idle ? '' : `${results.length} recipe${results.length === 1 ? '' : 's'} found`;
  const el = $('#searchResults');
  if (idle) { el.innerHTML = `<div class="empty"><div class="big">🔍</div><p>Pick a field above and start searching.</p></div>`; return; }
  if (!results.length) { el.innerHTML = `<div class="empty"><div class="big">🍳</div><p>Nothing matches yet.</p></div>`; return; }
  el.innerHTML = results.map(r => cardHTML(r, extra(r))).join('');
  bindCards(el, 'search');
}

/* ---------- backup ---------- */
function renderBackup() {
  const n = recipes.length;
  $('#backupStat').textContent = `${n} recipe${n === 1 ? '' : 's'} on this phone`;
  const m = loadMeta();
  $('#lastBackup').textContent = m.lastBackup ? `Last backup: ${new Date(m.lastBackup).toLocaleString('en-GB', { dateStyle: 'medium', timeStyle: 'short' })}` : 'No backup made yet';
}
$('#backupBtn').addEventListener('click', async () => {
  const payload = { app: 'aimee-recipes', version: 1, exported: new Date().toISOString(), recipes };
  const json = JSON.stringify(payload, null, 2);
  const name = `aimee-recipes-backup-${dayKey(new Date().toISOString())}.json`;
  const file = new File([json], name, { type: 'application/json' });
  let done = false;
  try {
    if (navigator.canShare && navigator.canShare({ files: [file] })) {
      await navigator.share({ files: [file], title: "Aimee's Recipes backup" });
      done = true;
    }
  } catch (err) {
    if (err && err.name === 'AbortError') return; // user closed share sheet
  }
  if (!done) {
    const url = URL.createObjectURL(file);
    const a = document.createElement('a'); a.href = url; a.download = name;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 4000);
  }
  saveMeta({ ...loadMeta(), lastBackup: new Date().toISOString() });
  renderBackup();
  toast('Backup created 💾');
});

/* ---------- restore ---------- */
let restoreMode = 'merge';
$$('#restoreMode button').forEach(b => b.addEventListener('click', () => {
  restoreMode = b.dataset.mode;
  $$('#restoreMode button').forEach(x => x.classList.toggle('active', x === b));
  $('#restoreHint').textContent = restoreMode === 'merge'
    ? 'Merge adds new recipes and updates changed ones. Nothing is deleted.'
    : 'Replace wipes the recipes on this phone and loads only the backup.';
}));

function cleanRecipe(r) {
  if (!r || typeof r !== 'object' || !String(r.title || '').trim()) return null;
  const date = new Date(r.dateAdded);
  const score = Number(r.score);
  return {
    id: String(r.id || uid()),
    title: String(r.title).trim().slice(0, 200),
    dateAdded: isNaN(date) ? new Date().toISOString() : date.toISOString(),
    forWho: r.forWho === 'aimee-dad' ? 'aimee-dad' : 'family',
    ingredients: String(r.ingredients || ''),
    method: String(r.method || ''),
    score: score >= 1 && score <= 10 ? Math.round(score) : null,
    updated: r.updated || r.dateAdded || new Date().toISOString(),
  };
}

$('#restoreFile').addEventListener('change', async e => {
  const f = e.target.files[0]; e.target.value = '';
  if (!f) return;
  let data;
  try { data = JSON.parse(await f.text()); } catch { return toast("That file isn't a recipe backup 😕"); }
  const incoming = (Array.isArray(data) ? data : data.recipes || []).map(cleanRecipe).filter(Boolean);
  if (!incoming.length) return toast('No recipes found in that file');
  if (restoreMode === 'replace') {
    if (!confirm(`Replace all ${recipes.length} recipes on this phone with ${incoming.length} from the backup?`)) return;
    recipes = incoming;
    saveRecipes(recipes);
    toast(`Restored ${incoming.length} recipes ✅`);
  } else {
    let added = 0, updated = 0;
    for (const r of incoming) {
      const i = recipes.findIndex(x => x.id === r.id);
      if (i === -1) { recipes.push(r); added++; }
      else if (new Date(r.updated) > new Date(recipes[i].updated || 0)) { recipes[i] = r; updated++; }
    }
    saveRecipes(recipes);
    toast(`Merged: ${added} new, ${updated} updated ✅`);
  }
  goTab('recipes');
});

/* ---------- updates (service worker) ---------- */
$('#appVersion').textContent = 'v' + APP_VERSION;
let swReg;
if ('serviceWorker' in navigator) {
  window.addEventListener('load', async () => {
    try {
      swReg = await navigator.serviceWorker.register('sw.js');
      swReg.update();
    } catch {}
  });
  let reloading = false;
  const hadController = !!navigator.serviceWorker.controller; // false on very first visit
  navigator.serviceWorker.addEventListener('controllerchange', () => {
    if (reloading || !hadController) return; reloading = true;
    sessionStorage.setItem('justUpdated', '1');
    location.reload();
  });
  document.addEventListener('visibilitychange', () => { if (!document.hidden && swReg) swReg.update().catch(() => {}); });
}
if (sessionStorage.getItem('justUpdated')) { sessionStorage.removeItem('justUpdated'); setTimeout(() => toast(`Updated to v${APP_VERSION} ✨`), 400); }
$('#updateBtn').addEventListener('click', async () => {
  if (!swReg) return toast('Updates work once installed from the web link');
  toast('Checking…');
  try {
    await swReg.update();
    if (!swReg.installing && !swReg.waiting) toast(`You're up to date (v${APP_VERSION})`);
  } catch { toast('Could not check – are you online?'); }
});

/* ---------- start ---------- */
buildScorePicker();
goTab('recipes');
