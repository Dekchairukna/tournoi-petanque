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
    
    events = db.relationship("Event", backref="creator", lazy=True)

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
    age_group = db.Column(db.String(50))
    rounds = db.Column(db.Integer)
    current_round = db.Column(db.Integer, default=1)
    date = db.Column(db.Date, nullable=True)
    auto_field_enabled = db.Column(db.Boolean, default=False)
    field_prefix = db.Column(db.String(10), default='')  # เช่น 'A', ''
    field_start = db.Column(db.Integer, default=1)
    field_max = db.Column(db.Integer, default=16)
    field_exclude = db.Column(db.String, default='')  # เช่น '3,7,11
    logo_filename = db.Column(db.Text)  # เก็บเป็น JSON list

    created_at = db.Column(db.DateTime, server_default=text('CURRENT_TIMESTAMP'), nullable=True)

    # เพิ่มบรรทัดนี้
    creator_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

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
    is_locked = db.Column(db.Boolean, default=False)
    field = db.Column(db.Integer, nullable=True)

    team1 = db.relationship("Team", foreign_keys=[team1_id], backref="matches_as_team1")
    team2 = db.relationship("Team", foreign_keys=[team2_id], backref="matches_as_team2")
    is_manual = db.Column(db.Boolean, default=True)  # เพื่อแยกจากการจับอัตโนมัติ
