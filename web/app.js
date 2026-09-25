'use strict';

// ════════════════════ 小工具 ════════════════════

const $ = (s, root = document) => root.querySelector(s);
const $$ = (s, root = document) => [...root.querySelectorAll(s)];

/** h('div.cls', {attr}, child, ...) —— 一个极简的 DOM 构造器，文本一律走 textContent */
function h(sel, attrs, ...kids) {
  const [tag, ...cls] = sel.split('.');
  const n = document.createElement(tag || 'div');
  if (cls.length) n.className = cls.join(' ');
  if (attrs && (typeof attrs !== 'object' || attrs instanceof Node || Array.isArray(attrs))) {
    kids.unshift(attrs);
    attrs = null;
  }
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v == null || v === false) continue;
    if (k === 'on') Object.entries(v).forEach(([ev, fn]) => n.addEventListener(ev, fn));
    else if (k === 'text') n.textContent = v;
    else if (k in n && typeof v !== 'string') n[k] = v;
    else n.setAttribute(k, v === true ? '' : v);
  }
  kids.flat().forEach((c) => {
    if (c == null || c === false) return;
    n.appendChild(c instanceof Node ? c : document.createTextNode(String(c)));
  });
  return n;
}

const SVGNS = 'http://www.w3.org/2000/svg';
function icon(name, cls = 'ic') {
  const s = document.createElementNS(SVGNS, 'svg');
  s.setAttribute('class', cls);
  s.setAttribute('aria-hidden', 'true');
  const u = document.createElementNS(SVGNS, 'use');
  u.setAttribute('href', '#i-' + name);
  s.appendChild(u);
  return s;
}

const ROMAN = ['', 'I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X', 'XI', 'XII'];
const roman = (n) => ROMAN[n] || String(n);
const EFFORT_CN = { low: '低', medium: '中', high: '高', xhigh: '超高', max: '极限' };
const STATUS_CN = { pending: '准备中', running: '进行中', finished: '已结束', failed: '出错', stopped: '已中止' };
const isNight = (phase) => /^NIGHT/.test(phase || '');
const stripGod = (t) => String(t || '').replace(/^上帝：/, '');
// 这些事件都是某个座位在「说话」，渲染成气泡
const SPEECH_TYPES = new Set(['speech', 'sheriff_speech', 'sheriff_pk_speech', 'pk_speech', 'last_words', 'wolf_chat']);
const isWolfRole = (p) => p && (p.role === 'WEREWOLF' || p.role_cn === '狼人');

function toast(msg, ms = 4000) {
  const t = $('#toast');
  t.textContent = msg;
  t.classList.remove('hidden');
  clearTimeout(toast._t);
  toast._t = setTimeout(() => t.classList.add('hidden'), ms);
}

function fmtDuration(s) {
  if (s == null || !isFinite(s)) return null;
  s = Math.round(s);
  if (s < 60) return `${s}秒`;
  const m = Math.floor(s / 60), r = s % 60;
  return m >= 60 ? `${Math.floor(m / 60)}:${String(m % 60).padStart(2, '0')}:${String(r).padStart(2, '0')}`
    : `${m}:${String(r).padStart(2, '0')}`;
}

// ════════════════════ 状态 ════════════════════

let OPTIONS = null;
let nPlayers = 12;
let seats = [];            // [{backend, model, custom, effort}]
let winRule = 'edge';
let deployment = 'inprocess';

let gameId = null;
let since = 0;
let poll = null;
let events = [];           // 已收到的事件（按当前视角）
let snap = null;           // 最近一次快照
let feedFilter = 'all';
let replayLoaded = false;
let view = 'setup';

// ════════════════════ 视图切换 ════════════════════

function show(v) {
  view = v;
  ['setup', 'live', 'review'].forEach((k) => $('#view-' + k).classList.toggle('hidden', k !== v));
  $$('.step').forEach((b) => b.classList.toggle('on', b.dataset.view === v));
  const lines = $$('.step-line');
  lines[0].classList.toggle('done', !!gameId);
  lines[1].classList.toggle('done', replayLoaded);
  $('.step[data-view="live"]').disabled = !gameId;
  $('.step[data-view="review"]').disabled = !replayLoaded;
  window.scrollTo({ top: 0 });
  if (v === 'live') layoutRing();
}

// ════════════════════ 1 · 配置 ════════════════════

