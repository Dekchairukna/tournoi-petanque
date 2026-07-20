from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
import io
import json
import math
import random
import re
from typing import Any, Iterable

import pandas as pd
from flask import (
    Blueprint,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required
from flask_socketio import join_room
from sqlalchemy import func

from models import (
    CompetitionStage,
    Event,
    Match,
    RoundRobinGroup,
    RoundRobinGroupMember,
    Team,
    Tournament,
    TournamentEvent,
    TournamentEventEntry,
    TournamentMasterTeam,
    db,
)


tcenter_bp = Blueprint("tcenter", __name__)

FORMAT_LABELS = {
    "round_robin": "Round Robin",
    "swiss": "Swiss",
    "double_knockout": "Double Elimination",
    "knockout": "Knockout",
}
PAIRING_LABELS = {
    "random": "Random",
    "seed": "ตาม Seed",
    "snake": "Snake Seeding",
    "manual": "กำหนดเอง",
}


def _admin_allowed() -> bool:
    return bool(
        current_user.is_authenticated
        and (getattr(current_user, "role", "") or "").lower() in {"admin", "superadmin"}
    )


def _require_admin_redirect():
    if _admin_allowed():
        return None
    flash("คุณไม่มีสิทธิ์แก้ไข Tournament Center", "warning")
    return redirect(url_for("tcenter.tournaments"))


def _stage_config(stage: CompetitionStage) -> dict[str, Any]:
    return stage.config


def _save_stage_config(stage: CompetitionStage, config: dict[str, Any]) -> None:
    stage.set_config(config)


def _stage_team_query(stage: CompetitionStage):
    if not stage.engine_event_id:
        return Team.query.filter(Team.id == -1)
    return Team.query.filter_by(event_id=stage.engine_event_id)


def _tournament_fields(tournament: Tournament) -> list[int]:
    start = max(1, int(tournament.field_start or 1))
    count = max(1, int(tournament.field_max or 16))
    excluded: set[int] = set()
    for raw in re.split(r"[,\s]+", tournament.field_exclude or ""):
        if raw.strip().isdigit():
            excluded.add(int(raw.strip()))
    return [n for n in range(start, start + count) if n not in excluded]


def _format_field(tournament: Tournament, field_number: int | None) -> str:
    if field_number is None:
        return "-"
    return f"{tournament.field_prefix or ''}{field_number}"


def _stage_status_label(stage: CompetitionStage) -> str:
    labels = {
        "draft": "ตั้งค่า",
        "ready": "พร้อมจับสลาก",
        "running": "กำลังแข่งขัน",
        "qualification_done": "จบรอบคัดเลือก",
        "completed": "จบแล้ว",
    }
    return labels.get(stage.status, stage.status or "-")


def _event_status_label(event: TournamentEvent) -> str:
    labels = {
        "draft": "กำลังตั้งค่า",
        "ready": "พร้อมแข่งขัน",
        "running": "กำลังแข่งขัน",
        "completed": "จบอีเวนต์",
    }
    return labels.get(event.status, event.status or "-")


def _normalize_names(values: Iterable[Any]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text or text.lower() == "nan":
            continue
        key = re.sub(r"\s+", " ", text).casefold()
        if key in seen:
            continue
        seen.add(key)
        output.append(re.sub(r"\s+", " ", text))
    return output


def _extract_team_names_from_upload(file_storage) -> list[str]:
    filename = (file_storage.filename or "").lower()
    raw = file_storage.read()
    if not raw:
        return []
    if filename.endswith((".xlsx", ".xls")):
        frame = pd.read_excel(io.BytesIO(raw))
    elif filename.endswith(".csv"):
        frame = pd.read_csv(io.BytesIO(raw))
    else:
        text_value = raw.decode("utf-8-sig", errors="ignore")
        return _normalize_names(line.split(",")[0] for line in text_value.splitlines())

    if frame.empty:
        return []
    preferred = ["team_name", "ทีม", "ชื่อทีม", "name"]
    column = next((c for c in preferred if c in frame.columns), frame.columns[0])
    return _normalize_names(frame[column].tolist())


def _ensure_all_event_entries(tournament: Tournament) -> None:
    team_ids = [team.id for team in tournament.master_teams]
    if not team_ids:
        return
    for event in tournament.events:
        existing = {entry.master_team_id for entry in event.entries}
        for team_id in team_ids:
            if team_id not in existing:
                db.session.add(
                    TournamentEventEntry(
                        tournament_event_id=event.id,
                        master_team_id=team_id,
                        is_active=True,
                    )
                )


def _active_master_teams(event: TournamentEvent) -> list[TournamentMasterTeam]:
    active_ids = [entry.master_team_id for entry in event.entries if entry.is_active]
    if not active_ids:
        return []
    return (
        TournamentMasterTeam.query.filter(TournamentMasterTeam.id.in_(active_ids))
        .order_by(TournamentMasterTeam.seed.asc().nullslast(), TournamentMasterTeam.name.asc())
        .all()
    )


def _create_engine_event(stage: CompetitionStage, selected_master_teams: list[TournamentMasterTeam]) -> Event:
    event = stage.tournament_event
    tournament = event.tournament
    rounds = max(1, int(_stage_config(stage).get("rounds") or 3))
    engine = Event(
        name=f"{event.name} — {stage.name}",
        location=tournament.location,
        category=event.category or event.name,
        sex=event.sex,
        age_group=event.age_group,
        rounds=rounds,
        current_round=1,
        date=tournament.start_date,
        auto_field_enabled=True,
        field_prefix=tournament.field_prefix or "",
        field_start=tournament.field_start or 1,
        field_max=tournament.field_max or 16,
        field_exclude=tournament.field_exclude or "",
        creator_id=current_user.id,
        logo_filename="[]",
    )
    db.session.add(engine)
    db.session.flush()
    for master_team in selected_master_teams:
        db.session.add(Team(name=master_team.name, event_id=engine.id))
    db.session.flush()
    stage.engine_event_id = engine.id
    return engine


def _sync_stage_engine_teams(stage: CompetitionStage, selected_master_teams: list[TournamentMasterTeam]) -> None:
    if not stage.engine_event_id:
        _create_engine_event(stage, selected_master_teams)
        return

    desired_names = [team.name for team in selected_master_teams]
    existing = Team.query.filter_by(event_id=stage.engine_event_id).all()
    existing_by_name = {team.name: team for team in existing}

    if Match.query.filter_by(event_id=stage.engine_event_id).count():
        # Changing teams after pairing invalidates every engine fairly. Caller confirms first.
        Match.query.filter_by(event_id=stage.engine_event_id).delete(synchronize_session=False)
        RoundRobinGroup.query.filter_by(stage_id=stage.id).delete(synchronize_session=False)

    for team in existing:
        if team.name not in desired_names:
            db.session.delete(team)
    for name in desired_names:
        if name not in existing_by_name:
            db.session.add(Team(name=name, event_id=stage.engine_event_id))
    db.session.flush()


def _create_stage(
    tournament_event: TournamentEvent,
    name: str,
    competition_format: str,
    pairing_method: str,
    selected_master_teams: list[TournamentMasterTeam],
    *,
    source_stage_id: int | None = None,
    rounds: int = 3,
    group_count: int = 1,
    advance_per_group: int = 2,
) -> CompetitionStage:
    next_no = (
        db.session.query(func.max(CompetitionStage.stage_no))
        .filter_by(tournament_event_id=tournament_event.id)
        .scalar()
        or 0
    ) + 1
    stage = CompetitionStage(
        tournament_event_id=tournament_event.id,
        stage_no=next_no,
        name=name or f"Stage {next_no}",
        competition_format=competition_format,
        pairing_method=pairing_method,
        status="ready",
        source_stage_id=source_stage_id,
    )
    stage.set_config(
        {
            "rounds": max(1, rounds),
            "group_count": max(1, group_count),
            "advance_per_group": max(1, advance_per_group),
            "first_time": "09:00",
            "match_minutes": 75,
            "break_minutes": 15,
            "team_seed_map": {team.name: team.seed for team in selected_master_teams if team.seed},
        }
    )
    db.session.add(stage)
    db.session.flush()
    _create_engine_event(stage, selected_master_teams)
    tournament_event.status = "ready"
    return stage


def _stage_open_url(stage: CompetitionStage) -> str:
    if stage.competition_format == "round_robin":
        return url_for("tcenter.round_robin_stage", stage_id=stage.id)
    if stage.competition_format == "swiss":
        return url_for("event_detail", event_id=stage.engine_event_id)
    return url_for("tcenter.start_legacy_stage", stage_id=stage.id)


@tcenter_bp.app_context_processor
def inject_tournament_center_helpers():
    return {
        "format_labels": FORMAT_LABELS,
        "pairing_labels": PAIRING_LABELS,
        "stage_status_label": _stage_status_label,
        "event_status_label": _event_status_label,
        "stage_open_url": _stage_open_url,
    }


@tcenter_bp.route("/tournaments")
@login_required
def tournaments():
    query = Tournament.query
    if not current_user.is_superadmin():
        query = query.filter_by(creator_id=current_user.id)
    rows = query.order_by(Tournament.created_at.desc(), Tournament.id.desc()).all()
    return render_template("tournament_list.html", tournaments=rows)


@tcenter_bp.route("/tournaments/create", methods=["POST"])
@login_required
def create_tournament():
    denied = _require_admin_redirect()
    if denied:
        return denied
    name = (request.form.get("name") or "").strip()
    if not name:
        flash("กรุณากรอกชื่อทัวร์นาเมนต์", "warning")
        return redirect(url_for("tcenter.tournaments"))

    def parse_date(value: str | None):
        if not value:
            return None
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
            return None

    tournament = Tournament(
        name=name,
        location=(request.form.get("location") or "").strip() or None,
        start_date=parse_date(request.form.get("start_date")),
        end_date=parse_date(request.form.get("end_date")),
        field_prefix=(request.form.get("field_prefix") or "").strip(),
        field_start=max(1, request.form.get("field_start", type=int) or 1),
        field_max=max(1, request.form.get("field_max", type=int) or 16),
        field_exclude=(request.form.get("field_exclude") or "").strip(),
        creator_id=current_user.id,
    )
    db.session.add(tournament)
    db.session.commit()
    flash("สร้างทัวร์นาเมนต์แล้ว เพิ่มรายชื่อทีมและอีเวนต์ต่อได้เลย", "success")
    return redirect(url_for("tcenter.tournament_dashboard", tournament_id=tournament.id))


@tcenter_bp.route("/tournament/<int:tournament_id>")
@login_required
def tournament_dashboard(tournament_id: int):
    tournament = Tournament.query.get_or_404(tournament_id)
    if not current_user.is_superadmin() and tournament.creator_id != current_user.id:
        flash("คุณไม่มีสิทธิ์เปิดทัวร์นาเมนต์นี้", "warning")
        return redirect(url_for("tcenter.tournaments"))
    _ensure_all_event_entries(tournament)
    db.session.commit()
    return render_template("tournament_dashboard.html", tournament=tournament)


@tcenter_bp.route("/tournament/<int:tournament_id>/delete", methods=["POST"])
@login_required
def delete_tournament(tournament_id: int):
    denied = _require_admin_redirect()
    if denied:
        return denied
    tournament = Tournament.query.get_or_404(tournament_id)
    # Engine Event rows are intentionally kept if they already contain a history.
    db.session.delete(tournament)
    db.session.commit()
    flash("ลบทัวร์นาเมนต์ออกจาก Tournament Center แล้ว", "success")
    return redirect(url_for("tcenter.tournaments"))


@tcenter_bp.route("/tournament/<int:tournament_id>/teams", methods=["POST"])
@login_required
def tournament_teams(tournament_id: int):
    denied = _require_admin_redirect()
    if denied:
        return denied
    tournament = Tournament.query.get_or_404(tournament_id)
    names: list[str] = []
    pasted = request.form.get("team_names") or ""
    names.extend(_normalize_names(pasted.splitlines()))
    upload = request.files.get("team_file")
    if upload and upload.filename:
        try:
            names.extend(_extract_team_names_from_upload(upload))
        except Exception as exc:
            flash(f"อ่านไฟล์รายชื่อไม่ได้: {exc}", "danger")
            return redirect(url_for("tcenter.tournament_dashboard", tournament_id=tournament.id))
    names = _normalize_names(names)
    if not names:
        flash("ไม่พบรายชื่อทีมที่จะเพิ่ม", "warning")
        return redirect(url_for("tcenter.tournament_dashboard", tournament_id=tournament.id))

    existing_keys = {team.name.casefold() for team in tournament.master_teams}
    added = 0
    for name in names:
        if name.casefold() in existing_keys:
            continue
        db.session.add(TournamentMasterTeam(tournament_id=tournament.id, name=name))
        existing_keys.add(name.casefold())
        added += 1
    db.session.flush()
    _ensure_all_event_entries(tournament)
    db.session.commit()
    flash(f"เพิ่มทีมกลาง {added} ทีม และเลือกเข้าทุกอีเวนต์ไว้ก่อนแล้ว", "success")
    return redirect(url_for("tcenter.tournament_dashboard", tournament_id=tournament.id))


@tcenter_bp.route("/tournament/<int:tournament_id>/team/<int:team_id>/delete", methods=["POST"])
@login_required
def delete_master_team(tournament_id: int, team_id: int):
    denied = _require_admin_redirect()
    if denied:
        return denied
    team = TournamentMasterTeam.query.filter_by(id=team_id, tournament_id=tournament_id).first_or_404()
    db.session.delete(team)
    db.session.commit()
    flash("ลบทีมออกจากรายชื่อกลางแล้ว", "success")
    return redirect(url_for("tcenter.tournament_dashboard", tournament_id=tournament_id))


@tcenter_bp.route("/tournament/<int:tournament_id>/event/add", methods=["POST"])
@login_required
def add_tournament_event(tournament_id: int):
    denied = _require_admin_redirect()
    if denied:
        return denied
    tournament = Tournament.query.get_or_404(tournament_id)
    name = (request.form.get("name") or "").strip()
    competition_format = (request.form.get("competition_format") or "round_robin").strip()
    if competition_format not in FORMAT_LABELS:
        competition_format = "round_robin"
    if not name:
        flash("กรุณากรอกชื่ออีเวนต์", "warning")
        return redirect(url_for("tcenter.tournament_dashboard", tournament_id=tournament.id))

    position = (db.session.query(func.max(TournamentEvent.position)).filter_by(tournament_id=tournament.id).scalar() or 0) + 1
    event = TournamentEvent(
        tournament_id=tournament.id,
        name=name,
        category=(request.form.get("category") or "").strip() or None,
        sex=(request.form.get("sex") or "").strip() or None,
        age_group=(request.form.get("age_group") or "").strip() or None,
        position=position,
        status="draft",
    )
    db.session.add(event)
    db.session.flush()
    for master_team in tournament.master_teams:
        db.session.add(
            TournamentEventEntry(
                tournament_event_id=event.id,
                master_team_id=master_team.id,
                is_active=True,
            )
        )
    db.session.flush()

    selected = list(tournament.master_teams)
    if len(selected) >= 2:
        _create_stage(
            event,
            "รอบแรก",
            competition_format,
            (request.form.get("pairing_method") or "random").strip(),
            selected,
            rounds=max(1, request.form.get("rounds", type=int) or 3),
            group_count=max(1, request.form.get("group_count", type=int) or 1),
            advance_per_group=max(1, request.form.get("advance_per_group", type=int) or 2),
        )
    db.session.commit()
    flash("เพิ่มอีเวนต์แล้ว ทุกทีมถูกเลือกไว้ก่อน สามารถเอาทีมที่ไม่ส่งออกได้", "success")
    return redirect(url_for("tcenter.event_roster", tournament_event_id=event.id))


@tcenter_bp.route("/tournament-event/<int:tournament_event_id>/delete", methods=["POST"])
@login_required
def delete_tournament_event(tournament_event_id: int):
    denied = _require_admin_redirect()
    if denied:
        return denied
    event = TournamentEvent.query.get_or_404(tournament_event_id)
    tournament_id = event.tournament_id
    db.session.delete(event)
    db.session.commit()
    flash("ลบอีเวนต์ออกจากทัวร์นาเมนต์แล้ว", "success")
    return redirect(url_for("tcenter.tournament_dashboard", tournament_id=tournament_id))


@tcenter_bp.route("/tournament-event/<int:tournament_event_id>/roster", methods=["GET", "POST"])
@login_required
def event_roster(tournament_event_id: int):
    event = TournamentEvent.query.get_or_404(tournament_event_id)
    if request.method == "POST":
        denied = _require_admin_redirect()
        if denied:
            return denied
        selected_ids = {int(raw) for raw in request.form.getlist("team_ids") if str(raw).isdigit()}
        stage = event.stages[-1] if event.stages else None
        had_matches = bool(stage and stage.engine_event_id and Match.query.filter_by(event_id=stage.engine_event_id).count())
        if had_matches and request.form.get("confirm_reset") != "1":
            flash("อีเวนต์นี้มีการประกบคู่แล้ว กรุณาติ๊กยืนยันล้างตารางเดิมก่อนเปลี่ยนทีม", "warning")
            return redirect(url_for("tcenter.event_roster", tournament_event_id=event.id))

        for entry in event.entries:
            entry.is_active = entry.master_team_id in selected_ids
        active = _active_master_teams(event)
        if len(active) < 2:
            flash("อีเวนต์ต้องมีอย่างน้อย 2 ทีม", "warning")
            return redirect(url_for("tcenter.event_roster", tournament_event_id=event.id))

        if stage:
            _sync_stage_engine_teams(stage, active)
            stage.status = "ready"
        event.status = "ready"
        db.session.commit()
        flash("บันทึกรายชื่อทีมของอีเวนต์แล้ว", "success")
        return redirect(_stage_open_url(stage) if stage else url_for("tcenter.new_stage", tournament_event_id=event.id))

    return render_template("tournament_event_roster.html", tournament_event=event)


@tcenter_bp.route("/tournament-event/<int:tournament_event_id>/stage/new", methods=["GET", "POST"])
@login_required
def new_stage(tournament_event_id: int):
    event = TournamentEvent.query.get_or_404(tournament_event_id)
    if request.method == "POST":
        denied = _require_admin_redirect()
        if denied:
            return denied
        selected_master_ids = {int(raw) for raw in request.form.getlist("master_team_ids") if str(raw).isdigit()}
        selected = [team for team in event.tournament.master_teams if team.id in selected_master_ids]
        if len(selected) < 2:
            flash("กรุณาเลือกอย่างน้อย 2 ทีมสำหรับ Stage ใหม่", "warning")
            return redirect(url_for("tcenter.new_stage", tournament_event_id=event.id))
        competition_format = request.form.get("competition_format") or "round_robin"
        if competition_format not in FORMAT_LABELS:
            competition_format = "round_robin"
        stage = _create_stage(
            event,
            (request.form.get("name") or "").strip() or "รอบถัดไป",
            competition_format,
            (request.form.get("pairing_method") or "random").strip(),
            selected,
            source_stage_id=request.form.get("source_stage_id", type=int),
            rounds=max(1, request.form.get("rounds", type=int) or 3),
            group_count=max(1, request.form.get("group_count", type=int) or 1),
            advance_per_group=max(1, request.form.get("advance_per_group", type=int) or 2),
        )
        db.session.commit()
        flash(f"สร้าง {stage.name} แบบ {FORMAT_LABELS[stage.competition_format]} แล้ว", "success")
        return redirect(_stage_open_url(stage))

    source_stage_id = request.args.get("source_stage_id", type=int)
    source_stage = CompetitionStage.query.get(source_stage_id) if source_stage_id else None
    candidates = _stage_candidates(source_stage) if source_stage else [
        {"id": team.id, "name": team.name, "label": "ทีมกลาง"} for team in _active_master_teams(event)
    ]
    return render_template(
        "tournament_stage_new.html",
        tournament_event=event,
        source_stage=source_stage,
        candidates=candidates,
    )


def _legacy_rows_for_stage(stage: CompetitionStage) -> list[dict[str, Any]]:
    teams = _stage_team_query(stage).order_by(Team.id.asc()).all()
    config = _stage_config(stage)
    seed_map = config.get("team_seed_map") or {}
    return [
        {
            "team_id": team.id,
            "team_name": team.name,
            "rank": idx,
            "seed": seed_map.get(team.name) or idx,
        }
        for idx, team in enumerate(teams, start=1)
    ]


@tcenter_bp.route("/stage/<int:stage_id>/start")
@login_required
def start_legacy_stage(stage_id: int):
    stage = CompetitionStage.query.get_or_404(stage_id)
    if stage.competition_format == "round_robin":
        return redirect(url_for("tcenter.round_robin_stage", stage_id=stage.id))
    if stage.competition_format == "swiss":
        stage.status = "running"
        stage.tournament_event.status = "running"
        db.session.commit()
        return redirect(url_for("event_detail", event_id=stage.engine_event_id))

    if stage.legacy_playoff_id:
        return redirect(url_for("playoff_detail", playoff_id=stage.legacy_playoff_id))

    denied = _require_admin_redirect()
    if denied:
        return denied
    service = (current_app.extensions.get("tournament_center_services") or {}).get("create_playoff")
    if not service:
        flash("ไม่พบเครื่องยนต์ Playoff เดิม", "danger")
        return redirect(url_for("tcenter.tournament_dashboard", tournament_id=stage.tournament_event.tournament_id))
    rows = _legacy_rows_for_stage(stage)
    try:
        playoff_id = service(
            stage.engine_event,
            rows,
            stage.name,
            stage.competition_format,
            stage.pairing_method if stage.pairing_method in {"seed", "random"} else "seed",
            False,
            None,
        )
    except Exception as exc:
        db.session.rollback()
        flash(f"สร้างสายการแข่งขันไม่ได้: {exc}", "danger")
        return redirect(url_for("tcenter.tournament_dashboard", tournament_id=stage.tournament_event.tournament_id))
    stage.legacy_playoff_id = playoff_id
    stage.status = "running"
    stage.tournament_event.status = "running"
    db.session.commit()
    return redirect(url_for("playoff_detail", playoff_id=playoff_id))


# -----------------------------------------------------------------------------
# Round Robin new engine
# -----------------------------------------------------------------------------

def _balanced_sizes(total: int, group_count: int) -> list[int]:
    group_count = max(1, min(group_count, max(1, total)))
    base, remainder = divmod(total, group_count)
    return [base + (1 if index < remainder else 0) for index in range(group_count)]


def _snake_assign(teams: list[Team], group_count: int) -> list[list[Team]]:
    groups: list[list[Team]] = [[] for _ in range(group_count)]
    if group_count == 1:
        return [teams]
    direction = 1
    group_index = 0
    for team in teams:
        groups[group_index].append(team)
        if direction == 1:
            if group_index == group_count - 1:
                direction = -1
            else:
                group_index += 1
        else:
            if group_index == 0:
                direction = 1
            else:
                group_index -= 1
    return groups


def _round_robin_number_pairs(team_count: int) -> list[list[tuple[int, int | None]]]:
    if team_count < 2:
        return []
    if team_count == 5:
        return [
            [(1, 2), (3, 4), (5, None)],
            [(1, 3), (2, 5), (4, None)],
            [(1, 5), (2, 4), (3, None)],
            [(1, 4), (3, 5), (2, None)],
            [(2, 3), (4, 5), (1, None)],
        ]

    numbers: list[int | None] = list(range(1, team_count + 1))
    if team_count % 2:
        numbers.append(None)
    size = len(numbers)
    rounds: list[list[tuple[int, int | None]]] = []
    rotation = list(numbers)
    for _round_index in range(size - 1):
        real_pairs: list[tuple[int, int | None]] = []
        bye_pair: tuple[int, int | None] | None = None
        for index in range(size // 2):
            a = rotation[index]
            b = rotation[size - 1 - index]
            if a is None or b is None:
                real = b if a is None else a
                if real is not None:
                    bye_pair = (int(real), None)
                continue
            left, right = sorted((int(a), int(b)))
            real_pairs.append((left, right))
        real_pairs.sort(key=lambda pair: pair[0])
        if bye_pair:
            real_pairs.append(bye_pair)
        rounds.append(real_pairs)
        rotation = [rotation[0], rotation[-1], *rotation[1:-1]]
    return rounds


def _clear_rr(stage: CompetitionStage) -> None:
    if stage.engine_event_id:
        Match.query.filter_by(event_id=stage.engine_event_id).delete(synchronize_session=False)
    for group in RoundRobinGroup.query.filter_by(stage_id=stage.id).all():
        db.session.delete(group)
    db.session.flush()


def _assign_rr_groups(stage: CompetitionStage, method: str, manual_groups: list[list[int]] | None = None) -> None:
    teams = _stage_team_query(stage).order_by(Team.id.asc()).all()
    if len(teams) < 2:
        raise ValueError("Round Robin ต้องมีอย่างน้อย 2 ทีม")
    config = _stage_config(stage)
    group_count = max(1, min(int(config.get("group_count") or 1), len(teams)))
    seed_map = config.get("team_seed_map") or {}

    if method == "manual":
        if not manual_groups:
            raise ValueError("ยังไม่ได้กำหนดทีมลงกลุ่ม")
        team_by_id = {team.id: team for team in teams}
        assigned_ids = [team_id for group in manual_groups for team_id in group]
        if len(set(assigned_ids)) != len(teams) or set(assigned_ids) != set(team_by_id):
            raise ValueError("ต้องลงทีมทุกทีมให้ครบและห้ามซ้ำ")
        grouped_teams = [[team_by_id[team_id] for team_id in group] for group in manual_groups]
    elif method == "snake":
        ordered = sorted(teams, key=lambda team: (seed_map.get(team.name) or 10**9, team.name))
        grouped_teams = _snake_assign(ordered, group_count)
    else:
        ordered = list(teams)
        if method == "seed":
            ordered.sort(key=lambda team: (seed_map.get(team.name) or 10**9, team.name))
        else:
            random.shuffle(ordered)
        sizes = _balanced_sizes(len(ordered), group_count)
        grouped_teams = []
        cursor = 0
        for size in sizes:
            grouped_teams.append(ordered[cursor : cursor + size])
            cursor += size

    _clear_rr(stage)
    for index, group_teams in enumerate(grouped_teams):
        group = RoundRobinGroup(stage_id=stage.id, name=chr(65 + index), position=index + 1)
        db.session.add(group)
        db.session.flush()
        for slot_no, team in enumerate(group_teams, start=1):
            db.session.add(RoundRobinGroupMember(group_id=group.id, team_id=team.id, slot_no=slot_no))
    stage.pairing_method = method
    db.session.flush()


def _parse_clock(value: str) -> datetime:
    try:
        return datetime.strptime(value, "%H:%M")
    except Exception:
        return datetime.strptime("09:00", "%H:%M")


def _generate_rr_matches(stage: CompetitionStage) -> None:
    tournament = stage.tournament_event.tournament
    config = _stage_config(stage)
    fields = _tournament_fields(tournament)
    first_time = _parse_clock(str(config.get("first_time") or "09:00"))
    match_minutes = max(1, int(config.get("match_minutes") or 75))
    break_minutes = max(0, int(config.get("break_minutes") or 15))
    step = timedelta(minutes=match_minutes + break_minutes)

    Match.query.filter_by(event_id=stage.engine_event_id).delete(synchronize_session=False)
    db.session.flush()

    round_entries: dict[int, list[dict[str, Any]]] = defaultdict(list)
    rr_groups = RoundRobinGroup.query.filter_by(stage_id=stage.id).order_by(RoundRobinGroup.position).all()
    for group in rr_groups:
        members = list(group.members)
        by_slot = {member.slot_no: member.team for member in members}
        for round_no, pairs in enumerate(_round_robin_number_pairs(len(members)), start=1):
            for pair_order, (slot1, slot2) in enumerate(pairs, start=1):
                round_entries[round_no].append(
                    {
                        "group": group.name,
                        "pair_order": pair_order,
                        "team1": by_slot[slot1],
                        "team2": by_slot.get(slot2) if slot2 else None,
                    }
                )

    schedule: dict[str, dict[str, Any]] = {}
    time_cursor = first_time
    for round_no in sorted(round_entries):
        entries = sorted(round_entries[round_no], key=lambda row: (row["group"], row["pair_order"]))
        real_entries = [row for row in entries if row["team2"] is not None]
        bye_entries = [row for row in entries if row["team2"] is None]
        wave_count = max(1, math.ceil(len(real_entries) / len(fields))) if fields else 1

        for index, row in enumerate(real_entries):
            wave = index // max(1, len(fields))
            field_no = fields[index % len(fields)] if fields else None
            match = Match(
                event_id=stage.engine_event_id,
                round=round_no,
                team1_id=row["team1"].id,
                team2_id=row["team2"].id,
                team1_score=None,
                team2_score=None,
                is_locked=False,
                is_manual=(stage.pairing_method == "manual"),
                field=field_no,
            )
            db.session.add(match)
            db.session.flush()
            schedule[str(match.id)] = {
                "group": row["group"],
                "time": (time_cursor + wave * step).strftime("%H:%M"),
                "field_label": _format_field(tournament, field_no),
                "bye": False,
            }

        for row in bye_entries:
            match = Match(
                event_id=stage.engine_event_id,
                round=round_no,
                team1_id=row["team1"].id,
                team2_id=None,
                team1_score=None,
                team2_score=None,
                is_locked=True,
                is_manual=(stage.pairing_method == "manual"),
                field=None,
            )
            db.session.add(match)
            db.session.flush()
            schedule[str(match.id)] = {
                "group": row["group"],
                "time": "พัก",
                "field_label": "-",
                "bye": True,
            }
        time_cursor += wave_count * step

    config["schedule"] = schedule
    _save_stage_config(stage, config)
    stage.status = "running"
    stage.tournament_event.status = "running"
    db.session.flush()


def _rr_group_for_team(stage: CompetitionStage) -> dict[int, str]:
    result: dict[int, str] = {}
    for group in RoundRobinGroup.query.filter_by(stage_id=stage.id).order_by(RoundRobinGroup.position).all():
        for member in group.members:
            result[member.team_id] = group.name
    return result


def _rr_stats_for_group(stage: CompetitionStage, group: RoundRobinGroup) -> tuple[list[dict[str, Any]], list[str]]:
    team_ids = [member.team_id for member in group.members]
    team_lookup = {member.team_id: member.team for member in group.members}
    stats: dict[int, dict[str, Any]] = {
        team_id: {
            "team_id": team_id,
            "team_name": team_lookup[team_id].name,
            "slot": next(member.slot_no for member in group.members if member.team_id == team_id),
            "played": 0,
            "wins": 0,
            "losses": 0,
            "pf": 0,
            "pa": 0,
            "diff": 0,
            "rank": 0,
            "qualified": False,
            "unresolved": False,
        }
        for team_id in team_ids
    }
    matches = (
        Match.query.filter(
            Match.event_id == stage.engine_event_id,
            Match.team1_id.in_(team_ids),
            Match.team2_id.in_(team_ids),
            Match.is_locked.is_(True),
        )
        .order_by(Match.round, Match.id)
        .all()
    )
    match_map: dict[frozenset[int], Match] = {}
    for match in matches:
        if match.team2_id is None or match.team1_score is None or match.team2_score is None:
            continue
        s1, s2 = int(match.team1_score), int(match.team2_score)
        a, b = stats[match.team1_id], stats[match.team2_id]
        a["played"] += 1
        b["played"] += 1
        a["pf"] += s1
        a["pa"] += s2
        b["pf"] += s2
        b["pa"] += s1
        if s1 > s2:
            a["wins"] += 1
            b["losses"] += 1
        elif s2 > s1:
            b["wins"] += 1
            a["losses"] += 1
        match_map[frozenset((match.team1_id, match.team2_id))] = match
    for row in stats.values():
        row["diff"] = row["pf"] - row["pa"]

    notes: list[str] = []
    buckets: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in stats.values():
        buckets[row["wins"]].append(row)
    ordered: list[dict[str, Any]] = []

    for win_count in sorted(buckets.keys(), reverse=True):
        tied = buckets[win_count]
        if len(tied) == 1:
            ordered.extend(tied)
            continue

        tied_ids = {row["team_id"] for row in tied}
        if len(tied) == 2:
            key = frozenset(tied_ids)
            match = match_map.get(key)
            if match and match.team1_score != match.team2_score:
                winner_id = match.team1_id if match.team1_score > match.team2_score else match.team2_id
                tied.sort(key=lambda row: (row["team_id"] != winner_id, -row["diff"], row["team_name"]))
                notes.append(
                    f"{tied[0]['team_name']} อยู่เหนือ {tied[1]['team_name']} จากผลพบกันโดยตรง"
                )
            else:
                tied.sort(key=lambda row: (-row["diff"], -row["pf"], row["team_name"]))
                if len(tied) == 2 and tied[0]["diff"] == tied[1]["diff"]:
                    tied[0]["unresolved"] = tied[1]["unresolved"] = True
                    notes.append(f"{tied[0]['team_name']} และ {tied[1]['team_name']} ยังเสมอกัน ต้องให้ผู้จัดตัดสิน")
            ordered.extend(tied)
            continue

        mini: dict[int, dict[str, int]] = {team_id: {"wins": 0, "pf": 0, "pa": 0} for team_id in tied_ids}
        for match in matches:
            if match.team1_id not in tied_ids or match.team2_id not in tied_ids:
                continue
            if match.team1_score is None or match.team2_score is None:
                continue
            s1, s2 = int(match.team1_score), int(match.team2_score)
            mini[match.team1_id]["pf"] += s1
            mini[match.team1_id]["pa"] += s2
            mini[match.team2_id]["pf"] += s2
            mini[match.team2_id]["pa"] += s1
            if s1 > s2:
                mini[match.team1_id]["wins"] += 1
            elif s2 > s1:
                mini[match.team2_id]["wins"] += 1
        for row in tied:
            values = mini[row["team_id"]]
            row["mini_wins"] = values["wins"]
            row["mini_diff"] = values["pf"] - values["pa"]
        tied.sort(
            key=lambda row: (
                -row.get("mini_wins", 0),
                -row.get("mini_diff", 0),
                -row["diff"],
                -row["pf"],
                row["team_name"],
            )
        )
        notes.append(
            "ทีมที่ชนะเท่ากัน 3 ทีมขึ้นไป ใช้ตารางเฉพาะคู่กรณี: "
            + ", ".join(
                f"{row['team_name']} ชนะคู่กรณี {row.get('mini_wins', 0)} ผลต่าง {row.get('mini_diff', 0):+d}"
                for row in tied
            )
        )
        for index in range(len(tied) - 1):
            a, b = tied[index], tied[index + 1]
            key_a = (a.get("mini_wins", 0), a.get("mini_diff", 0), a["diff"])
            key_b = (b.get("mini_wins", 0), b.get("mini_diff", 0), b["diff"])
            if key_a == key_b:
                a["unresolved"] = b["unresolved"] = True
        ordered.extend(tied)

    current_rank = 0
    previous_key = None
    for index, row in enumerate(ordered, start=1):
        rank_key = (
            row["wins"],
            row.get("mini_wins"),
            row.get("mini_diff"),
            row["diff"],
        )
        if row["unresolved"] and previous_key == rank_key:
            row["rank"] = current_rank
        else:
            current_rank = index
            row["rank"] = current_rank
        previous_key = rank_key

    advance = max(1, int(_stage_config(stage).get("advance_per_group") or 2))
    for row in ordered:
        row["qualified"] = row["rank"] <= advance and not row["unresolved"]
    return ordered, notes


def _rr_view_data(stage: CompetitionStage) -> dict[str, Any]:
    config = _stage_config(stage)
    group_by_team = _rr_group_for_team(stage)
    slot_by_team: dict[int, str] = {}
    rr_groups = RoundRobinGroup.query.filter_by(stage_id=stage.id).order_by(RoundRobinGroup.position).all()
    for group in rr_groups:
        for member in group.members:
            slot_by_team[member.team_id] = f"{group.name}{member.slot_no}"
    matches = Match.query.filter_by(event_id=stage.engine_event_id).order_by(Match.round, Match.id).all()
    schedule_map = config.get("schedule") or {}
    rounds: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for match in matches:
        meta = schedule_map.get(str(match.id)) or {}
        rounds[match.round].append(
            {
                "match": match,
                "group": meta.get("group") or group_by_team.get(match.team1_id) or "-",
                "time": meta.get("time") or "-",
                "field": meta.get("field_label") or _format_field(stage.tournament_event.tournament, match.field),
                "bye": match.team2_id is None,
                "slot1": slot_by_team.get(match.team1_id, "-"),
                "slot2": slot_by_team.get(match.team2_id, "-") if match.team2_id else "-",
            }
        )

    standings: dict[str, list[dict[str, Any]]] = {}
    tie_notes: dict[str, list[str]] = {}
    matrices: dict[str, dict[str, Any]] = {}
    for group in rr_groups:
        rows, notes = _rr_stats_for_group(stage, group)
        standings[group.name] = rows
        tie_notes[group.name] = notes
        matrix_scores: dict[tuple[int, int], str] = {}
        for match in matches:
            if match.team2_id is None:
                continue
            if match.team1_id not in {member.team_id for member in group.members}:
                continue
            if match.team1_score is None or match.team2_score is None:
                continue
            matrix_scores[(match.team1_id, match.team2_id)] = f"{match.team1_score}-{match.team2_score}"
            matrix_scores[(match.team2_id, match.team1_id)] = f"{match.team2_score}-{match.team1_score}"
        members = list(group.members)
        stats_by_team = {row["team_id"]: row for row in rows}

        # Matrix แบบ Excel: หา "คู่กรณี" จากทีมที่จำนวนชนะเท่ากัน
        # และคำนวณเฉพาะผลที่พบกันภายในกลุ่มคู่กรณีนั้น
        win_buckets: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            win_buckets[int(row.get("wins") or 0)].append(row)

        tie_groups: list[dict[str, Any]] = []
        tie_pairs: set[tuple[int, int]] = set()
        case_stats: dict[int, dict[str, int]] = {
            member.team_id: {"wins": 0, "pf": 0, "pa": 0, "diff": 0}
            for member in members
        }

        for win_count in sorted(win_buckets.keys(), reverse=True):
            tied_rows = win_buckets[win_count]
            if len(tied_rows) < 2:
                continue
            tied_ids = {row["team_id"] for row in tied_rows}
            local_stats = {
                team_id: {"wins": 0, "pf": 0, "pa": 0, "diff": 0}
                for team_id in tied_ids
            }
            for match in matches:
                if match.team2_id is None:
                    continue
                if match.team1_id not in tied_ids or match.team2_id not in tied_ids:
                    continue
                if match.team1_score is None or match.team2_score is None:
                    continue
                s1, s2 = int(match.team1_score), int(match.team2_score)
                local_stats[match.team1_id]["pf"] += s1
                local_stats[match.team1_id]["pa"] += s2
                local_stats[match.team2_id]["pf"] += s2
                local_stats[match.team2_id]["pa"] += s1
                if s1 > s2:
                    local_stats[match.team1_id]["wins"] += 1
                elif s2 > s1:
                    local_stats[match.team2_id]["wins"] += 1
            for team_id, values in local_stats.items():
                values["diff"] = values["pf"] - values["pa"]
                case_stats[team_id] = values
            for row_id in tied_ids:
                for col_id in tied_ids:
                    if row_id != col_id:
                        tie_pairs.add((row_id, col_id))
            tie_groups.append(
                {
                    "wins": win_count,
                    "rows": tied_rows,
                    "team_ids": tied_ids,
                    "names": [row["team_name"] for row in tied_rows],
                }
            )

        matrices[group.name] = {
            "members": members or [],
            "scores": matrix_scores or {},
            "stats": stats_by_team or {},
            "case_stats": case_stats or {},
            "tie_pairs": tie_pairs or set(),
            "tie_groups": tie_groups or [],
        }

    return {
        "rounds": dict(rounds),
        "standings": standings,
        "tie_notes": tie_notes,
        "matrices": matrices,
        "config": config,
    }


@tcenter_bp.route("/stage/<int:stage_id>/round-robin", methods=["GET", "POST"])
@login_required
def round_robin_stage(stage_id: int):
    stage = CompetitionStage.query.get_or_404(stage_id)
    if stage.competition_format != "round_robin":
        return redirect(_stage_open_url(stage))
    teams = _stage_team_query(stage).order_by(Team.name.asc()).all()
    config = _stage_config(stage)

    if request.method == "POST":
        denied = _require_admin_redirect()
        if denied:
            return denied
        action = request.form.get("action") or "random"
        config["group_count"] = max(1, request.form.get("group_count", type=int) or int(config.get("group_count") or 1))
        config["advance_per_group"] = max(1, request.form.get("advance_per_group", type=int) or int(config.get("advance_per_group") or 2))
        config["first_time"] = request.form.get("first_time") or config.get("first_time") or "09:00"
        config["match_minutes"] = max(1, request.form.get("match_minutes", type=int) or int(config.get("match_minutes") or 75))
        config["break_minutes"] = max(0, request.form.get("break_minutes", type=int) or int(config.get("break_minutes") or 15))
        _save_stage_config(stage, config)

        manual_groups = None
        if action == "manual":
            manual_groups = []
            for group_index in range(config["group_count"]):
                values = [int(raw) for raw in request.form.getlist(f"group_{group_index}") if str(raw).isdigit()]
                manual_groups.append(values)
        try:
            _assign_rr_groups(stage, action, manual_groups=manual_groups)
            _generate_rr_matches(stage)
            db.session.commit()
        except Exception as exc:
            db.session.rollback()
            flash(f"สร้าง Round Robin ไม่สำเร็จ: {exc}", "danger")
            return redirect(url_for("tcenter.round_robin_stage", stage_id=stage.id))
        flash("แบ่งกลุ่มและสร้างตาราง Round Robin ใหม่แล้ว", "success")
        return redirect(url_for("tcenter.round_robin_stage", stage_id=stage.id))

    view = _rr_view_data(stage) if stage.rr_groups else None
    return render_template(
        "round_robin_center.html",
        stage=stage,
        teams=teams,
        view=view,
    )


@tcenter_bp.route("/api/stage/<int:stage_id>/round-robin/score/<int:match_id>", methods=["POST"])
@login_required
def round_robin_score(stage_id: int, match_id: int):
    if not _admin_allowed():
        return jsonify({"ok": False, "error": "permission"}), 403
    stage = CompetitionStage.query.get_or_404(stage_id)
    match = Match.query.filter_by(id=match_id, event_id=stage.engine_event_id).first_or_404()
    if match.team2_id is None:
        return jsonify({"ok": False, "error": "bye"}), 400
    payload = request.get_json(silent=True) or request.form
    try:
        s1 = int(payload.get("team1_score"))
        s2 = int(payload.get("team2_score"))
    except Exception:
        return jsonify({"ok": False, "error": "invalid_score"}), 400
    if not (0 <= s1 <= 13 and 0 <= s2 <= 13):
        return jsonify({"ok": False, "error": "score_range"}), 400
    match.team1_score = s1
    match.team2_score = s2
    match.is_locked = True
    db.session.commit()

    socketio = current_app.extensions.get("socketio")
    if socketio:
        socketio.emit(
            "rr_score_updated",
            {
                "stage_id": stage.id,
                "match_id": match.id,
                "team1_score": s1,
                "team2_score": s2,
                "updated_at": datetime.utcnow().isoformat(),
            },
            to=f"rr_stage_{stage.id}",
        )
    return jsonify({"ok": True})


@tcenter_bp.route("/stage/<int:stage_id>/round-robin/config", methods=["POST"])
@login_required
def round_robin_config(stage_id: int):
    denied = _require_admin_redirect()
    if denied:
        return denied
    stage = CompetitionStage.query.get_or_404(stage_id)
    config = _stage_config(stage)
    config["advance_per_group"] = max(1, request.form.get("advance_per_group", type=int) or 2)
    _save_stage_config(stage, config)
    db.session.commit()
    flash("บันทึกการตั้งค่า Round Robin แล้ว", "success")
    return redirect(url_for("tcenter.round_robin_stage", stage_id=stage.id))


def _stage_candidates(stage: CompetitionStage | None) -> list[dict[str, Any]]:
    if not stage:
        return []
    if stage.competition_format == "round_robin" and stage.rr_groups:
        result: list[dict[str, Any]] = []
        for group in stage.rr_groups:
            rows, _notes = _rr_stats_for_group(stage, group)
            for row in rows:
                result.append(
                    {
                        "id": row["team_id"],
                        "name": row["team_name"],
                        "label": f"{group.name}{row['rank']} · ชนะ {row['wins']} · ผลต่าง {row['diff']:+d}",
                        "checked": row["qualified"],
                    }
                )
        return result

    if stage.legacy_playoff_id:
        fetcher = (current_app.extensions.get("tournament_center_services") or {}).get("fetch_playoff")
        if fetcher:
            try:
                view = fetcher(stage.legacy_playoff_id)
                latest = (view or {}).get("round_views", [])[-1] if (view or {}).get("round_views") else None
                rows: list[dict[str, Any]] = []
                seen: set[Any] = set()
                if latest:
                    for group_view in latest.get("group_views", []):
                        result = group_view.get("result") or {}
                        qualified = [result.get("winner")]
                        if stage.competition_format == "double_knockout":
                            qualified.append(result.get("second"))
                        for position, payload in enumerate(qualified, start=1):
                            if not payload:
                                continue
                            key = payload.get("team_id") or payload.get("team_name")
                            if key in seen:
                                continue
                            seen.add(key)
                            rows.append({
                                "id": payload.get("team_id"),
                                "name": payload.get("team_name"),
                                "label": f"ผ่านสาย {group_view.get('group_no')} · ลำดับ {position}",
                                "checked": True,
                            })
                if rows:
                    return rows
            except Exception:
                pass

    if stage.competition_format == "swiss" and stage.engine_event_id:
        calculator = (current_app.extensions.get("tournament_center_services") or {}).get("calculate_standings")
        if calculator:
            try:
                rows = calculator(stage.engine_event_id)
                return [
                    {
                        "id": row.get("team_id"),
                        "name": row.get("team_name") or row.get("name"),
                        "label": f"อันดับ {row.get('rank') or index}",
                        "checked": False,
                    }
                    for index, row in enumerate(rows, start=1)
                ]
            except Exception:
                pass
    return [
        {"id": team.id, "name": team.name, "label": "เลือกด้วยมือ", "checked": False}
        for team in _stage_team_query(stage).order_by(Team.name.asc()).all()
    ]


@tcenter_bp.route("/stage/<int:stage_id>/next", methods=["GET", "POST"])
@login_required
def stage_next(stage_id: int):
    stage = CompetitionStage.query.get_or_404(stage_id)
    candidates = _stage_candidates(stage)
    if request.method == "POST":
        denied = _require_admin_redirect()
        if denied:
            return denied
        selected_engine_ids = {int(raw) for raw in request.form.getlist("team_ids") if str(raw).isdigit()}
        selected_names = [row["name"] for row in candidates if row["id"] in selected_engine_ids]
        master_by_name = {team.name: team for team in stage.tournament_event.tournament.master_teams}
        selected_master = [master_by_name[name] for name in selected_names if name in master_by_name]
        if len(selected_master) < 2:
            flash("กรุณาเลือกอย่างน้อย 2 ทีมสำหรับ Stage ถัดไป", "warning")
            return redirect(url_for("tcenter.stage_next", stage_id=stage.id))
        competition_format = request.form.get("competition_format") or "knockout"
        if competition_format not in FORMAT_LABELS:
            competition_format = "knockout"
        next_stage = _create_stage(
            stage.tournament_event,
            (request.form.get("name") or "").strip() or "Playoff",
            competition_format,
            (request.form.get("pairing_method") or "seed").strip(),
            selected_master,
            source_stage_id=stage.id,
            rounds=max(1, request.form.get("rounds", type=int) or 3),
            group_count=max(1, request.form.get("group_count", type=int) or 1),
            advance_per_group=max(1, request.form.get("advance_per_group", type=int) or 2),
        )
        stage.status = "qualification_done"
        db.session.commit()
        flash(f"ดึง {len(selected_master)} ทีมไปสร้าง {next_stage.name} แล้ว", "success")
        return redirect(_stage_open_url(next_stage))
    return render_template("tournament_stage_next.html", stage=stage, candidates=candidates)


@tcenter_bp.route("/tournament/<int:tournament_id>/random-ready", methods=["POST"])
@login_required
def random_ready_stages(tournament_id: int):
    denied = _require_admin_redirect()
    if denied:
        return denied
    tournament = Tournament.query.get_or_404(tournament_id)
    results: list[str] = []
    errors: list[str] = []
    for event in tournament.events:
        if not event.stages:
            continue
        stage = event.stages[-1]
        if stage.status not in {"draft", "ready"}:
            continue
        try:
            if stage.competition_format == "round_robin":
                _assign_rr_groups(stage, stage.pairing_method if stage.pairing_method in {"random", "seed", "snake"} else "random")
                _generate_rr_matches(stage)
                results.append(f"{event.name}: Round Robin")
            elif stage.competition_format == "swiss":
                service = (current_app.extensions.get("tournament_center_services") or {}).get("swiss_pairing")
                if not service:
                    raise ValueError("ไม่พบเครื่องยนต์ Swiss")
                ok, message = service(stage.engine_event_id, 1, False)
                if not ok:
                    raise ValueError(message)
                stage.status = "running"
                event.status = "running"
                results.append(f"{event.name}: Swiss รอบแรก")
            elif stage.competition_format in {"knockout", "double_knockout"}:
                service = (current_app.extensions.get("tournament_center_services") or {}).get("create_playoff")
                if not service:
                    raise ValueError("ไม่พบเครื่องยนต์ Playoff")
                rows = _legacy_rows_for_stage(stage)
                stage.legacy_playoff_id = service(
                    stage.engine_event,
                    rows,
                    stage.name,
                    stage.competition_format,
                    stage.pairing_method if stage.pairing_method in {"seed", "random"} else "random",
                    False,
                    None,
                )
                stage.status = "running"
                event.status = "running"
                results.append(f"{event.name}: {FORMAT_LABELS[stage.competition_format]}")
            db.session.commit()
        except Exception as exc:
            db.session.rollback()
            errors.append(f"{event.name}: {exc}")
            continue
    if results:
        flash("Random รายการที่พร้อมแล้ว: " + " · ".join(results), "success")
    if errors:
        flash("รายการที่ทำไม่สำเร็จ: " + " · ".join(errors), "warning")
    return redirect(url_for("tcenter.tournament_dashboard", tournament_id=tournament.id))


def register_tournament_center(app, socketio, services: dict[str, Any] | None = None) -> None:
    app.register_blueprint(tcenter_bp)
    app.extensions["tournament_center_services"] = services or {}

    @socketio.on("join_rr_stage")
    def _join_rr_stage(payload):
        stage_id = int((payload or {}).get("stage_id") or 0)
        if stage_id:
            join_room(f"rr_stage_{stage_id}")
