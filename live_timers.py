"""Server-owned countdowns shared by controller and public displays."""
from time import time as current_time
from flask import request, jsonify
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError
from models import db, Event, LiveEventTimer


def snapshot(event, timer, now):
    remaining = max(0, timer.end_at - now) if timer and timer.end_at is not None else (timer.remaining if timer else 3600)
    return dict(event_id=event.id, name=event.name, duration=timer.duration if timer else 3600,
                remaining=remaining, running=bool(timer and timer.end_at is not None and remaining > 0),
                version=timer.version if timer else 0)


def register_live_timers(app, can_manage):
    @app.get('/api/public/live-timers')
    def public_live_timers():
        raw = (request.args.get('events') or '').split(',')
        if len(raw) > 100 or any(x and not x.isdigit() for x in raw):
            return jsonify(ok=False, message='อีเวนต์ไม่ถูกต้อง'), 400
        ids = list({int(x) for x in raw if x})
        events = Event.query.filter(Event.id.in_(ids)).order_by(Event.id).all()
        timers = {t.event_id: t for t in LiveEventTimer.query.filter(LiveEventTimer.event_id.in_(ids)).all()}
        now = current_time()
        response = jsonify(ok=True, timers=[snapshot(e, timers.get(e.id), now) for e in events])
        response.headers['Cache-Control'] = 'no-store'
        return response

    @app.post('/live/timers/command')
    @login_required
    def live_timer_command():
        data = request.get_json(silent=True) or {}
        if not isinstance(data, dict):
            return jsonify(ok=False, message='คำสั่งเวลาไม่ถูกต้อง'), 400
        ids, action, versions = data.get('event_ids'), data.get('action'), data.get('versions')
        if (not isinstance(ids, list) or not 1 <= len(ids) <= 100
                or any(type(i) is not int or i <= 0 for i in ids)
                or action not in {'set', 'start', 'pause', 'resume', 'reset'}
                or not isinstance(versions, dict)):
            return jsonify(ok=False, message='คำสั่งเวลาไม่ถูกต้อง'), 400
        ids = sorted(set(ids))
        duration = data.get('seconds')
        if action in {'set', 'start'} and (type(duration) is not int or not 1 <= duration <= 86400):
            return jsonify(ok=False, message='ตั้งเวลาได้ตั้งแต่ 1 วินาที ถึง 24 ชั่วโมง'), 400
        events = Event.query.filter(Event.id.in_(ids)).order_by(Event.id).all()
        if len(events) != len(ids):
            return jsonify(ok=False, message='ไม่พบอีเวนต์'), 404
        if (current_user.role not in {'admin', 'mainadmin', 'superadmin'}
                or any(not can_manage(e) for e in events)):
            return jsonify(ok=False, message='คุณไม่มีสิทธิ์ควบคุมเวลาอีเวนต์นี้'), 403
        timers = {t.event_id: t for t in LiveEventTimer.query.filter(LiveEventTimer.event_id.in_(ids)).with_for_update().all()}
        # One timestamp and transaction: a bulk start shares the exact deadline.
        now = current_time()
        for e in events:
            timer = timers.get(e.id)
            expected = versions.get(str(e.id))
            if type(expected) is not int or expected != (timer.version if timer else 0):
                db.session.rollback()
                return jsonify(ok=False, message='เวลาถูกเปลี่ยนจากอีกหน้าจอแล้ว กรุณาตรวจเวลาแล้วกดใหม่'), 409
            if timer is None:
                timer = LiveEventTimer(event_id=e.id, duration=3600, remaining=3600)
                db.session.add(timer)
                timers[e.id] = timer
            left = max(0, timer.end_at - now) if timer.end_at is not None else timer.remaining
            if action in {'set', 'start'}:
                timer.duration = duration
                timer.remaining = duration
                timer.end_at = now + duration if action == 'start' else None
            elif action == 'pause':
                timer.remaining, timer.end_at = left, None
            elif action == 'resume':
                if timer.end_at is None and left > 0:
                    timer.end_at = now + left
            elif action == 'reset':
                timer.remaining, timer.end_at = timer.duration, None
        try:
            db.session.commit()
        except (IntegrityError, StaleDataError):
            db.session.rollback()
            return jsonify(ok=False, message='มีคำสั่งเวลาอื่นเข้ามาพร้อมกัน กรุณาตรวจเวลาแล้วกดใหม่'), 409
        return jsonify(ok=True, timers=[snapshot(e, timers[e.id], current_time()) for e in events])
