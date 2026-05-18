/* Market Analysis Dashboard
   - Reads portfolio.json + data/* from GitHub Contents API
   - Edits saved back via authenticated PUT (PAT in localStorage)
*/

const OWNER  = 'SittinonNC';
const REPO   = 'market-analysis';
const BRANCH = 'master';
const API    = `https://api.github.com/repos/${OWNER}/${REPO}/contents`;

// ── State ────────────────────────────────────────────────────────────────────
const state = {
  config:    null,   // parsed portfolio.json
  configSha: null,
  dirty:     false,
};
let snapMarket    = null;
let snapPortfolio = null;
let history       = [];

// ── GitHub API ───────────────────────────────────────────────────────────────
function getPat() { return localStorage.getItem('gh_pat') || ''; }
function setPat(v) { localStorage.setItem('gh_pat', v); }
function clearPat() { localStorage.removeItem('gh_pat'); }

async function ghGet(path) {
  const headers = { 'Accept': 'application/vnd.github+json' };
  const pat = getPat();
  if (pat) headers.Authorization = `Bearer ${pat}`;
  const res = await fetch(`${API}/${path}?ref=${BRANCH}&_=${Date.now()}`, {
    headers, cache: 'no-store',
  });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`GET ${path}: ${res.status} ${await res.text()}`);
  const data = await res.json();
  const decoded = atob(data.content.replace(/\n/g, ''));
  const text = decodeURIComponent(escape(decoded));  // utf-8 safe
  return { content: text, sha: data.sha };
}

