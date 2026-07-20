# models.py
from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import text

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='user')
    start_time = db.Column(db.DateTime, nullable=True)
    end_time = db.Column(db.DateTime, nullable=True)

    def has_roles(self, *roles):
        return self.role in roles
    
    events = db.relationship(
    "Event",
    foreign_keys="Event.creator_id",
    backref="creator",
    lazy=True
)
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def is_viewer(self):
        return self.role == "viewer"

    def is_user(self):
        return self.role == "user"

    def is_admin(self):
        return self.role == "admin"

    def is_superadmin(self):
        return self.role == "superadmin"
    
    
class Event(db.Model):
    __tablename__ = "events"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    location = db.Column(db.String(100))
    category = db.Column(db.String(50))
    sex = db.Column(db.String(50))
    age_group = db.Column(db.String(50))
    rounds = db.Column(db.Integer)
    # รูปแบบการแข่งขันหลักของอีเวนต์: swiss / round_robin / double_knockout / knockout
    competition_format = db.Column(db.String(40), nullable=False, default="swiss")
    current_round = db.Column(db.Integer, default=1)
    date = db.Column(db.Date, nullable=True)
    auto_field_enabled = db.Column(db.Boolean, default=False)
    field_prefix = db.Column(db.String(10), default='')  # เช่น 'A', ''
    field_start = db.Column(db.Integer, default=1)
    field_max = db.Column(db.Integer, default=16)
    field_exclude = db.Column(db.String, default='')  # เช่น '3,7,11
    logo_filename = db.Column(db.Text)  # เก็บเป็น JSON list

    # สถานะจบอีเว้นท์แบบ manual: ไม่เดาจากรอบล่าสุดล็อกครบแล้ว
    is_finished = db.Column(db.Boolean, default=False, nullable=False)
    finished_at = db.Column(db.DateTime, nullable=True)
    finished_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    created_at = db.Column(db.DateTime, server_default=text('CURRENT_TIMESTAMP'), nullable=True)

    # เพิ่มบรรทัดนี้
    creator_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    tournament_id = db.Column(db.Integer, db.ForeignKey("tournaments.id"), nullable=True, index=True)

    teams = db.relationship("Team", backref="event", cascade="all, delete-orphan", lazy=True)
    matches = db.relationship("Match", backref="event", cascade="all, delete-orphan", lazy=True)



class Team(db.Model):
    __tablename__ = "teams"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    event_id = db.Column(db.Integer, db.ForeignKey("events.id"), nullable=False)


class Match(db.Model):
    __tablename__ = "matches"

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("events.id"), nullable=False)
    round = db.Column(db.Integer, nullable=False)

    team1_id = db.Column(db.Integer, db.ForeignKey("teams.id"), nullable=False)
    team2_id = db.Column(db.Integer, db.ForeignKey("teams.id"), nullable=True)  # None = Bye

    team1_score = db.Column(db.Integer, default=0)
    team2_score = db.Column(db.Integer, default=0)

    # คะแนนจากหน้าสกอร์การ์ดออนไลน์
    # autosave: แสดงสดในหน้า round แต่ยังไม่ให้ admin ยืนยัน
    # finish: เมื่อกดสิ้นสุดการแข่งขันและมีลายเซ็นครบ จึงเป็นคะแนนรอยืนยัน
    pending_team1_score = db.Column(db.Integer, nullable=True)
    pending_team2_score = db.Column(db.Integer, nullable=True)
    pending_is_submitted = db.Column(db.Boolean, default=False, nullable=False)
    pending_submitted_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    pending_submitted_at = db.Column(db.DateTime, nullable=True)
    team1_signature = db.Column(db.Text, nullable=True)
    team2_signature = db.Column(db.Text, nullable=True)
    scorer_signature = db.Column(db.Text, nullable=True)
    # รายละเอียดการลงคะแนนแบบ end-by-end จากหน้าสกอร์การ์ดออนไลน์
    score_ends = db.Column(db.Text, nullable=True)
    # token ลับสำหรับเปิดหน้าสกอร์การ์ดผ่าน QR โดยไม่ต้อง login
    scorecard_token = db.Column(db.String(80), unique=True, nullable=True, index=True)

    is_locked = db.Column(db.Boolean, default=False)
    field = db.Column(db.Integer, nullable=True)

    team1 = db.relationship("Team", foreign_keys=[team1_id], backref="matches_as_team1")
    team2 = db.relationship("Team", foreign_keys=[team2_id], backref="matches_as_team2")
    pending_submitted_by = db.relationship("User", foreign_keys=[pending_submitted_by_id])
    is_manual = db.Column(db.Boolean, default=True)  # เพื่อแยกจากการจับอัตโนมัติ


