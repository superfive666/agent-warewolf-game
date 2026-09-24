'use strict';

const $ = (s) => document.querySelector(s);
const el = (tag, cls, txt) => {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (txt != null) n.textContent = txt;
  return n;
};

let OPTIONS = null;
let nPlayers = 12;
let gameId = null;
let since = 0;
let poll = null;

// ════════════════════ 配置 ════════════════════

async function init() {
  OPTIONS = await (await fetch('/api/options')).json();

  const picker = $('#board-picker');
  Object.keys(OPTIONS.boards).map(Number).sort((a, b) => a - b).forEach((n) => {
    const b = el('button', 'chip' + (n === 12 ? ' on' : ''), `${n} 人`);
    b.onclick = () => {
      nPlayers = n;
      [...picker.children].forEach((c) => c.classList.remove('on'));
      b.classList.add('on');
      renderBoard();
      renderSeats();
    };
    picker.appendChild(b);
  });

  fillSelect($('#bulk-backend'),
    Object.entries(OPTIONS.backends).map(([k, v]) => [k, v.label]));
  const syncBulk = () => {
    const b = OPTIONS.backends[$('#bulk-backend').value] || {};
    fillSelect($('#bulk-model'), Object.entries(b.models || {}).map(([k, v]) => [k, v.label]));
    const custom = !!b.custom_model;
    $('#bulk-custom-model').classList.toggle('hidden', !custom);
    $('#bulk-model').classList.toggle('hidden', !Object.keys(b.models || {}).length);
  };
  $('#bulk-backend').onchange = syncBulk;
  syncBulk();
  fillSelect($('#bulk-effort'), OPTIONS.efforts.map((e) => [e, e]));
  fillSelect($('#deployment'), Object.keys(OPTIONS.deployments).map((k) => [k, k]));
  $('#deployment').value = OPTIONS.defaults.deployment || 'inprocess';
  const syncDep = () => {
    $('#deployment-hint').textContent = OPTIONS.deployments[$('#deployment').value] || '';
  };
  $('#deployment').onchange = syncDep;
  syncDep();
  $('#bulk-effort').value = 'medium';
  $('#bulk-apply').onclick = applyBulk;
  $('#start').onclick = startGame;
  $('#stop').onclick = stopGame;
  $('#god-toggle').onchange = reloadFeed;
  $('#toggle-setup').onclick = (ev) => {
    ev.stopPropagation();
    const c = $('#setup').classList.toggle('collapsed');
    $('#toggle-setup').textContent = c ? '改配置' : '收起';
  };
  document.querySelectorAll('.tab').forEach((t) => {
    t.onclick = () => {
      document.querySelectorAll('.tab').forEach((x) => x.classList.remove('active'));
      document.querySelectorAll('.tabpane').forEach((x) => x.classList.add('hidden'));
      t.classList.add('active');
      $('#' + t.dataset.tab).classList.remove('hidden');
    };
  });

  renderBoard();
  renderSeats();
}

function fillSelect(sel, pairs) {
  sel.innerHTML = '';
  pairs.forEach(([v, label]) => {
    const o = el('option', null, label);
    o.value = v;
    sel.appendChild(o);
  });
}

function renderBoard() {
  const b = OPTIONS.boards[String(nPlayers)];
  $('#board-desc').textContent =
    `${b.name} — 狼人 ${b.wolves} / 神职 ${b.gods} / 平民 ${b.villagers}，屠边胜负。`;
}

