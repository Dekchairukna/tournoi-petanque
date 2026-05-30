import random
import re
from standings import calculate_standings
from models import Match, Team
from sqlalchemy import or_


#----------------------------รอบเก็บตก----------------



def have_played(event_id, team1_id, team2_id):
    # ตรวจสอบว่าทีมเคยเจอกันใน event นี้หรือยัง
    return Match.query.filter_by(event_id=event_id).filter(
        or_(
            (Match.team1_id == team1_id) & (Match.team2_id == team2_id),
            (Match.team1_id == team2_id) & (Match.team2_id == team1_id)
        )
    ).first() is not None


def extract_base_name(name):
    """ตัดเลข/รหัสท้ายชื่อทีมออก เพื่อแยกทีมชื่อฐานเดียวกันไม่ให้เจอกัน"""
    if not name:
        return ''
    base = name.strip().lower()
    base = re.sub(r'\s+', ' ', base)
    # ตัวอย่าง: ทีม A 1, ทีม A-2, ทีม A_3, ทีม A(4)
    base = re.sub(r'\s*[\-_]*\s*[\(\[]?\d+[\)\]]?\s*$', '', base)
    return base.strip()


def same_base_name(team_names, team1_id, team2_id):
    if team1_id is None or team2_id is None:
        return False
    return extract_base_name(team_names.get(team1_id, '')) == extract_base_name(team_names.get(team2_id, ''))


def generate_manual_pairings(event_id, team_ids=None):
    if team_ids is None:
        standings = calculate_standings(event_id)
        team_ids = [team['team_id'] for team in standings]
    else:
        # ใช้ลำดับตามที่ส่งมา
        pass

    pairings = []
    used = set()
    unpaired = []

    for i, team_id in enumerate(team_ids):
        if team_id in used:
            continue

        found_pair = False
        for j in range(i + 1, len(team_ids)):
            opponent_id = team_ids[j]
            if opponent_id in used:
                continue

            # ไม่จับคู่ทีมที่เคยเจอกัน
            if not have_played(event_id, team_id, opponent_id):
                pairings.append({
                    'team1_id': team_id,
                    'team2_id': opponent_id,
                    'field': ''
                })
                used.add(team_id)
                used.add(opponent_id)
                found_pair = True
                break

        if not found_pair:
            unpaired.append(team_id)

    # ถ้าเหลือทีมเดียว ถือว่าได้ BYE
    if len(unpaired) == 1:
        pairings.append({
            'team1_id': unpaired[0],
            'team2_id': 0,  # None หรือ 0 แล้วแต่ template
            'field': ''
        })
        unpaired = []

    return pairings, unpaired







#--------------------จัดการสนาม----------------------
def get_available_fields(event, used_fields=None):
    if used_fields is None:
        used_fields = []

    # เตรียมเซตของสนามที่ต้องไม่ใช้
    exclude = set(f.strip() for f in event.field_exclude.split(',')) if event.field_exclude else set()

    available_fields = []
    for i in range(event.field_start, event.field_max + 1):
        if str(i) not in exclude:
            field = f"{event.field_prefix}{i}"
            if field not in used_fields:
                available_fields.append(field)

    return available_fields

#-------------logic--------------------------------------
def generate_pairings(event_id, round_no, max_retries=200, separate_same_name=False):
    """
    จับคู่ Swiss รอบถัดไปแบบทนทานขึ้น
    - ถ้า separate_same_name=True: ห้ามทีมชื่อฐานเดียวกันเจอกันแบบกฎแข็ง ห้ามผ่อนกฎนี้
    - ถ้า separate_same_name=False: ทีมชื่อฐานเดียวกันเจอกันได้ตามปกติ
    - ห้ามทีมที่เคยเจอกันแล้วเจอกันซ้ำแบบกฎแข็ง ไม่ผ่อนกฎนี้
    - พยายามเลี่ยง BYE ซ้ำ แต่ถ้าจำเป็นสามารถให้ BYE ซ้ำได้ เพื่อไม่ให้ระบบตันง่าย
    """
    standings = calculate_standings(event_id)
    team_ids = [team["team_id"] for team in standings]
    team_names = {team.id: team.name for team in Team.query.filter_by(event_id=event_id).all()}
    previous_matches = Match.query.filter_by(event_id=event_id).all()

    if len(team_ids) < 2:
        return []

    past_opponents = {}
    bye_teams = set()

    for match in previous_matches:
        if match.team2_id is None or match.team2_id == 0:
            if match.team1_id:
                bye_teams.add(match.team1_id)
        else:
            past_opponents.setdefault(match.team1_id, set()).add(match.team2_id)
            past_opponents.setdefault(match.team2_id, set()).add(match.team1_id)

    def can_pair(t1, t2, allow_same_base=False):
        if t1 == t2:
            return False
        # กฎแข็ง: ทีมที่เคยเจอกันแล้ว ห้ามเจอกันซ้ำทุกกรณี
        if t2 in past_opponents.get(t1, set()):
            return False
        if separate_same_name and (not allow_same_base) and same_base_name(team_names, t1, t2):
            return False
        return True

    def backtrack_pair(remaining, allow_same_base=False):
        """จับคู่ด้วย backtracking เพื่อแก้กรณี greedy เลือกคู่แรกแล้วตันภายหลัง"""
        if not remaining:
            return []
        first = remaining[0]

        for idx in range(1, len(remaining)):
            second = remaining[idx]
            if not can_pair(first, second, allow_same_base=allow_same_base):
                continue
            rest = remaining[1:idx] + remaining[idx + 1:]
            sub = backtrack_pair(rest, allow_same_base=allow_same_base)
            if sub is not None:
                return [(first, second)] + sub
        return None

    def choose_bye_candidates(ids):
        """
        เลือกทีม BYE จากอันดับล่างขึ้นบนก่อน
        - ทีมที่ยังไม่เคย BYE มาก่อนจะถูกลองก่อน
        - ถ้าจัดคู่ไม่ได้จริง ๆ จะลองทีมที่เคย BYE แล้วด้วย เพื่อให้ BYE ซ้ำได้เมื่อจำเป็น
        """
        bottom_up = list(reversed(ids))
        never_bye = [tid for tid in bottom_up if tid not in bye_teams]
        already_bye = [tid for tid in bottom_up if tid in bye_teams]
        return never_bye + already_bye

    if separate_same_name:
        # ติ๊ก checkbox: ห้ามชื่อฐานเดียวกันเจอกันแบบกฎแข็ง
        # คู่เดิมซ้ำก็เป็นกฎแข็ง ห้ามผ่อนทั้งสองเรื่อง
        rule_levels = [
            {"allow_same_base": False},
        ]
    else:
        # ไม่ติ๊ก checkbox: ทีมชื่อฐานเดียวกันเจอกันได้เลย แต่คู่เดิมซ้ำยังห้ามเด็ดขาด
        rule_levels = [
            {"allow_same_base": True},
        ]

    if len(team_ids) % 2 == 1:
        for bye_team in choose_bye_candidates(team_ids):
            remaining = [tid for tid in team_ids if tid != bye_team]
            for rule in rule_levels:
                pairs = backtrack_pair(remaining, **rule)
                if pairs is not None:
                    return pairs + [(bye_team, None)]
        return None

    for rule in rule_levels:
        pairs = backtrack_pair(team_ids, **rule)
        if pairs is not None:
            return pairs

    return None
