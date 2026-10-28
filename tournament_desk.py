"""Tournament operations desk for the existing Event engine."""
from collections import defaultdict
from datetime import datetime, time, timedelta

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from models import (db, Tournament, Event, Team, Match, EventTeamRegistration,
                    TournamentMatchSchedule, EventRoundRobinMember, EventRoundRobinConfig)

bp = Blueprint('tournament_desk', __name__)
STATUSES = {'pending': 'รอรายงานตัว', 'checked_in': 'รายงานตัวแล้ว', 'withdrawn': 'ถอนทีม'}
FORMATS = {'swiss': 'Swiss', 'round_robin': 'พบกันหมด', 'knockout': 'แพ้คัดออก', 'double_knockout': 'แพ้สองครั้งคัดออก'}


def _tournament(tournament_id):
    tournament = db.get_or_404(Tournament, tournament_id)
    if current_user.role not in {'admin', 'mainadmin', 'superadmin'}:
        abort(403)
    if not (current_user.id == tournament.creator_id or current_user.role in {'mainadmin', 'superadmin'}
            or current_user.has_permission('access_other_events')):
        abort(403)
    return tournament


def _text(name, limit, required=False):
    value = (request.form.get(name) or '').strip()
    if required and not value:
        raise ValueError('กรุณากรอกข้อมูลที่จำเป็นให้ครบ')
    if len(value) > limit:
        raise ValueError(f'ข้อมูลยาวเกิน {limit} ตัวอักษร')
    return value


def _roster_locked(event_id):
    return (Match.query.filter_by(event_id=event_id).first() is not None
            or db.session.query(EventRoundRobinMember).join(Team, Team.id == EventRoundRobinMember.team_id)
            .filter(Team.event_id == event_id).first() is not None)


def _fields(start, end, excluded):
    if not 1 <= start <= end <= 999:
        raise ValueError('ช่วงสนามต้องอยู่ระหว่าง 1–999 และสนามสุดท้ายต้องไม่น้อยกว่าสนามแรก')
    try:
        omit = {int(v.strip()) for v in excluded.split(',') if v.strip()}
    except ValueError:
        raise ValueError('สนามที่เว้นต้องเป็นตัวเลขคั่นด้วยเครื่องหมายจุลภาค')
    fields = [n for n in range(start, end + 1) if n not in omit]
    if not fields:
        raise ValueError('ต้องเหลือสนามให้ใช้อย่างน้อย 1 สนาม')
    return fields


def build_schedule(matches, events, fields, start_date, day_start, day_end, minutes, rest):
    """Allocate shared courts, keep event rounds ordered, and carry overflow to next day.

    A fixed 12:00–13:00 lunch break is included. No athlete identity inference is made.
    """
    if not 5 <= minutes <= 240 or not 0 <= rest <= 120:
        raise ValueError('เวลาแข่งต้องเป็น 5–240 นาที และเวลาพัก 0–120 นาที')
    if day_start >= day_end:
        raise ValueError('เวลาสิ้นสุดต้องอยู่หลังเวลาเริ่ม')
    anchor = datetime.combine(start_date, day_start)
    duration = timedelta(minutes=minutes)
    gap = timedelta(minutes=rest)
    lunch_start, lunch_end = time(12), time(13)
    # At least one session on a day must fit the complete match.
    windows = [(day_start, min(day_end, lunch_start)), (max(day_start, lunch_end), day_end)]
    if not any(a < b and datetime.combine(start_date, b) - datetime.combine(start_date, a) >= duration for a, b in windows):
        raise ValueError('เวลาแข่งยาวเกินช่วงเปิดสนาม (พักกลางวัน 12:00–13:00)')

    def fit(value):
        while True:
            value = max(value, datetime.combine(value.date(), day_start))
            end = value + duration
            lunch_a = datetime.combine(value.date(), lunch_start)
            lunch_b = datetime.combine(value.date(), lunch_end)
            if value < lunch_b and end > lunch_a:
                value = lunch_b
                continue
            if end > datetime.combine(value.date(), day_end):
                value = datetime.combine(value.date() + timedelta(days=1), day_start)
                continue
            return value

    available = {field: anchor for field in fields}
    team_ready = {}
    round_done = {}
    result = []
    ordered = sorted(matches, key=lambda m: (max(events[m.event_id].date or start_date, start_date), m.round, m.event_id, m.id))
    for match in ordered:
        event = events[match.event_id]
        earliest = max(anchor, datetime.combine(max(event.date or start_date, start_date), day_start))
        previous = [end for (eid, rnd), end in round_done.items() if eid == event.id and rnd < match.round]
        earliest = max([earliest, *previous, team_ready.get(match.team1_id, anchor), team_ready.get(match.team2_id, anchor)])
        starts, field = min((fit(max(earliest, value)), field) for field, value in available.items())
        ends = starts + duration
        available[field] = ends + gap
        team_ready[match.team1_id] = ends + gap
        team_ready[match.team2_id] = ends + gap
        key = (event.id, match.round)
        round_done[key] = max(round_done.get(key, anchor), ends + gap)
        result.append((match, field, starts, ends))
    return result


