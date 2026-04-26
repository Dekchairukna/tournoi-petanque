from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from flask_socketio import SocketIO, emit

from flask_login import LoginManager, current_user, login_user, logout_user, login_required
from datetime import datetime, timedelta, date
from flask import session
from PIL import Image
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, Match, Team, Event, User
import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import pandas as pd
from flask_migrate import Migrate
from swiss_logic import generate_pairings, generate_manual_pairings
from standings import calculate_standings
from flask import Blueprint
from dotenv import load_dotenv
from sqlalchemy import func
from functools import wraps
from collections import defaultdict
from routes.match import match_bp  # import blueprint ที่สร้างในไฟล์ routes/match.py
from flask_wtf.file import FileField, FileAllowed
import json
# สำหรับ Excel
import io
from openpyxl import Workbook
from openpyxl.styles import PatternFill, Font, Border, Side, Alignment
from openpyxl.utils import get_column_letter

load_dotenv()
app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "your_secret_key")
# ใช้ DATABASE_URL เฉพาะตอน deploy/ตั้งค่าไว้จริง; ถ้ารันในเครื่องให้ใช้ SQLite อัตโนมัติ
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
INSTANCE_DIR = os.path.join(BASE_DIR, 'instance')
os.makedirs(INSTANCE_DIR, exist_ok=True)
LOCAL_DB_PATH = os.path.join(INSTANCE_DIR, 'tournoi.db')
database_url = os.environ.get('DATABASE_URL')

if database_url:
    # Railway/Heroku บางที่ส่ง postgres:// ให้ SQLAlchemy รุ่นใหม่ต้องใช้ postgresql://
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{LOCAL_DB_PATH}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config["UPLOAD_FOLDER"] = "uploads"
#app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://swiss_user:pRF2UGRYcncpoB7byrGFn1c6RrVnMwio@dpg-d0q4qqmuk2gs73a8ba50-a.singapore-postgres.render.com/swissdb'

socketio = SocketIO(
    app,
    async_mode="threading",
    cors_allowed_origins="*",
    ping_timeout=60,
    ping_interval=25,
    max_http_buffer_size=10_000_000,
    logger=False,
    engineio_logger=False
)

db.init_app(app)  # ✅ ตรงนี้สำคัญ
migrate = Migrate(app, db)
migrate.init_app(app, db)
app.register_blueprint(match_bp, url_prefix='/match')  # ลงทะเบียน blueprint
event_bp = Blueprint('event', __name__)  # สร้าง blueprint event ถ้ามี
# Setup Flask-Login
login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.init_app(app)

with app.app_context():
    db.create_all()  # สร้างตารางตามโมเดล

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

#------------------------เรียลไทม์ SocketIO-------------------------------------------------------------


@socketio.on('update_score')
@login_required
def handle_update_score(data):
    """
    Handles score updates via SocketIO.
    Requires user to be logged in.
    Updates the database and broadcasts the new score to all connected clients.
    """
    match_id = data.get('match_id')
    team_a_score = data.get('team_a_score')
    team_b_score = data.get('team_b_score')

    # Get user information from the current_user Flask-Login object
    user_id = current_user.id
    username = current_user.username

    with app.app_context():
        # Find the match in the database
        match = Match.query.get(match_id) # Assuming Match model is imported from models.py
        
        if match:
            try:
                # Update scores (convert to int to ensure correct data type)
                match.team1_score = int(team_a_score)
                match.team2_score = int(team_b_score)
                db.session.commit() # Save changes to the database
                
                print(f"Score updated for Match {match_id} by {username}: {team_a_score}-{team_b_score}")

                # Emit the updated score to all connected clients
                # Including username and timestamp for potential future use/debugging
                emit('score_updated', {
                    'match_id': match.id, # Use match.id to ensure it's the correct integer ID
                    'team_a_score': match.team1_score,
                    'team_b_score': match.team2_score,
                    'updated_by_username': username,
                    'timestamp': datetime.utcnow().isoformat()
                }, broadcast=True)

            except ValueError:
                # Handle cases where score might not be a valid integer
                print(f"Invalid score value received for Match {match_id}: team_a_score={team_a_score}, team_b_score={team_b_score}")
                emit('error_message', {'message': 'Invalid score format'}, room=request.sid)
            except Exception as e:
                # Catch any other unexpected database errors
                db.session.rollback() # Rollback changes in case of error
                print(f"Database error updating score for Match {match_id}: {e}")
                emit('error_message', {'message': 'Server error updating score'}, room=request.sid)
        else:
            print(f"Match with ID {match_id} not found.")
            emit('error_message', {'message': 'Match not found'}, room=request.sid)





# ฟังก์ชันแปลงวันที่เป็นภาษาไทยแบบเต็ม
def thai_date_full(dt):
    days = ['วันจันทร์', 'วันอังคาร', 'วันพุธ', 'วันพฤหัสบดี', 'วันศุกร์', 'วันเสาร์', 'วันอาทิตย์']
    months = ['มกราคม', 'กุมภาพันธ์', 'มีนาคม', 'เมษายน', 'พฤษภาคม', 'มิถุนายน',
              'กรกฎาคม', 'สิงหาคม', 'กันยายน', 'ตุลาคม', 'พฤศจิกายน', 'ธันวาคม']
    
    day_name = days[dt.weekday()]  # weekday() จันทร์=0
    day = dt.day
    month_name = months[dt.month - 1]
    year = dt.year + 543  # ปี พ.ศ.
    
    return f"{day_name} ที่ {day} {month_name} {year}"

# ลงทะเบียนฟังก์ชันนี้ให้ Jinja template ใช้งานได้
app.jinja_env.globals.update(thai_date_full=thai_date_full)

def roles_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash("กรุณาเข้าสู่ระบบก่อน", "warning")
                return redirect(url_for('login'))

            role = current_user.role.lower()
            print(f"DEBUG current_user.role = {role}")

            if role == 'superadmin':
                return f(*args, **kwargs)

            if role in [r.lower() for r in roles]:
                return f(*args, **kwargs)

            flash("คุณไม่มีสิทธิ์ทำรายการนี้", "warning")
            return redirect(url_for('index'))
        return decorated_function
    return decorator

# ฟังก์ชันช่วยแปลงค่าเป็น int และคืน 0 ถ้าค่าเป็น None หรือไม่ถูกต้อง
def safe_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def swiss_pairing(event_id, round_no):
    # ตรวจสอบว่ารอบก่อนหน้า (round_no - 1) ถูกล็อกผลหมดหรือยัง
    if round_no > 1:
        unlocked_matches = Match.query.filter_by(event_id=event_id, round=round_no - 1, is_locked=False).all()
        if unlocked_matches:
            return False, f"กรุณาล็อกผลการแข่งขันรอบที่ {round_no - 1} ก่อนจับคู่รอบถัดไป"

    # ลบแมตช์รอบนี้ถ้ามีอยู่ก่อน เพื่อจับคู่ใหม่
    Match.query.filter_by(event_id=event_id, round=round_no).delete()
    db.session.commit()

    # เรียกใช้ฟังก์ชัน generate_pairings เพื่อจับคู่
    pairing_results = generate_pairings(event_id, round_no)
    
     # >>> ตรวจจับว่า generate_pairings ล้มเหลวเพราะ BYE ซ้ำ
    if pairing_results is None:
        return False, "ทีมใดทีมหนึ่งได้ BYE ซ้ำหลายรอบ ต้องจัดการด้วยมือ"

    matches = []
    for p in pairing_results:
        match = Match(
            round=round_no,
            team1_id=p[0],
            team2_id=p[1],
            event_id=event_id,
            is_locked=False,
        )
        if p[1] is None:
            match.team1_score = 1
            match.team2_score = 0
            match.is_locked = True
        matches.append(match)


    db.session.add_all(matches)
    db.session.commit()

    return True, "จับคู่สำเร็จ"


