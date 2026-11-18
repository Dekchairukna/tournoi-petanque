import json
from flask import g
from test_live_board import LiveBoardTests
from kku2026 import ensure_event, COUNTRIES, initial_slots
from models import db, Team, Match


class KkuDrawTests(LiveBoardTests):
    def setUp(self):
        super().setUp()
        self.draw=ensure_event(self.match.event.creator_id)

    def post(self, slots=None, action='save', **extra):
        data={'action':action,'version':self.draw.version,'rounds':5,'slots':slots or ['']*48}
        data.update(extra)
        return self.client.post('/kku2026/round/1',data=data)

    def test_roster_and_round_one_entry(self):
        self.assertEqual(Team.query.filter_by(event_id=self.draw.event_id).count(),48)
        self.assertEqual(ensure_event(self.match.event.creator_id).id,self.draw.id)
        page=self.client.get('/kku2026/round/1')
        self.assertEqual(page.status_code,200)
        self.assertIn(b'data-code="THA"',page.data)
        self.assertNotIn(b'name="number_',page.data)
        response=self.client.get(f'/event/{self.draw.event_id}/round/1')
        self.assertEqual(response.status_code,200)
        self.assertIn('จับสลากแมนนวล'.encode(),response.data)

    def test_partial_replace_clear_duplicate_and_stale(self):
        slots=['ALG','AND']+['']*46
        self.assertEqual(self.post(slots).status_code,302)
        slots[:2]=['AND','ALG']
        self.assertEqual(self.post(slots).status_code,302)
        self.assertEqual(self.post(['ALG','ALG']+['']*46).status_code,400)
        self.assertEqual(json.loads(self.draw.entries_json)['__slots'][:2],['AND','ALG'])
        self.assertEqual(self.post(slots,version=0).status_code,400)
        self.assertEqual(self.post(['NOPE']+['']*47).status_code,400)
        self.assertEqual(self.post(slots,action='apply').status_code,400)
        self.assertEqual(self.post(['']*48).status_code,302)
        self.assertEqual(json.loads(self.draw.entries_json)['__slots'],['']*48)

    def test_exact_pairs_and_edit_before_scoring(self):
        slots=[c['code'] for c in COUNTRIES]
        self.assertEqual(self.post(slots,action='apply').status_code,302)
        matches=Match.query.filter_by(event_id=self.draw.event_id).order_by(Match.field).all()
        self.assertEqual(len(matches),24)
        self.assertEqual(matches[0].team1.name,'ALGERIA (ALG)')
        self.assertEqual(matches[0].team2.name,'Andorra (AND)')
        original_id=matches[0].id
        slots[0],slots[2]=slots[2],slots[0]
        self.assertEqual(self.post(slots,action='apply').status_code,302)
        self.assertEqual(db.session.get(Match,original_id).team1.name,'Argentina (ARG)')
        self.assertEqual(Match.query.filter_by(event_id=self.draw.event_id).count(),24)
        board=self.client.get(f'/api/public/live-board?events={self.draw.event_id}').get_json()
        self.assertEqual(board['matches'][0]['team1_flag'],'kku2026/flags/ARG.png')

    def test_scored_match_cannot_be_reassigned(self):
        slots=[c['code'] for c in COUNTRIES];self.post(slots,action='apply')
        m=Match.query.filter_by(event_id=self.draw.event_id,field=1).one()
        m.team1_score=3;db.session.commit();original=m.team1_id
        slots[0],slots[2]=slots[2],slots[0]
        self.assertEqual(self.post(slots,action='apply').status_code,400)
        self.assertEqual(m.team1_id,original);self.assertEqual(m.team1_score,3)

    def test_legacy_numbers_preserved(self):
        entries=json.loads(self.draw.entries_json)
        entries['ALG']['number']=1;entries['AND']['number']=25;entries['__pairing']='halves'
        self.assertEqual(initial_slots(entries,[])[:2],['ALG','AND'])

    def test_anonymous_cannot_edit(self):
        self.client.get('/logout');g.pop('_login_user',None)
        self.assertEqual(self.post().status_code,302)
        self.assertNotIn('__slots',json.loads(self.draw.entries_json))


class KkuLaterRoundTests(KkuDrawTests):
    def post_round(self, rnd, slots=None, action='save'):
        data={'action':action,'version':self.draw.version,'rounds':5,'slots':slots or ['']*48}
        return self.client.post(f'/kku2026/round/{rnd}',data=data)

    def _apply_round1_and_lock(self):
        slots=[c['code'] for c in COUNTRIES]
        self.assertEqual(self.post(slots,action='apply').status_code,302)
        for m in Match.query.filter_by(event_id=self.draw.event_id,round=1):
            m.is_locked=True
        db.session.commit()
        return slots

    def test_round_two_requires_locked_round_one(self):
        slots=[c['code'] for c in COUNTRIES]
        self.assertEqual(self.post_round(2,slots,'apply').status_code,400)  # no round 1 yet
        self.post(slots,action='apply')
        self.assertEqual(self.post_round(2,slots,'apply').status_code,400)  # round 1 not locked
        self.assertEqual(Match.query.filter_by(event_id=self.draw.event_id,round=2).count(),0)

    def test_round_two_draw_and_clear(self):
        slots=self._apply_round1_and_lock()
        page=self.client.get('/kku2026/round/2')
        self.assertEqual(page.status_code,200)
        self.assertIn('ล้างประกบคู่'.encode(),page.data)
        r2=slots[1:]+slots[:1]
        self.assertEqual(self.post_round(2,r2,'apply').status_code,302)
        self.assertEqual(Match.query.filter_by(event_id=self.draw.event_id,round=2).count(),24)
        self.assertEqual(json.loads(self.draw.entries_json)['__slots'],slots)
        # round 1 can no longer change while round 2 exists
        self.assertEqual(self.post(slots,action='apply').status_code,400)
        round_page=self.client.get(f'/event/{self.draw.event_id}/round/2')
        self.assertIn('จับสลากแมนนวล Round 2'.encode(),round_page.data)
        # clear round 2
        self.assertEqual(self.post_round(2,r2,'clear').status_code,302)
        self.assertEqual(Match.query.filter_by(event_id=self.draw.event_id,round=2).count(),0)
        self.assertEqual(json.loads(self.draw.entries_json)['__slots_r2'],['']*48)
        self.assertEqual(Match.query.filter_by(event_id=self.draw.event_id,round=1).count(),24)

    def test_clear_refuses_started_round(self):
        slots=self._apply_round1_and_lock()
        self.assertEqual(self.post(slots,action='clear').status_code,400)  # round 1 locked
        self.assertEqual(Match.query.filter_by(event_id=self.draw.event_id,round=1).count(),24)

    def test_clear_unscored_round_one(self):
        slots=[c['code'] for c in COUNTRIES]
        self.post(slots,action='apply')
        self.assertEqual(self.post(slots,action='clear').status_code,302)
        self.assertEqual(Match.query.filter_by(event_id=self.draw.event_id).count(),0)
        self.assertEqual(json.loads(self.draw.entries_json)['__slots'],['']*48)