@bp.route('/tournament/<int:tournament_id>/desk', methods=['GET', 'POST'])
@login_required
def desk(tournament_id):
    tournament = _tournament(tournament_id)
    events = Event.query.filter_by(tournament_id=tournament.id).order_by(Event.date, Event.id).all()
    event_map = {e.id: e for e in events}
    tab = request.args.get('tab', 'overview')
    if tab not in {'overview', 'registration', 'schedule', 'documents'}:
        tab = 'overview'
    if request.method == 'POST':
        action = request.form.get('action')
        try:
            if action == 'starter_events':
                if events:
                    raise ValueError('ชุดเริ่มต้นใช้ได้เฉพาะงานที่ยังไม่มีอีเวนต์')
                if not current_user.has_permission('create_non_swiss_event'):
                    abort(403)
                for category, sex in [('เดี่ยว','ชาย'), ('เดี่ยว','หญิง'), ('คู่ผสม','ผสม'), ('คู่','ชาย'), ('คู่','หญิง'), ('ทีม','ชาย'), ('ทีม','หญิง')]:
                    db.session.add(Event(name=category + (sex if category != 'คู่ผสม' else ''),
                        category=category, sex=sex, age_group='อายุไม่เกิน 18 ปี', competition_format='round_robin', rounds=1,
                        tournament_id=tournament.id, creator_id=current_user.id, date=tournament.start_date,
                        location=tournament.location, logo_filename='[]'))
                flash('สร้าง 7 ประเภทระบบพบกันหมดแล้ว แก้ไขรุ่นอายุและวันที่ของแต่ละประเภทได้ในหน้าอีเวนต์', 'success')
            elif action in {'add_team', 'update_team'}:
                tab = 'registration'
                if action == 'add_team':
                    event = event_map.get(request.form.get('event_id', type=int))
                    if not event:
                        abort(404)
                    if _roster_locked(event.id):
                        raise ValueError('จับสลากแล้ว กรุณาจัดการรายชื่อและล้างตารางในหน้าอีเวนต์ก่อนเพิ่มทีม')
                    name = _text('name', 100, True)
                    if any(t.name.strip().casefold() == name.casefold() for t in event.teams):
                        raise ValueError('มีชื่อทีมนี้ในอีเวนต์แล้ว')
                    team = Team(name=name, event_id=event.id)
                    db.session.add(team)
                    db.session.flush()
                else:
                    team = db.get_or_404(Team, request.form.get('team_id', type=int))
                    if team.event_id not in event_map:
                        abort(404)
                record = db.session.get(EventTeamRegistration, team.id)
                status = request.form.get('status')
                if status not in STATUSES:
                    raise ValueError('กรุณาเลือกสถานะรายงานตัว')
                if _roster_locked(team.event_id) and status != (record.status if record else 'checked_in'):
                    raise ValueError('จับสลากแล้ว เปลี่ยนสถานะไม่ได้ กรุณาจัดการตารางในหน้าอีเวนต์ก่อน')
                if not record:
                    record = EventTeamRegistration(team_id=team.id)
                    db.session.add(record)
                record.affiliation = _text('affiliation', 180)
                record.athletes = _text('athletes', 2000)
                record.status = status
                flash('บันทึกทะเบียนทีมแล้ว', 'success')
            elif action == 'schedule':
                tab = 'schedule'
                matches = Match.query.filter(Match.event_id.in_(event_map), Match.team2_id.isnot(None)).all()
                if not matches:
                    raise ValueError('ยังไม่มีคู่แข่งขัน กรุณาจับสลากในหน้าอีเวนต์ก่อน')
                if any(event_map[m.event_id].competition_format != 'round_robin' for m in matches):
                    raise ValueError('รุ่นทดลองจัดตารางกลางสำหรับงานที่มีคู่แข่งขัน Round Robin เท่านั้น')
                if any(m.is_locked or m.pending_is_submitted for m in matches):
                    raise ValueError('มีผลการแข่งขันหรือคะแนนรอตรวจแล้ว ไม่สามารถจัดเวลาและสนามใหม่ได้')
                if TournamentMatchSchedule.query.filter(TournamentMatchSchedule.match_id.in_([m.id for m in matches])).first() and request.form.get('replace') != '1':
                    raise ValueError('มีตารางกลางแล้ว กรุณายืนยันแทนที่ตารางเดิม')
                start = int(request.form.get('field_start', '1'))
                end = int(request.form.get('field_max', '8'))
                excluded = _text('field_exclude', 255)
                fields = _fields(start, end, excluded)
                start_date = datetime.strptime(request.form['start_date'], '%Y-%m-%d').date()
                day_start = datetime.strptime(request.form['day_start'], '%H:%M').time()
                day_end = datetime.strptime(request.form['day_end'], '%H:%M').time()
                plan = build_schedule(matches, event_map, fields, start_date, day_start, day_end,
                                      int(request.form['minutes']), int(request.form['rest']))
                if tournament.end_date and any(ends.date() > tournament.end_date for _, _, _, ends in plan):
                    raise ValueError('ตารางเกินวันสิ้นสุดงาน กรุณาเพิ่มสนามหรือปรับเวลา/วันที่งานก่อน')
                tournament.field_start, tournament.field_max, tournament.field_exclude = start, end, excluded
                tournament.field_prefix = _text('field_prefix', 10)
                for event in events:
                    event.field_prefix = tournament.field_prefix
                    cfg = EventRoundRobinConfig.query.filter_by(event_id=event.id).first()
                    if cfg:
                        cfg.first_time = day_start.strftime('%H:%M')
                        cfg.match_minutes = int(request.form['minutes'])
                        cfg.break_minutes = int(request.form['rest'])
                for match, field, starts, ends in plan:
                    record = db.session.get(TournamentMatchSchedule, match.id)
                    if not record:
                        record = TournamentMatchSchedule(match_id=match.id)
                        db.session.add(record)
                    record.starts_at, record.ends_at, record.field_number = starts, ends, field
                    match.field = field
                flash(f'จัดตารางกลาง {len(plan)} คู่แล้ว สนามไม่ซ้อนเวลาและเว้นพักกลางวัน', 'success')
            else:
                abort(400)
            db.session.commit()
        except (ValueError, KeyError) as exc:
            db.session.rollback()
            flash(str(exc) if isinstance(exc, ValueError) else 'กรุณากรอกข้อมูลให้ครบ', 'danger')
        return redirect(url_for('.desk', tournament_id=tournament.id, tab=tab))

    teams = Team.query.filter(Team.event_id.in_(event_map)).order_by(Team.name, Team.id).all()
    registrations = {r.team_id: r for r in EventTeamRegistration.query.filter(EventTeamRegistration.team_id.in_([t.id for t in teams])).all()}
    matches = Match.query.filter(Match.event_id.in_(event_map), Match.team2_id.isnot(None)).all()
    schedules = {s.match_id: s for s in TournamentMatchSchedule.query.filter(TournamentMatchSchedule.match_id.in_([m.id for m in matches])).all()}
    rows = sorted(matches, key=lambda m: (schedules[m.id].starts_at if m.id in schedules else datetime.max, m.field or 0, m.id))
    counts = {e.id: {'teams': 0, 'checked_in': 0, 'matches': 0, 'locked': 0} for e in events}
    matrix = defaultdict(lambda: defaultdict(list))
    for team in teams:
        record = registrations.get(team.id)
        counts[team.event_id]['teams'] += 1
        counts[team.event_id]['checked_in'] += int(record is not None and record.status == 'checked_in')
        matrix[record.affiliation if record and record.affiliation else team.name][team.event_id].append(team)
    for match in matches:
        counts[match.event_id]['matches'] += 1
        counts[match.event_id]['locked'] += int(match.is_locked)
    return render_template('tournament_desk.html', tournament=tournament, events=events, event_map=event_map,
        teams=teams, registrations=registrations, statuses=STATUSES, formats=FORMATS, tab=tab, counts=counts,
        matrix=sorted(matrix.items()), matches=rows, schedules=schedules,
        checked_in=sum(c['checked_in'] for c in counts.values()), locked=sum(c['locked'] for c in counts.values()),
        selected_events=','.join(str(e.id) for e in events), today=datetime.now().date(),
        demo=current_app.config.get('DESK_DEMO', False))