@app.route("/event/<int:event_id>/manual_pairing/<int:round_num>", methods=["GET", "POST"])
@login_required
@roles_required("admin")
def manual_pairing(event_id, round_num):
    event = Event.query.get_or_404(event_id)
     # ดึงข้อมูลทีมจากฐานข้อมูลหรือที่เก็บไว้ (ตัวอย่างสมมติ)
    
    # ✅ แปลง logo_filename เป็น list
    try:
        event.logo_list = json.loads(event.logo_filename) if event.logo_filename else []
    except Exception:
        event.logo_list = []

    if request.method == "POST":
        # รับข้อมูลคู่จากฟอร์ม เช่น pairs=["1,2", "3,0", ...]  (0=BYE)
        pairs_raw = request.form.getlist("pairs")
        pairs = []
        
        for p in pairs_raw:
            try:
                t1, t2 = p.split(",")
                t1_id = int(t1)
                t2_id = int(t2) if t2.isdigit() and int(t2) != 0 else None  # None = BYE
                pairs.append((t1_id, t2_id))
            except Exception:
                flash("ข้อมูลคู่แข่งขันไม่ถูกต้อง", "danger")
                return redirect(request.url)

        # ลบแมตช์เดิมในรอบนี้ทั้งหมด (ไม่แยก is_manual)
        Match.query.filter_by(event_id=event_id, round=round_num).delete()
        
        # บันทึกแมตช์คู่ใหม่ตามแมนนวลโดยตรง ไม่เช็คกฎใดๆ
        for t1_id, t2_id in pairs:
            match = Match(event_id=event_id, round=round_num,
                          team1_id=t1_id, team2_id=t2_id,
                          is_manual=True, is_locked=False)
            db.session.add(match)
        db.session.commit()

        flash(f"บันทึกคู่แข่งขันรอบที่ {round_num} แบบแมนนวลเรียบร้อยแล้ว", "success")
        return redirect(url_for("round_matches", event_id=event_id, round=round_num))

    else:
        # GET: แสดงฟอร์มให้แก้ไขคู่
        standings = calculate_standings(event_id)
        team_ids = [team['team_id'] for team in standings]
        
        

        # ดึงชื่อทีมจากฐานข้อมูล
        teams_query = Team.query.filter(Team.id.in_(team_ids)).all()
        teams = {team.id: team.name for team in teams_query}
         # ดึงข้อมูลทีมจากฐานข้อมูลหรือที่เก็บไว้ (ตัวอย่างสมมติ)
        suggested_pairings, unpaired = generate_manual_pairings(event_id, team_ids)

        # สร้างข้อความโน้ตจากคู่แนะนำ
        pairing_notes = []
        team_dict = {team['team_id']: team['team_name'] for team in standings}
        

        for pair in suggested_pairings:
            t1 = team_dict.get(pair['team1_id'], 'Unknown Team')
            t2 = team_dict.get(pair['team2_id'], 'BYE') if pair['team2_id'] != 0 else 'BYE'
            pairing_notes.append(f" {t1} VS {t2}")

        for bye_team_id in unpaired:
            t = team_dict.get(bye_team_id, 'Unknown Team')
            pairing_notes.append(f" {t} ควรได้ BYE")


        # สร้างคู่คร่าวๆ จากฟังก์ชัน generate_manual_pairings (ยังไม่บันทึก)
        pairings, unpaired = generate_manual_pairings(event_id, team_ids)

        return render_template("admin_manual_pairings.html",
                               standings=standings, 
                               event=event,
                               round_num=round_num,
                               pairings=pairings,
                               pairings_count=(len(standings) + 1) // 2,   # <== เพิ่มตรงนี้
                               teams=teams,  # <== สำคัญ
                               pairing_notes=pairing_notes,
                               unpaired=unpaired)
        

@app.route("/")
def index():
    today = date.today()

    all_events = Event.query.order_by(Event.date.desc()).all()

    upcoming_events = []
    finished_events_by_year = defaultdict(list)

    for event in all_events:
        latest_round = db.session.query(db.func.max(Match.round)).filter(Match.event_id == event.id).scalar()
        matches = Match.query.filter_by(event_id=event.id, round=latest_round).all()

        is_finished = all(m.is_locked for m in matches) if matches else False

        if not is_finished:
            upcoming_events.append(event)
        else:
            finished_events_by_year[event.date.year].append(event)

    # เรียงปีจากใหม่ -> เก่า
    finished_events_by_year = dict(sorted(finished_events_by_year.items(), reverse=True))

    return render_template(
        "index.html",
        upcoming_events=sorted(upcoming_events, key=lambda e: e.date),
        finished_events_by_year=finished_events_by_year,
        events=upcoming_events + [e for year in finished_events_by_year.values() for e in year]  # รวมรายการทั้งหมด
    )

    


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        user = User.query.filter_by(username=username).first()
        
        if user is None:
            flash("ไม่พบชื่อผู้ใช้", "danger")
        elif not user.check_password(password):
            flash("รหัสผ่านไม่ถูกต้อง", "danger")
        else:
            login_user(user)
            next_page = request.args.get("next")
            # ป้องกันการ redirect ไป URL ภายนอก (security)
            if not next_page or not next_page.startswith('/'):
                next_page = url_for("index")
            return redirect(next_page)
            
    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("ออกจากระบบแล้ว", "success")
    return redirect(url_for("index"))

#-------------------------------------------------------------------------------

