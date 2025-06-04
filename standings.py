from models import Match, Team
from sqlalchemy import or_

def safe_int(val):
    try:
        return int(val)
    except:
        return 0

def calculate_standings(event_id):
    matches = Match.query.filter_by(event_id=event_id).all()
    teams = Team.query.filter_by(event_id=event_id).all()

    team_dict = {team.id: team for team in teams}
    standings = {}
    rounds_set = set()

    for team in teams:
        standings[team.id] = {
            "name": team.name,
            "score": 0,
            "win": 0,
            "draw": 0,
            "lose": 0,
            "played": 0,
            "point_for": 0,
            "point_against": 0,
            "opponents": {}
        }

    # index แมตช์แบบรวบไว้ lookup เร็ว
    match_lookup = {}
    for match in matches:
        if match.round:
            rounds_set.add(match.round)
        if match.team1_id and match.team2_id:
            key = (match.round, min(match.team1_id, match.team2_id), max(match.team1_id, match.team2_id))
            match_lookup[key] = match

        if not match.is_locked:
            continue

        t1_id = match.team1_id
        t2_id = match.team2_id
        r = match.round

        if t2_id is None:
            # BYE
            standings[t1_id]["score"] += 1
            standings[t1_id]["win"] += 1
            standings[t1_id]["played"] += 1
            standings[t1_id]["opponents"][r] = None
            continue

        standings[t1_id]["opponents"][r] = t2_id
        standings[t2_id]["opponents"][r] = t1_id

        standings[t1_id]["played"] += 1
        standings[t2_id]["played"] += 1

        s1 = safe_int(match.team1_score)
        s2 = safe_int(match.team2_score)

        standings[t1_id]["point_for"] += s1
        standings[t1_id]["point_against"] += s2
        standings[t2_id]["point_for"] += s2
        standings[t2_id]["point_against"] += s1

        if s1 > s2:
            standings[t1_id]["score"] += 1
            standings[t1_id]["win"] += 1
            standings[t2_id]["lose"] += 1
        elif s2 > s1:
            standings[t2_id]["score"] += 1
            standings[t2_id]["win"] += 1
            standings[t1_id]["lose"] += 1
        else:
            standings[t1_id]["draw"] += 1
            standings[t2_id]["draw"] += 1

    rounds = sorted(rounds_set or [1])
    team_scores = {tid: data["score"] for tid, data in standings.items()}

    # คำนวณ Buchholz
    team_buchholz = {}
    for tid, data in standings.items():
        bhn = sum(team_scores.get(oid, 0) for oid in data["opponents"].values() if oid)
        team_buchholz[tid] = bhn

    results = []
    for tid, data in standings.items():
        bhn = team_buchholz.get(tid, 0)
        fbhn = sum(team_buchholz.get(oid, 0) for oid in data["opponents"].values() if oid)
        bye_bonus = 6 if any(oid is None for oid in data["opponents"].values()) else 0

        row = {
            "team_id": tid,
            "team_name": data["name"],
            "score": data["score"],
            "buchholz": bhn,
            "final_buchholz": fbhn,
            "point_for": data["point_for"],
            "point_against": data["point_against"],
            "point_diff": (data["point_for"] - data["point_against"]) + bye_bonus,
        }

        for r in rounds:
            opp_id = data["opponents"].get(r)
            if opp_id is None:
                row[f"VS_Round{r}"] = "Bye"
            else:
                opp_name = team_dict.get(opp_id).name
                key = (r, min(tid, opp_id), max(tid, opp_id))
                match = match_lookup.get(key)

                if match:
                    s1 = safe_int(match.team1_score)
                    s2 = safe_int(match.team2_score)
                    score_str = f"{s1}-{s2}" if match.team1_id == tid else f"{s2}-{s1}"
                    row[f"VS_Round{r}"] = f"{opp_name} ({score_str})"
                else:
                    row[f"VS_Round{r}"] = opp_name

        results.append(row)

    results.sort(key=lambda x: (x["score"], x["buchholz"], x["final_buchholz"], x["point_diff"]), reverse=True)
    return results