async function init() {
  try {
    OPTIONS = await (await fetch('/api/options')).json();
  } catch (e) {
    toast('连不上服务端：' + e.message, 10000);
    return;
  }
  const d = OPTIONS.defaults || {};
  nPlayers = d.n_players || 12;
  deployment = d.deployment || 'inprocess';
  $('#max-speech').value = d.max_speech_chars || 450;
  $('#max-iter').value = d.max_iterations || 3;
  $('#sheriff').checked = d.sheriff !== false;
  $('#explode').checked = d.wolf_explode !== false;

  renderBoards();
  initBulk();
  renderDeployments();
  resetSeats();

  $('#api-key').addEventListener('input', checkLLM);
  $('#bulk-apply').onclick = applyBulk;
  $('#start').onclick = startGame;
  $('#stop').onclick = stopGame;
  $('#again').onclick = () => show('setup');
  $('#god-toggle').onchange = () => {
    document.body.classList.toggle('god', $('#god-toggle').checked);
    syncFilterChips();
    reloadFeed();
  };
  $$('#win-rule button').forEach((b) => b.onclick = () => {
    winRule = b.dataset.value;
    $$('#win-rule button').forEach((x) => x.setAttribute('aria-checked', String(x === b)));
    renderBoardHint();
  });
  $$('.step').forEach((b) => b.onclick = () => !b.disabled && show(b.dataset.view));
  $('#brand').onclick = (ev) => { ev.preventDefault(); show('setup'); };
  $$('#feed-filter .chip').forEach((c) => c.onclick = () => {
    if (c.disabled) return;
    feedFilter = c.dataset.f;
    $$('#feed-filter .chip').forEach((x) => x.classList.toggle('on', x === c));
    renderFeed();
  });
  $$('.tab').forEach((t) => t.onclick = () => {
    $$('.tab').forEach((x) => x.setAttribute('aria-selected', String(x === t)));
    $$('.tabpane').forEach((x) => x.classList.toggle('hidden', x.id !== t.dataset.tab));
  });
  const feed = $('#feed');
  feed.addEventListener('scroll', () => $('#jump').classList.toggle('hidden', nearBottom(feed)));
  $('#jump').onclick = () => { feed.scrollTop = feed.scrollHeight; };
  $('#open-history').onclick = openHistory;
  $('#close-history').onclick = () => $('#history').close();
  $('#history').addEventListener('click', (ev) => { if (ev.target.id === 'history') $('#history').close(); });
  window.addEventListener('resize', layoutRing);
  window.addEventListener('hashchange', routeFromHash);

  syncFilterChips();
  show('setup');
  routeFromHash();
}

function renderBoards() {
  const picker = $('#board-picker');
  picker.innerHTML = '';
  Object.keys(OPTIONS.boards).map(Number).sort((a, b) => a - b).forEach((n) => {
    const b = OPTIONS.boards[String(n)];
    picker.appendChild(h('button.board', {
      type: 'button', role: 'radio', 'aria-checked': String(n === nPlayers), 'data-n': n,
      on: { click: () => { nPlayers = n; renderBoards(); resetSeats(); } },
    }, h('b', null, String(n), h('small', { text: '人' })),
    h('span', { text: `${b.wolves}狼 · ${b.gods}神 · ${b.villagers}民` })));
  });
  const b = OPTIONS.boards[String(nPlayers)];
  const box = $('#board-roles');
  box.innerHTML = '';
  box.appendChild(h('span.hint', { text: b.name.split('：')[0] }));
  const WOLF = 'WEREWOLF', VIL = 'VILLAGER';
  const ROLE_NAME = { WEREWOLF: '狼人', SEER: '预言家', WITCH: '女巫', HUNTER: '猎人', IDIOT: '白痴', VILLAGER: '平民' };
  Object.entries(b.roles || {}).sort(([a], [c]) => (a === WOLF ? -1 : c === WOLF ? 1 : a === VIL ? 1 : c === VIL ? -1 : 0))
    .forEach(([r, cnt]) => {
      const cls = r === WOLF ? 'wolf' : r === VIL ? 'vil' : 'god';
      box.appendChild(h('span.rp.' + cls, { text: (ROLE_NAME[r] || r) + (cnt > 1 ? ` ×${cnt}` : '') }));
    });
  renderBoardHint();
}

function renderBoardHint() {
  $('#board-hint').textContent = winRule === 'city' ? '胜负规则：屠城（狼人要杀光所有好人）' : '胜负规则：屠边（杀光神职或平民即胜）';
  updateCtaSub();
}

function backendModels(backend) {
  return (OPTIONS.backends[backend] || {}).models || {};
}

function defaultSeat() {
  return { backend: 'heuristic', model: '', custom: '', effort: 'medium' };
}

function resetSeats() {
  const old = seats;
  seats = Array.from({ length: nPlayers }, (_, i) => old[i] || defaultSeat());
  renderSeats();
}

function fillSelect(sel, pairs, value) {
  sel.innerHTML = '';
  pairs.forEach(([v, label]) => sel.appendChild(h('option', { value: v, text: label })));
  if (value != null && pairs.some(([v]) => v === value)) sel.value = value;
}

function initBulk() {
  const be = $('#bulk-backend');
  fillSelect(be, Object.entries(OPTIONS.backends).map(([k, v]) => [k, v.label]), 'claude');
  const sync = () => {
    const b = OPTIONS.backends[be.value] || {};
    const models = Object.entries(b.models || {});
    fillSelect($('#bulk-model'), models.map(([k, v]) => [k, v.label]));
    $('#bulk-model').classList.toggle('hidden', !models.length);
    $('#bulk-custom-model').classList.toggle('hidden', !b.custom_model);
    $('#bulk-effort').disabled = !models.length && !b.custom_model;
  };
  be.onchange = sync;
  sync();
  fillSelect($('#bulk-effort'), OPTIONS.efforts.map((e) => [e, '思考 · ' + (EFFORT_CN[e] || e)]), 'medium');
}

function applyBulk() {
  const backend = $('#bulk-backend').value;
  const model = $('#bulk-model').value;
  const custom = $('#bulk-custom-model').value.trim();
  const effort = $('#bulk-effort').value;
  seats = seats.map(() => ({ backend, model, custom, effort }));
  renderSeats();
}