@app.route('/event/<int:event_id>/score-sheet')
@login_required
@roles_required('admin')  # เพิ่มบรรทัดนี้
def score_sheet_all(event_id):
  
    event = Event.query.get_or_404(event_id)
    selected_round = request.args.get('round', type=int)

    # ✅ แปลง logo_filename เป็น list
    try:
        event.logo_list = json.loads(event.logo_filename) if event.logo_filename else []
    except Exception:
        event.logo_list = []

    query = Match.query.filter_by(event_id=event_id)
    if selected_round:
        query = query.filter_by(round=selected_round)

    matches = query.order_by(Match.round, Match.id).all()
    teams = Team.query.filter_by(event_id=event_id).all()
    num_teams = len(teams)

    # คำนวณจำนวนใบต่อหน้า (1 ใบต่อ 1 แมตช์)
    matches_per_page = max(1, num_teams // 2)  # อย่างน้อย 1 เพื่อป้องกันหารศูนย์

    total_rounds = db.session.query(func.max(Match.round)).filter_by(event_id=event_id).scalar() or 1
    print(event.logo_list)
    return render_template(
        'score_sheet.html',
        event=event,
        matches=matches,
        teams=teams,
        total_rounds=total_rounds,
        num_teams=num_teams,
        matches_per_page=matches_per_page  # ✅ ส่งเข้า template
        
    )
#-------------------------------------------------------------------------------

@app.route("/event/<int:event_id>")
#--------------------------สำหรับเข้าดูอีเว้น-------------------------------------------------------------อย่าไปยุ่งกับมัน
def event_detail(event_id):
    event = db.session.get(Event, event_id)
    teams = Team.query.filter_by(event_id=event_id).all()
    standings = calculate_standings(event_id)
    matches = Match.query.filter_by(event_id=event_id).all()

   

    # 🔧 แก้ตรงนี้: คำนวณ current_round
    current_round = (
        db.session.query(db.func.max(Match.round))
        .filter(Match.event_id == event_id)
        .scalar()
        or 0
    )

    # ถ้าคุณใช้ matches_round_1 ใน template ก็เพิ่มตรงนี้ด้วย
    matches_round_1 = Match.query.filter_by(event_id=event_id, round=1).all()

    # ✅ แปลง logo_filename เป็น list
    try:
        event.logo_list = json.loads(event.logo_filename) if event.logo_filename else []
    except Exception:
        event.logo_list = []

    return render_template(
        "event.html",
        event=event,
        teams=teams,
        standings=standings,
        matches=matches,
        current_round=current_round,      # ✅ ส่งไปยัง template
        matches_round_1=matches_round_1   # ✅ ส่งไปด้วยหากใช้
    )


from flask import flash

@app.route("/event/<int:event_id>/upload", methods=["POST"])
@login_required
@roles_required('admin')
def upload_teams(event_id):
    file = request.files.get("file")

    if not file or file.filename == '':
        flash("กรุณาเลือกไฟล์เพื่ออัปโหลด", "danger")
        return redirect(url_for("event_detail", event_id=event_id))

    if not file.filename.endswith(('.xls', '.xlsx')):
        flash("กรุณาอัปโหลดไฟล์ Excel (.xls หรือ .xlsx)", "danger")
        return redirect(url_for("event_detail", event_id=event_id))

    try:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(filepath)

        df = pd.read_excel(filepath)

        if "team_name" not in df.columns:
            flash("ไฟล์ต้องมีคอลัมน์ชื่อ 'team_name'", "danger")
            return redirect(url_for("event_detail", event_id=event_id))

        latest_round = get_latest_round_for_event(event_id)
        new_teams = 0
        late_matches = 0

        for raw_name in df["team_name"]:
            name = str(raw_name).strip() if raw_name is not None else ""
            if not name or name.lower() == "nan":
                continue

            if not Team.query.filter_by(name=name, event_id=event_id).first():
                team = Team(name=name, event_id=event_id)
                db.session.add(team)
                db.session.flush()
                new_teams += 1

                if latest_round:
                    created = create_late_entry_match(event_id, team, latest_round)
                    if created:
                        late_matches += 1

        db.session.commit()

        if latest_round:
            flash(
                f"เพิ่มทีม/นักกีฬาสำเร็จ {new_teams} รายการ และสร้างแถวคีย์คะแนนเฉพาะรายชื่อใหม่ในรอบที่ {latest_round} จำนวน {late_matches} แถว โดยไม่กระทบผลจับสลากเดิม",
                "success"
            )
        else:
            flash(f"เพิ่มทีมสำเร็จ {new_teams} ทีม", "success")
    except Exception as e:
        flash(f"เกิดข้อผิดพลาดในการอัปโหลด: {str(e)}", "danger")

    return redirect(url_for("event_detail", event_id=event_id))
def generate_field_numbers(event):
    prefix = event.field_prefix or ''
    start = event.field_start or 1
    max_field = event.field_max or 16
    exclude = set(event.field_exclude.split(',')) if event.field_exclude else set()

    fields = []
    for i in range(start, start + max_field):
        field_name = f"{prefix}{i}"
        if field_name not in exclude:
            fields.append(field_name)
    return fields


def get_latest_round_for_event(event_id):
    """คืนค่ารอบล่าสุดที่มีการจับคู่แล้ว ถ้ายังไม่จับคู่คืน None"""
    return db.session.query(db.func.max(Match.round)).filter_by(event_id=event_id).scalar()


def create_late_entry_match(event_id, team, target_round=None):
    """
    สร้างแถวคะแนนเฉพาะทีม/นักกีฬาที่เพิ่มภายหลัง โดยไม่ลบหรือสุ่มคู่เดิม
    ใช้ is_manual=False เพื่อให้ template แยกสี/ป้ายว่าเป็นรายการเพิ่มภายหลังได้
    """
    if target_round is None:
        target_round = get_latest_round_for_event(event_id)

    if not target_round:
        return None

    existing = Match.query.filter(
        Match.event_id == event_id,
        Match.round == target_round,
        ((Match.team1_id == team.id) | (Match.team2_id == team.id))
    ).first()
    if existing:
        return existing

    late_match = Match(
        event_id=event_id,
        round=target_round,
        team1_id=team.id,
        team2_id=None,
        team1_score=None,
        team2_score=None,
        is_locked=False,
        is_manual=False
    )
    db.session.add(late_match)
    return late_match


@app.route('/event/<int:event_id>/add_team', methods=['POST'])
@login_required
@roles_required('admin', 'superadmin')
def add_team_route(event_id):
    Event.query.get_or_404(event_id)

    team_name = (request.form.get('team_name') or '').strip()
    if not team_name:
        flash('กรุณากรอกชื่อทีม/ชื่อนักกีฬา', 'danger')
        return redirect(url_for('event_detail', event_id=event_id))

    existing_team = Team.query.filter_by(name=team_name, event_id=event_id).first()
    if existing_team:
        flash('ชื่อทีม/ชื่อนักกีฬานี้มีอยู่แล้ว', 'warning')
        return redirect(url_for('event_detail', event_id=event_id))

    latest_round = get_latest_round_for_event(event_id)

    new_team = Team(name=team_name, event_id=event_id)
    db.session.add(new_team)
    db.session.flush()  # ให้ได้ id ก่อนสร้างแถวคะแนน

    if latest_round:
        create_late_entry_match(event_id, new_team, latest_round)
        db.session.commit()
        flash(
            f'เพิ่ม {team_name} เรียบร้อยแล้ว และสร้างแถวคีย์คะแนนเฉพาะชื่อนี้ในรอบที่ {latest_round} โดยไม่กระทบผลจับสลากเดิม',
            'success'
        )
        return redirect(url_for('round_matches', event_id=event_id, round=latest_round))

    db.session.commit()
    flash('เพิ่มทีม/นักกีฬาเรียบร้อยแล้ว', 'success')
    return redirect(url_for('event_detail', event_id=event_id))


@app.route("/event/add", methods=["POST"])
@login_required
@roles_required('admin')
def add_event_route():
    try:
        name = request.form["name"]
        rounds = int(request.form["rounds"])
        location = request.form.get("location")
        category = request.form["category"]
        sex = request.form["sex"]
        age_group = request.form["age_group"]
        date_str = request.form.get("date")
        event_date = datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else None

        field_prefix = request.form.get("field_prefix", "")
        field_start = request.form.get("field_start", type=int)
        field_max = request.form.get("field_max", type=int)
        field_exclude = request.form.get("field_exclude", "")

        logo_files = request.files.getlist("logo")
        logo_filenames = []

        upload_folder = os.path.join("static", "logos")
        os.makedirs(upload_folder, exist_ok=True)

        # ฟังก์ชันลบพื้นหลัง (copy จากที่คุณมี)
        def remove_background(image, threshold=200):
            image = image.convert("RGBA")
            datas = image.getdata()
            new_data = []
            for item in datas:
                if item[0] > threshold and item[1] > threshold and item[2] > threshold:
                    new_data.append((255, 255, 255, 0))
                else:
                    new_data.append(item)
            image.putdata(new_data)
            return image

        def resize_logo_fixed_height(image, fixed_height=60):
            width, height = image.size
            new_height = fixed_height
            new_width = int((new_height / height) * width)
            return image.resize((new_width, new_height), Image.Resampling.LANCZOS)

        # ประมวลผลไฟล์โลโก้ทีละไฟล์
        for logo_file in logo_files:
            if logo_file and logo_file.filename != "":
                filename = secure_filename(logo_file.filename)
                logo_path = os.path.join(upload_folder, filename)

                image = Image.open(logo_file)
                image = remove_background(image, threshold=200)
                image = resize_logo_fixed_height(image, fixed_height=60)
                image.save(logo_path, format="PNG")

                logo_filenames.append(filename)

        new_event = Event(
            name=name,
            rounds=rounds,
            location=location,
            sex=sex,
            category=category,
            age_group=age_group,
            date=event_date,
            field_prefix=field_prefix,
            field_start=field_start,
            field_max=field_max,
            field_exclude=field_exclude,
            creator_id=current_user.id,
            logo_filename=json.dumps(logo_filenames)
        )

        db.session.add(new_event)
        db.session.commit()
        flash("เพิ่มรายการแข่งขันเรียบร้อยแล้ว", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"เกิดข้อผิดพลาด: {str(e)}", "danger")

    return redirect(url_for("index"))





@app.route('/event/<int:event_id>/team/<int:team_id>/edit', methods=['GET', 'POST'])
@login_required
@roles_required('admin')  # เพิ่มบรรทัดนี้
def edit_teams_route(event_id, team_id):
   
    team = Team.query.filter_by(id=team_id, event_id=event_id).first_or_404()
    if request.method == 'POST':
        new_name = request.form.get('name')
        if new_name:
            team.name = new_name
            db.session.commit()
            flash('แก้ไขชื่อทีมเรียบร้อย', 'success')
            return redirect(url_for('event_detail', event_id=event_id))
        else:
            flash('กรุณากรอกชื่อทีม', 'warning')
    return render_template('edit_team.html', team=team, event_id=event_id)


@app.route("/event/<int:event_id>/pair_first_round", methods=['POST'])
@login_required
@roles_required('admin')
def pair_first_round(event_id):
    import re
    import random
    from collections import defaultdict

    def extract_base_name(name):
        # ลบรหัสตัวเลข หรือเครื่องหมายด้านหลังชื่อ เช่น "ขอนแก่น 1", "ขอนแก่น-2" → "ขอนแก่น"
        base = re.split(r'[\s\-]*\d+$', name.strip())[0]
        return base

    event = Event.query.get(event_id)
    if event is None:
        flash("ไม่พบรายการแข่งขันนี้", "warning")
        return redirect(url_for("event_detail", event_id=event_id))

    existing_matches = Match.query.filter_by(event_id=event_id, round=1).count()
    if existing_matches > 0:
        flash("มีการจับคู่รอบแรกแล้ว", "warning")
        return redirect(url_for("event_detail", event_id=event_id))

    teams = Team.query.filter_by(event_id=event_id).all()
    if len(teams) < 2:
        flash("ต้องมีทีมอย่างน้อย 2 ทีมในการจับคู่", "warning")
        return redirect(url_for("event_detail", event_id=event_id))

    separate_same_name = request.form.get('separate_same_name') == 'on'

    # สุ่มลำดับทีม
    teams = teams[:]  # copy
    random.shuffle(teams)

    pairings = []
    used_ids = set()

    for i, team1 in enumerate(teams):
        if team1.id in used_ids:
            continue
        for j in range(i + 1, len(teams)):
            team2 = teams[j]
            if team2.id in used_ids:
                continue
            if separate_same_name and extract_base_name(team1.name) == extract_base_name(team2.name):
                continue  # ข้ามถ้ารากชื่อเหมือนกัน เช่น "ขอนแก่น 1" vs "ขอนแก่น 2"
            # จับคู่
            pairings.append((team1, team2))
            used_ids.add(team1.id)
            used_ids.add(team2.id)
            break

    # BYE หากยังเหลือทีมที่จับไม่ได้
    remaining = [t for t in teams if t.id not in used_ids]
    if remaining:
        pairings.append((remaining[0], None))

    for team1, team2 in pairings:
        match = Match(
            event_id=event_id,
            round=1,
            team1_id=team1.id,
            team2_id=team2.id if team2 else None,
            is_locked=False
        )
        db.session.add(match)

    db.session.commit()
    flash("จับคู่รอบแรกเสร็จสิ้น", "success")
    return redirect(url_for("round_matches", event_id=event_id, round=1))



@app.route('/event/<int:event_id>/team/<int:team_id>/delete', methods=['POST'])
@login_required
@roles_required('admin')  # เพิ่มบรรทัดนี้
def delete_team_route(event_id, team_id):
    team = Team.query.get_or_404(team_id)

    # ตรวจสอบว่าเป็นทีมใน event นี้จริง
    if team.event_id != event_id:
        flash('ไม่พบทีมในรายการนี้', 'danger')
        return redirect(url_for('event_detail', event_id=event_id))

    # เช็คว่ามีแมตช์ที่ประกบคู่ทีมนี้แล้วหรือยัง
    existing_matches = Match.query.filter(
        ((Match.team1_id == team_id) | (Match.team2_id == team_id)) &
        (Match.event_id == event_id)
    ).count()

    

    # ถ้ายังไม่มีแมตช์ที่ประกบคู่ทีมนี้ ลบได้เลย
    Match.query.filter(
        ((Match.team1_id == team_id) | (Match.team2_id == team_id)) &
        (Match.event_id == event_id)
    ).delete()

    db.session.delete(team)
    db.session.commit()
    flash('ลบทีมเรียบร้อยแล้ว', 'success')
    return redirect(url_for('event_detail', event_id=event_id))

@app.route("/event/<int:event_id>/round/<int:round>/delete_all", methods=["POST"])
@login_required
@roles_required('admin', 'superadmin')
def delete_round_pairings(event_id, round):
    deleted = Match.query.filter_by(event_id=event_id, round=round).delete()
    db.session.commit()

    if deleted:
        flash(f"ลบคู่ประกบทั้งหมดของรอบที่ {round} เรียบร้อยแล้ว", "success")
    else:
        flash(f"ไม่พบคู่ประกบของรอบที่ {round}", "warning")

    return redirect(url_for("event_detail", event_id=event_id))

@app.route('/event/<int:event_id>/team/<int:team_id>/edit', methods=['POST'])
@login_required
@roles_required('admin')  # เพิ่มบรรทัดนี้
def edit_team(event_id, team_id):
    
    new_name = request.form.get('new_name')
    if not new_name:
        flash('กรุณากรอกชื่อทีมใหม่', 'danger')
        return redirect(url_for('event_detail', event_id=event_id))

    team = Team.query.get_or_404(team_id)
    if team.event_id != event_id:
        flash('ไม่พบทีมในรายการนี้', 'danger')
        return redirect(url_for('event_detail', event_id=event_id))

    team.name = new_name.strip()
    db.session.commit()
    flash('แก้ไขชื่อทีมเรียบร้อยแล้ว', 'success')
    return redirect(url_for('event_detail', event_id=event_id))


@app.route("/event/<int:event_id>/pair_next_round", methods=['POST'])
@login_required
@roles_required('admin')
def pair_next_round(event_id):
    import re
    import random
    from collections import defaultdict

    def extract_base_name(name):
        # ลบรหัสตัวเลข หรือเครื่องหมายด้านหลังชื่อ เช่น "ขอนแก่น 1", "ขอนแก่น-2" → "ขอนแก่น"
        base = re.split(r'[\s\-]*\d+$', name.strip())[0]
        return base
    
    max_round = db.session.query(db.func.max(Match.round)).filter_by(event_id=event_id).scalar()
    next_round = (max_round or 0) + 1

    if max_round is None:
        flash("ยังไม่มีการจับคู่รอบแรก กรุณาจับคู่รอบแรกก่อน", "warning")
        return redirect(url_for("event_detail", event_id=event_id))

    # ตรวจสอบว่าแมตช์รอบก่อนหน้าล็อกผลหมดหรือยัง
    unlocked_matches = Match.query.filter_by(event_id=event_id, round=max_round, is_locked=False).count()
    if unlocked_matches > 0:
        flash(f"กรุณาล็อกผลการแข่งขันรอบที่ {max_round} ก่อนจับคู่รอบถัดไป", "warning")
        return redirect(url_for("event_detail", event_id=event_id))

    event = Event.query.get(event_id)
    if not event:
        flash("ไม่พบรายการแข่งขันนี้", "danger")
        return redirect(url_for("index"))

    if next_round > event.rounds:
        flash("ครบจำนวนรอบการแข่งขันแล้ว ไม่สามารถจับคู่รอบใหม่ได้", "info")
        return redirect(url_for("event_detail", event_id=event_id))

    # 🔁 เรียก swiss_pairing แล้วตรวจสอบผลลัพธ์
    success, message = swiss_pairing(event_id, next_round)

    if not success:
        flash(message, "warning")

        # ถ้าเป็นกรณี BYE ซ้ำหลายรอบ → ส่งไป manual pairing
        if "BYE ซ้ำ" in message or "จับคู่ด้วยมือ" in message:
            return redirect(url_for("manual_pairing", event_id=event_id, round_num=next_round))

        # กรณีอื่นๆ กลับหน้า event_detail
        return redirect(url_for("event_detail", event_id=event_id))

    flash(f"จับคู่รอบที่ {next_round} เรียบร้อยแล้ว", "success")
    return redirect(url_for("round_matches", event_id=event_id, round=next_round))





@app.route("/event/<int:event_id>/match/<int:match_id>", methods=["POST"])
@login_required
@roles_required('admin')  # เพิ่มบรรทัดนี้
def submit_score(event_id, match_id):
 
    match = Match.query.get_or_404(match_id)
    match.team1_score = int(request.form.get("team1_score", 0))
    match.team2_score = int(request.form.get("team2_score", 0))
    db.session.commit()
    return redirect(url_for("event_detail", event_id=event_id))


@app.route("/event/<int:event_id>/lock", methods=["POST"])
@login_required
@roles_required('admin')  # เพิ่มบรรทัดนี้
def lock_round(event_id):
   
    max_round = db.session.query(db.func.max(Match.round)).filter_by(event_id=event_id).scalar()
    if max_round:
        matches = Match.query.filter_by(event_id=event_id, round=max_round).all()
        for m in matches:
            if m.team2_id is not None and (m.team1_score is None or m.team2_score is None):
                flash("กรุณากรอกคะแนนให้ครบก่อนล็อกผล")
                return redirect(url_for("event_detail", event_id=event_id))
        for m in matches:
            m.is_locked = True
        db.session.commit()
    return redirect(url_for("event_detail", event_id=event_id))


@app.route("/event/<int:event_id>/delete")
@login_required
@roles_required('admin')  # เพิ่มบรรทัดนี้
def delete_event(event_id):
    
    event = Event.query.get(event_id)
    if event is None:
        flash("ไม่พบรายการแข่งขันนี้", "warning")
        return redirect(url_for("index"))
    db.session.delete(event)
    db.session.commit()
    flash("ลบรายการแข่งขันเรียบร้อยแล้ว", "success")
    return redirect(url_for("index"))

@app.route("/event/<int:event_id>/clear", methods=["POST"])
@login_required
@roles_required('admin')
def clear_teams_route(event_id):
    # เช็คว่ามีแมตช์จับคู่ในอีเวนท์นี้หรือยัง
    existing_match = Match.query.filter_by(event_id=event_id).first()
    if existing_match:
        flash("ไม่สามารถลบทีมทั้งหมดได้ เนื่องจากมีการจับคู่แมตช์แล้ว", "danger")
        return redirect(url_for("event_detail", event_id=event_id))

    # ถ้ายังไม่มีแมตช์จึงลบทีมทั้งหมด
    Team.query.filter_by(event_id=event_id).delete()
    db.session.commit()
    flash("ลบรายชื่อทีมทั้งหมดเรียบร้อยแล้ว", "success")
    return redirect(url_for("event_detail", event_id=event_id))



@app.route('/event/<int:event_id>/round/<int:round>', methods=['GET', 'POST'])
def round_matches(event_id, round):
    event = Event.query.get(event_id)
    if event is None:
        flash("ไม่พบรายการแข่งขันนี้", "warning")
        return redirect(url_for("index"))
    
    # ✅ แปลง logo_filename เป็น list
    try:
        event.logo_list = json.loads(event.logo_filename) if event.logo_filename else []
    except Exception:
        event.logo_list = []

    matches = Match.query.filter_by(event_id=event_id, round=round).order_by(Match.field.asc(), Match.id.asc()).all()
    teams = {team.id: team.name for team in Team.query.filter_by(event_id=event_id).all()}

    auto_assign_field = event.auto_field_enabled
     # ดึงรายการรอบทั้งหมดเพื่อทำปุ่มเปลี่ยนรอบ
    rounds = db.session.query(Match.round).filter_by(event_id=event_id).distinct().order_by(Match.round).all()
    rounds = [r[0] for r in rounds]

    def generate_field_numbers(event, count):
        prefix = event.field_prefix or ''
        start = event.field_start or 1
        max_field = event.field_max or 16
        exclude_str = event.field_exclude or ''
        exclude = set(x.strip() for x in exclude_str.split(',') if x.strip())

        fields = []
        num = start
        while len(fields) < count and num < start + max_field * 10:
            field_name = f"{prefix}{num}"
            if field_name not in exclude:
                fields.append(field_name)
            num += 1
        return fields

    # กำหนดค่าพวกนี้ก่อน render เสมอ
    standings = calculate_standings(event_id)
    total_rounds = event.rounds if event.rounds else db.session.query(db.func.max(Match.round)).filter(Match.event_id == event_id).scalar() or 1
    auto_fields = generate_field_numbers(event, len(matches)) if auto_assign_field else []

    if request.method == "POST":
        action = request.form.get("action")

        # ** แก้ไขตรงนี้: toggle auto_assign_field โดยใช้ชื่อปุ่มเฉพาะ (เช่น toggle_auto_assign)**
        # วิธีที่ถูกต้อง: ตรวจสอบว่าปุ่ม toggle_auto_assign ถูกกดหรือไม่ก่อนอัปเดตสถานะ
        if "toggle_auto_assign" in request.form:
            event.auto_field_enabled = not event.auto_field_enabled  # สลับสถานะ
            auto_assign_field = event.auto_field_enabled

            # อัปเดตค่าที่รับจาก form ด้วย
            try:
                event.field_start = int(request.form.get("field_start", event.field_start or 1))
            except ValueError:
                event.field_start = 1
            event.field_prefix = request.form.get("field_prefix", event.field_prefix or "")
            event.field_exclude = request.form.get("field_exclude", event.field_exclude or "")

            db.session.commit()

            # คำนวณเลขสนามถ้าเปิด auto_assign_field
            auto_fields = generate_field_numbers(event, len(matches)) if auto_assign_field else []

            # กำหนดเลขสนามอัตโนมัติหากเปิดใช้งาน
            if auto_assign_field:
                for i, match in enumerate(matches):
                    match.field = auto_fields[i] if i < len(auto_fields) else None
            else:
                # ถ้าปิด auto ให้ล้างเลขสนามออก
                for match in matches:
                    match.field = None

            db.session.commit()
            flash(f"{'เปิด' if auto_assign_field else 'ปิด'} การกำหนดเลขสนามอัตโนมัติเรียบร้อยแล้ว", "success")
            return redirect(url_for("round_matches", event_id=event_id, round=round))

        # อ่านค่าจาก form ที่เหลือ (เมื่อไม่ใช่ toggle)
        # อ่านสถานะ checkbox auto_assign_field จริงๆ จากชื่อในฟอร์ม ไม่ใช่ "auto_assign_field" in request.form
        # **แก้ไข**: ดึงค่า checkbox ให้ถูกต้อง
        auto_assign_field = True if request.form.get("auto_assign_field") == "on" else False
        event.auto_field_enabled = auto_assign_field

        # อัปเดต config ค่าอื่นๆ
        try:
            event.field_start = int(request.form.get("field_start", event.field_start or 1))
        except ValueError:
            event.field_start = 1
        event.field_prefix = request.form.get("field_prefix", event.field_prefix or "")
        event.field_exclude = request.form.get("field_exclude", event.field_exclude or "")

        db.session.commit()  # commit ก่อน เพื่อใช้ config ล่าสุด

        auto_fields = generate_field_numbers(event, len(matches)) if auto_assign_field else []

        if action == "save_fields":
            # กรณี auto assign
            
            if auto_assign_field:
                for i, match in enumerate(matches):
                    match.field = auto_fields[i] if i < len(auto_fields) else None
            else:
                # กรณีกรอกเลขสนามแมนนวล (ใน form)
                for match in matches:
                    field_key = f"field_{match.id}"
                    field_value = request.form.get(field_key)
                    print(f"{field_key} = {field_value}")  # debug
                    if field_value:
                        match.field = field_value.strip()
                    else:
                        match.field = None  # ถ้าไม่กรอก ให้ล้างเลขสนาม

            db.session.commit()
            flash("บันทึกเลขสนามเรียบร้อยแล้ว", "success")
            return redirect(url_for("round_matches", event_id=event_id, round=round))

        # 🔴 บันทึกคะแนน + ล็อกผล
        elif action == "lock_scores":
            for match in matches:
                score1 = request.form.get(f"score_{match.id}_1")
                score2 = request.form.get(f"score_{match.id}_2")

                if score1 is not None:
                    try:
                        match.team1_score = int(score1)
                    except ValueError:
                        flash(f"คะแนนทีม {teams.get(match.team1_id, '')} ต้องเป็นตัวเลข", "danger")
                        return redirect(url_for("round_matches", event_id=event_id, round=round))

                # รายชื่อที่เพิ่มภายหลังจะไม่มีคู่แข่ง ให้คีย์เฉพาะคะแนนฝั่งนี้ และเก็บฝั่งคู่แข่งเป็น 0
                if match.team2_id is None and match.is_manual == False:
                    if score1 is None or str(score1).strip() == "":
                        flash(f"กรุณากรอกคะแนนของ {teams.get(match.team1_id, '')}", "danger")
                        return redirect(url_for("round_matches", event_id=event_id, round=round))
                    match.team2_score = 0
                elif match.team2_id is not None and score2 is not None:
                    try:
                        match.team2_score = int(score2)
                    except ValueError:
                        flash(f"คะแนนทีม {teams.get(match.team2_id, '')} ต้องเป็นตัวเลข", "danger")
                        return redirect(url_for("round_matches", event_id=event_id, round=round))

                match.is_locked = True

            db.session.commit()
            flash("บันทึกคะแนนและล็อกผลเรียบร้อยแล้ว", "success")
            return redirect(url_for("round_matches", event_id=event_id, round=round))

        # กรณี POST ที่ไม่ได้กด save_fields หรือ lock_scores (เช่น แค่ติ๊ก checkbox)
        standings = calculate_standings(event_id)
        total_rounds = event.rounds if event.rounds else db.session.query(db.func.max(Match.round)).filter(Match.event_id == event_id).scalar() or 1
        auto_fields = generate_field_numbers(event, len(matches)) if auto_assign_field else []

    return render_template(
        "round_matches.html",
        event=event,
        matches=matches,
        teams=teams,
        round=round,
        standings=standings,
        total_rounds=total_rounds,
        auto_assign_field=auto_assign_field,
        auto_fields=auto_fields,
        error_message=None,
        selected_round=round,  # ✅ ส่งตัวแปรนี้ไปให้ HTML
    )

@app.route("/users")
def user_list():
    users = User.query.all()
    return render_template("user_list.html", users=users)

@app.route("/users/add", methods=["POST"])
def add_user():
    username = request.form["username"]
    password = request.form["password"]
    role = request.form["role"]
    start_time = request.form.get("start_time")
    end_time = request.form.get("end_time")

    if User.query.filter_by(username=username).first():
        flash("Username already exists")
        return redirect(url_for("user.user_list"))

    user = User(
        username=username,
        password_hash=generate_password_hash(password),
        role=role,
        start_time=datetime.fromisoformat(start_time) if start_time else None,
        end_time=datetime.fromisoformat(end_time) if end_time else None
    )
    db.session.add(user)
    db.session.commit()
    flash("User added successfully")
    return redirect(url_for("user.user_list"))

#--------------------------------------------------------------------------------------------

@app.route('/admin/users/add', methods=['GET', 'POST'])
@login_required
@roles_required('admin', 'superadmin')
def admin_add_user():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']
        duration = request.form.get('duration', '1m')  # default 1 เดือน

        if User.query.filter_by(username=username).first():
            flash("ชื่อผู้ใช้นี้มีอยู่แล้ว", "danger")
            return redirect(url_for('admin_add_user'))

        start_time = datetime.utcnow()
        end_time = calculate_end_time(duration)

        new_user = User(username=username, role=role, start_time=start_time, end_time=end_time)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        flash("เพิ่มผู้ใช้เรียบร้อยแล้ว", "success")
        return redirect(url_for('admin_users'))  # ไปหน้ารายชื่อผู้ใช้

    return render_template('admin_add_user.html')
  


@app.route('/admin/users')
@login_required
@roles_required('admin', 'superadmin')
def admin_users():
    users = User.query.all()
    for u in users:
        if u.end_time:
            u.end_time_str = u.end_time.strftime('%Y-%m-%d %H:%M:%S')
        else:
            u.end_time_str = "ถาวร"
    return render_template('admin_users.html', users=users)


@app.route('/admin/users/delete/<int:user_id>', methods=['POST'])
@login_required
@roles_required('admin', 'superadmin')
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    
    # ห้าม admin ลบ superadmin
    if current_user.role == 'admin' and user.role == 'superadmin':
        flash("คุณไม่มีสิทธิ์ลบ superadmin", "danger")
        return redirect(url_for('admin_users'))

    db.session.delete(user)
    db.session.commit()
    flash("ลบผู้ใช้เรียบร้อยแล้ว", "success")
    return redirect(url_for('admin_users'))

@app.route('/admin/users/edit/<int:user_id>', methods=['GET', 'POST'])
@login_required
def edit_user(user_id):
    user = User.query.get_or_404(user_id)

    if current_user.role != 'superadmin' and (user.role == 'superadmin'):
        flash('คุณไม่มีสิทธิ์แก้ไขผู้ใช้นี้', 'danger')
        return redirect(url_for('admin_users'))

    if request.method == 'POST':
        new_role = request.form.get('role')
        end_time_str = request.form.get('end_time')
        user.role = new_role

        if end_time_str:
            user.end_time = datetime.strptime(end_time_str, '%Y-%m-%dT%H:%M')
        else:
            user.end_time = None

        db.session.commit()
        flash('แก้ไขผู้ใช้สำเร็จ', 'success')
        return redirect(url_for('admin_users'))

    return render_template('admin_edit_user.html', user=user)

@app.route('/match/event/<int:event_id>/match_pairs')
def match_pairs(event_id):
    
    event = Event.query.get_or_404(event_id)
    selected_round = request.args.get('round', None, type=int)

    
     # แปลง logo_filename เป็น list หรือ [] ถ้า error
    try:
        event.logo_list = json.loads(event.logo_filename) if event.logo_filename else []
    except Exception:
        event.logo_list = []   
    
    # ถ้าไม่ระบุรอบ ให้เลือกรอบล่าสุดที่มีใน event นั้น
    if not selected_round:
        latest_match = db.session.query(Match.round)\
            .filter_by(event_id=event_id)\
            .order_by(Match.round.desc())\
            .first()
        selected_round = latest_match.round if latest_match else None

    # ดึงแมตช์ของ event และรอบที่เลือก (หรือรอบล่าสุด)
    query = Match.query.filter_by(event_id=event_id)
    if selected_round:
        query = query.filter_by(round=selected_round)
    matches = query.order_by(Match.field.asc()).all()

    # เตรียมชื่อทีม
    teams = {team.id: team.name for team in Team.query.filter_by(event_id=event_id).all()}
    
    matches_by_round = defaultdict(list)
    for m in matches:
        matches_by_round[m.round].append(m)

    return render_template(
        'match_pairs.html',
        event=event,
        matches=matches,
        matches_by_round=matches_by_round,
        teams=teams,
        selected_round=selected_round
    )

#--------------------------------------------------------------------------------------
# Swiss System Logic & Standings Display - เริ่มปรับปรุงที่นี่

# ฟังก์ชันคำนวณ Buchholz (BHN) และ Fine Buchholz (fBHN) ที่นำมาจาก standings.py
# (ถ้า standings.py คำนวณให้แล้ว ไม่ต้องทำซ้ำตรงนี้)
# จากที่ดู standings.py ของคุณ calculate_standings จะคืนค่า bhn และ fbhn มาให้แล้ว

@app.route('/event/<int:event_id>/standings')
@login_required
def event_standings(event_id):
    current_event = Event.query.get_or_404(event_id)

    # เรียกใช้ calculate_standings จาก standings.py
    # ฟังก์ชันนี้ควรจะคืนค่า standings_data ที่จัดเรียงแล้วและมีข้อมูล BHN, fBHN, point_diff ครบถ้วน
    standings_data = calculate_standings(event_id) # standings_data จะเป็น list ของ dicts

    # รับค่าจำนวนทีมที่เข้ารอบจากฟอร์ม (หรือใช้ค่าเริ่มต้น)
    # ถ้าไม่มีการส่งค่ามาหรือค่าว่าง จะใช้ 8 เป็นค่าเริ่มต้น
    num_qualified_teams = request.args.get('num_qualified_teams', type=int, default=8)

    # ตรวจสอบว่าค่าไม่เกินจำนวนทีมทั้งหมด
    if num_qualified_teams > len(standings_data):
        num_qualified_teams = len(standings_data)
    if num_qualified_teams < 0: # ป้องกันค่าติดลบ
        num_qualified_teams = 0

    return render_template(
        'event_standings.html',
        event=current_event,
        standings=standings_data,
        num_qualified_teams=num_qualified_teams # ส่งค่านี่ไปที่ template ด้วย
    )

# เส้นทางใหม่สำหรับดาวน์โหลด Excel

@app.route('/event/<int:event_id>/download_standings_excel')
@login_required
def download_standings_excel(event_id):
    current_event = Event.query.get_or_404(event_id)
    
    # ดึงค่า 'num_qualified_teams' จาก URL (Frontend)
    # ถ้าไม่ได้ส่งมา ให้ใช้ค่าเริ่มต้น เช่น 8
    num_qualified_teams = request.args.get('num_qualified_teams', type=int, default=8)
    
    # ดึงข้อมูล Round ที่อาจจะส่งมา (ถ้ามี)
    # ถ้า 'round' ไม่ได้ถูกส่งมา, อาจจะถือว่าเป็นการดาวน์โหลดตารางคะแนนรวม
    requested_round = request.args.get('round', type=int) 
    
    standings_data = calculate_standings(event_id) # เรียกใช้ฟังก์ชันเดิม
    
    # ถ้ามีการระบุ round ให้กรองข้อมูล (สำหรับตอนนี้ ยังคง pass ไว้)
    if requested_round:
        # คุณอาจจะต้องปรับ calculate_standings ในไฟล์ standings.py ให้รับ round_number
        # หรือกรองข้อมูล standings_data ที่นี่ หากข้อมูลที่ได้กลับมามีรายละเอียดรอบอยู่
        pass 

    output = io.BytesIO()
    wb = Workbook()
    ws = wb.active
    ws.title = "Standings"

    # --- Header Information (ชื่อกิจกรรม, ประเภท, รุ่น) ---
    ws.merge_cells('A1:F1') # รวมเซลล์สำหรับหัวข้อหลัก
    ws['A1'] = f"รายงานผลจัดลำดับ: {current_event.name}"
    ws['A1'].font = Font(bold=True, size=14)
    ws['A1'].alignment = Alignment(horizontal='center', vertical='center')

    ws.merge_cells('A2:F2') # รวมเซลล์สำหรับประเภทและรุ่น
    # ใช้ฟิลด์ category และ age_group ตามที่เราได้ตกลงกันไว้ใน models.py
    event_type_str = current_event.category if hasattr(current_event, 'category') and current_event.category else 'ไม่ระบุประเภท'
    event_category_str = current_event.age_group if hasattr(current_event, 'age_group') and current_event.age_group else 'ไม่ระบุรุ่น'
    ws['A2'] = f"ประเภท: {event_type_str} | รุ่น: {event_category_str}"
    ws['A2'].font = Font(size=12)
    ws['A2'].alignment = Alignment(horizontal='center', vertical='center')

    # ถ้ามีข้อมูลรอบที่เฉพาะเจาะจงที่ดาวน์โหลด
    if requested_round:
        ws.merge_cells('A3:F3') # รวมเซลล์สำหรับรอบที่
        ws['A3'] = f"ครั้งการแข่งขัน: รอบที่ {requested_round}"
        ws['A3'].font = Font(bold=True)
        ws['A3'].alignment = Alignment(horizontal='center', vertical='center')
        header_row_start = 5 # ถ้ามีรอบ จะเริ่มหัวตารางที่แถว 5
    else:
        header_row_start = 4 # ไม่มีรอบ จะเริ่มหัวตารางที่แถว 4
    
    ws.row_dimensions[1].height = 25 # กำหนดความสูงของแถว
    ws.row_dimensions[2].height = 20
    if requested_round: ws.row_dimensions[3].height = 20

    # --- Table Headers (หัวตาราง) ---
    # ******************************** สำคัญ: ลบ "Point For" และ "Point Against" ออกจาก headers ********************************
    headers = ["อันดับ", "ชื่อทีม", "คะแนน", "BHN", "fBHN", "Point Diff"] 
    col_start = 1 # เริ่มต้นคอลัมน์ A (Excel)
    for col_num, header in enumerate(headers, col_start):
        cell = ws.cell(row=header_row_start, column=col_num, value=header)
        cell.font = Font(bold=True, color="FFFFFF") # กำหนดฟอนต์ตัวหนาและสีข้อความเป็นสีขาว
        cell.alignment = Alignment(horizontal='center', vertical='center') # จัดกึ่งกลาง
        cell.fill = PatternFill(start_color="4CAF50", end_color="4CAF50", fill_type="solid") # สีพื้นหลังหัวตารางเป็นสีเขียวเข้ม
        cell.border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin')) # ขอบเซลล์

    # --- Data Rows (ข้อมูลทีมและการกำหนดสีแถว) ---
    row_num = header_row_start + 1 # เริ่มต้นแถวข้อมูลหลังจากหัวตาราง
    for i, team in enumerate(standings_data, 1): # i คืออันดับทีม
        # กำหนดสไตล์เริ่มต้น (ไม่มีพื้นหลัง)
        row_fill = None
        row_font = Font() # ฟอนต์ปกติ
        row_border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))
        
        # ถ้าทีมนี้เป็นทีมที่เข้ารอบ (อันดับ <= num_qualified_teams) ให้กำหนดสีพื้นหลัง
        if i <= num_qualified_teams:
            row_fill = PatternFill(start_color="D4EDDA", end_color="D4EDDA", fill_type="solid") # สีเขียวอ่อนสำหรับทีมเข้ารอบ
            row_font = Font(color="000000") # สีข้อความดำสำหรับทีมเข้ารอบ
        else:
            # กำหนดสีพื้นหลังสำหรับทีมที่ตกรอบ
            row_fill = PatternFill(start_color="FFFFFF", end_color="FFFFFF", fill_type="solid") # สีขาวสำหรับทีมตกรอบ
            row_font = Font(color="000000") # สีข้อความดำสำหรับทีมตกรอบ


        # ใส่ข้อมูลและกำหนดสไตล์ให้กับแต่ละเซลล์ในแถวนี้
        ws.cell(row=row_num, column=1, value=i).alignment = Alignment(horizontal='center')
        ws.cell(row=row_num, column=2, value=team['team_name'])
        ws.cell(row=row_num, column=3, value=team['score']).alignment = Alignment(horizontal='center')
        ws.cell(row=row_num, column=4, value=team['buchholz']).alignment = Alignment(horizontal='center')
        ws.cell(row=row_num, column=5, value=team['final_buchholz']).alignment = Alignment(horizontal='center')
        # ******************************** สำคัญ: ลบ team['point_for'] และ team['point_against'] ออก ********************************
        # ******************************** และปรับ column ของ 'point_diff' เป็น 6 ********************************
        ws.cell(row=row_num, column=6, value=f"{team['point_for']}:{team['point_against']}").alignment = Alignment(horizontal='center') 

        # วนลูปเพื่อกำหนดสีพื้นหลัง, ฟอนต์ และขอบให้กับทุกเซลล์ในแถวปัจจุบัน
        # len(headers) จะเป็น 6 (ตามจำนวน headers ใหม่) ทำให้ลูปวนแค่ 6 คอลัมน์
        for col_idx in range(1, len(headers) + 1): 
            cell = ws.cell(row=row_num, column=col_idx)
            if row_fill:
                cell.fill = row_fill
            if row_font:
                cell.font = row_font
            cell.border = row_border # ใช้ border ที่กำหนดไว้
        
        row_num += 1

    # --- Auto-size Columns --- 
    for col_cells in ws.columns: # 'col_cells' ตอนนี้คือ tuple ของเซลล์ในคอลัมน์นั้นๆ แล้ว
        max_length = 0
        # เราจะวนลูปโดยตรงผ่าน tuple ของเซลล์ในคอลัมน์นั้นๆ
        for cell in col_cells:
            try:
                if cell.value is not None: # ตรวจสอบว่ามีค่าในเซลล์ก่อน
                    cell_value_str = str(cell.value)
                    if len(cell_value_str) > max_length:
                        max_length = len(cell_value_str)
            except:
                pass
        
        # ปรับความกว้างของคอลัมน์
        adjusted_width = (max_length + 2)
        if col_cells: # ตรวจสอบว่า col_cells ไม่ว่างเปล่าก่อนเข้าถึง [0] เพื่อหา column letter
            ws.column_dimensions[get_column_letter(col_cells[0].column)].width = adjusted_width

    wb.save(output)
    output.seek(0)

    # --- ตั้งชื่อไฟล์ Excel สำหรับดาวน์โหลด ---
    # ทำให้ชื่อไฟล์สะอาดสำหรับ URL
    event_name_safe = current_event.name.replace(" ", "_").replace("/", "-")
    # ใช้ค่าที่ได้จาก current_event.category และ current_event.age_group
    event_type_safe = event_type_str.replace(" ", "_").replace("/", "-")
    event_category_safe = event_category_str.replace(" ", "_").replace("/", "-")
    
    filename_parts = [
        event_name_safe,
        event_type_safe,
        event_category_safe
    ]
    if requested_round:
        filename_parts.append(f"Round_{requested_round}")

    filename = "_".join(part for part in filename_parts if part) + "_Standings.xlsx"

    return send_file(output, as_attachment=True, download_name=filename, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

#--------------------------------------------------------------------------------------
# เส้นทางใหม่สำหรับนำข้อมูลทีมที่ได้ไปจัดทำตารางรอบน็อคเอาท์
@app.route('/event/<int:event_id>/create_bracket')
@login_required
def create_bracket(event_id):
    current_event = Event.query.get_or_404(event_id)
    standings_data = calculate_standings(event_id)

    num_qualified_teams = request.args.get('num_qualified_teams', type=int, default=8)
    if num_qualified_teams > len(standings_data):
        num_qualified_teams = len(standings_data)
    if num_qualified_teams < 0:
        num_qualified_teams = 0

    qualified_teams = standings_data[:num_qualified_teams]

    # ส่งข้อมูลทีมที่เข้ารอบไปยัง template ใหม่สำหรับสร้างตารางรอบน็อคเอาท์
    return render_template(
        'bracket_setup.html', # คุณจะต้องสร้างไฟล์นี้ขึ้นมา
        event=current_event,
        qualified_teams=qualified_teams
    )

# --- เพิ่ม Route สำหรับบันทึกการจับคู่ ---
@app.route('/event/<int:event_id>/save_bracket_pairings', methods=['POST'])
@login_required # ถ้าต้องการให้ต้อง Login ก่อน
def save_bracket_pairings(event_id):
    """
    ฟังก์ชันนี้จะรับข้อมูลการจับคู่รอบน็อคเอาท์จากฟอร์มใน bracket_setup.html
    และทำการบันทึกข้อมูลนั้นลงในฐานข้อมูล
    """
    try:
        # รับข้อมูลการจับคู่จากฟอร์ม
        # วิธีการรับข้อมูลขึ้นอยู่กับว่าคุณสร้างฟอร์มใน bracket_setup.html อย่างไร
        # ตัวอย่าง: หากคุณใช้ JavaScript ส่งข้อมูลเป็น JSON
        # pairings_data = request.get_json()

        # ตัวอย่าง: หากคุณใช้ input hidden field ชื่อ 'pairings_json' เก็บ JSON string
        pairings_json = request.form.get('pairings_data') # สมมติว่ามี input field ชื่อ 'pairings_data'
        if pairings_json:
            pairings_list = json.loads(pairings_json)
            
            # === ส่วนนี้คือที่คุณจะเขียนโค้ดเพื่อบันทึกข้อมูลลงฐานข้อมูล ===
            # วนลูปผ่าน pairings_list และสร้าง/อัปเดต Match objects
            # for pairing in pairings_list:
            #     team1_id = pairing['team1_id']
            #     team2_id = pairing['team2_id']
            #     round_num = pairing.get('round', 1) # กำหนดรอบเริ่มต้น
            #     
            #     # ตรวจสอบว่าคู่นี้มีอยู่แล้วหรือไม่ หรือสร้างใหม่
            #     # existing_match = Match.query.filter_by(event_id=event_id, round=round_num, team1_id=team1_id, team2_id=team2_id).first()
            #     # if not existing_match:
            #     #    new_match = Match(event_id=event_id, team1_id=team1_id, team2_id=team2_id, round=round_num, is_locked=False)
            #     #    db.session.add(new_match)
            # db.session.commit() # บันทึกการเปลี่ยนแปลงทั้งหมดในคราวเดียว
            # === จบส่วนบันทึกข้อมูล ===
            
            flash('บันทึกการจับคู่รอบน็อคเอาท์สำเร็จ!', 'success')
        else:
            flash('ไม่พบข้อมูลการจับคู่ที่จะบันทึก', 'warning')

        # หลังจากบันทึกเสร็จแล้ว Redirect ไปยังหน้าที่แสดง Bracket ที่สร้างเสร็จ
        # หรือกลับไปหน้า create_bracket อีกครั้ง
        return redirect(url_for('create_bracket', event_id=event_id))

    except Exception as e:
        # db.session.rollback() # หากมีการใช้ db.session.add/commit และเกิดข้อผิดพลาด
        flash(f'เกิดข้อผิดพลาดในการบันทึกการจับคู่: {str(e)}', 'danger')
        return redirect(url_for('create_bracket', event_id=event_id))



def calculate_end_time(duration: str):
    now = datetime.utcnow()
    if duration == '1d':
        return now + timedelta(days=1)
    elif duration == '1w':
        return now + timedelta(weeks=1)
    elif duration == '1m':
        return now + timedelta(days=30)
    elif duration == '1y':
        return now + timedelta(days=365)
    elif duration == 'forever':
        return None
    else:
        return None



#--------------------------------------------------------------------------------------

def setup():   
    with app.app_context():
        db.create_all()  # สร้างตารางถ้ายังไม่มี 

        # สร้าง superadmin ถ้ายังไม่มี
        if not User.query.filter_by(username='superadmin').first():
            superadmin = User(username='superadmin', role='superadmin')
            superadmin.set_password('yagami1225')
            db.session.add(superadmin)
            print("Superadmin user created.")

        # สร้าง admin ถ้ายังไม่มี
        if not User.query.filter_by(username='admin').first():
            admin = User(username='admin', role='admin')
            admin.set_password('Admin1234!')
            db.session.add(admin)
            print("Admin user created.")

        db.session.commit()



if __name__ == '__main__':
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    setup()
    socketio.run(app, debug=True)