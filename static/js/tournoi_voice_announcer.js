(function () {
  const PREF_KEY = 'tournoi_voice_behavior_v6';
  const OLD_PREF_KEY = 'tournoi_voice_behavior_v5';
  const ABBR_KEY = 'tournoi_voice_abbrev_v2';

  function qs(sel, root = document) { return root.querySelector(sel); }
  function qsa(sel, root = document) { return Array.from(root.querySelectorAll(sel)); }
  function norm(v) { return (v || '').toString().trim().replace(/\s+/g, ' '); }
  function getPrefs() {
    try {
      return JSON.parse(localStorage.getItem(PREF_KEY) || localStorage.getItem(OLD_PREF_KEY) || '{}') || {};
    } catch (e) { return {}; }
  }
  function savePrefs(p) { localStorage.setItem(PREF_KEY, JSON.stringify(p || {})); }
  function getDict() { try { return JSON.parse(localStorage.getItem(ABBR_KEY) || '{}') || {}; } catch (e) { return {}; } }
  function saveDict(m) { localStorage.setItem(ABBR_KEY, JSON.stringify(m || {})); }

  window.tournoiVoice = window.tournoiVoice || {};
  Object.assign(window.tournoiVoice, { getPrefs, savePrefs, norm, getDict, saveDict });

  window.voiceLang = function () {
    return qs('#voiceLangSelect')?.value || getPrefs().lang || 'th-TH';
  };
  window.voiceVersusText = function () {
    return voiceLang().startsWith('en') ? 'versus' : 'พบ';
  };
  window.voiceFieldText = function (field) {
    field = norm(field);
    if (!field || field === '-') return voiceLang().startsWith('en') ? 'Court not assigned' : 'ยังไม่ระบุสนามแข่งขัน';
    return voiceLang().startsWith('en') ? `Court ${field}` : `สนามแข่งขันที่ ${field}`;
  };
  window.voiceIntro = function () {
    return voiceLang().startsWith('en') ? 'Match announcement' : 'ประกาศผลการประกบคู่';
  };

  function isPlaceholderTeam(name) {
    const x = norm(name).toLowerCase();
    if (!x) return true;
    return ['x', '-', 'bye', 'ทีมว่าง', 'ว่าง', 'none', 'null', 'undefined'].includes(x);
  }

  function applyDictionary(text) {
    let output = norm(text);
    const map = getDict();
    Object.keys(map).sort((a, b) => b.length - a.length).forEach(key => {
      const val = map[key];
      if (val) output = output.split(key).join(val);
    });
    return output;
  }
  window.applyVoiceDictionary = applyDictionary;

  function findVoiceCandidates(text) {
    const tokens = (text.match(/[A-Za-z]{2,}|[ก-๙]{1,6}\.|[ก-๙A-Za-z]{2,}/g) || [])
      .map(x => x.trim())
      .filter(x => x.length >= 2);
    const unique = [];
    tokens.forEach(t => {
      const looksLikeAbbrev = /\.$/.test(t) || /^[A-Z]{2,}$/.test(t) || /^[ก-๙]{1,5}$/.test(t);
      if (looksLikeAbbrev && !unique.includes(t)) unique.push(t);
    });
    return unique.slice(0, 12);
  }

  window.learnVoiceWordsFromText = function (text) {
    const map = getDict();
    const candidates = findVoiceCandidates(text).filter(w => !map[w]);
    if (!candidates.length) return;
    const shouldAsk = confirm('พบคำย่อ/ชื่อที่อาจอ่านผิด ต้องการตั้งคำอ่านก่อนประกาศไหม?\n' + candidates.join(', '));
    if (!shouldAsk) return;
    candidates.forEach(word => {
      const answer = prompt(`ให้ระบบอ่านคำว่า "${word}" ว่าอย่างไร?\nเว้นว่างหรือกดยกเลิก = ใช้คำเดิม`, word);
      if (answer && answer.trim()) map[word] = answer.trim();
    });
    saveDict(map);
  };

  function selectedVoice() { return qs('#voiceNameSelect')?.value || getPrefs().voice || ''; }
  async function speakAny(text, opts = {}) {
    if (!('speechSynthesis' in window)) { alert('เครื่องนี้ยังไม่รองรับระบบอ่านเสียงของเบราว์เซอร์'); return; }
    const original = norm(text);
    if (!original) return;
    if (opts.askWords !== false && typeof window.learnVoiceWordsFromText === 'function') {
      await window.learnVoiceWordsFromText(original);
    }
    const finalText = applyDictionary(original);
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(finalText);
    u.lang = voiceLang();
    u.rate = Number(getPrefs().rate || 0.9);
    u.pitch = Number(getPrefs().pitch || 1);
    const name = selectedVoice();
    if (name) {
      const v = speechSynthesis.getVoices().find(x => x.name === name);
      if (v) u.voice = v;
    }
    window.speechSynthesis.speak(u);
  }
  window.speakText = speakAny;
  window.stopMatchVoice = function () { if ('speechSynthesis' in window) window.speechSynthesis.cancel(); };

  function getPlayoffInput(roundId, groupNo, slot, stage) {
    return qs(`.autosave-score[data-round="${roundId}"][data-group="${groupNo}"][data-slot="${slot}"][data-stage="${stage}"]`);
  }
  function getPlayoffTeam(roundId, groupNo, slot) {
    const el = getPlayoffInput(roundId, groupNo, slot, 1) || getPlayoffInput(roundId, groupNo, slot, 2) || getPlayoffInput(roundId, groupNo, slot, 3);
    return norm(el ? el.dataset.team : '') || 'ทีมว่าง';
  }
  function getPlayoffCourt(roundId, groupNo, pairStart) {
    const input = qs(`.court-pair-input[data-round="${roundId}"][data-group="${groupNo}"][data-pair-start="${pairStart}"]`);
    return norm(input ? input.value : '');
  }
  function getRoundNumber(roundName) {
    const m = norm(roundName).match(/รอบ(?:ที่)?\s*(\d+)/i) || norm(roundName).match(/round\s*(\d+)/i);
    return m ? m[1] : '';
  }
  function activeRoundPanel() {
    return qsa('.js-round-panel').find(p => !p.hidden) || qsa('.js-round-panel').slice(-1)[0];
  }
  function visibleGroupsInActiveRound() {
    const round = activeRoundPanel();
    if (!round) return [];
    let groups = qsa('.js-group-panel', round).filter(g => !g.hidden);
    if (!groups.length) groups = qsa('.js-group-panel', round);
    return groups;
  }
  function countRealTeamsInGroups(groups) {
    const seen = new Set();
    groups.forEach(g => {
      const roundId = g.dataset.roundId;
      const groupNo = g.dataset.groupPanel;
      [1, 2, 3, 4].forEach(slot => {
        const t = getPlayoffTeam(roundId, groupNo, slot);
        if (!isPlaceholderTeam(t)) seen.add(t);
      });
    });
    return seen.size;
  }
  function groupHasRealPair(roundId, groupNo, a, b) {
    const t1 = getPlayoffTeam(roundId, groupNo, a);
    const t2 = getPlayoffTeam(roundId, groupNo, b);
    return !isPlaceholderTeam(t1) && !isPlaceholderTeam(t2);
  }

  window.buildPlayoffGroupVoice = function (roundId, groupNo, options = {}) {
    const box = qs(`.js-group-panel[data-round-id="${roundId}"][data-group-panel="${groupNo}"]`);
    const roundName = norm(box ? box.dataset.roundName : '');
    const pairs = [];
    [[1, 2], [3, 4]].forEach(pair => {
      const t1 = getPlayoffTeam(roundId, groupNo, pair[0]);
      const t2 = getPlayoffTeam(roundId, groupNo, pair[1]);
      if (groupHasRealPair(roundId, groupNo, pair[0], pair[1])) {
        pairs.push(`${voiceFieldText(getPlayoffCourt(roundId, groupNo, pair[0]))} ${t1} ${voiceVersusText()} ${t2}`);
      }
    });
    const includeRound = options.includeRound === true;
    let prefix = `สายที่ ${groupNo}`;
    if (includeRound) {
      const n = getRoundNumber(roundName);
      const teams = countRealTeamsInGroups([box].filter(Boolean));
      prefix = voiceLang().startsWith('en')
        ? `${voiceIntro()} round ${n || ''}${teams ? ` (${teams} teams)` : ''} . Group ${groupNo}`
        : `${voiceIntro()} รอบที่ ${n || ''}${teams ? ` (${teams} ทีม)` : ''} . สายที่ ${groupNo}`;
    }
    return [prefix, ...pairs].filter(Boolean).join(' . ');
  };

  function buildActivePlayoffScript() {
    const groups = visibleGroupsInActiveRound();
    if (!groups.length) return '';
    const roundName = norm(groups[0].dataset.roundName || '');
    const roundNo = getRoundNumber(roundName);
    const teamCount = countRealTeamsInGroups(groups);
    const header = voiceLang().startsWith('en')
      ? `${voiceIntro()} round ${roundNo || ''}${teamCount ? ` (${teamCount} teams)` : ''}`
      : `${voiceIntro()} รอบที่ ${roundNo || ''}${teamCount ? ` (${teamCount} ทีม)` : ''}`;
    const lines = [header];
    groups.forEach(g => {
      const line = window.buildPlayoffGroupVoice(g.dataset.roundId, g.dataset.groupPanel, { includeRound: false });
      // ไม่อ่านสายเปล่า หรือคู่ทีมว่างพบทีมว่าง
      if (line && line.split(' . ').length > 1) lines.push(line);
    });
    return lines.join(' . ');
  }
  function setVoiceScript(text) {
    const box = qs('#voiceScriptText');
    if (box) box.value = norm(text);
  }
  window.refreshPlayoffVoiceScript = function () { const text = buildActivePlayoffScript(); setVoiceScript(text); return text; };
  window.speakPlayoffGroup = function (roundId, groupNo) {
    const script = window.buildPlayoffGroupVoice(roundId, groupNo, { includeRound: true });
    setVoiceScript(script);
    speakAny(script);
  };
  window.speakAllPlayoffMatches = function () {
    const textarea = qs('#voiceScriptText');
    const fresh = buildActivePlayoffScript();
    const script = norm(textarea && textarea.value ? textarea.value : fresh);
    if (!script) return alert('ยังไม่มีสายเพลย์ออฟให้อ่าน');
    setVoiceScript(script);
    const p = getPrefs();
    p.lastMode = 'active-round-only';
    p.lastGeneratedScript = fresh;
    savePrefs(p);
    speakAny(script);
  };



  function getSwissRows() {
    return qsa('.match-voice-row');
  }

  function getSwissRoundNo() {
    const row = getSwissRows()[0];
    return norm(row ? row.dataset.round : '') || '';
  }

  function countSwissRealTeams(rows) {
    const seen = new Set();
    rows.forEach(row => {
      const t1 = norm(row.dataset.team1);
      const t2 = norm(row.dataset.team2);
      if (!isPlaceholderTeam(t1)) seen.add(t1);
      if (!isPlaceholderTeam(t2)) seen.add(t2);
    });
    return seen.size;
  }

  window.buildSwissMatchVoice = function (row) {
    if (!row) return '';
    const fieldInput = qs('.match-field-input', row);
    const field = norm(fieldInput ? fieldInput.value : row.dataset.field);
    const team1 = norm(row.dataset.team1) || 'ทีมว่าง';
    const team2 = norm(row.dataset.team2) || 'ทีมว่าง';
    if (isPlaceholderTeam(team1) || isPlaceholderTeam(team2)) return '';
    return `${voiceFieldText(field)} ${team1} ${voiceVersusText()} ${team2}`;
  };

  function buildSwissVoiceScript() {
    const rows = getSwissRows();
    if (!rows.length) return '';

    const roundNo = getSwissRoundNo();
    const header = voiceLang().startsWith('en')
      ? `Match announcement Round ${roundNo}`
      : `ประกาศผลการประกบคู่

การแข่งขันครั้งที่ ${roundNo}`;

    const lines = [header];
    rows.forEach(row => {
      const line = window.buildSwissMatchVoice(row);
      if (line) lines.push(line);
    });
    return lines.join(' . ');
  }

  window.refreshSwissVoiceScript = function () {
    const text = buildSwissVoiceScript();
    setVoiceScript(text);
    return text;
  };

  window.speakMatchRow = function (row) {
    const script = window.buildSwissMatchVoice(row);
    setVoiceScript(script);
    speakAny(script);
  };

  window.speakAllMatches = function () {
    const textarea = qs('#voiceScriptText');
    const fresh = buildSwissVoiceScript();
    const script = norm(textarea && textarea.value ? textarea.value : fresh);
    if (!script) return alert('ยังไม่มีข้อมูลคู่แข่งขันให้อ่าน');
    setVoiceScript(script);
    const p = getPrefs();
    p.lastMode = 'swiss-active-round';
    p.lastGeneratedSwissScript = fresh;
    savePrefs(p);
    speakAny(script);
  };

  function refreshVoiceListCommon() {
    const select = qs('#voiceNameSelect');
    if (!select || !('speechSynthesis' in window)) return;
    const prefs = getPrefs();
    const selected = localStorage.getItem('tournoi_voice_name') || prefs.voice || '';
    select.innerHTML = '<option value="">เสียงอัตโนมัติ</option>';
    speechSynthesis.getVoices()
      .filter(v => !voiceLang() || v.lang.toLowerCase().startsWith(voiceLang().slice(0, 2).toLowerCase()))
      .forEach(v => {
        const opt = document.createElement('option');
        opt.value = v.name; opt.textContent = `${v.name} (${v.lang})`;
        if (v.name === selected) opt.selected = true;
        select.appendChild(opt);
      });
  }
  window.refreshVoiceList = refreshVoiceListCommon;

  document.addEventListener('DOMContentLoaded', () => {
    const prefs = getPrefs();
    const lang = qs('#voiceLangSelect');
    const voice = qs('#voiceNameSelect');
    if (lang) {
      lang.value = localStorage.getItem('tournoi_voice_lang') || prefs.lang || lang.value || 'th-TH';
      lang.addEventListener('change', () => {
        const p = getPrefs(); p.lang = lang.value; savePrefs(p);
        localStorage.setItem('tournoi_voice_lang', lang.value);
        refreshVoiceListCommon();
        if (typeof window.refreshPlayoffVoiceScript === 'function') window.refreshPlayoffVoiceScript();
        if (typeof window.refreshSwissVoiceScript === 'function') window.refreshSwissVoiceScript();
      });
    }
    if (voice) voice.addEventListener('change', () => { const p = getPrefs(); p.voice = voice.value || ''; savePrefs(p); localStorage.setItem('tournoi_voice_name', voice.value || ''); });
    refreshVoiceListCommon();
    if ('speechSynthesis' in window) speechSynthesis.onvoiceschanged = refreshVoiceListCommon;
    const scriptBox = qs('#voiceScriptText');
    if (scriptBox) {
      scriptBox.addEventListener('input', () => {
        const p = getPrefs();
        p.lastManualScript = scriptBox.value || '';
        p.prefersEditingScript = true;
        savePrefs(p);
      });
    }
    qsa('.js-round-tab,.js-group-tab').forEach(btn => btn.addEventListener('click', () => setTimeout(() => { if (typeof window.refreshPlayoffVoiceScript === 'function') window.refreshPlayoffVoiceScript();
        if (typeof window.refreshSwissVoiceScript === 'function') window.refreshSwissVoiceScript(); }, 50)));
    setTimeout(() => { if (typeof window.refreshPlayoffVoiceScript === 'function') window.refreshPlayoffVoiceScript();
        if (typeof window.refreshSwissVoiceScript === 'function') window.refreshSwissVoiceScript(); }, 100);
  });
})();