async function ghPut(path, contentText, sha, message) {
  const pat = getPat();
  if (!pat) throw new Error('ต้องตั้งค่า PAT ก่อน (กดไอคอน ⚙)');
  const body = {
    message,
    content: btoa(unescape(encodeURIComponent(contentText))),
    branch: BRANCH,
  };
  if (sha) body.sha = sha;
  const res = await fetch(`${API}/${path}`, {
    method: 'PUT',
    headers: {
      'Accept': 'application/vnd.github+json',
      'Authorization': `Bearer ${pat}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`PUT ${path}: ${res.status} ${await res.text()}`);
  return res.json();
}

// ── Utils ────────────────────────────────────────────────────────────────────
const $ = s => document.querySelector(s);
const $$ = s => document.querySelectorAll(s);
const fmtMoney = v => isFinite(v) ? `$${Number(v).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}` : '—';
const fmtPct   = v => isFinite(v) ? `${v >= 0 ? '+' : ''}${Number(v).toFixed(2)}%` : '—';
const cls      = v => isFinite(v) ? (v >= 0 ? 'green' : 'red') : 'muted';

function toast(msg, kind = '') {
  const el = $('#toast');
  el.textContent = msg;
  el.className = `toast ${kind}`;
  setTimeout(() => el.classList.add('hidden'), 3000);
}

function markDirty() {
  state.dirty = true;
  $('#saveBtn').disabled = false;
}

// ── Load everything ──────────────────────────────────────────────────────────
async function loadAll() {
  try {
    const cfg = await ghGet('portfolio.json');
    if (!cfg) throw new Error('portfolio.json ไม่พบใน repo');
    state.config = JSON.parse(cfg.content);
    state.configSha = cfg.sha;
  } catch (e) {
    toast('โหลด portfolio.json ล้มเหลว: ' + e.message, 'error');
    return;
  }

  try {
    const m = await ghGet('data/latest_market.json');
    snapMarket = m ? JSON.parse(m.content) : null;
  } catch (_) { snapMarket = null; }

  try {
    const p = await ghGet('data/latest_portfolio.json');
    snapPortfolio = p ? JSON.parse(p.content) : null;
  } catch (_) { snapPortfolio = null; }

  try {
    const i = await ghGet('data/index.json');
    history = i ? JSON.parse(i.content) : [];
  } catch (_) { history = []; }

  const last = [snapMarket?.ts, snapPortfolio?.ts].filter(Boolean).sort().pop();
  $('#lastUpdated').textContent = last
    ? `ข้อมูลล่าสุด: ${formatTs(last)}`
    : 'ยังไม่มี snapshot จาก workflow';

  renderAll();
}

function formatTs(ts) {
  // 2026-05-18T13-00-00Z → readable
  if (!ts) return '—';
  const iso = ts.replace(/-(\d{2})-(\d{2})Z$/, ':$1:$2Z');
  const d = new Date(iso);
  if (isNaN(d)) return ts;
  return d.toLocaleString('th-TH', { timeZone: 'Asia/Bangkok', dateStyle: 'short', timeStyle: 'short' });
}

// ── Render: HOLDINGS ─────────────────────────────────────────────────────────
function renderHoldings() {
  const tbody = $('#holdingsTable tbody');
  tbody.innerHTML = '';
  const pf = state.config?.portfolio || {};
  let totalValue = 0, totalCost = 0;

  const livePrices = snapMarket?.pnl || {};

  for (const [symbol, h] of Object.entries(pf)) {
    const isGold = symbol === 'GOLD_OZ';
    const qty    = isGold ? (h.oz ?? 0) : (h.shares ?? 0);
    const cost   = h.avg_cost ?? 0;
    const live   = livePrices[symbol]?.current_price;
    const price  = typeof live === 'number' ? live : null;
    const value  = (price != null) ? qty * price : null;
    const pnl    = (value != null) ? value - qty * cost : null;
    const pnlPct = (pnl != null && qty * cost > 0) ? (pnl / (qty * cost)) * 100 : null;

    if (value != null) totalValue += value;
    totalCost += qty * cost;

    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><input type="text" value="${symbol}" data-field="symbol" data-orig="${symbol}" /></td>
      <td class="right"><input type="number" step="any" value="${qty}" data-field="${isGold ? 'oz' : 'shares'}" data-symbol="${symbol}" /></td>
      <td class="right"><input type="number" step="any" value="${cost}" data-field="avg_cost" data-symbol="${symbol}" /></td>
      <td class="right">${price != null ? fmtMoney(price) : '—'}</td>
      <td class="right">${value != null ? fmtMoney(value) : '—'}</td>
      <td class="right ${cls(pnl)}">
        ${pnl != null ? fmtMoney(pnl) : '—'}
        ${pnlPct != null ? `<div class="muted" style="font-size:11px">${fmtPct(pnlPct)}</div>` : ''}
      </td>
      <td><button class="danger small" data-del="${symbol}">✕</button></td>
    `;
    tbody.appendChild(tr);
  }

  $('#totalValue').textContent = totalValue ? fmtMoney(totalValue) : '—';
  const totalGain = totalValue - totalCost;
  $('#totalPnl').textContent = totalValue ? fmtMoney(totalGain) : '—';
  $('#totalPnl').className = `right strong ${cls(totalGain)}`;

  // input → update state
  tbody.querySelectorAll('input').forEach(inp => {
    inp.addEventListener('input', e => {
      const t = e.target;
      const symbol = t.dataset.symbol || t.dataset.orig;
      if (t.dataset.field === 'symbol') {
        const newSym = t.value.trim().toUpperCase();
        if (newSym && newSym !== t.dataset.orig) {
          state.config.portfolio[newSym] = state.config.portfolio[t.dataset.orig];
          delete state.config.portfolio[t.dataset.orig];
          t.dataset.orig = newSym;
        }
      } else {
        const v = parseFloat(t.value) || 0;
        if (state.config.portfolio[symbol]) {
          state.config.portfolio[symbol][t.dataset.field] = v;
        }
      }
      markDirty();
    });
  });
  tbody.querySelectorAll('[data-del]').forEach(btn => {
    btn.addEventListener('click', () => {
      const sym = btn.dataset.del;
      if (confirm(`ลบ ${sym}?`)) {
        delete state.config.portfolio[sym];
        markDirty();
        renderHoldings();
      }
    });
  });
}

function addHolding() {
  const sym = prompt('Symbol (เช่น AAPL, BTC-USD, GOLD_OZ):');
  if (!sym) return;
  const upper = sym.trim().toUpperCase();
  if (state.config.portfolio[upper]) { toast('Symbol นี้มีอยู่แล้ว', 'error'); return; }
  state.config.portfolio[upper] = upper === 'GOLD_OZ'
    ? { oz: 0, avg_cost: 0 }
    : { shares: 0, avg_cost: 0 };
  markDirty();
  renderHoldings();
}

// ── Render: GOALS + ALLOCATION ───────────────────────────────────────────────
function renderGoals() {
  const g = state.config?.financial_goals || {};
  $('#goal_target').value  = g.target_portfolio_value ?? 0;
  $('#goal_date').value    = g.target_date || '';
  $('#goal_monthly').value = g.monthly_investment ?? 0;
  $('#goal_risk').value    = g.risk_profile || 'moderate';

  const a = state.config?.target_allocation || {};
  $('#alloc_mag7').value      = a.mag7 ?? 0;
  $('#alloc_watchlist').value = a.watchlist ?? 0;
  $('#alloc_crypto').value    = a.crypto ?? 0;
  $('#alloc_gold').value      = a.gold ?? 0;
  updateAllocSum();

  const bindG = (id, field) => $(id).addEventListener('input', e => {
    const v = e.target.type === 'number' ? parseFloat(e.target.value) || 0 : e.target.value;
    state.config.financial_goals[field] = v;
    markDirty();
  });
  bindG('#goal_target',  'target_portfolio_value');
  bindG('#goal_date',    'target_date');
  bindG('#goal_monthly', 'monthly_investment');
  bindG('#goal_risk',    'risk_profile');

  const bindA = (id, field) => $(id).addEventListener('input', e => {
    state.config.target_allocation[field] = parseFloat(e.target.value) || 0;
    updateAllocSum();
    markDirty();
  });
  bindA('#alloc_mag7',      'mag7');
  bindA('#alloc_watchlist', 'watchlist');
  bindA('#alloc_crypto',    'crypto');
  bindA('#alloc_gold',      'gold');
}

function updateAllocSum() {
  const a = state.config?.target_allocation || {};
  const sum = (a.mag7 || 0) + (a.watchlist || 0) + (a.crypto || 0) + (a.gold || 0);
  const el = $('#allocSum');
  el.textContent = `รวม: ${sum}%`;
  el.style.color = sum === 100 ? 'var(--green)' : 'var(--red)';
}

// ── Render: ALERTS ───────────────────────────────────────────────────────────
function renderAlerts() {
  const t = state.config?.alert_thresholds || {};
  $('#th_stocks').value = t.stocks ?? 2;
  $('#th_gold').value   = t.gold ?? 1;
  $('#th_crypto').value = t.crypto ?? 3;

  const bind = (id, field) => $(id).addEventListener('input', e => {
    state.config.alert_thresholds[field] = parseFloat(e.target.value) || 0;
    markDirty();
  });
  bind('#th_stocks', 'stocks');
  bind('#th_gold',   'gold');
  bind('#th_crypto', 'crypto');
}

// ── Render: LIVE P&L ─────────────────────────────────────────────────────────
function renderLivePnl() {
  const pnl   = snapMarket?.pnl || snapPortfolio?.pnl;
  const alloc = snapMarket?.allocation || snapPortfolio?.allocation;

  // Summary
  const sum = $('#pnlSummary');
  if (!pnl || !pnl.__total__) {
    sum.innerHTML = '<p class="hint">ยังไม่มีข้อมูล — รอ workflow รันครั้งแรก</p>';
  } else {
    const t = pnl.__total__;
    sum.innerHTML = `
      <div class="kv-card"><div class="k">มูลค่ารวม</div><div class="v">${fmtMoney(t.value)}</div></div>
      <div class="kv-card"><div class="k">ต้นทุน</div><div class="v">${fmtMoney(t.cost)}</div></div>
      <div class="kv-card"><div class="k">P&L</div><div class="v ${cls(t.gain)}">${fmtMoney(t.gain)}</div></div>
      <div class="kv-card"><div class="k">% Return</div><div class="v ${cls(t.gain_pct)}">${fmtPct(t.gain_pct)}</div></div>
    `;
  }

  // Allocation bars
  const ab = $('#allocBars');
  if (!alloc) {
    ab.innerHTML = '<p class="hint">ยังไม่มีข้อมูล</p>';
  } else {
    const labels = { mag7: 'Magnificent 7', watchlist: 'Watchlist', crypto: 'Crypto', gold: 'Gold' };
    ab.innerHTML = ['mag7', 'watchlist', 'crypto', 'gold'].map(k => {
      const d = alloc[k]; if (!d) return '';
      const cur = d.current_pct, tgt = d.target_pct;
      return `
        <div class="alloc-row">
          <div class="alloc-label">
            <span>${labels[k]}</span>
            <span class="muted">${cur.toFixed(1)}% / เป้า ${tgt}% (${d.diff >= 0 ? '+' : ''}${d.diff.toFixed(1)})</span>
          </div>
          <div class="alloc-bar">
            <div class="fill" style="width: ${Math.min(cur, 100)}%"></div>
            <div class="target" style="left: ${tgt}%"></div>
          </div>
        </div>
      `;
    }).join('');
  }

  // Goal progress
  const goal = state.config?.financial_goals;
  const totalVal = pnl?.__total__?.value;
  const gp = $('#goalProgress');
  if (!goal || !totalVal) {
    gp.innerHTML = '<p class="hint">ยังไม่มีข้อมูล</p>';
  } else {
    const pct = (totalVal / goal.target_portfolio_value) * 100;
    const remaining = Math.max(0, goal.target_portfolio_value - totalVal);
    const monthsNeeded = goal.monthly_investment > 0 ? Math.ceil(remaining / goal.monthly_investment) : null;
    gp.innerHTML = `
      <div class="kv-grid">
        <div class="kv-card"><div class="k">ปัจจุบัน</div><div class="v">${fmtMoney(totalVal)}</div></div>
        <div class="kv-card"><div class="k">เป้า</div><div class="v">${fmtMoney(goal.target_portfolio_value)}</div></div>
        <div class="kv-card"><div class="k">คืบหน้า</div><div class="v">${pct.toFixed(1)}%</div></div>
        <div class="kv-card"><div class="k">ขาดอีก</div><div class="v">${fmtMoney(remaining)}</div></div>
      </div>
      <div class="alloc-bar" style="margin-top: 14px; height: 12px;">
        <div class="fill" style="width: ${Math.min(pct, 100)}%; background: var(--green);"></div>
      </div>
      <p class="hint">
        เป้า ${goal.target_date} · DCA $${goal.monthly_investment}/เดือน
        ${monthsNeeded ? `· ประมาณ ${monthsNeeded} เดือนถึงเป้า (เฉพาะ DCA, ไม่นับผลตอบแทน)` : ''}
      </p>
    `;
  }
}

// ── Render: ANALYSIS ─────────────────────────────────────────────────────────
function renderAnalysis() {
  if (snapMarket) {
    $('#marketMeta').textContent = `บันทึก: ${formatTs(snapMarket.ts)}`;
    $('#marketAnalysis').textContent = snapMarket.analysis || '(ไม่มีข้อความวิเคราะห์)';
  } else {
    $('#marketAnalysis').textContent = 'ยังไม่มีข้อมูล — รอ workflow รันครั้งแรก';
  }
  if (snapPortfolio) {
    $('#portfolioMeta').textContent = `บันทึก: ${formatTs(snapPortfolio.ts)}`;
    $('#portfolioAnalysis').textContent = snapPortfolio.analysis || '(ไม่มีข้อความวิเคราะห์)';
  } else {
    $('#portfolioAnalysis').textContent = 'ยังไม่มีข้อมูล';
  }
}

// ── Render: NEWS ─────────────────────────────────────────────────────────────
function renderNews() {
  // News (raw text blob from workflow)
  const news = snapMarket?.news || snapPortfolio?.news;
  const nb = $('#newsBody');
  if (!news) {
    nb.innerHTML = '<p class="hint">ยังไม่มีข้อมูลข่าว</p>';
  } else {
    // news in workflow is concatenated string with "[Source] Title\nSummary" separated by \n\n
    const items = String(news).split(/\n\n+/).filter(Boolean).slice(0, 30);
    nb.innerHTML = items.map(it => {
      const lines = it.split('\n');
      const head = lines[0] || '';
      const body = lines.slice(1).join(' ');
      const m = head.match(/^\[(.+?)\]\s*(.*)$/);
      const src = m ? m[1] : '';
      const title = m ? m[2] : head;
      return `
        <div class="news-item">
          <div class="title">${escapeHtml(title)}</div>
          ${src ? `<div class="src">${escapeHtml(src)}</div>` : ''}
          ${body ? `<div class="summary">${escapeHtml(body)}</div>` : ''}
        </div>`;
    }).join('');
  }

  // Truth Social
  const truth = snapMarket?.truth_posts;
  const tb = $('#truthBody');
  if (!truth || (Array.isArray(truth) && truth.length === 0)) {
    tb.innerHTML = '<p class="hint">ไม่มีโพสต์ใหม่ในรอบล่าสุด</p>';
  } else {
    const arr = Array.isArray(truth) ? truth : [truth];
    tb.innerHTML = arr.slice(0, 10).map(t => {
      const text = typeof t === 'string' ? t : (t.text || t.content || JSON.stringify(t));
      return `<div class="news-item"><div class="summary">${escapeHtml(text)}</div></div>`;
    }).join('');
  }

  // Calendar
  const cal = snapMarket?.calendar;
  const cb = $('#calendarBody');
  if (!cal || (!cal.today?.length && !cal.upcoming?.length)) {
    cb.innerHTML = '<p class="hint">ไม่มี event impact วันนี้/3 วันถัดไป</p>';
  } else {
    const blocks = [];
    if (cal.today?.length) {
      blocks.push('<h3 style="margin: 8px 0; font-size: 13px;">วันนี้</h3>');
      blocks.push(...cal.today.map(e => `
        <div class="news-item">
          <div class="title">[${escapeHtml(e.country || '?')}] ${escapeHtml(e.title || '?')}</div>
          <div class="src">⏰ ${escapeHtml(e.time || '?')} · Forecast: ${escapeHtml(String(e.forecast ?? '?'))} · Previous: ${escapeHtml(String(e.previous ?? '?'))}</div>
        </div>`));
    }
    if (cal.upcoming?.length) {
      blocks.push('<h3 style="margin: 12px 0 8px; font-size: 13px;">3 วันข้างหน้า (USD)</h3>');
      blocks.push(...cal.upcoming.slice(0, 10).map(e => `
        <div class="news-item">
          <div class="title">${escapeHtml(e.title || '?')}</div>
          <div class="src">${escapeHtml(String(e.date || '').slice(0, 10))} · ${escapeHtml(e.time || '?')}</div>
        </div>`));
    }
    cb.innerHTML = blocks.join('');
  }
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

// ── Render: HISTORY ──────────────────────────────────────────────────────────
function renderHistory() {
  const hl = $('#historyList');
  if (!history.length) {
    hl.innerHTML = '<p class="hint">ยังไม่มีประวัติ</p>';
    return;
  }
  hl.innerHTML = history.slice(0, 30).map(h => `
    <div class="history-item" data-file="${escapeHtml(h.file)}">
      <span class="ts">${formatTs(h.ts)}</span>
      <span class="kind ${h.kind}">${h.kind}</span>
    </div>
  `).join('');
  hl.querySelectorAll('.history-item').forEach(el => {
    el.addEventListener('click', async () => {
      const file = el.dataset.file;
      try {
        const r = await ghGet(`data/${file}`);
        if (!r) return toast('โหลดไม่ได้', 'error');
        const data = JSON.parse(r.content);
        if (data.kind === 'market') { snapMarket = data; }
        else if (data.kind === 'portfolio') { snapPortfolio = data; }
        renderAnalysis();
        renderLivePnl();
        renderNews();
        toast(`โหลด snapshot ${formatTs(data.ts)} แล้ว`, 'success');
        // switch to analysis tab
        document.querySelector('[data-tab="analysis"]').click();
      } catch (e) {
        toast('error: ' + e.message, 'error');
      }
    });
  });
}

function renderAll() {
  renderHoldings();
  renderGoals();
  renderAlerts();
  renderLivePnl();
  renderAnalysis();
  renderNews();
  renderHistory();
}

// ── Save ─────────────────────────────────────────────────────────────────────
async function save() {
  if (!state.dirty) return;
  const sum = ['mag7','watchlist','crypto','gold']
    .reduce((s, k) => s + (state.config.target_allocation[k] || 0), 0);
  if (sum !== 100) {
    if (!confirm(`Target allocation รวม ${sum}% ไม่เท่ากับ 100% บันทึกอยู่ดีหรือไม่?`)) return;
  }
  const text = JSON.stringify(state.config, null, 2) + '\n';
  $('#saveBtn').disabled = true;
  try {
    const ts = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
    const r = await ghPut(
      'portfolio.json',
      text,
      state.configSha,
      `chore(dashboard): update portfolio.json ${ts}`,
    );
    state.configSha = r.content.sha;
    state.dirty = false;
    toast('บันทึกลง GitHub แล้ว ✓', 'success');
  } catch (e) {
    $('#saveBtn').disabled = false;
    if (String(e.message).includes('401') || String(e.message).includes('403')) {
      toast('PAT ไม่ถูกต้องหรือไม่มีสิทธิ์ — กด ⚙ ตั้งใหม่', 'error');
    } else {
      toast('บันทึกล้มเหลว: ' + e.message, 'error');
    }
  }
}

// ── Events ───────────────────────────────────────────────────────────────────
function bindEvents() {
  $$('.tab').forEach(t => t.addEventListener('click', () => {
    $$('.tab').forEach(x => x.classList.remove('active'));
    $$('.tab-pane').forEach(x => x.classList.remove('active'));
    t.classList.add('active');
    $('#tab-' + t.dataset.tab).classList.add('active');
  }));

  $('#addHoldingBtn').addEventListener('click', addHolding);
  $('#saveBtn').addEventListener('click', save);
  $('#reloadBtn').addEventListener('click', () => {
    if (state.dirty && !confirm('มีการแก้ที่ยังไม่ได้บันทึก ทิ้งไหม?')) return;
    state.dirty = false;
    $('#saveBtn').disabled = true;
    loadAll();
  });

  $('#settingsBtn').addEventListener('click', () => {
    $('#patInput').value = getPat();
    $('#patModal').classList.remove('hidden');
  });
  $('#patCancel').addEventListener('click', () => $('#patModal').classList.add('hidden'));
  $('#patSave').addEventListener('click', () => {
    setPat($('#patInput').value.trim());
    $('#patModal').classList.add('hidden');
    toast('บันทึก PAT แล้ว', 'success');
  });
  $('#patClear').addEventListener('click', () => {
    clearPat();
    $('#patInput').value = '';
    toast('ลบ PAT แล้ว', 'success');
  });
}

// ── Bootstrap ────────────────────────────────────────────────────────────────
bindEvents();
loadAll();