function seatSummary(s) {
  const b = OPTIONS.backends[s.backend] || {};
  const models = backendModels(s.backend);
  const hasModel = Object.keys(models).length || b.custom_model;
  const m = s.custom || (models[s.model] || {}).label || s.model;
  return [b.label || s.backend, hasModel ? m : null, hasModel ? (EFFORT_CN[s.effort] || s.effort) : null]
    .filter(Boolean).join(' · ');
}

function renderSeats() {
  const box = $('#seats');
  const openIdx = new Set($$('.seat.open', box).map((x) => Number(x.dataset.i)));
  box.innerHTML = '';
  seats.forEach((s, i) => {
    const b = OPTIONS.backends[s.backend] || {};
    const models = backendModels(s.backend);
    const modelKeys = Object.keys(models);
    if (modelKeys.length && !models[s.model]) s.model = modelKeys[0];
    if (!modelKeys.length) s.model = '';
    const hasModel = modelKeys.length > 0 || !!b.custom_model;

    const no = String(i + 1).padStart(2, '0');
    const card = h('div.seat', { 'data-i': i });
    if (openIdx.has(i)) card.classList.add('open');
    const summary = h('small', { text: seatSummary(s) });
    const tag = h('span.tag', { text: b.label || s.backend });
    if (s.backend === 'claude') tag.classList.add('claude');
    if (s.backend === 'openai') tag.classList.add('openai');

    const head = h('button.seat-head', {
      type: 'button', 'aria-expanded': String(card.classList.contains('open')),
      on: { click: () => { const o = card.classList.toggle('open'); head.setAttribute('aria-expanded', String(o)); } },
    }, h('span.medal', { text: no }),
    h('span.seat-title', null, h('b', { text: `${i + 1} 号位` }), summary), tag, icon('chev', 'ic chev'));

    const backendSel = h('select', { 'aria-label': `${i + 1} 号位后端` });
    fillSelect(backendSel, Object.entries(OPTIONS.backends).map(([k, v]) => [k, v.label]), s.backend);
    backendSel.onchange = () => { s.backend = backendSel.value; s.custom = ''; renderSeats(); };

    const body = h('div.seat-body', null, backendSel);
    if (modelKeys.length) {
      const modelSel = h('select', { 'aria-label': `${i + 1} 号位模型` });
      fillSelect(modelSel, modelKeys.map((k) => [k, models[k].label]), s.model);
      modelSel.title = (models[s.model] || {}).note || '';
      modelSel.onchange = () => { s.model = modelSel.value; summary.textContent = seatSummary(s); modelSel.title = (models[s.model] || {}).note || ''; };
      body.appendChild(modelSel);
    }
    if (b.custom_model) {
      // 自建网关可以服务任意模型名，所以 openai 后端多给一个自由输入框
      const custom = h('input', { type: 'text', placeholder: '自定义模型名（可选）', value: s.custom || '', 'aria-label': `${i + 1} 号位自定义模型名` });
      custom.oninput = () => { s.custom = custom.value.trim(); summary.textContent = seatSummary(s); };
      body.appendChild(custom);
    }
    const effort = h('div.effort', { role: 'group', 'aria-label': `${i + 1} 号位思考强度` });
    OPTIONS.efforts.forEach((e) => {
      effort.appendChild(h('button', {
        type: 'button', text: EFFORT_CN[e] || e, title: e, disabled: !hasModel,
        'aria-pressed': String(hasModel && s.effort === e),
        on: { click: () => { s.effort = e; $$('button', effort).forEach((x) => x.setAttribute('aria-pressed', String(x.title === e))); summary.textContent = seatSummary(s); } },
      }));
    });
    body.appendChild(effort);
    card.append(head, body);
    box.appendChild(card);
  });
  checkLLM();
  updateCtaSub();
}

function renderDeployments() {
  const box = $('#deployment');
  box.innerHTML = '';
  Object.entries(OPTIONS.deployments).forEach(([k, desc]) => {
    const label = String(desc).split(' —— ')[0];
    box.appendChild(h('button', {
      type: 'button', role: 'radio', 'aria-checked': String(k === deployment), text: label, title: desc,
      on: { click: () => { deployment = k; renderDeployments(); updateCtaSub(); } },
    }));
  });
  const desc = OPTIONS.deployments[deployment] || '';
  $('#deployment-hint').textContent = desc.split(' —— ')[1] || desc;
}

function updateCtaSub() {
  if (!OPTIONS) return;
  const dep = String(OPTIONS.deployments[deployment] || deployment).split(' —— ')[0];
  $('#cta-sub').textContent = `${nPlayers} 人 · ${winRule === 'city' ? '屠城' : '屠边'} · ${dep} · 开局后全自动跑完`;
}