# -----------------------------------------------------------------------------
# Tournament Center V1
# -----------------------------------------------------------------------------
class Tournament(db.Model):
    __tablename__ = "tournaments"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(180), nullable=False)
    location = db.Column(db.String(180), nullable=True)
    start_date = db.Column(db.Date, nullable=True)
    end_date = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(30), nullable=False, default="active")
    field_prefix = db.Column(db.String(10), nullable=False, default="")
    field_start = db.Column(db.Integer, nullable=False, default=1)
    field_max = db.Column(db.Integer, nullable=False, default=16)
    field_exclude = db.Column(db.String(255), nullable=False, default="")
    creator_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    events = db.relationship(
        "TournamentEvent",
        backref="tournament",
        cascade="all, delete-orphan",
        lazy=True,
        order_by="TournamentEvent.position",
    )
    engine_events = db.relationship(
        "Event",
        backref="tournament",
        lazy=True,
        foreign_keys="Event.tournament_id",
        order_by="Event.date, Event.id",
    )
    master_teams = db.relationship(
        "TournamentMasterTeam",
        backref="tournament",
        cascade="all, delete-orphan",
        lazy=True,
        order_by="TournamentMasterTeam.name",
    )


class TournamentEvent(db.Model):
    __tablename__ = "tournament_events"

    id = db.Column(db.Integer, primary_key=True)
    tournament_id = db.Column(db.Integer, db.ForeignKey("tournaments.id"), nullable=False, index=True)
    name = db.Column(db.String(180), nullable=False)
    category = db.Column(db.String(80), nullable=True)
    sex = db.Column(db.String(50), nullable=True)
    age_group = db.Column(db.String(80), nullable=True)
    status = db.Column(db.String(30), nullable=False, default="draft")
    position = db.Column(db.Integer, nullable=False, default=1)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    entries = db.relationship(
        "TournamentEventEntry",
        backref="tournament_event",
        cascade="all, delete-orphan",
        lazy=True,
    )
    stages = db.relationship(
        "CompetitionStage",
        backref="tournament_event",
        cascade="all, delete-orphan",
        lazy=True,
        order_by="CompetitionStage.stage_no",
    )


class TournamentMasterTeam(db.Model):
    __tablename__ = "tournament_master_teams"
    __table_args__ = (
        db.UniqueConstraint("tournament_id", "name", name="uq_tournament_master_team_name"),
    )

    id = db.Column(db.Integer, primary_key=True)
    tournament_id = db.Column(db.Integer, db.ForeignKey("tournaments.id"), nullable=False, index=True)
    name = db.Column(db.String(180), nullable=False)
    affiliation = db.Column(db.String(180), nullable=True)
    seed = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    event_entries = db.relationship(
        "TournamentEventEntry",
        backref="master_team",
        cascade="all, delete-orphan",
        lazy=True,
    )


