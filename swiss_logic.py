import random
from standings import calculate_standings
from models import Match
from sqlalchemy import or_
import re
import random
from collections import defaultdict

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
    """
    สร้างการจับคู่สำหรับรอบถัดไปของการแข่งขันแบบ Swiss-pairing

    อาร์กิวเมนต์:
        event_id (int): ID ของอีเวนต์
        round_no (int): หมายเลขรอบที่จะจับคู่
        max_retries (int): จำนวนครั้งสูงสุดในการพยายามจับคู่ใหม่ หากเกิดปัญหา

    คืนค่า:
        list: รายการของคู่ทีมที่จับคู่กัน (team1_id, team2_id) หรือ None หากจับคู่ไม่ได้
    """

    # ฟังก์ชันช่วยในการดึงชื่อพื้นฐานของทีม (เช่น "ขอนแก่น 1" -> "ขอนแก่น")
    # ย้ายมาไว้ในฟังก์ชันนี้เพื่อให้เข้าถึงได้ง่าย
    def extract_base_name(name):
        """
        ดึงชื่อพื้นฐานของทีม โดยลบรหัสตัวเลขหรือเครื่องหมายที่ตามหลังชื่อ
        เช่น "ขอนแก่น 1", "ขอนแก่น-2" จะกลายเป็น "ขอนแก่น"
        """
        base = re.split(r'[\s\-]*\d+$', name.strip())[0]
        return base

    # ดึงข้อมูลทีมทั้งหมดเพื่อสร้าง map สำหรับชื่อทีม
    # เพื่อให้สามารถใช้ extract_base_name ได้เมื่อมีแค่ team_id
    all_teams = Team.query.filter_by(event_id=event_id).all()
    team_name_map = {team.id: team.name for team in all_teams}


    # คำนวณอันดับปัจจุบันของทีม
    standings = calculate_standings(event_id)
    # ดึงข้อมูลแมตช์ที่เคยเกิดขึ้นทั้งหมดสำหรับอีเวนต์นี้
    previous_matches = Match.query.filter_by(event_id=event_id).all()

    # เก็บข้อมูลคู่ต่อสู้ที่เคยพบกันมาแล้ว
    past_opponents = {}
    # เก็บข้อมูลทีมที่เคยได้ BYE (ไม่จับคู่)
    bye_teams = set()

    for match in previous_matches:
        # ถ้าทีมที่ 2 เป็น BYE หรือไม่มี (None/0) แสดงว่าทีมที่ 1 ได้ BYE
        if match.team2_id == "BYE" or match.team2_id is None or match.team2_id == 0:
            bye_teams.add(match.team1_id)
        else:
            # เพิ่มคู่ต่อสู้ให้กับทั้งสองทีม
            past_opponents.setdefault(match.team1_id, set()).add(match.team2_id)
            past_opponents.setdefault(match.team2_id, set()).add(match.team1_id)

    # จัดกลุ่มทีมตามคะแนน
    score_groups = {}
    for team in standings:
        score_groups.setdefault(team["score"], []).append(team["team_id"])

    # เรียงลำดับคะแนนจากมากไปน้อย
    sorted_scores = sorted(score_groups.keys(), reverse=True)

    # ตรวจสอบว่ามีจำนวนทีมคี่หรือไม่ เพื่อพิจารณาการให้ BYE
    total_teams = sum(len(teams) for teams in score_groups.values())
    allow_bye = (total_teams % 2 == 1)

    def try_pairing(groups, past_opponents_data):
        """
        พยายามสร้างการจับคู่จากกลุ่มคะแนนที่กำหนด

        อาร์กิวเมนต์:
            groups (dict): กลุ่มทีมที่จัดตามคะแนน
            past_opponents_data (dict): ข้อมูลคู่ต่อสู้ที่เคยพบกัน

        คืนค่า:
            list: รายการของคู่ทีมที่จับคู่กัน (team1_id, team2_id) หรือ None หากจับคู่ไม่ได้
        """
        pairings = []
        used_teams = set() # เก็บทีมที่ถูกใช้ไปแล้วในรอบนี้
        carry_over = None # ทีมที่ค้างจากการจับคู่ในกลุ่มคะแนนเดียวกัน

        for score in sorted_scores:
            group = list(groups[score]) # ทำสำเนาของกลุ่มเพื่อแก้ไขได้

            # ถ้ามีทีมที่ค้างมาจากกลุ่มคะแนนที่สูงกว่า
            if carry_over:
                found = False
                # พยายามหาคู่ให้ทีมที่ค้างในกลุ่มคะแนนปัจจุบัน
                for idx, t in enumerate(group):
                    # ตรวจสอบว่าไม่เคยพบกันมาก่อน และชื่อเบสไม่ซ้ำกัน
                    if (t not in past_opponents_data.get(carry_over, set()) and
                        extract_base_name(team_name_map[carry_over]) != extract_base_name(team_name_map[t])):
                        pairings.append((carry_over, t))
                        used_teams.update({carry_over, t})
                        group.pop(idx) # ลบทีมที่ถูกใช้ไปแล้วออกจากกลุ่ม
                        carry_over = None # ล้างทีมที่ค้าง
                        found = True
                        break
                if not found:
                    # ถ้าหาคู่ให้ทีมที่ค้างไม่ได้ แสดงว่าจับคู่ไม่ได้
                    return None

            temp = [] # เก็บทีมที่ยังหาคู่ไม่ได้ในกลุ่มปัจจุบัน
            while group:
                t1 = group.pop(0) # ดึงทีมแรกจากกลุ่ม
                found_pair = False
                for idx, t2 in enumerate(group):
                    # ตรวจสอบว่าไม่เคยพบกันมาก่อน และชื่อเบสไม่ซ้ำกัน
                    if (t2 not in past_opponents_data.get(t1, set()) and
                        extract_base_name(team_name_map[t1]) != extract_base_name(team_name_map[t2])):
                        pairings.append((t1, t2))
                        used_teams.update({t1, t2})
                        group.pop(idx) # ลบทีมที่ถูกใช้ไปแล้วออกจากกลุ่ม
                        found_pair = True
                        break
                if not found_pair:
                    # ถ้าหาคู่ไม่ได้ ให้เก็บไว้ใน temp
                    temp.append(t1)

            # จัดการทีมที่ยังหาคู่ไม่ได้ในกลุ่มปัจจุบัน (temp)
            if len(temp) == 1:
                if carry_over is not None:
                    # ถ้ามีทีมค้างอยู่แล้ว และมีทีมค้างเพิ่มอีก 1 ทีม แสดงว่ามี 2 ทีมค้าง
                    # ซึ่งไม่ควรเกิดขึ้นในระบบ Swiss (ยกเว้นกรณี BYE)
                    return None
                carry_over = temp[0] # เก็บทีมที่ค้างไว้เพื่อจับคู่กับกลุ่มคะแนนถัดไป
            elif len(temp) > 1:
                # ถ้ามีทีมค้างมากกว่า 1 ทีม แสดงว่าจับคู่ในกลุ่มนี้ไม่ได้
                return None

        # จัดการเงื่อนไข BYE (ถ้ามีทีมค้าง 1 ทีมเมื่อจบทุกกลุ่มคะแนน)
        if carry_over:
            if not allow_bye:
                # ถ้าไม่ได้รับอนุญาตให้มี BYE แต่มีทีมค้าง แสดงว่าจับคู่ไม่ได้
                return None
            if carry_over in bye_teams:
                # ถ้าทีมที่ได้ BYE ซ้ำรอบก่อนหน้า แสดงว่าจับคู่ไม่ได้
                return None
            pairings.append((carry_over, "BYE")) # เพิ่ม BYE ให้ทีมที่ค้าง

        return pairings

    # พยายามจับคู่หลายครั้ง โดยสุ่มลำดับทีมในแต่ละกลุ่มคะแนน
    for attempt in range(max_retries):
        temp_groups = {score: list(teams) for score, teams in score_groups.items()}
        for g in temp_groups.values():
            random.shuffle(g) # สุ่มลำดับทีมในแต่ละกลุ่ม

        pairings = try_pairing(temp_groups, past_opponents)
        if pairings is not None:
            # ถ้าจับคู่ได้สำเร็จ ให้คืนค่าการจับคู่
            return pairings

    # หากพยายามจนครบจำนวนครั้งแล้วยังจับคู่ไม่ได้
    return None # หรือ raise Exception("ไม่สามารถจับคู่ได้")


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
