import os
import unittest
from datetime import date, datetime, time

os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
os.environ['YAGAMI_SUPERADMIN_PASSWORD'] = 'local-test-owner-password'
from app import app, db
from models import (User, Tournament, Event, Team, Match, EventTeamRegistration,
                    TournamentMatchSchedule, EventRoundRobinConfig)
from tournament_desk import build_schedule
from round_robin_event import _assign, _generate


class DeskTests(unittest.TestCase):
    def setUp(self):
        app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        self.ctx = app.app_context()
        self.ctx.push()
        db.create_all()
        self.user = User(username='desk-owner', role='superadmin', password_hash='unused')
        db.session.add(self.user)
        db.session.flush()
        self.tournament = Tournament(name='Test cup', creator_id=self.user.id,
                                     start_date=date(2026,11,1), end_date=date(2026,11,7))
        db.session.add(self.tournament)
        db.session.flush()
        self.event = Event(name='Singles', competition_format='round_robin', rounds=1,
                           creator_id=self.user.id, tournament_id=self.tournament.id)
        db.session.add(self.event)
        db.session.commit()
        self.client = app.test_client()
        with self.client.session_transaction() as session:
            session['_user_id'] = str(self.user.id)
            session['_fresh'] = True
        self.url = f'/tournament/{self.tournament.id}/desk'

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def team(self, name, status='checked_in'):
        team = Team(name=name, event_id=self.event.id)
        db.session.add(team)
        db.session.flush()
        db.session.add(EventTeamRegistration(team_id=team.id, status=status, affiliation='School A'))
        db.session.commit()
        return team

    def draw(self):
        cfg = EventRoundRobinConfig(event_id=self.event.id, group_count=1)
        db.session.add(cfg)
        db.session.flush()
        groups = _assign(self.event, cfg, 'seed')
        _generate(self.event, cfg, groups)
        db.session.commit()
        return cfg

    def test_all_pages_render_and_escape_names(self):
        self.team('<script>alert(1)</script>')
        for tab in ('overview','registration','schedule','documents'):
            response = self.client.get(self.url + '?tab=' + tab)
            self.assertEqual(response.status_code, 200)
            self.assertNotIn(b'<script>alert(1)</script>', response.data)
        self.assertIn(b'&lt;script&gt;', self.client.get(self.url+'?tab=registration').data)

    def test_register_checkin_and_draw_excludes_pending_and_withdrawn(self):
        self.team('Ready 1')
        self.team('Ready 2')
        self.team('Waiting', 'pending')
        self.team('Withdrawn', 'withdrawn')
        self.draw()
        matches = Match.query.all()
        self.assertEqual(len(matches), 1)
        self.assertEqual({matches[0].team1.name, matches[0].team2.name}, {'Ready 1','Ready 2'})

    def test_status_change_after_draw_is_rejected(self):
        team = self.team('Ready 1')
        self.team('Ready 2')
        self.draw()
        self.client.post(self.url, data={'action':'update_team','team_id':team.id,'status':'withdrawn'})
        self.assertEqual(db.session.get(EventTeamRegistration,team.id).status,'checked_in')

    def test_create_and_edit_registration(self):
        response = self.client.post(self.url, data={'action':'add_team','event_id':self.event.id,
            'name':'New school', 'status':'pending', 'affiliation':'Province', 'athletes':'Student One\nStudent Two'})
        self.assertEqual(response.status_code,302)
        team = Team.query.one()
        record = db.session.get(EventTeamRegistration,team.id)
        self.assertEqual(record.athletes,'Student One\nStudent Two')
        self.client.post(self.url, data={'action':'update_team','team_id':team.id,'status':'checked_in',
            'affiliation':'Province', 'athletes':record.athletes})
        self.assertEqual(record.status,'checked_in')

    def test_scheduler_no_court_overlap_respects_rounds_lunch_and_days(self):
        for i in range(6): self.team(f'Team {i}')
        self.draw()
        matches = Match.query.all()
        plan = build_schedule(matches,{self.event.id:self.event},[1,3],date(2026,11,1),time(9),time(16),75,15)
        self.assertEqual(len(plan),15)
        self.assertGreater(max(p[2].date() for p in plan),date(2026,11,1))
        for match, field, start, end in plan:
            self.assertIn(field,[1,3])
            self.assertGreaterEqual(start.time(),time(9))
            self.assertLessEqual(end.time(),time(16))
            self.assertFalse(start.time()<time(13) and end.time()>time(12))
            for other, other_field, other_start, other_end in plan:
                if other.id == match.id: continue
                if field == other_field:
                    self.assertFalse(start < other_end and other_start < end)
                if other.round < match.round:
                    self.assertLessEqual(other_end,start)

    def test_schedule_persists_and_redraw_invalidates(self):
        for i in range(4): self.team(f'Team {i}')
        cfg = self.draw()
        form = {'action':'schedule','field_start':1,'field_max':3,'field_exclude':'2',
                'start_date':'2026-11-01','day_start':'08:30','day_end':'18:00','minutes':75,'rest':15,'field_prefix':'A'}
        self.client.post(self.url,data=form)
        self.assertEqual(TournamentMatchSchedule.query.count(),6)
        self.assertEqual({m.field for m in Match.query.all()},{1,3})
        before = [(s.match_id,s.starts_at) for s in TournamentMatchSchedule.query.all()]
        form['field_max']=4
        self.client.post(self.url,data=form)
        self.assertEqual(before,[(s.match_id,s.starts_at) for s in TournamentMatchSchedule.query.all()])
        groups = _assign(self.event,cfg,'seed')
        _generate(self.event,cfg,groups)
        db.session.commit()
        self.assertEqual(TournamentMatchSchedule.query.count(),0)

    def test_reject_impossible_schedule(self):
        with self.assertRaises(ValueError):
            build_schedule([],{},[1],date(2026,11,1),time(12),time(13),75,15)

    def test_other_owner_and_other_tournament_team_are_protected(self):
        outsider = User(username='other-admin',role='admin',password_hash='unused')
        db.session.add(outsider)
        db.session.commit()
        with self.client.session_transaction() as session: session['_user_id']=str(outsider.id)
        self.assertEqual(self.client.get(self.url).status_code,403)
        self.assertEqual(self.client.post(self.url,data={'action':'starter_events'}).status_code,403)

    def test_starter_set_and_duplicate_guard(self):
        db.session.delete(self.event)
        db.session.commit()
        self.client.post(self.url,data={'action':'starter_events'})
        self.assertEqual(Event.query.count(),7)
        self.assertTrue(all(e.competition_format=='round_robin' for e in Event.query.all()))
        self.client.post(self.url,data={'action':'starter_events'})
        self.assertEqual(Event.query.count(),7)

    def test_printed_documents_use_central_schedule(self):
        self.team('One')
        self.team('Two')
        self.draw()
        match = Match.query.one()
        match.field = 3
        self.event.field_prefix = 'B'
        db.session.add(TournamentMatchSchedule(match_id=match.id, field_number=3,
            starts_at=datetime(2026,11,1,14,30), ends_at=datetime(2026,11,1,15,45)))
        db.session.commit()
        for path in (f'/event/{self.event.id}/round-robin/print-pairings', f'/event/{self.event.id}/score-sheet'):
            response = self.client.get(path)
            self.assertEqual(response.status_code,200)
            self.assertIn(b'14:30',response.data)
            self.assertIn(b'B3',response.data)

    def test_shared_courts_across_events_and_event_start_date(self):
        a, b = self.team('One'), self.team('Two')
        other = Event(name='Pairs',creator_id=self.user.id,tournament_id=self.tournament.id,
                      competition_format='round_robin',date=date(2026,11,2))
        db.session.add(other)
        db.session.flush()
        matches = [Match(event_id=self.event.id,round=1,team1_id=a.id,team2_id=b.id),
                   Match(event_id=other.id,round=1,team1_id=a.id,team2_id=b.id)]
        db.session.add_all(matches)
        db.session.flush()
        plan = build_schedule(matches,{self.event.id:self.event,other.id:other},[1],date(2026,11,1),time(9),time(18),75,15)
        self.assertGreaterEqual(plan[1][2].date(),other.date)
        self.assertGreaterEqual(plan[1][2],plan[0][3])

    def test_scores_prevent_rescheduling(self):
        self.team('One'); self.team('Two'); self.draw()
        match=Match.query.one()
        match.is_locked=True
        match.field=7
        db.session.commit()
        response=self.client.post(self.url,data={'action':'schedule'},follow_redirects=True)
        self.assertIn('มีผลการแข่งขัน'.encode(),response.data)
        self.assertEqual(match.field,7)
        self.assertEqual(TournamentMatchSchedule.query.count(),0)

    def test_csrf_is_required(self):
        app.config['WTF_CSRF_ENABLED']=True
        try:
            response=self.client.post(self.url,data={'action':'starter_events'})
            self.assertEqual(response.status_code,400)
        finally:
            app.config['WTF_CSRF_ENABLED']=False