function checkLLM() {
  const warn = $('#llm-warn');
  const counts = {};
  seats.forEach((s) => { if (s.backend !== 'heuristic') counts[s.backend] = (counts[s.backend] || 0) + 1; });
  const used = Object.keys(counts);
  if (!used.length) { warn.classList.add('hidden'); return; }
  warn.classList.remove('hidden', 'error');
  warn.innerHTML = '';
  const text = h('span');
  text.appendChild(document.createTextNode(
    used.map((b) => `${counts[b]} 个座位用了 ${OPTIONS.backends[b].label}`).join('，') + '。'));
  const typed = $('#api-key').value.trim();
  const missing = used.filter((b) => OPTIONS.keys_present && OPTIONS.keys_present[b] === false);
  if (typed) {
    text.appendChild(document.createTextNode(' 已在「模型接入」里填了 API Key。'));
  } else if (missing.length) {
    warn.classList.add('error');
    text.appendChild(document.createTextNode(' 服务端没有设置 '));
    missing.forEach((b, i) => {
      if (i) text.appendChild(document.createTextNode(' / '));
      text.appendChild(h('code', { text: OPTIONS.backends[b].needs_key }));
    });
    text.appendChild(h('b', { text: '，也没在「模型接入」里填 API Key —— 开局会被拒绝。' }));
  } else {
    text.appendChild(document.createTextNode(' 服务端环境里已有密钥。'));
  }
  warn.append(icon('warn'), text);
}

function collectSeats() {
  const baseUrl = $('#base-url').value.trim();
  const apiKey = $('#api-key').value;
  const keyEnv = $('#api-key-env').value.trim();
  // 挂自己的 provider 的三件套：base_url + model + api_key。
  // 密钥只用于这一次请求 —— 服务端不会把它写进会话库，也不会回传给页面。
  return seats.map((s, i) => ({
    seat: i + 1,
    backend: s.backend,
    model: s.custom || s.model,
    effort: s.effort,
    base_url: baseUrl,
    api_key: apiKey,
    api_key_env: keyEnv,
  }));
}

// ════════════════════ 开局 ════════════════════

async function startGame() {
  const seedRaw = $('#seed').value.trim();
  const body = {
    n_players: nPlayers,
    seats: collectSeats(),
    seed: seedRaw === '' ? null : Number(seedRaw),
    sheriff: $('#sheriff').checked,
    wolf_explode: $('#explode').checked,
    win_rule: winRule,
    max_speech_chars: Number($('#max-speech').value),
    max_iterations: Number($('#max-iter').value),
    deployment,
  };
  const btn = $('#start');
  btn.disabled = true;
  $('span', btn).textContent = '正在发牌…';
  let res, data;
  try {
    res = await fetch('/api/games', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
    });
    data = await res.json();
  } catch (e) {
    data = { error: e.message };
  }
  btn.disabled = false;
  $('span', btn).textContent = '天黑请闭眼';
  if (!res || !res.ok) {
    toast('开局失败：' + (data.error || (res && res.status)), 8000);
    return;
  }
  location.hash = '#/game/' + data.id;   // routeFromHash 会接手
}

async function stopGame() {
  if (!gameId) return;
  await fetch(`/api/games/${gameId}/stop`, { method: 'POST' });
}

// ════════════════════ 路由 / 接入一局 ════════════════════

