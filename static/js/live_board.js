/* Live Board display: scores, shared countdowns, board settings and (for managers) timer control. */
(() => {
  const CFG = window.LIVE_BOARD_CONFIG;
  const SELECTED = CFG.selected || [];
  const CONTROLLABLE = new Set(CFG.controllable || []);
  const board = document.getElementById('board');
  const $ = id => document.getElementById(id);
  if (CFG.isKku) document.body.classList.add('kku-board');

  const TEXT = {
    th: {
      lane: 'สนาม', team: 'ทีม', score: 'คะแนน', round: n => `รอบ ${n}`, multiRound: 'หลายรอบ',
      events: n => `${n} รายการ`, page: (a, b) => `หน้า ${a}/${b}`, connected: 'เชื่อมต่อแล้ว',
      connecting: 'กำลังเชื่อมต่อ…', offline: 'ขาดการเชื่อมต่อ · แสดงข้อมูลล่าสุด', updated: 'อัปเดต',
      awaitingDraw: 'รอจับสลาก', noMatches: 'ยังไม่มีคู่แข่งขันในขณะนี้', waitingList: 'รอจับสลาก: ',
      running: 'กำลังนับ', paused: 'หยุดชั่วคราว', expired: 'หมดเวลา',
      settings: 'รูปแบบบอร์ด', start: 'เริ่ม', pause: 'หยุดชั่วคราว', resume: 'ต่อเวลา', set: 'ตั้งเวลา', reset: 'รีเซ็ต',
      close: 'ปิด', cancel: 'ยกเลิก', apply: 'ใช้รูปแบบนี้', minutes: 'นาที', seconds: 'วินาที',
      timerTitle: 'ตั้งเวลาแข่งขัน', timerHint: 'นับถอยหลัง · ทุกจอที่เปิดบอร์ดนี้จะนับตามเวลาเดียวกัน',
      allEvents: 'เลือกทุกอีเวนต์', settingsTitle: 'รูปแบบบอร์ด', settingsHint: 'ดูตัวอย่างบนจอได้ทันที กด "ใช้รูปแบบนี้" เพื่อบันทึกลงลิงก์ของบอร์ดนี้',
      theme: 'ธีม', theme_light: 'สว่างสบายตา', theme_cream: 'ครีมอ่อน', theme_dark: 'เข้ม', theme_event: 'ธีมงานแข่งขัน',
      perPage: 'จำนวนคู่ต่อหน้า', fontSize: 'ขนาดตัวอักษร', font_s: 'เล็ก', font_m: 'ปกติ', font_l: 'ใหญ่', font_xl: 'ใหญ่มาก',
      pages: 'จำนวนหน้าขั้นต่ำ', interval: 'เปลี่ยนหน้าทุก', language: 'ภาษา', shareLink: 'ลิงก์สำหรับเปิดบนจออื่น',
      sending: 'กำลังส่งคำสั่ง…', sent: n => `ส่งคำสั่งแล้ว ${n} อีเวนต์`, pickEvent: 'กรุณาเลือกอย่างน้อย 1 อีเวนต์',
      badTime: 'ตั้งเวลาได้ 1 วินาที ถึง 24 ชั่วโมง (วินาที 0–59)', failed: 'ส่งคำสั่งไม่สำเร็จ', restart: 'เริ่มใหม่'
    },
    en: {
      lane: 'Lane', team: 'Team', score: 'Score', round: n => `Round ${n} / Tour ${n}`, multiRound: 'Multiple rounds',
      events: n => `${n} events`, page: (a, b) => `Page ${a}/${b}`, connected: 'Connected',
      connecting: 'Connecting…', offline: 'Connection lost · showing last data', updated: 'Updated',
      awaitingDraw: 'Awaiting draw', noMatches: 'No matches on court right now', waitingList: 'Awaiting draw: ',
      running: 'running', paused: 'paused', expired: 'Time up',
      settings: 'Board style', start: 'Start', pause: 'Pause', resume: 'Resume', set: 'Set time', reset: 'Reset',
      close: 'Close', cancel: 'Cancel', apply: 'Apply', minutes: 'Minutes', seconds: 'Seconds',
      timerTitle: 'Match timer', timerHint: 'Countdown · every screen showing this board follows the same clock',
      allEvents: 'Select all events', settingsTitle: 'Board style', settingsHint: 'Changes preview on screen. Apply saves them into this board link.',
      theme: 'Theme', theme_light: 'Light', theme_cream: 'Cream', theme_dark: 'Dark', theme_event: 'Event theme',
      perPage: 'Matches per page', fontSize: 'Text size', font_s: 'Small', font_m: 'Normal', font_l: 'Large', font_xl: 'Extra large',
      pages: 'Minimum pages', interval: 'Rotate every', language: 'Language', shareLink: 'Link for other screens',
      sending: 'Sending…', sent: n => `Sent to ${n} event(s)`, pickEvent: 'Select at least one event',
      badTime: 'Time must be 1 second to 24 hours (seconds 0–59)', failed: 'Command failed', restart: 'Restart'
    }
  };

  // ---------- settings (URL is the source of truth so every screen with the link matches) ----------
  let settings = {...CFG.settings, pages: CFG.pages, interval: CFG.interval};
  const storeKey = 'liveBoard:' + (SELECTED.length ? SELECTED.join(',') : 'today');
  try {
    const saved = JSON.parse(localStorage.getItem(storeKey) || 'null');
    const params = new URLSearchParams(location.search);
    if (saved && !params.has('theme')) settings = {...settings, ...saved};
  } catch (_) { /* storage unavailable: URL settings only */ }
  const t = () => TEXT[settings.lang] || TEXT.th;

  function applySettings(s) {
    board.dataset.theme = s.theme;
    board.dataset.font = s.font;
    document.documentElement.lang = s.lang;
    document.querySelectorAll('[data-label]').forEach(el => {
      const v = t()[el.dataset.label];
      if (typeof v === 'string') el.textContent = v;
    });
    renderTable();
    renderTimers();
  }

  function boardUrl(s) {
    const q = new URLSearchParams();
    if (SELECTED.length) q.set('events', SELECTED.join(','));
    q.set('pages', s.pages); q.set('interval', s.interval); q.set('theme', s.theme);
    q.set('per_page', s.per_page); q.set('font', s.font); q.set('lang', s.lang);
    return location.pathname + '?' + q.toString();
  }

  // ---------- scores ----------
  let matches = [], events = [], page = 0, totalPages = 1, lastBoardOk = 0, boardFailed = false, lastUpdated = '';
  const esc = v => { const d = document.createElement('div'); d.textContent = v ?? ''; return d.innerHTML; };

  function layout() {
    const per = Number(settings.per_page) || 24;
    const cols = per >= 12 && window.innerWidth >= 1000 ? 2 : 1;
    return {per, cols, rows: Math.ceil(per / cols)};
  }

  function splitPages(items, per, desired) {
    const count = Math.max(Math.ceil(items.length / per), Math.max(1, desired), 1);
    const out = [], base = Math.floor(items.length / count), extra = items.length % count;
    let at = 0;
    for (let i = 0; i < count; i++) { const size = base + (i < extra ? 1 : 0); out.push(items.slice(at, at + size)); at += size; }
    return out;
  }

  function teamCell(name, flag, right) {
    const img = flag ? `<img class="flag" src="/static/${esc(flag)}" alt="">` : '';
    const nm = `<span class="nm">${esc(name)}</span>`;
    return `<div class="team${right ? ' right' : ''}">${right ? nm + img : img + nm}</div>`;
  }

  function matchRow(m, multi, roundsDiffer) {
    let tag = '';
    if (multi) tag = `<span class="tag">${esc(m.event_name)}${roundsDiffer ? ' · ' + esc(t().round(m.round)) : ''}</span>`;
    return `<div class="row"><div class="lane"><b>${esc(m.field ?? '')}</b></div>${teamCell(m.team1, m.team1_flag, false)}`
      + `<div class="score"><span class="pts">${m.score1 ?? ''}<i>:</i>${m.score2 ?? ''}</span>${tag}</div>`
      + `${teamCell(m.team2, m.team2_flag, true)}</div>`;
  }

  function headRow() {
    const x = t();
    return `<div class="row head"><div>${x.lane}</div><div>${x.team}</div><div>${x.score}</div><div>${x.team}</div></div>`;
  }

  function renderTable() {
    const x = t();
    const {per, cols, rows} = layout();
    const pages = splitPages(matches, per, Number(settings.pages) || 1);
    totalPages = pages.length || 1;
    if (page >= totalPages) page = 0;
    const current = pages[page] || [];
    const live = events.filter(e => e.status !== 'awaiting_draw');
    const waiting = events.filter(e => e.status === 'awaiting_draw');
    const multi = live.length > 1;
    const rounds = [...new Set(live.map(e => e.round))];
    const roundsDiffer = rounds.length > 1;

    // header title: event name once, round once
    const shown = live.length ? live : waiting;
    $('boardTitle').textContent = shown.length === 1 ? shown[0].name : shown.length ? shown.map(e => e.name).join(' · ') : 'Live Board';
    let sub = '';
    if (live.length) sub = roundsDiffer ? x.multiRound : x.round(rounds[0]);
    if (multi) sub = x.events(live.length) + ' · ' + sub;
    $('boardSub').textContent = sub;

    const empty = $('emptyState');
    const colsEl = $('cols');
    if (!matches.length) {
      colsEl.innerHTML = '';
      empty.hidden = false;
      empty.innerHTML = !lastBoardOk ? `<span>${esc(x.connecting)}</span>` : waiting.length
        ? `<strong>${esc(x.awaitingDraw)}</strong><span>${esc(waiting.map(e => e.name).join(' · '))}</span>`
        : `<strong>${esc(x.noMatches)}</strong>`;
      $('waitingNote').textContent = '';
    } else {
      empty.hidden = true;
      // "awaiting draw" appears in exactly one place: here when other events are live
      $('waitingNote').textContent = waiting.length ? x.waitingList + waiting.map(e => e.name).join(', ') : '';
      colsEl.style.setProperty('--cols', cols);
      board.style.setProperty('--rows', rows);
      let html = '';
      for (let c = 0; c < cols; c++) {
        const slice = current.slice(c * rows, (c + 1) * rows);
        let body = '';
        for (let r = 0; r < rows; r++) body += slice[r] ? matchRow(slice[r], multi, roundsDiffer) : '<div class="row blank"></div>';
        html += `<div class="col">${headRow()}${body}</div>`;
      }
      colsEl.innerHTML = html;
    }
    $('pageBadge').textContent = x.page(page + 1, totalPages);
    renderConnection();
  }

  async function refreshBoard() {
    try {
      const q = new URLSearchParams();
      if (SELECTED.length) q.set('events', SELECTED.join(','));
      const r = await fetch('/api/public/live-board?' + q.toString(), {cache: 'no-store', headers: {Accept: 'application/json'}});
      const d = await r.json();
      if (!r.ok || !d.ok) throw new Error(d.message || 'load failed');
      matches = d.matches || []; events = d.events || [];
      lastBoardOk = performance.now(); boardFailed = false; lastUpdated = new Date().toLocaleTimeString('en-GB');
      renderTable();
      refreshTimers();
    } catch (_) {
      boardFailed = true; renderConnection();
    }
  }

  function renderConnection() {
    const x = t();
    const bad = boardFailed || !lastBoardOk || performance.now() - lastBoardOk > 7000;
    $('conn').classList.toggle('bad', bad && !!lastBoardOk);
    $('connText').textContent = !lastBoardOk ? x.connecting
      : bad ? x.offline
      : `${x.connected} · ${x.updated} ${lastUpdated}`;
  }

  // ---------- timers (server keeps the deadline; screens count locally between polls) ----------
  const timers = new Map();
  let timerBusy = false, timerReading = false, timerEpoch = 0;
  const timerIds = () => SELECTED.length ? SELECTED : events.map(e => e.id);
  const leftOf = s => Math.max(0, s.remaining - (s.running ? (performance.now() - s.received) / 1000 : 0));
  const fmt = sec => { const n = Math.ceil(Math.max(0, sec)); return `${String(Math.floor(n / 60)).padStart(2, '0')}:${String(n % 60).padStart(2, '0')}`; };

  function acceptTimers(list, requestStart) {
    const received = performance.now();
    for (const s of list) {
      s.remaining = Math.max(0, s.remaining - (s.running ? (received - requestStart) / 2000 : 0));
      timers.set(s.event_id, {...s, received});
    }
  }

  async function refreshTimers() {
    const ids = timerIds();
    if (timerReading || timerBusy || !ids.length) return;
    timerReading = true;
    const epoch = timerEpoch, start = performance.now();
    try {
      const r = await fetch('/api/public/live-timers?events=' + ids.join(','), {cache: 'no-store'});
      const d = await r.json();
      if (!r.ok || !d.ok) throw Error();
      if (epoch === timerEpoch) { acceptTimers(d.timers, start); renderTimers(); }
    } catch (_) { /* the board connection indicator already reports outages */ }
    finally { timerReading = false; }
  }

  function renderTimers() {
    const x = t();
    const wrap = $('timerChips');
    const ids = timerIds().filter(id => timers.has(id));
    wrap.classList.toggle('many', ids.length > 1);
    const existing = new Map([...wrap.querySelectorAll('[data-timer]')].map(el => [Number(el.dataset.timer), el]));
    for (const [id, el] of existing) if (!ids.includes(id)) el.remove();
    for (const id of ids) {
      const s = timers.get(id);
      let el = existing.get(id);
      if (!el) {
        el = document.createElement(CONTROLLABLE.has(id) ? 'button' : 'div');
        el.className = 'chip' + (CONTROLLABLE.has(id) ? ' controllable' : '');
        el.dataset.timer = id;
        if (CONTROLLABLE.has(id)) { el.type = 'button'; el.addEventListener('click', () => openTimerDialog(id)); }
        el.innerHTML = '<span class="name"></span><span class="clock"></span><span class="state"></span>';
        wrap.appendChild(el);
      }
      const left = leftOf(s);
      el.querySelector('.name').textContent = ids.length > 1 ? s.name : '';
      el.querySelector('.name').hidden = ids.length <= 1;
      el.querySelector('.clock').textContent = '◷ ' + fmt(left);
      const ready = !s.running && left >= s.duration;
      const st = left <= 0 ? x.expired : s.running || ready ? '' : x.paused;
      el.querySelector('.state').textContent = st;
      el.querySelector('.state').hidden = !st;
      el.classList.toggle('expired', left <= 0);
      el.classList.toggle('paused', left > 0 && !s.running && !ready);
      el.title = s.name;
    }
    renderQuickButton();
  }

  // ---------- timer control (only rendered for managers of these events) ----------
  const dialog = $('timerDialog');
  const quick = $('quickTimer');
  const controllableShown = () => timerIds().filter(id => CONTROLLABLE.has(id) && timers.has(id));

  function renderQuickButton() {
    if (!quick) return;
    const ids = controllableShown();
    quick.hidden = !ids.length;
    if (!ids.length) return;
    const anyRunning = ids.some(id => timers.get(id).running && leftOf(timers.get(id)) > 0);
    const allExpired = ids.every(id => leftOf(timers.get(id)) <= 0);
    quick.dataset.action = anyRunning ? 'pause' : allExpired ? 'dialog' : 'resume';
    quick.textContent = anyRunning ? '⏸ ' + t().pause : allExpired ? '↻ ' + t().restart : '▶ ' + t().start;
    quick.disabled = timerBusy;
  }

  async function sendTimer(ids, action, seconds) {
    const notice = $('timerNotice');
    timerBusy = true; timerEpoch++; renderQuickButton();
    if (notice) notice.textContent = t().sending;
    const start = performance.now();
    try {
      const r = await fetch('/live/timers/command', {
        method: 'POST',
        headers: {'Content-Type': 'application/json', 'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').content},
        body: JSON.stringify({event_ids: ids, action, seconds,
          versions: Object.fromEntries(ids.map(id => [id, timers.get(id) ? timers.get(id).version : 0]))})
      });
      const d = await r.json().catch(() => ({}));
      if (!r.ok || !d.ok) throw Error(d.message || t().failed);
      acceptTimers(d.timers, start);
      if (notice) notice.textContent = t().sent(ids.length);
      return true;
    } catch (e) {
      if (notice) notice.textContent = e.message || t().failed;
      return false;
    } finally {
      timerBusy = false; renderTimers(); refreshTimers();
    }
  }

  function openTimerDialog(focusId) {
    if (!dialog) return;
    const ids = controllableShown();
    const list = $('timerEvents');
    const s = timers.get(focusId) || timers.get(ids[0]);
    list.innerHTML = (ids.length > 1 ? `<label class="all"><input type="checkbox" id="timerAll"> ${esc(t().allEvents)}</label>` : '')
      + ids.map(id => `<label><input type="checkbox" value="${id}" ${id === focusId || ids.length === 1 ? 'checked' : ''}> ${esc(timers.get(id).name)}<span class="t" data-t="${id}"></span></label>`).join('');
    const all = $('timerAll');
    if (all) all.addEventListener('change', () => list.querySelectorAll('input[value]').forEach(i => { i.checked = all.checked; }));
    if (s) { $('timerMinutes').value = Math.floor(s.duration / 60); $('timerSeconds').value = s.duration % 60; }
    $('timerNotice').textContent = '';
    dialog.showModal();
  }

  if (dialog) {
    dialog.addEventListener('click', async e => {
      const b = e.target.closest('[data-timer-action]');
      if (!b || timerBusy) return;
      const ids = [...$('timerEvents').querySelectorAll('input[value]:checked')].map(i => Number(i.value));
      if (!ids.length) { $('timerNotice').textContent = t().pickEvent; return; }
      const action = b.dataset.timerAction;
      const m = Number($('timerMinutes').value), sec = Number($('timerSeconds').value);
      const total = m * 60 + sec;
      if (['set', 'start'].includes(action) && (!Number.isInteger(m) || !Number.isInteger(sec) || m < 0 || sec < 0 || sec > 59 || total < 1 || total > 86400)) {
        $('timerNotice').textContent = t().badTime; return;
      }
      await sendTimer(ids, action, total);
    });
    setInterval(() => {
      if (!dialog.open) return;
      dialog.querySelectorAll('[data-t]').forEach(el => { const s = timers.get(Number(el.dataset.t)); if (s) el.textContent = fmt(leftOf(s)); });
    }, 250);
  }
  if (quick) quick.addEventListener('click', () => {
    const ids = controllableShown();
    if (!ids.length || timerBusy) return;
    if (quick.dataset.action === 'dialog') return openTimerDialog(ids[0]);
    sendTimer(ids, quick.dataset.action);
  });

  // ---------- board style dialog with live preview ----------
  const sDialog = $('settingsDialog');
  const sForm = $('settingsForm');
  let before = null;
  function readForm() {
    const f = new FormData(sForm);
    return {theme: f.get('theme'), per_page: Number(f.get('per_page')), font: f.get('font'),
      pages: Number(f.get('pages')), interval: Number(f.get('interval')), lang: f.get('lang')};
  }
  function fillForm(s) {
    sForm.querySelectorAll('input[name="theme"]').forEach(i => { i.checked = i.value === s.theme; });
    for (const k of ['per_page', 'font', 'pages', 'interval', 'lang']) sForm.elements[k].value = String(s[k]);
    $('shareLink').value = location.origin + boardUrl(s);
  }
  $('openSettings').addEventListener('click', () => { before = {...settings}; fillForm(settings); sDialog.showModal(); });
  sForm.addEventListener('change', () => { settings = readForm(); applySettings(settings); $('shareLink').value = location.origin + boardUrl(settings); });
  $('cancelSettings').addEventListener('click', () => { if (before) { settings = before; applySettings(settings); } sDialog.close(); });
  sDialog.addEventListener('cancel', () => { if (before) { settings = before; applySettings(settings); } });
  $('applySettings').addEventListener('click', () => {
    settings = readForm(); before = null;
    try { localStorage.setItem(storeKey, JSON.stringify(settings)); } catch (_) { /* optional */ }
    history.replaceState(null, '', boardUrl(settings));
    restartRotation();
    applySettings(settings);
    sDialog.close();
  });

  // ---------- loops ----------
  let rotation = null;
  function restartRotation() {
    clearInterval(rotation);
    rotation = setInterval(() => { if (totalPages > 1) { page = (page + 1) % totalPages; renderTable(); } }, (Number(settings.interval) || 8) * 1000);
  }
  window.addEventListener('resize', () => renderTable());

  applySettings(settings);
  refreshBoard();
  setInterval(refreshBoard, 2000);
  setInterval(() => { renderTimers(); renderConnection(); }, 250);
  restartRotation();
})();