function renderSeats() {
  const tb = $('#seats tbody');
  tb.innerHTML = '';
  for (let s = 1; s <= nPlayers; s++) {
    const tr = el('tr');
    tr.appendChild(el('td', null, `${s} 号`));

    const backend = el('select');
    fillSelect(backend, Object.entries(OPTIONS.backends).map(([k, v]) => [k, v.label]));
    backend.dataset.seat = s;
    backend.className = 'seat-backend';

    const model = el('select');
    model.className = 'seat-model';
    const custom = el('input');
    custom.type = 'text';
    custom.className = 'seat-custom-model hidden';
    custom.placeholder = '自定义模型名';

    const effort = el('select');
    fillSelect(effort, OPTIONS.efforts.map((e) => [e, e]));
    effort.value = 'medium';
    effort.className = 'seat-effort';

    const sync = () => {
      const b = OPTIONS.backends[backend.value] || {};
      const models = b.models || {};
      const hasModels = Object.keys(models).length > 0;
      const prev = model.value;
      fillSelect(model, Object.entries(models).map(([k, v]) => [k, v.label]));
      if (prev && models[prev]) model.value = prev;
      model.classList.toggle('hidden', !hasModels);
      // 自建网关可以服务任意模型名，所以 openai 后端多给一个自由输入框
      custom.classList.toggle('hidden', !b.custom_model);
      effort.disabled = !hasModels;
      checkLLM();
    };
    backend.onchange = sync;
    sync();

    const tdModel = el('td');
    tdModel.appendChild(model);
    tdModel.appendChild(custom);
    [backend, tdModel, effort].forEach((c, i) => {
      if (i === 1) { tr.appendChild(c); return; }
      const td = el('td');
      td.appendChild(c);
      tr.appendChild(td);
    });
    tb.appendChild(tr);
  }
  checkLLM();
}

function applyBulk() {
  const b = $('#bulk-backend').value, m = $('#bulk-model').value,
        cm = $('#bulk-custom-model').value.trim(), e = $('#bulk-effort').value;
  document.querySelectorAll('.seat-backend').forEach((x) => { x.value = b; x.onchange(); });
  document.querySelectorAll('.seat-model').forEach((x) => { if (m) x.value = m; });
  document.querySelectorAll('.seat-custom-model').forEach((x) => { x.value = cm; });
  document.querySelectorAll('.seat-effort').forEach((x) => { x.value = e; });
  checkLLM();
}

function checkLLM() {
  const used = new Set([...document.querySelectorAll('.seat-backend')]
    .map((x) => x.value).filter((v) => v !== 'heuristic'));
  const warn = $('#llm-warn');
  if (!used.size) { warn.classList.add('hidden'); return; }
  const missing = [...used].filter((b) => OPTIONS.keys_present && OPTIONS.keys_present[b] === false);
  warn.classList.remove('hidden');
  warn.innerHTML = '';
  const names = [...used].map((b) => OPTIONS.backends[b].label).join('、');
  warn.appendChild(document.createTextNode(`有座位选了 ${names}。`));
  if (missing.length) {
    const envs = missing.map((b) => OPTIONS.backends[b].needs_key).join(' / ');
    warn.appendChild(el('b', null,
      ` 服务端还没有设置 ${envs}，这些座位会连续报错并退回安全默认动作。`));
  } else {
    warn.appendChild(document.createTextNode(' 服务端已配置好密钥。'));
  }
}