function routeFromHash() {
  const m = location.hash.match(/^#\/game\/([\w-]+)/);
  if (m && m[1] !== gameId) attachGame(m[1]);
}

async function attachGame(id) {
  if (poll) { clearInterval(poll); poll = null; }
  gameId = id;
  since = 0;
  events = [];
  snap = null;
  replayLoaded = false;
  $('#feed').innerHTML = '';
  $('#game-id').textContent = 'game · ' + id.slice(0, 6);
  const r = await fetch(`/api/games/${id}`);
  if (!r.ok) {
    toast('找不到这局对局（可能是服务重启前的对局）');
    gameId = null;
    $('#game-id').textContent = '';
    history.replaceState(null, '', '#/');
    show('setup');
    return;
  }
  const s = await r.json();
  renderSnapshot(s);
  const done = ['finished', 'failed', 'stopped'].includes(s.status);
  show('live');
  await tick();
  if (!done) poll = setInterval(tick, 600);
}

function reloadFeed() {
  if (!gameId) return;
  since = 0;
  events = [];
  renderFeed();
  tick();
}

// ════════════════════ 轮询 ════════════════════

let ticking = false;
async function tick() {
  if (!gameId || ticking) return;
  ticking = true;
  const id = gameId;
  try {
    const god = $('#god-toggle').checked ? 1 : 0;
    const r = await fetch(`/api/games/${id}/events?since=${since}&god=${god}`);
    if (!r.ok || id !== gameId) return;
    const data = await r.json();
    since = data.total != null ? data.total : since + data.events.length;
    const wasDone = snap && ['finished', 'failed', 'stopped'].includes(snap.status);
    data.events.forEach((e) => { events.push(e); appendEvent(e); });
    renderSnapshot(data.snapshot);
    renderThinking();

    const st = data.snapshot.status;
    if (['finished', 'failed', 'stopped'].includes(st)) {
      if (poll) { clearInterval(poll); poll = null; }
      if (st === 'failed') {
        $('#feed').appendChild(h('div.sys.god', { text: '引擎异常：\n' + (data.snapshot.error || '') }));
      } else if (!replayLoaded) {
        await loadReplay(!wasDone && view === 'live');
      }
    }
  } catch (e) {
    console.warn(e);
  } finally {
    ticking = false;
  }
}

// ════════════════════ 2 · 对局：快照 + 圆桌 ════════════════════

function renderSnapshot(s) {
  snap = s;
  const pill = $('#status-pill');
  pill.className = 'pill ' + s.status;
  pill.textContent = STATUS_CN[s.status] || s.status;
  const night = isNight(s.phase);
  const dayWord = night ? '夜' : '天';
  $('#phase-eyebrow').textContent = `${night ? 'NIGHT' : 'DAY'} ${roman(s.day)}`;
  $('#phase-label').textContent = s.day ? `第 ${s.day} ${dayWord} · ${s.phase_cn || s.phase}` : (s.phase_cn || s.phase);
  const cur = s.current || {};
  const w = $('#waiting');
  w.innerHTML = '';
  if (s.status === 'running' && cur.seat) {
    w.append('正在等 ', h('em', { text: `${cur.seat} 号` }), `「${cur.action_cn || cur.action_type || ''}」`);
  } else if (s.status !== 'running') {
    w.textContent = s.winner_cn ? `${s.winner_cn}胜利` : '';
  }
  $('#stop').disabled = s.status !== 'running';

  // 桌心
  const pi = $('#phase-icon');
  pi.innerHTML = '';
  pi.appendChild(icon(night ? 'moon' : 'sun'));
  $('#table-eyebrow').textContent = `${night ? 'NIGHT' : 'DAY'} ${roman(s.day)}`;
  $('#table-phase').textContent = s.phase_cn || s.phase || '';
  const alive = s.players.filter((p) => p.alive).length;
  const sub = [];
  if (s.sheriff) sub.push(`警长 ${s.sheriff} 号`);
  else if (s.sheriff_status_cn) sub.push(s.sheriff_status_cn);
  sub.push(`存活 ${alive} / ${s.players.length}`);
  $('#table-sub').textContent = sub.join(' · ');
  const prog = $('#progress');
  prog.innerHTML = '';
  const sp = s.speech_progress;
  if (sp && sp.total) {
    prog.setAttribute('aria-label', `发言进度 ${sp.done} / ${sp.total}`);
    for (let i = 0; i < sp.total; i++) {
      prog.appendChild(h('i' + (i < sp.done ? '.done' : i === sp.done ? '.now' : '')));
    }
  }

  // 座位
  const ring = $('#seat-ring');
  ring.innerHTML = '';
  s.players.forEach((p) => {
    const active = s.status === 'running' && cur.seat === p.seat;
    const tok = h('div.ptoken', { 'data-seat': p.seat });
    const known = p.role_cn || null;
    if (known) tok.classList.add(isWolfRole(p) ? 'wolf' : 'good');
    if (!p.alive) tok.classList.add('dead');
    if (active) tok.classList.add('active');
    const disc = h('div.disc', { text: String(p.seat) });
    if (p.is_sheriff) disc.appendChild(h('span.badge', { title: '警长' }, icon('star', '')));
    let role = '', claimed = false;
    if (!p.alive) {
      const nightDeath = p.died_cause === 'killed' || p.died_cause === 'poisoned';
      role = (p.died_day ? `第${p.died_day}${nightDeath ? '夜' : '天'} ` : '') + (p.died_cause_cn || '出局');
    } else if (known) {
      role = known + (p.claim_cn && p.claim_cn !== known ? ` · 自称${p.claim_cn}` : '');
    } else if (p.revealed_role_cn) {
      role = p.revealed_role_cn + '（已翻牌）'; claimed = true;
    } else if (p.claim) {
      role = '自称' + (p.claim_cn || p.claim); claimed = true;
    }
    if (active) role = cur.action_cn || '行动中';
    tok.append(disc, h('span.agent', { text: p.agent || '', title: p.agent || '' }),
      h('span.role' + (claimed ? '.claimed' : ''), { text: role || ' ' }));
    ring.appendChild(tok);
  });
  layoutRing();
}

function layoutRing() {
  const toks = $$('#seat-ring .ptoken');
  const n = toks.length;
  if (!n) return;
  const cy = 47;   // 圆桌中心略靠上，给最下面座位的标签留位置
  const rx = window.innerWidth <= 640 ? 38.5 : 40.5;
  const ry = window.innerWidth <= 640 ? 38 : 39;
  toks.forEach((t, i) => {
    const a = (-90 + (i * 360) / n) * Math.PI / 180;
    t.style.left = (50 + rx * Math.cos(a)) + '%';
    t.style.top = (cy + ry * Math.sin(a)) + '%';
  });
}

// ════════════════════ 2 · 对局：实况 ════════════════════

function eventKind(e) {
  if (e.audience === 'wolves') return 'wolves';
  if (e.audience === 'private') return 'private';
  if (SPEECH_TYPES.has(e.type) && e.actor) return 'speech';
  return 'system';
}

function passesFilter(e) {
  if (feedFilter === 'all') return true;
  return eventKind(e) === feedFilter;
}

function nearBottom(feed) {
  return feed.scrollHeight - feed.scrollTop - feed.clientHeight < 80;
}

function playerOf(seat) {
  return snap && snap.players ? snap.players.find((p) => p.seat === seat) : null;
}

/** 把一条事件渲染成一个节点（或者 null = 不显示） */
function eventNode(e) {
  const text = String(e.text || '');
  // —— 第 N 夜 —— / —— 第 N 天 白天 —— 这种是分隔线
  const m = text.match(/^——\s*(.+?)\s*——\s*(.*)$/s);
  if (m && (e.type === 'phase' || e.type === 'daybreak')) {
    const frag = document.createDocumentFragment();
    frag.appendChild(h('div.divider', { text: m[1].replace(/\s+白天$/, '') + (isNight(e.phase) ? ' · 天黑请闭眼' : '') }));
    const rest = stripGod(m[2]).trim();
    if (rest && !/^天黑请闭眼。?$/.test(rest)) frag.appendChild(h('div.sys', { text: rest }));
    return frag;
  }
  if (e.actor && SPEECH_TYPES.has(e.type)) {
    const p = playerOf(e.actor);
    const body = text.replace(/^\[[^\]]+\]\s*/, '').replace(/^[^：]{1,12}：/, '');
    const av = h('span.av', { text: String(e.actor) });
    if (p && p.role_cn) av.classList.add(isWolfRole(p) ? 'wolf' : 'good');
    const who = h('span.who', { text: `${e.actor} 号` + (p && p.agent ? ` · ${p.agent}` : '') });
    if (p && p.role_cn && $('#god-toggle').checked) who.appendChild(h('em', { text: ' · ' + p.role_cn }));
    if (e.type === 'wolf_chat') who.prepend(icon('wolf', 'ic'));
    return h('div.msg.' + (e.audience === 'wolves' ? 'wolves' : e.audience === 'private' ? 'private' : 'public'),
      null, av, h('div.body', null, who, h('div.bubble', { text: body })));
  }
  if (e.audience === 'wolves' || e.audience === 'private') {
    const label = e.audience === 'wolves' ? '狼人频道' : '私聊';
    return h('div.chan.' + e.audience, null, icon(e.audience === 'wolves' ? 'wolf' : 'lock'),
      h('span', null, h('b', { text: `${label} · ${e.phase_cn || ''}` }), stripGod(text)));
  }
  if (e.audience === 'god') {
    return h('div.sys.god', null, icon('eye', 'ic'), ' ', stripGod(text));
  }
  if (e.type === 'explode') return h('div.sys.explode', { text: text.replace(/^💥\s*/, '') });
  return h('div.sys', { text: stripGod(text) });
}