class TournamentEventEntry(db.Model):
    __tablename__ = "tournament_event_entries"
    __table_args__ = (
        db.UniqueConstraint("tournament_event_id", "master_team_id", name="uq_event_master_team"),
    )

    id = db.Column(db.Integer, primary_key=True)
    tournament_event_id = db.Column(db.Integer, db.ForeignKey("tournament_events.id"), nullable=False, index=True)
    master_team_id = db.Column(db.Integer, db.ForeignKey("tournament_master_teams.id"), nullable=False, index=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    seed = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class CompetitionStage(db.Model):
    __tablename__ = "competition_stages"
    __table_args__ = (
        db.UniqueConstraint("tournament_event_id", "stage_no", name="uq_event_stage_no"),
    )

    id = db.Column(db.Integer, primary_key=True)
    tournament_event_id = db.Column(db.Integer, db.ForeignKey("tournament_events.id"), nullable=False, index=True)
    stage_no = db.Column(db.Integer, nullable=False, default=1)
    name = db.Column(db.String(180), nullable=False)
    competition_format = db.Column(db.String(40), nullable=False)
    pairing_method = db.Column(db.String(40), nullable=False, default="random")
    status = db.Column(db.String(30), nullable=False, default="draft")
    source_stage_id = db.Column(db.Integer, db.ForeignKey("competition_stages.id"), nullable=True)
    engine_event_id = db.Column(db.Integer, db.ForeignKey("events.id"), nullable=True, index=True)
    legacy_playoff_id = db.Column(db.Integer, nullable=True)
    config_json = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    engine_event = db.relationship("Event", foreign_keys=[engine_event_id])
    source_stage = db.relationship("CompetitionStage", remote_side=[id], foreign_keys=[source_stage_id])
    rr_groups = db.relationship(
        "RoundRobinGroup",
        backref="stage",
        cascade="all, delete-orphan",
        lazy=True,
        order_by="RoundRobinGroup.position",
    )

    @property
    def config(self):
        import json as _json
        try:
            return _json.loads(self.config_json or "{}")
        except Exception:
            return {}

    def set_config(self, value):
        import json as _json
        self.config_json = _json.dumps(value or {}, ensure_ascii=False)


class RoundRobinGroup(db.Model):
    __tablename__ = "round_robin_groups"
    __table_args__ = (
        db.UniqueConstraint("stage_id", "name", name="uq_rr_stage_group_name"),
    )

    id = db.Column(db.Integer, primary_key=True)
    stage_id = db.Column(db.Integer, db.ForeignKey("competition_stages.id"), nullable=False, index=True)
    name = db.Column(db.String(20), nullable=False)
    position = db.Column(db.Integer, nullable=False, default=1)

    members = db.relationship(
        "RoundRobinGroupMember",
        backref="group",
        cascade="all, delete-orphan",
        lazy=True,
        order_by="RoundRobinGroupMember.slot_no",
    )


class RoundRobinGroupMember(db.Model):
    __tablename__ = "round_robin_group_members"
    __table_args__ = (
        db.UniqueConstraint("group_id", "slot_no", name="uq_rr_group_slot"),
        db.UniqueConstraint("group_id", "team_id", name="uq_rr_group_team"),
    )

    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey("round_robin_groups.id"), nullable=False, index=True)
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id"), nullable=False, index=True)
    slot_no = db.Column(db.Integer, nullable=False)

    team = db.relationship("Team", foreign_keys=[team_id])


# Native Round Robin attached directly to Event (Tournament Center is no longer used)
class EventRoundRobinConfig(db.Model):
    __tablename__ = "event_round_robin_configs"
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("events.id"), nullable=False, unique=True, index=True)
    group_count = db.Column(db.Integer, nullable=False, default=1)
    advance_per_group = db.Column(db.Integer, nullable=False, default=2)
    pairing_method = db.Column(db.String(40), nullable=False, default="random")
    first_time = db.Column(db.String(10), nullable=False, default="09:00")
    match_minutes = db.Column(db.Integer, nullable=False, default=75)
    break_minutes = db.Column(db.Integer, nullable=False, default=15)
    event = db.relationship("Event", foreign_keys=[event_id], backref=db.backref("rr_config_row", uselist=False, cascade="all, delete-orphan"))


class EventRoundRobinGroup(db.Model):
    __tablename__ = "event_round_robin_groups"
    __table_args__ = (db.UniqueConstraint("event_id", "name", name="uq_event_rr_group"),)
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("events.id"), nullable=False, index=True)
    name = db.Column(db.String(20), nullable=False)
    position = db.Column(db.Integer, nullable=False, default=1)
    event = db.relationship("Event", foreign_keys=[event_id], backref=db.backref("native_rr_groups", cascade="all, delete-orphan", order_by="EventRoundRobinGroup.position"))
    members = db.relationship("EventRoundRobinMember", backref="group", cascade="all, delete-orphan", order_by="EventRoundRobinMember.slot_no")


class EventRoundRobinMember(db.Model):
    __tablename__ = "event_round_robin_members"
    __table_args__ = (
        db.UniqueConstraint("group_id", "slot_no", name="uq_event_rr_slot"),
        db.UniqueConstraint("group_id", "team_id", name="uq_event_rr_team"),
    )
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey("event_round_robin_groups.id"), nullable=False, index=True)
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id"), nullable=False, index=True)
    slot_no = db.Column(db.Integer, nullable=False)
    team = db.relationship("Team", foreign_keys=[team_id])
