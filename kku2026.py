"""Roster and editable external Swiss draw for KKU 2026."""
import json
from datetime import date
from pathlib import Path
from flask import request, render_template, redirect, url_for, flash, abort
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError
from models import db, Event, Team, Match, KkuSwissDraw

COUNTRIES = json.loads((Path(__file__).parent / 'data/kku2026_countries.json').read_text())
PRESET = 'kku2026-world-championships'


def ensure_event(owner_id):
    existing = KkuSwissDraw.query.filter_by(preset_key=PRESET).first()
    if existing:
        return existing
    event = Event(name='KKU 2026 World Championships', location='Khon Kaen University, Thailand',
                  date=date(2026, 11, 20), competition_format='swiss', rounds=5, current_round=1,
                  category='World Championships', creator_id=owner_id, field_max=24)
    db.session.add(event); db.session.flush()
    entries = {}
    for country in COUNTRIES:
        team = Team(name=f"{country['name']} ({country['code']})", event_id=event.id)
        db.session.add(team); db.session.flush()
        entries[country['code']] = dict(team_id=team.id, number=None)
    draw = KkuSwissDraw(preset_key=PRESET, event_id=event.id, entries_json=json.dumps(entries))
    db.session.add(draw)
    db.session.commit()
    return draw


def validate_slots(slots, complete=False):
    if not isinstance(slots, list) or len(slots) != 48:
        raise ValueError('ต้องมีช่องประเทศ 48 ช่อง')
    valid = {c['code'] for c in COUNTRIES}
    seen = set()
    for code in slots:
        if not isinstance(code, str) or (code and code not in valid):
            raise ValueError('พบประเทศที่ไม่อยู่ในรายชื่อ')
        if code and code in seen:
            raise ValueError(f'เลือกประเทศ {code} ซ้ำ กรุณาตรวจคู่แข่งขัน')
        if code: seen.add(code)
    if complete and len(seen) != 48:
        raise ValueError(f'เลือกประเทศให้ครบก่อนยืนยัน ขณะนี้ {len(seen)}/48 ประเทศ')
    return slots


def slots_key(rnd):
    # Round 1 keeps the original key so existing drafts stay intact.
    return '__slots' if rnd == 1 else f'__slots_r{rnd}'


def initial_slots(entries, matches, rnd=1):
    key = slots_key(rnd)
    if key in entries:
        return entries[key]
    codes = {e['team_id']: c['code'] for c in COUNTRIES if (e := entries.get(c['code']))}
    if matches:
        result = []
        for match in matches:
            result.extend([codes.get(match.team1_id, ''), codes.get(match.team2_id, '')])
        return (result + [''] * 48)[:48]
    if rnd != 1:
        return [''] * 48
    # Preserve previously entered draw numbers without exposing number inputs.
    numbered = {e['number']: c['code'] for c in COUNTRIES
                if (e := entries.get(c['code'])) and e.get('number')}
    order = list(range(1,49))
    if entries.get('__pairing') == 'halves':
        order = [n for pair in zip(range(1,25), range(25,49)) for n in pair]
    return [numbered.get(n,'') for n in order]


def _match_started(m):
    return bool(m.is_locked or m.team1_score or m.team2_score or m.pending_team1_score is not None
                or m.pending_team2_score is not None or m.pending_is_submitted
                or m.team1_signature or m.team2_signature or m.scorer_signature
                or m.score_ends not in (None, '', '[]'))


def _round_matches(event_id, rnd, lock=False):
    q = Match.query.filter_by(event_id=event_id, round=rnd).order_by(Match.id.asc())
    return q.with_for_update().all() if lock else q.all()


def _check_round_open(event_id, rnd):
    """Raise ValueError if round `rnd` may not be (re)drawn or cleared."""
    if Match.query.filter(Match.event_id == event_id, Match.round > rnd).first():
        raise ValueError(f'มีการแข่งขันรอบที่ {rnd + 1} แล้ว ไม่สามารถเปลี่ยนคู่รอบที่ {rnd} ได้ (ล้างรอบถัดไปก่อน)')
    if rnd > 1:
        prev = Match.query.filter_by(event_id=event_id, round=rnd - 1).all()
        if not prev:
            raise ValueError(f'ยังไม่มีคู่รอบที่ {rnd - 1} กรุณาจับสลากรอบที่ {rnd - 1} ก่อน')
        if any(not m.is_locked for m in prev):
            raise ValueError(f'กรุณาล็อกผลรอบที่ {rnd - 1} ให้ครบก่อนจับสลากรอบที่ {rnd}')


def _previous_opponents(event_id, rnd):
    met = set()
    for m in Match.query.filter(Match.event_id == event_id, Match.round < rnd).all():
        if m.team1_id and m.team2_id:
            met.add(frozenset((m.team1_id, m.team2_id)))
    return met