function appendEvent(e) {
  if (!passesFilter(e)) return;
  const node = eventNode(e);
  if (!node) return;
  const feed = $('#feed');
  const stick = nearBottom(feed);
  const th = $('.thinking', feed);
  if (th) th.remove();
  feed.appendChild(node);
  if (stick) feed.scrollTop = feed.scrollHeight;
  $('#feed-count').textContent = `${events.length} 条`;
}

function renderFeed() {
  const feed = $('#feed');
  feed.innerHTML = '';
  const frag = document.createDocumentFragment();
  events.filter(passesFilter).forEach((e) => { const n = eventNode(e); if (n) frag.appendChild(n); });
  feed.appendChild(frag);
  feed.scrollTop = feed.scrollHeight;
  $('#feed-count').textContent = events.length ? `${events.length} 条` : '';
  renderThinking();
}

function renderThinking() {
  const feed = $('#feed');
  const old = $('.thinking', feed);
  if (old) old.remove();
  if (!snap || snap.status !== 'running') return;
  const cur = snap.current || {};
  if (!cur.seat) return;
  const stick = nearBottom(feed);
  feed.appendChild(h('div.thinking', null, h('span.av', { text: String(cur.seat) }),
    h('span.bubble', null, `${cur.seat} 号正在想「${cur.action_cn || cur.action_type || ''}」`,
      h('span.dots', null, h('i'), h('i'), h('i')))));
  if (stick) feed.scrollTop = feed.scrollHeight;
}

function syncFilterChips() {
  const god = $('#god-toggle').checked;
  $$('#feed-filter .chip.wolves, #feed-filter .chip.private').forEach((c) => {
    c.disabled = !god;
    c.title = god ? '' : '开启上帝视角后可看';
  });
  if (!god && (feedFilter === 'wolves' || feedFilter === 'private')) {
    feedFilter = 'all';
    $$('#feed-filter .chip').forEach((x) => x.classList.toggle('on', x.dataset.f === 'all'));
  }
}

// ════════════════════ 3 · 复盘 ════════════════════

async function loadReplay(autoShow) {
  const r = await fetch(`/api/games/${gameId}/replay`);
  if (!r.ok) return;
  const data = await r.json();
  const res = data.result || {};
  replayLoaded = true;

  const village = res.winner === 'VILLAGE';
  const box = $('#result');
  box.classList.toggle('wolf', !village && !!res.winner);
  $('#result-eyebrow').textContent = village ? 'THE VILLAGE PREVAILS' : res.winner ? 'THE WOLVES PREVAIL' : 'THE NIGHT ENDS';
  $('#result-title').textContent = (res.winner_cn || '平局') + (res.winner ? '胜利' : '');
  $('#result-reason').textContent = res.reason || (snap && snap.status === 'stopped' ? '对局被中止' : '');
  const ri = $('#result-icon');
  ri.innerHTML = '';
  ri.appendChild(document.createElementNS(SVGNS, 'use')).setAttribute('href', village ? '#i-sun' : '#i-wolf');

  const st = res.stats || {};
  const alive = st.n_alive != null ? st.n_alive : (res.alive || []).length;
  const stats = [
    [st.days != null ? st.days : res.days, '天'],
    [st.n_speeches, '条发言'],
    [alive, '人存活'],
    [fmtDuration(data.duration_s), '用时'],
    [res.n_thoughts, '条心路历程'],
  ].filter(([v]) => v != null && v !== '');
  const sb = $('#result-stats');
  sb.innerHTML = '';
  stats.slice(0, 4).forEach(([v, l]) => sb.appendChild(h('span', null, h('b', { text: String(v) }), l)));

  renderTimeline(data);
  renderReveal(res);
  renderThoughts(data.thoughts || [], res);
  renderSessions(data.sessions || [], res);

  link('#dl-replay', data.markdown || '', 'text/markdown');
  link('#dl-result', JSON.stringify(res, null, 2), 'application/json');
  $('#raw-pre').textContent = JSON.stringify(res, null, 2);
  fetch(`/api/games/${gameId}/views`).then((x) => (x.ok ? x.json() : null)).then((raw) => {
    const a = $('#dl-views');
    if (raw) { link('#dl-views', JSON.stringify(raw, null, 2), 'application/json'); a.classList.remove('hidden'); }
    else a.classList.add('hidden');
  }).catch(() => $('#dl-views').classList.add('hidden'));

  if (autoShow) show('review');
  else show(view);
}

