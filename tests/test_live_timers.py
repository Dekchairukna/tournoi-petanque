from unittest.mock import patch
from flask import g
from test_live_board import LiveBoardTests
from models import db, User, Event, LiveEventTimer


class LiveTimerTests(LiveBoardTests):
    def command(self, action, ids=None, seconds=60, versions=None):
        ids = ids or [self.event_id]
        if versions is None:
            versions = {str(i): db.session.get(LiveEventTimer, i).version if db.session.get(LiveEventTimer, i) else 0 for i in ids}
        g.pop('_login_user', None)
        return self.client.post('/live/timers/command', json=dict(action=action, event_ids=ids, seconds=seconds, versions=versions))

    def state(self):
        g.pop('_login_user', None)
        return self.client.get(f'/api/public/live-timers?events={self.event_id}').get_json()['timers'][0]

    def test_countdown_pause_resume_reset_and_expiry(self):
        with patch('live_timers.current_time', return_value=1000):
            self.assertEqual(self.command('start').status_code, 200)
        with patch('live_timers.current_time', return_value=1010):
            self.assertEqual(self.state()['remaining'], 50)
            self.assertEqual(self.command('pause').status_code, 200)
        db.session.remove()  # A fresh session / another display reads persisted state.
        with patch('live_timers.current_time', return_value=2000):
            self.assertEqual(self.state()['remaining'], 50)
            self.assertFalse(self.state()['running'])
            self.assertEqual(self.command('resume').status_code, 200)
        with patch('live_timers.current_time', return_value=2051):
            self.assertEqual(self.state()['remaining'], 0)
            self.assertFalse(self.state()['running'])
            self.command('reset')
            self.assertEqual(self.state()['remaining'], 60)
            self.assertFalse(self.state()['running'])

    def test_bulk_start_same_deadline_and_individual_pause(self):
        event = Event(name='Second', creator_id=self.match.event.creator_id)
        db.session.add(event); db.session.commit()
        with patch('live_timers.current_time', return_value=1000):
            self.assertEqual(self.command('start', [self.event_id, event.id], 90).status_code, 200)
            self.assertEqual(db.session.get(LiveEventTimer, event.id).end_at, db.session.get(LiveEventTimer, self.event_id).end_at)
            self.command('pause')
            self.assertIsNone(db.session.get(LiveEventTimer, self.event_id).end_at)
            self.assertEqual(db.session.get(LiveEventTimer, event.id).end_at, 1090)

    def test_stale_and_invalid_commands_do_not_change_clock(self):
        self.command('start')
        self.assertEqual(self.command('pause', versions={str(self.event_id): 0}).status_code, 409)
        for seconds in [0, -1, 86401, True, 2.5, '60']:
            self.assertEqual(self.command('set', seconds=seconds).status_code, 400)
        self.assertTrue(self.state()['running'])

    def test_public_read_and_no_public_or_cross_owner_control(self):
        self.client.get('/logout')
        self.assertEqual(self.client.get(f'/api/public/live-timers?events={self.event_id}').status_code, 200)
        self.assertIn(self.command('start').status_code, [302, 401])
        other = User(username='other', role='admin', password_hash='unused')
        db.session.add(other); db.session.flush()
        own = Event(name='Own', creator_id=other.id)
        db.session.add(own); db.session.commit()
        with self.client.session_transaction() as session:
            session['_user_id'] = str(other.id); session['_fresh'] = True
        response = self.command('start', [own.id, self.event_id])
        self.assertEqual(response.status_code, 403, response.location)
        self.assertEqual(LiveEventTimer.query.count(), 0)