def register_kku2026(app, can_manage):
    @app.route('/kku2026', methods=['GET', 'POST'])
    @app.route('/kku2026/round/<int:rnd>', methods=['GET', 'POST'])
    @login_required
    def kku2026_draw(rnd=1):
        draw = KkuSwissDraw.query.filter_by(preset_key=PRESET).first()
        if draw and not 1 <= rnd <= max(draw.event.rounds or 1, 1):
            abort(404)
        allowed = current_user.role in {'admin','mainadmin','superadmin'} and (draw is None or can_manage(draw.event))
        error = None; slots = None; status = 200
        matches = _round_matches(draw.event_id, rnd) if draw else []
        if request.method == 'POST':
            if not allowed: abort(403)
            action = request.form.get('action')
            try:
                if action == 'create':
                    created = ensure_event(current_user.id)
                    return redirect(url_for('round_matches', event_id=created.event_id, round=1))
                if draw is None: abort(404)
                if action not in {'save','apply','clear'}: raise ValueError('คำสั่งไม่ถูกต้อง')
                if request.form.get('version', type=int) != draw.version:
                    raise ValueError('ข้อมูลเปลี่ยนจากอีกหน้าจอ กรุณาเปิดหน้าล่าสุดก่อนบันทึก')
                entries = json.loads(draw.entries_json)

                if action == 'clear':
                    matches = _round_matches(draw.event_id, rnd, lock=True)
                    if matches:
                        if Match.query.filter(Match.event_id == draw.event_id, Match.round > rnd).first():
                            raise ValueError(f'มีการแข่งขันรอบที่ {rnd + 1} แล้ว ล้างรอบถัดไปก่อน')
                        started = [m for m in matches if _match_started(m)]
                        if started:
                            raise ValueError(f'สนาม {started[0].field} เริ่มบันทึกผลแล้ว ไม่สามารถล้างประกบคู่รอบที่ {rnd} ได้')
                        for m in matches:
                            db.session.delete(m)
                    entries[slots_key(rnd)] = [''] * 48
                    draw.entries_json = json.dumps(entries)
                    draw.version += 1
                    db.session.flush()
                    latest = db.session.query(db.func.max(Match.round)).filter_by(event_id=draw.event_id).scalar()
                    draw.event.current_round = int(latest or 1)
                    db.session.commit()
                    flash(f'ล้างประกบคู่ Round {rnd} แล้ว' + (f' (ลบ {len(matches)} คู่)' if matches else ''), 'success')
                    return redirect(url_for('kku2026_draw', rnd=rnd))

                slots = request.form.getlist('slots')
                validate_slots(slots, complete=action == 'apply')
                rounds = request.form.get('rounds', type=int)
                if rounds is None or not 1 <= rounds <= 20: raise ValueError('จำนวนรอบต้องอยู่ระหว่าง 1–20')
                if rounds < rnd: raise ValueError(f'จำนวนรอบต้องไม่น้อยกว่า {rnd}')
                for c in COUNTRIES:
                    team = db.session.get(Team, entries[c['code']]['team_id'])
                    if not team or team.event_id != draw.event_id:
                        raise ValueError('รายชื่อทีมในอีเวนต์เปลี่ยน กรุณาตรวจรายชื่อก่อน')
                repeats = []
                if action == 'apply':
                    _check_round_open(draw.event_id, rnd)
                    matches = _round_matches(draw.event_id, rnd, lock=True)
                    if matches and len(matches) != 24:
                        raise ValueError(f'คู่แข่งขันเดิมมีจำนวนไม่ตรง 24 คู่ กรุณากดล้างประกบคู่ Round {rnd} ก่อน')
                    met = _previous_opponents(draw.event_id, rnd)
                    for i in range(24):
                        a = entries[slots[2*i]]['team_id']; b = entries[slots[2*i+1]]['team_id']
                        if frozenset((a, b)) in met:
                            repeats.append(f'{slots[2*i]}–{slots[2*i+1]}')
                        if matches:
                            m = matches[i]
                            if (m.team1_id, m.team2_id) == (a,b): continue
                            if _match_started(m):
                                raise ValueError(f'สนาม {m.field} เริ่มบันทึกผลแล้ว ไม่สามารถเปลี่ยนประเทศในคู่นี้ได้')
                            m.team1_id, m.team2_id = a,b
                            m.scorecard_token = None
                        else:
                            db.session.add(Match(event_id=draw.event_id, round=rnd, field=i+1,
                                                 team1_id=a, team2_id=b, is_locked=False))
                    draw.event.current_round = rnd
                entries[slots_key(rnd)] = slots
                draw.entries_json = json.dumps(entries)
                draw.version += 1; draw.event.rounds = rounds
                db.session.commit()
                flash(f'ยืนยันคู่ Round {rnd} แล้ว' if action == 'apply' else 'บันทึกร่างคู่แข่งขันแล้ว', 'success')
                if repeats:
                    flash('คำเตือน: คู่ที่เคยพบกันแล้วในรอบก่อน — ' + ', '.join(repeats), 'warning')
                return redirect(url_for('round_matches', event_id=draw.event_id, round=rnd) if action == 'apply' else url_for('kku2026_draw', rnd=rnd))
            except (ValueError, IntegrityError, StaleDataError) as exc:
                db.session.rollback(); status = 400
                error = str(exc) if isinstance(exc, ValueError) else 'มีการบันทึกพร้อมกัน กรุณาเปิดหน้าล่าสุดแล้วลองอีกครั้ง'
                matches = _round_matches(draw.event_id, rnd) if draw else []
        entries = json.loads(draw.entries_json) if draw else {}
        if slots is None or len(slots) != 48: slots = initial_slots(entries, matches, rnd)
        blocker = None
        if draw:
            try:
                _check_round_open(draw.event_id, rnd)
            except ValueError as exc:
                blocker = str(exc)
        return render_template('kku2026_draw.html', countries=COUNTRIES, draw=draw, slots=slots, rnd=rnd,
                               blocker=blocker, allowed=allowed, error=error, has_matches=bool(matches),
                               fields=[m.field for m in matches] if len(matches)==24 else list(range(1,25))), status


def flag_for_team(name):
    return next((c['flag'] for c in COUNTRIES if name == f"{c['name']} ({c['code']})"), None)