function collectSeats() {
  const backends = [...document.querySelectorAll('.seat-backend')];
  const models = [...document.querySelectorAll('.seat-model')];
  const customs = [...document.querySelectorAll('.seat-custom-model')];
  const efforts = [...document.querySelectorAll('.seat-effort')];
  const baseUrl = $('#base-url').value.trim();
  const keyEnv = $('#api-key-env').value.trim();
  // 注意：这里只传变量名，绝不传密钥 —— 阵容会原样写进会话库
  return backends.map((b, i) => ({
    seat: Number(b.dataset.seat),
    backend: b.value,
    model: (customs[i].value.trim() || models[i].value),
    effort: efforts[i].value,
    base_url: baseUrl,
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
    win_rule: $('#win-rule').value,
    max_speech_chars: Number($('#max-speech').value),
    max_iterations: Number($('#max-iter').value),
    deployment: $('#deployment').value,
  };
  $('#start').disabled = true;
  $('#start').textContent = '开局中…';
  const res = await fetch('/api/games', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  if (!res.ok) {
    alert('开局失败：' + (data.error || res.status));
    $('#start').disabled = false;
    $('#start').textContent = '开始游戏（开局后自动跑完）';
    return;
  }
  gameId = data.id;
  since = 0;
  // 开局后把配置面板收起来，把舞台让给对局
  $('#setup').classList.add('collapsed');
  $('#toggle-setup').classList.remove('hidden');
  $('#toggle-setup').textContent = '改配置';
  $('#feed').innerHTML = '';
  $('#live').classList.remove('hidden');
  $('#review').classList.add('hidden');
  $('#live').scrollIntoView({ behavior: 'smooth' });
  poll = setInterval(tick, 600);
  tick();
}

async function stopGame() {
  if (!gameId) return;
  await fetch(`/api/games/${gameId}/stop`, { method: 'POST' });
}

function reloadFeed() {
  since = 0;
  $('#feed').innerHTML = '';
  tick();
}

// ════════════════════ 轮询 ════════════════════

async function tick() {
  if (!gameId) return;
  const god = $('#god-toggle').checked ? 1 : 0;
  const r = await fetch(`/api/games/${gameId}/events?since=${since}&god=${god}`);
  const data = await r.json();
  since = data.total;
  data.events.forEach(appendEvent);
  renderSnapshot(data.snapshot);

  const st = data.snapshot.status;
  if (st === 'finished' || st === 'failed' || st === 'stopped') {
    clearInterval(poll);
    poll = null;
    $('#start').disabled = false;
    $('#start').textContent = '再来一局';
    if (st === 'failed') {
      $('#feed').appendChild(el('div', 'ev god', '引擎异常：\n' + data.snapshot.error));
    } else {
      loadReplay();
    }
  }
}

function appendEvent(e) {
  const d = el('div', 'ev ' + e.audience + (e.type === 'explode' ? ' explode' : ''));
  const mark = { public: '', wolves: '🐺 ', private: '🔒 ', god: '👁 ' }[e.audience] || '';
  d.appendChild(el('span', 'ph', `第${e.day}天 ${e.phase}`));
  d.appendChild(document.createTextNode(mark + e.text));
  const feed = $('#feed');
  const atBottom = feed.scrollHeight - feed.scrollTop - feed.clientHeight < 60;
  feed.appendChild(d);
  if (atBottom) feed.scrollTop = feed.scrollHeight;
}

function renderSnapshot(s) {
  const pill = $('#status-pill');
  pill.className = 'pill ' + s.status;
  pill.textContent = {
    pending: '准备中', running: '进行中', finished: '已结束',
    failed: '出错', stopped: '已中止',
  }[s.status] || s.status;
  const cur = s.current || {};
  $('#phase-label').textContent =
    `第 ${s.day} 天 · ${s.phase}` +
    (cur.seat && s.status === 'running' ? ` · 正在等 ${cur.seat}号 做「${cur.action_type}」` : '');

  const grid = $('#seat-grid');
  grid.innerHTML = '';
  s.players.forEach((p) => {
    const box = el('div', 'seat' + (p.alive ? '' : ' dead') +
      (cur.seat === p.seat && s.status === 'running' ? ' active' : ''));
    const no = el('div', 'no');
    no.textContent = `${p.seat}号`;
    if (p.is_sheriff) no.appendChild(el('span', 'badge', ' 👑'));
    box.appendChild(no);
    box.appendChild(el('div', 'meta', p.agent));
    const shown = p.role_cn || p.revealed_role_cn;
    if (shown) {
      box.appendChild(el('div', 'role ' + (shown === '狼人' ? 'wolf' : 'good'),
        shown + (p.role_cn ? '' : '（已翻牌）')));
    } else if (p.claim) {
      box.appendChild(el('div', 'meta', '自称 ' + p.claim));
    }
    if (!p.alive) box.appendChild(el('div', 'meta', `第${p.died_day}天出局`));
    grid.appendChild(box);
  });
}

// ════════════════════ 复盘 ════════════════════

async function loadReplay() {
  const r = await fetch(`/api/games/${gameId}/replay`);
  if (!r.ok) return;
  const data = await r.json();
  const res = data.result;

  const banner = $('#result-banner');
  banner.className = res.winner === 'VILLAGE' ? 'good' : 'wolf';
  banner.innerHTML = '';
  banner.appendChild(document.createTextNode(
    (res.winner === 'VILLAGE' ? '🟢 ' : '🔴 ') + res.winner_cn + '胜利'));
  banner.appendChild(el('span', 'why',
    `${res.reason} · 共 ${res.days} 天 · ${res.n_thoughts} 条心路历程`));

  $('#tab-replay').innerHTML = '';
  $('#tab-replay').appendChild(el('pre', null, data.markdown));
  renderThoughts(data.thoughts, res);
  renderSessions(data.sessions || [], res);

  const raw = await (await fetch(`/api/games/${gameId}/views`)).json();
  $('#raw-pre').textContent = JSON.stringify(res, null, 2);
  link('#dl-views', JSON.stringify(raw, null, 2), 'application/json');
  link('#dl-result', JSON.stringify(res, null, 2), 'application/json');
  link('#dl-replay', data.markdown, 'text/markdown');

  $('#review').classList.remove('hidden');
  $('#review').scrollIntoView({ behavior: 'smooth' });
}

function link(sel, text, type) {
  $(sel).href = URL.createObjectURL(new Blob([text], { type }));
}

function renderSessions(sessions, res) {
  const pane = $('#tab-sessions');
  pane.innerHTML = '';
  pane.appendChild(el('p', 'hint',
    '每个座位的 agent 会话。玩家离场时容器/进程会被销毁，但会话在销毁之前就已经存进会话库，' +
    '所以这里始终是完整的。'));
  if (!sessions.length) {
    pane.appendChild(el('p', 'hint', '（这一局没有会话记录）'));
    return;
  }
  sessions.forEach((s) => {
    const d = el('details', 'thought-seat');
    const roleCn = res.roles_cn[String(s.seat)] || s.role || '';
    const n = (s.messages || []).length;
    d.appendChild(el('summary', null,
      `${s.seat}号 · ${roleCn} · ${s.backend || ''}${s.model ? ' / ' + s.model : ''}` +
      ` · ${n} 条消息 · 释放原因 ${s.release_reason || '—'}`));
    const body = el('div', 'body');
    if (s.memory_uri) body.appendChild(el('div', 'act', 'memory 卷：' + s.memory_uri));
    if (s.notes) {
      body.appendChild(el('div', 'when', '私人笔记本（只有它自己看得到）'));
      body.appendChild(el('pre', null, s.notes));
    }
    if (s.system_prompt) {
      const sp = el('details');
      sp.appendChild(el('summary', null, 'system prompt（整局逐字不变）'));
      sp.appendChild(el('pre', null, s.system_prompt));
      body.appendChild(sp);
    }
    (s.messages || []).forEach((m, i) => {
      const b = el('div', 'th');
      b.appendChild(el('div', 'when', `#${i + 1} ${m.role}`));
      b.appendChild(el('pre', null,
        typeof m.content === 'string' ? m.content : JSON.stringify(m.content)));
      body.appendChild(b);
    });
    d.appendChild(body);
    pane.appendChild(d);
  });
}

function renderThoughts(thoughts, res) {
  const pane = $('#tab-thoughts');
  pane.innerHTML = '';
  pane.appendChild(el('p', 'hint',
    '每个 agent 在每个决策点的内心想法。这些内容从未进入过任何其他玩家的视角。'));

  const bySeat = {};
  thoughts.forEach((t) => (bySeat[t.seat] = bySeat[t.seat] || []).push(t));
  Object.keys(bySeat).map(Number).sort((a, b) => a - b).forEach((seat) => {
    const d = el('details', 'thought-seat');
    const roleCn = res.roles_cn[String(seat)];
    d.appendChild(el('summary', null,
      `${seat}号 · ${roleCn} · ${bySeat[seat].length} 条`));
    const body = el('div', 'body');
    bySeat[seat].forEach((t) => {
      const b = el('div', 'th' + (t.accepted ? '' : ' rejected'));
      b.appendChild(el('div', 'when',
        `第${t.day}天 · ${t.phase} · ${t.action_type}` +
        (t.accepted ? '' : `（第${t.attempt}次尝试被判非法：${t.error}）`)));
      b.appendChild(el('div', 'txt', t.thought));
      if (t.action) b.appendChild(el('div', 'act', '→ ' + JSON.stringify(t.action)));
      body.appendChild(b);
    });
    d.appendChild(body);
    pane.appendChild(d);
  });
}

init();