function link(sel, text, type) {
  const a = $(sel);
  if (a.dataset.url) URL.revokeObjectURL(a.dataset.url);
  a.dataset.url = URL.createObjectURL(new Blob([text], { type }));
  a.href = a.dataset.url;
}

function renderTimeline(data) {
  const box = $('#timeline');
  box.innerHTML = '';
  const rounds = Array.isArray(data.timeline) ? data.timeline.filter((r) => (r.items || []).length) : [];
  if (!rounds.length) {
    // 旧服务端没有结构化时间线：直接展示 Markdown 战报
    box.appendChild(h('pre.md', { text: data.markdown || '（没有战报）' }));
    return;
  }
  rounds.forEach((r) => {
    const night = r.kind === 'night';
    box.appendChild(h('div.round.' + (night ? 'night' : 'day'), null,
      h('div.rail', null, h('span.dot', null, icon(night ? 'moon' : 'sun'))),
      h('div.content', null, h('h3', { text: r.title || `第 ${r.day} ${night ? '夜' : '天'}` }),
        (r.items || []).map((t) => h('p', { text: stripGod(t) })))));
  });
}

function revealRows(res) {
  if (Array.isArray(res.players) && res.players.length) return res.players;
  // 兼容：旧版 result 没有 players 列表，用 roles_cn + lineup 拼
  const alive = new Set(res.alive || []);
  const lineup = res.lineup || [];
  return Object.keys(res.roles_cn || {}).map(Number).sort((a, b) => a - b).map((seat) => {
    const d = (res.death_record || []).find((x) => x.seat === seat) || {};
    const spec = lineup.find((x) => x.seat === seat) || {};
    return {
      seat, role: res.roles[String(seat)], role_cn: res.roles_cn[String(seat)],
      side: res.roles[String(seat)] === 'WEREWOLF' ? 'wolf' : 'good',
      agent: spec.label || spec.model || spec.backend || '',
      alive: alive.has(seat), is_sheriff: res.sheriff === seat,
      fate_cn: alive.has(seat) ? (res.sheriff === seat ? '存活 · 警长' : '存活') : (d.day ? `第${d.day}天出局` : '出局'),
    };
  });
}

function roleClass(p) {
  if (p.side === 'wolf' || p.role === 'WEREWOLF') return 'wolf';
  return p.role === 'VILLAGER' || p.role_cn === '平民' ? 'vil' : 'god';
}

function renderReveal(res) {
  const box = $('#reveal');
  box.innerHTML = '';
  revealRows(res).forEach((p) => {
    box.appendChild(h('div.reveal-row' + (p.alive ? '' : '.out'), null,
      h('span.n', { text: `${p.seat} 号` }),
      h('span.rp.' + roleClass(p), { text: p.role_cn || p.role || '' }),
      h('span.ag', { text: p.agent || '', title: p.agent || '' }),
      h('span.fate' + (p.alive ? '.alive' : ''), { text: p.fate_cn || (p.alive ? '存活' : p.died_cause_cn || '出局') })));
  });
}

function seatAvatar(seat, res) {
  const role = (res.roles || {})[String(seat)];
  return h('span.av' + (role ? (role === 'WEREWOLF' ? '.wolf' : '.good') : ''), { text: String(seat) });
}

function accordion(seat, res, title, sub, bodyNodes, open) {
  const d = h('details.acc', open ? { open: true } : null);
  d.appendChild(h('summary', null, seatAvatar(seat, res),
    h('span.t', null, h('b', { text: title }), h('small', { text: sub })), icon('chev')));
  d.appendChild(h('div.acc-body', null, bodyNodes));
  return d;
}

function agentLabel(res, seat) {
  const spec = (res.lineup || []).find((x) => x.seat === seat);
  return spec ? (spec.label || spec.model || spec.backend || '') : '';
}

