import random
from standings import calculate_standings
from models import Match
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
def generate_pairings(event_id, round_no, max_retries=10):
    standings = calculate_standings(event_id)
    previous_matches = Match.query.filter_by(event_id=event_id).all()

    past_opponents = {}
    bye_teams = set()

    for match in previous_matches:
        if match.team2_id == "BYE" or match.team2_id is None or match.team2_id == 0:
            bye_teams.add(match.team1_id)
        else:
            past_opponents.setdefault(match.team1_id, set()).add(match.team2_id)
            past_opponents.setdefault(match.team2_id, set()).add(match.team1_id)

    score_groups = {}
    for team in standings:
        score_groups.setdefault(team["score"], []).append(team["team_id"])

    sorted_scores = sorted(score_groups.keys(), reverse=True)

    total_teams = sum(len(teams) for teams in score_groups.values())
    allow_bye = (total_teams % 2 == 1)

    def try_pairing(groups, past_opponents):
        pairings = []
        used_teams = set()
        carry_over = None

        for score in sorted_scores:
            group = list(groups[score])

            if carry_over:
                found = False
                for idx, t in enumerate(group):
                    if t not in past_opponents.get(carry_over, set()):
                        pairings.append((carry_over, t))
                        used_teams.update({carry_over, t})
                        group.pop(idx)
                        carry_over = None
                        found = True
                        break
                if not found:
                    return None

            temp = []
            while group:
                t1 = group.pop(0)
                for idx, t2 in enumerate(group):
                    if t2 not in past_opponents.get(t1, set()):
                        pairings.append((t1, t2))
                        used_teams.update({t1, t2})
                        group.pop(idx)
                        break
                else:
                    temp.append(t1)

            if len(temp) == 1:
                if carry_over is not None:
                    return None  # ค้าง 2 ทีมไม่ได้
                carry_over = temp[0]
            elif len(temp) > 1:
                return None

        # เงื่อนไข BYE
        if carry_over:
            if not allow_bye:
                return None
            if carry_over in bye_teams:
                return None  # ได้ BYE ซ้ำ
            pairings.append((carry_over, None))

        return pairings

    for attempt in range(max_retries):
        temp_groups = {score: list(teams) for score, teams in score_groups.items()}
        for g in temp_groups.values():
            random.shuffle(g)

        pairings = try_pairing(temp_groups, past_opponents)
        if pairings is not None:
            return pairings

    # ล้มเหลว -> manual pairing
    return pairings


    # ถ้าเกิน max_retries ให้ลองจับคู่แบบผ่อนปรน (คะแนนติดกัน)

    # สร้าง list ทีมตามคะแนนเรียงจากมากไปน้อย
    teams_ordered = []
    for score in sorted_scores:
        teams_ordered.extend(score_groups[score])

    used = set()
    pairings = []

    # ฟังก์ชันช่วยจับคู่ทีมหาคู่ที่ยังไม่เคยเจอ และทีมที่ได้ BYE แล้วจะไม่จับ BYE ซ้ำ
    def find_partner(team):
        for candidate in teams_ordered:
            if candidate != team and candidate not in used and candidate not in past_opponents.get(team, set()):
                # หลีกเลี่ยงจับ BYE ซ้ำกับทีมที่เคยได้ BYE แล้ว
                if candidate in bye_teams and team in bye_teams:
                    continue
                return candidate
        return None

    for team in teams_ordered:
        if team in used:
            continue
        partner = find_partner(team)
        if partner:
            pairings.append((team, partner))
            used.add(team)
            used.add(partner)
        else:
            # ทีมนี้จับคู่ไม่ได้ ต้องได้ BYE
            # แต่ถ้าเคยได้ BYE แล้ว อาจต้องแจ้งเตือนหรือจัดการด้วยมือ
            if team in bye_teams:
                return None  # หรือโยน exception เฉพาะของคุณ เช่น TooManyByesError
            else:
                pairings.append((team, None))
                used.add(team)

    return pairings
