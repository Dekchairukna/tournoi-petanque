/* All clients project the server's remaining time using a monotonic clock. */
(() => {
  const root = document.getElementById('liveTimers');
  if (!root) return;
  const controller = root.dataset.controller === 'true';
  const status = document.getElementById('timerConnection');
  let states = new Map(), busy = false, reading = false, epoch = 0, lastSync = 0;
  function ids() {
    if (controller) return [...document.querySelectorAll('.board-event:checked')].map(x => Number(x.value));
    return window.liveBoardTimerEventIds || [];
  }
  function left(s) { return Math.max(0, s.remaining - (s.running ? (performance.now() - s.received) / 1000 : 0)); }
  function format(seconds) {
    const n = Math.ceil(Math.max(0, seconds));
    return `${String(Math.floor(n / 60)).padStart(2, '0')}:${String(n % 60).padStart(2, '0')}`;
  }
  function apply(data, requestStart) {
    const received = performance.now();
    for (const s of data.timers) {
      const previous = states.get(s.event_id);
      if (controller && (!previous || previous.duration !== s.duration)) {
        const card = root.querySelector(`[data-timer-event="${s.event_id}"]`);
        if (card && card.querySelector('[data-minutes]') && !card.contains(document.activeElement)) {
          card.querySelector('[data-minutes]').value = Math.floor(s.duration / 60);
          card.querySelector('[data-seconds]').value = s.duration % 60;
        }
      }
      s.remaining = Math.max(0, s.remaining - (s.running ? (received - requestStart) / 2000 : 0));
      states.set(s.event_id, {...s, received});
    }
    lastSync = received;
    status.textContent = 'เชื่อมต่อเวลาแล้ว';
    tick();
  }
  function tick() {
    const chosen = new Set(ids());
    root.querySelectorAll('[data-timer-event]').forEach(card => {
      const id = Number(card.dataset.timerEvent), s = states.get(id);
      card.hidden = !chosen.has(id);
      if (!s) return;
      const seconds = left(s);
      card.querySelector('[data-clock]').textContent = format(seconds);
      card.querySelector('[data-clock-state]').textContent = seconds <= 0 ? 'หมดเวลา' : s.running ? 'กำลังนับ' : 'หยุดอยู่';
      card.classList.toggle('timer-expired', seconds <= 0);
    });
    if (lastSync && performance.now() - lastSync > 7000) status.textContent = 'ขาดการเชื่อมต่อ · กำลังแสดงเวลาจากข้อมูลล่าสุด';
    if (controller) root.querySelectorAll('button[data-timer-action]').forEach(button => {
      const card = button.closest('[data-timer-event]');
      const targets = card ? [Number(card.dataset.timerEvent)] : [...chosen].filter(id => root.querySelector(`[data-timer-event="${id}"] [data-timer-action]`));
      button.disabled = busy || !targets.length || targets.some(id => !states.has(id)) || !lastSync || performance.now() - lastSync > 7000;
    });
  }
  function buildDisplay() {
    if (controller) return;
    const grid = root.querySelector('[data-timer-grid]');
    for (const id of ids()) {
      const s = states.get(id);
      if (!s || grid.querySelector(`[data-timer-event="${id}"]`)) continue;
      const card = document.createElement('div');
      card.className = 'live-timer-card'; card.dataset.timerEvent = id;
      const name = document.createElement('span'); name.className = 'timer-name'; name.textContent = s.name;
      card.appendChild(name);
      const clock = document.createElement('strong'); clock.dataset.clock = ''; card.appendChild(clock);
      const state = document.createElement('small'); state.dataset.clockState = ''; card.appendChild(state);
      grid.appendChild(card);
    }
  }
  async function refresh() {
    if (reading || busy) return;
    const selected = ids();
    tick();
    if (!selected.length) return;
    reading = true;
    const version = epoch, start = performance.now();
    try {
      const response = await fetch('/api/public/live-timers?events=' + selected.join(','), {cache: 'no-store', signal: AbortSignal.timeout(5000)});
      const data = await response.json();
      if (!response.ok || !data.ok) throw Error();
      if (version !== epoch) return;
      apply(data, start); buildDisplay(); tick();
    } catch (_) { status.textContent = 'เชื่อมต่อเวลาไม่ได้ · กำลังลองใหม่'; }
    finally { reading = false; }
  }
  if (controller) {
    const notice = document.getElementById('timerNotice');
    document.addEventListener('change', e => { if(e.target.matches('.board-event')) { epoch++; refresh(); } });
    document.querySelectorAll('#selectNearEvents,#clearBoardEvents').forEach(b => b.addEventListener('click', () => { epoch++; refresh(); }));
    root.addEventListener('click', async e => {
      const button = e.target.closest('button[data-timer-action]');
      if (!button || button.disabled || busy) return;
      const card = button.closest('[data-timer-event]');
      const targets = card ? [Number(card.dataset.timerEvent)] : ids().filter(id => root.querySelector(`[data-timer-event="${id}"] [data-timer-action]`));
      const scope = card || document.getElementById('timerBulk');
      const minutes = Number(scope.querySelector('[data-minutes]').value);
      const seconds = Number(scope.querySelector('[data-seconds]').value);
      const action = button.dataset.timerAction;
      if (['set','start'].includes(action) && (!Number.isInteger(minutes) || !Number.isInteger(seconds) || minutes < 0 || seconds < 0 || seconds > 59 || minutes * 60 + seconds < 1 || minutes * 60 + seconds > 86400)) {
        notice.textContent = 'กรุณาตั้งเวลา 1 วินาที ถึง 24 ชั่วโมง โดยช่องวินาทีอยู่ระหว่าง 0–59'; return;
      }
      busy = true; epoch++; tick(); notice.textContent = 'กำลังส่งคำสั่ง…';
      const start = performance.now();
      try {
        const response = await fetch('/live/timers/command', {
          method:'POST', headers:{'Content-Type':'application/json','X-CSRFToken':document.querySelector('meta[name="csrf-token"]').content},
          body:JSON.stringify({event_ids:targets, action, seconds:minutes * 60 + seconds, versions:Object.fromEntries(targets.map(id => [id, states.get(id).version]))}),
          signal:AbortSignal.timeout(5000)
        });
        const data = await response.json();
        if (!response.ok || !data.ok) throw Error(data.message || 'ส่งคำสั่งไม่สำเร็จ');
        apply(data, start); notice.textContent = `ส่งคำสั่งแล้ว ${targets.length} อีเวนต์`;
      } catch (error) { notice.textContent = error.name === 'TimeoutError' ? 'ยังยืนยันคำสั่งไม่ได้ กำลังตรวจเวลาล่าสุดก่อนกดอีกครั้ง' : error.message; }
      finally { busy = false; tick(); refresh(); }
    });
  }
  refresh(); setInterval(refresh, 2000); setInterval(tick, 200);
})();
