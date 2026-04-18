from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file
from flask_login import login_required, current_user
from collections import defaultdict
import io
import pandas as pd

from models import db, Match, Team, Event
from standings import calculate_standings


match_bp = Blueprint('match', __name__)

def get_current_round(event_id):
    last_match = Match.query.filter_by(event_id=event_id).order_by(Match.round.desc()).first()
    if last_match:
        return last_match.round + 1
    else:
        return 1



# ----------------- Download Standings as Excel -----------------
@match_bp.route('/event/<int:event_id>/download_standings')
def download_standings(event_id):
    standings = calculate_standings(event_id)
    df = pd.DataFrame(standings)

    buffer = io.BytesIO()
    df.to_excel(buffer, index=False)
    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name=f'standings_event_{event_id}.xlsx',
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )


# ----------------- Show Pairings -----------------
@match_bp.route('/event/<int:event_id>/pairings')
def show_pairings(event_id):
    selected_round = request.args.get('round', type=int)
    event = Event.query.get_or_404(event_id)

    if selected_round:
        matches = Match.query.filter_by(event_id=event_id, round=selected_round).order_by(Match.field.asc()).all()
        matches_by_round = {selected_round: matches}
    else:
        all_matches = Match.query.filter_by(event_id=event_id).order_by(Match.round.asc(), Match.field.asc()).all()
        matches_by_round = defaultdict(list)
        for match in all_matches:
            matches_by_round[match.round].append(match)

    teams = {team.id: team.name for team in event.teams}

    return render_template(
        'match_pairs.html',
        event=event,
        matches_by_round=matches_by_round,
        teams=teams,
        selected_round=selected_round
    )


# ----------------- Print Matches -----------------
@match_bp.route('/event/<int:event_id>/match/print')
def print_matches(event_id):
    event = Event.query.get_or_404(event_id)
    teams = {team.id: team.name for team in Team.query.filter_by(event_id=event_id).all()}
    all_matches = Match.query.filter_by(event_id=event_id).order_by(Match.round.asc()).all()

    selected_round = request.args.get('round', type=int)

    if selected_round:
        matches = Match.query.filter_by(event_id=event_id, round=selected_round).all()
        matches_by_round = {selected_round: matches}
    else:
        matches_by_round = defaultdict(list)
        for match in all_matches:
            matches_by_round[match.round].append(match)

    return render_template(
        "match_print.html",
        event=event,
        teams=teams,
        matches_by_round=matches_by_round,
        selected_round=selected_round
    )

# ----------------- Swiss Pairing Logic Helper -----------------
def try_pairing(groups, past_opponents):
    pairings = []
    carry_over = []

    for score in sorted(groups.keys(), reverse=True):  # สมมติ sorted_scores = sorted(groups.keys(), reverse=True)
        group = list(groups[score])

        if carry_over:
            group = carry_over + group
            carry_over = []

        temp = []
        while group:
            t1 = group.pop(0)
            for idx, t2 in enumerate(group):
                if t2 not in past_opponents.get(t1, set()):
                    pairings.append((t1, t2))
                    group.pop(idx)
                    break
            else:
                temp.append(t1)

        if temp:
            carry_over.extend(temp)

    if carry_over:
        return None

    return pairings