function renderThoughts(thoughts, res) {
  const pane = $('#tab-thoughts');
  pane.innerHTML = '';
  pane.appendChild(h('p.hint', { text: '每个 agent 在每个决策点的内心想法。这些内容从未进入过任何其他玩家的视角。', style: 'margin:0 0 16px' }));
  const bySeat = {};
  thoughts.forEach((t) => (bySeat[t.seat] = bySeat[t.seat] || []).push(t));
  const seatsWith = Object.keys(bySeat).map(Number).sort((a, b) => a - b);
  if (!seatsWith.length) { pane.appendChild(h('p.hint', { text: '（这一局没有记录到心路历程）' })); return; }
  seatsWith.forEach((seat, idx) => {
    const list = bySeat[seat];
    const roleCn = (res.roles_cn || {})[String(seat)] || '';
    const nodes = list.map((t) => {
      const when = h('div.th-when', { text: `第${t.day}天 · ${t.phase_cn || t.phase} · ${t.action_cn || t.action_type}` });
      if (!t.accepted) when.appendChild(h('span.rej', { text: `第 ${t.attempt} 次被打回` }));
      return h('div.th' + (t.accepted ? '' : '.rejected'), null, when,
        h('p.th-txt', { text: t.thought }),
        !t.accepted && t.error ? h('span.th-err', { text: '被判非法：' + t.error }) : null,
        t.action_desc ? h('span.th-act', { text: '→ ' + t.action_desc }) : null);
    });
    pane.appendChild(accordion(seat, res, `${seat} 号 · ${roleCn}`,
      [agentLabel(res, seat), `${list.length} 条`].filter(Boolean).join(' · '), nodes, idx === 0));
  });
}

function renderSessions(sessions, res) {
  const pane = $('#tab-sessions');
  pane.innerHTML = '';
  pane.appendChild(h('p.hint', { style: 'margin:0 0 16px', text:
    '每个座位的 agent 会话。玩家离场时容器/进程会被销毁，但会话在销毁之前就已经存进会话库，所以这里始终是完整的。' }));
  if (!sessions.length) { pane.appendChild(h('p.hint', { text: '（这一局没有会话记录）' })); return; }
  sessions.forEach((s) => {
    const roleCn = s.role_cn || (res.roles_cn || {})[String(s.seat)] || s.role || '';
    const msgs = s.messages || [];
    const nodes = [];
    nodes.push(h('div.sess-meta', { style: 'padding-top:14px', text:
      `${s.backend_cn || s.backend || ''}${s.model ? ' / ' + s.model : ''} · 离场原因：${s.release_reason_cn || s.release_reason || '—'}` +
      (s.memory_uri ? ` · memory 卷：${s.memory_uri}` : '') }));
    if (s.notes) nodes.push(h('div', null, h('div.sess-sub', { text: '私人笔记本（只有它自己看得到）' }), h('pre', { text: s.notes })));
    if (s.system_prompt) {
      nodes.push(h('details.adv', null, h('summary', null, icon('chev'), 'system prompt（整局逐字不变）'), h('pre', { text: s.system_prompt })));
    }
    msgs.forEach((m, i) => nodes.push(h('div', null, h('div.sess-sub', { text: `#${i + 1} ${m.role}` }),
      h('pre', { text: typeof m.content === 'string' ? m.content : JSON.stringify(m.content, null, 2) }))));
    pane.appendChild(accordion(s.seat, res, `${s.seat} 号 · ${roleCn}`, `${msgs.length} 条消息`, nodes, false));
  });
}

// ════════════════════ 历史对局 ════════════════════

async function openHistory() {
  const dlg = $('#history');
  const list = $('#history-list');
  list.innerHTML = '';
  list.appendChild(h('p.hint', { text: '加载中…' }));
  if (dlg.showModal) dlg.showModal(); else dlg.setAttribute('open', '');
  let data;
  try {
    data = await (await fetch('/api/games')).json();
  } catch (e) {
    list.innerHTML = '';
    list.appendChild(h('p.hint', { text: '加载失败：' + e.message }));
    return;
  }
  const rows = [...(data.live || []), ...(data.past || [])];
  list.innerHTML = '';
  if (!rows.length) { list.appendChild(h('p.hint', { text: '还没有对局记录。' })); return; }
  rows.sort((a, b) => String(b.created_at).localeCompare(String(a.created_at)));
  rows.forEach((g) => {
    const created = typeof g.created_at === 'number'
      ? new Date(g.created_at * 1000).toLocaleString('zh-CN', { hour12: false })
      : String(g.created_at || '').replace('T', ' ');
    const n = g.n_players || (g.config && g.config.n_players) || (g.board && g.board.name ? parseInt(g.board.name, 10) : '');
    const winner = g.winner_cn || (g.winner === 'VILLAGE' ? '好人阵营' : g.winner ? '狼人阵营' : '');
    list.appendChild(h('button.hist', {
      type: 'button',
      on: { click: () => { dlg.close(); location.hash = '#/game/' + g.id; if (g.id === gameId) show(replayLoaded ? 'review' : 'live'); } },
    }, h('span.medal', { text: n ? String(n) : '?' }),
    h('span.t', null, h('b', { text: `${n ? n + ' 人局 · ' : ''}${STATUS_CN[g.status] || g.status || ''}` }),
      h('small', { text: `${created} · ${String(g.id).slice(0, 6)}${g.days ? ` · ${g.days} 天` : ''}` })),
    winner ? h('span.w.' + (g.winner === 'VILLAGE' ? 'good' : 'wolf'), { text: winner + '胜' }) : null));
  });
}

init();
