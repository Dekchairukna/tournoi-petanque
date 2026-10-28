"""Local-only preview, isolated from the real database. Run from the project root."""
import os
import secrets
import sys
import tempfile
from pathlib import Path
from datetime import date

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
preview_dir = tempfile.mkdtemp(prefix='petanque-desk-preview-')
os.environ['DATABASE_URL'] = 'sqlite:///' + str(Path(preview_dir) / 'preview.db')
os.environ['YAGAMI_SUPERADMIN_PASSWORD'] = secrets.token_urlsafe(24)
os.environ['SECRET_KEY'] = secrets.token_urlsafe(32)
os.environ['COOKIE_SECURE'] = '0'
from app import app, db
from models import User, Tournament, Event, Team, EventTeamRegistration, EventRoundRobinConfig, Match, TournamentMatchSchedule
from round_robin_event import _assign, _generate
from tournament_desk import build_schedule
from datetime import time

app.config['DESK_DEMO'] = True
password = secrets.token_urlsafe(18)
with app.app_context():
    user = User(username='preview',role='superadmin')
    user.set_password(password)
    db.session.add(user)
    db.session.flush()
    tournament = Tournament(name='กีฬานักเรียน · รอบคัดเลือกเขต', location='สนามเปตองจังหวัด · งานตัวอย่าง',
        creator_id=user.id,start_date=date(2026,11,25),end_date=date(2026,12,1),field_max=8)
    db.session.add(tournament)
    db.session.flush()
    categories = [('เดี่ยว','ชาย'),('เดี่ยว','หญิง'),('คู่ผสม','ผสม'),('คู่','ชาย'),('คู่','หญิง'),('ทีม','ชาย'),('ทีม','หญิง')]
    events = []
    for index,(category,sex) in enumerate(categories):
        event = Event(name=category+(sex if category!='คู่ผสม' else ''),category=category,sex=sex,
            age_group='อายุไม่เกิน 18 ปี',competition_format='round_robin',rounds=1,
            tournament_id=tournament.id,creator_id=user.id,date=tournament.start_date,
            location=tournament.location,logo_filename='[]')
        db.session.add(event)
        db.session.flush()
        for i in range(8):
            team = Team(name=f'โรงเรียนตัวอย่าง {i+1}',event_id=event.id)
            db.session.add(team)
            db.session.flush()
            db.session.add(EventTeamRegistration(team_id=team.id,affiliation=f'จังหวัดตัวอย่าง {i+1}',
                athletes=f'นักกีฬาตัวอย่าง {index+1}.{i+1}',status='checked_in' if index<2 or i<5 else 'pending'))
        if index<2:
            cfg=EventRoundRobinConfig(event_id=event.id,group_count=2)
            db.session.add(cfg)
            db.session.flush()
            _generate(event,cfg,_assign(event,cfg,'seed'))
        events.append(event)
    db.session.flush()
    plan=build_schedule(Match.query.filter(Match.team2_id.isnot(None)).all(),{e.id:e for e in events},
        list(range(1,9)),tournament.start_date,time(8,30),time(18),75,15)
    for match,field,start,end in plan:
        match.field=field
        db.session.add(TournamentMatchSchedule(match_id=match.id,starts_at=start,ends_at=end,field_number=field))
    db.session.commit()
    preview_url=f'http://127.0.0.1:5012/tournament/{tournament.id}/desk'
Path('/tmp/petanque-desk-preview-login.txt').write_text('preview\n'+password+'\n'+preview_url)
Path('/tmp/petanque-desk-preview-login.txt').chmod(0o600)
print('Preview:',preview_url,flush=True)
app.run(host='127.0.0.1',port=5012,debug=False,use_reloader=False)
