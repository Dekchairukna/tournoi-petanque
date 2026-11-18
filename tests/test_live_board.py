"""Run with python -m unittest discover -s tests -p test_live_board.py."""
import os
import unittest
from datetime import date

# Never connect these regression tests to the tournament database.
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
os.environ['YAGAMI_SUPERADMIN_PASSWORD'] = 'isolated-live-board-test'
from app import app, db, limiter
from models import User, Event, Team, Match


class LiveBoardTests(unittest.TestCase):
    def setUp(self):
        app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        limiter.enabled = False
        self.context = app.app_context()
        self.context.push()
        db.drop_all()
        db.create_all()
        user = User(username='board-test', role='superadmin', password_hash='unused')
        db.session.add(user)
        db.session.flush()
        event = Event(name='Board test', creator_id=user.id, date=date.today(), rounds=1, current_round=1)
        db.session.add(event)
        db.session.flush()
        a, b = Team(name='Red', event_id=event.id), Team(name='Blue', event_id=event.id)
        db.session.add_all([a, b])
        db.session.flush()
        self.match = Match(event_id=event.id, round=1, field=1, team1_id=a.id, team2_id=b.id, team1_score=5, team2_score=3, is_locked=False)
        db.session.add(self.match)
        db.session.commit()
        self.client = app.test_client()
        with self.client.session_transaction() as session:
            session['_user_id'] = str(user.id)
            session['_fresh'] = True
        self.event_id = event.id

    def tearDown(self):
        db.session.remove()
        self.context.pop()

    def board(self):
        response = self.client.get(f'/api/public/live-board?events={self.event_id}')
        self.assertEqual(response.status_code, 200)
        return response.get_json()['matches']

    def test_main_score_appears_without_lock_and_without_stale_cache(self):
        self.assertEqual(self.board()[0]['score1'], 5)
        response = self.client.post(f'/event/{self.event_id}/match/{self.match.id}', json={'team_a_score': 7, 'team_b_score': 4})
        self.assertEqual(response.status_code, 200)
        card = self.board()[0]
        self.assertEqual((card['team1'], card['team2'], card['score1'], card['score2']), ('Red', 'Blue', 7, 4))
        self.assertFalse(self.match.is_locked)

    def test_scorecard_pending_scores_include_zero_before_approval(self):
        response = self.client.post(f'/event/{self.event_id}/match/{self.match.id}/scorecard/autosave', json={'team1_score': 0, 'team2_score': 8})
        self.assertEqual(response.status_code, 200)
        card = self.board()[0]
        self.assertEqual((card['score1'], card['score2']), (0, 8))
        self.assertEqual((self.match.team1_score, self.match.team2_score), (5, 3))
        self.assertFalse(self.match.is_locked)
        self.match.pending_team1_score = self.match.pending_team2_score = None
        db.session.commit()
        self.assertEqual(self.board()[0]['score1'], 5)

    def test_undrawn_event_visible_then_transitions_to_matches(self):
        event = Event(name='Waiting draw event', creator_id=self.match.event.creator_id,
                      date=date.today(), rounds=1, current_round=1)
        db.session.add(event); db.session.commit()
        self.assertIn(b'Waiting draw event', self.client.get('/live').data)
        url=f'/api/public/live-board?events={event.id}'
        payload=self.client.get(url).get_json()
        self.assertEqual(payload['events'][0]['status'], 'awaiting_draw')
        self.assertEqual(payload['matches'], [])
        a=Team(name='A',event_id=event.id); b=Team(name='B',event_id=event.id)
        db.session.add_all([a,b]); db.session.flush()
        db.session.add(Match(event_id=event.id,round=1,field=1,team1_id=a.id,team2_id=b.id,is_locked=False))
        db.session.commit()
        payload=self.client.get(url).get_json()
        self.assertNotEqual(payload['events'][0].get('status'), 'awaiting_draw')
        self.assertEqual(len(payload['matches']),1)

    def test_removed_entry_and_remaining_pages(self):
        for path in ['/live-scoring', '/live-scoring/event/1/round/1/matches']:
            self.assertEqual(self.client.get(path).status_code, 404)
        self.assertEqual(self.client.post('/live-scoring/match/1/score', json={}).status_code, 404)
        for path in ['/', '/live', '/live-board', '/multi-score']:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200, path)
            self.assertNotIn(b'/live-scoring', response.data)


    def test_board_page_settings_and_controls_follow_permissions(self):
        url = f'/live-board?events={self.event_id}'
        html = self.client.get(url).get_data(as_text=True)
        # admin who manages the event gets the timer dialog and their event id
        self.assertIn('id="timerDialog"', html)
        self.assertIn(f'controllable: [{self.event_id}]', html)
        self.assertIn('data-theme="light"', html)
        self.assertIn('name="csrf-token"', html)
        # viewers (not logged in) only see the clock
        from flask import g
        g.pop('_login_user', None)  # the shared test app context caches the signed-in user
        viewer = app.test_client()
        html = viewer.get(url).get_data(as_text=True)
        self.assertNotIn('id="timerDialog"', html)
        self.assertNotIn('id="quickTimer"', html)
        self.assertIn('controllable: []', html)

    def test_board_style_comes_from_link_and_bad_values_fall_back(self):
        html = self.client.get(f'/live-board?events={self.event_id}&theme=dark&per_page=12&font=l&lang=en').get_data(as_text=True)
        self.assertIn('data-theme="dark"', html)
        self.assertIn('data-font="l"', html)
        self.assertIn('"per_page": 12', html)
        self.assertIn('"lang": "en"', html)
        html = self.client.get(f'/live-board?events={self.event_id}&theme=neon&per_page=7&font=huge&lang=xx').get_data(as_text=True)
        self.assertIn('data-theme="light"', html)
        self.assertIn('data-font="m"', html)
        self.assertIn('"per_page": 24', html)
        self.assertIn('"lang": "th"', html)

    def test_kku_event_defaults_to_event_theme(self):
        import kku2026
        draw = kku2026.ensure_event(self.match.event.creator_id)
        html = self.client.get(f'/live-board?events={draw.event_id}').get_data(as_text=True)
        self.assertIn('data-theme="event"', html)
        self.assertIn('data-kku="true"', html)
        self.assertIn('"lang": "en"', html)

    def test_timer_command_from_board_requires_manager(self):
        other = User(username='other-admin', role='admin', password_hash='unused')
        db.session.add(other); db.session.commit()
        with self.client.session_transaction() as session:
            session['_user_id'] = str(other.id)
        from flask import g
        g.pop('_login_user', None)
        html = self.client.get(f'/live-board?events={self.event_id}').get_data(as_text=True)
        self.assertNotIn('id="timerDialog"', html)
        response = self.client.post('/live/timers/command', json={'event_ids': [self.event_id], 'action': 'start',
                                                                  'seconds': 60, 'versions': {str(self.event_id): 0}})
        self.assertEqual(response.status_code, 403)


if __name__ == '__main__':
    unittest.main()
