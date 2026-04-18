import random
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from models import db, Team, Match
from sqlalchemy import desc
from models import db, Team, Match
from sqlalchemy.orm import joinedload


def generate_pairings(event_id, round_number):
    # ดึงทีมทั้งหมดในรายการนี้
    teams = Team.query.filter_by(event_id=event_id).options(joinedload(Team.matches_as_team1), joinedload(Team.matches_as_team2)).all()

    # จัดเรียงตามลำดับคะแนนแบบ Swiss (score > BHN > fBHN > difference)
    teams.sort(key=lambda t: (-t.score, -t.bhn, -t.fbhn, -t.difference, t.id))

    # เตรียมตรวจสอบประวัติการเจอกัน
    team_matches = {team.id: set() for team in teams}
    for team in teams:
        for match in team.matches_as_team1 + team.matches_as_team2:
            opponent_id = match.team2_id if match.team1_id == team.id else match.team1_id
            team_matches[team.id].add(opponent_id)

    # สร้างคู่
    paired = set()
    pairings = []

    for i, team in enumerate(teams):
        if team.id in paired:
            continue
        for j in range(i + 1, len(teams)):
            opponent = teams[j]
            if opponent.id in paired:
                continue
            # ถ้าไม่เคยเจอกัน
            if opponent.id not in team_matches[team.id]:
                pairings.append((team, opponent))
                paired.add(team.id)
                paired.add(opponent.id)
                break
        else:
            # ถ้าไม่มีใครให้จับแล้ว อาจ bye หรือ unmatched
            pass

    # บันทึกลง DB
    for team1, team2 in pairings:
        match = Match(
            event_id=event_id,
            round=round_number,
            team1_id=team1.id,
            team2_id=team2.id,
            score1=None,
            score2=None
        )
        db.session.add(match)

    db.session.commit()
