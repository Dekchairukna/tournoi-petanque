from flask import Flask, render_template, request, redirect, url_for, flash
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

load_dotenv()
app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "your_secret_key")
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:vpIukBThkAUpgSjNcTAaQTssfCOAYjSW@trolley.proxy.rlwy.net:46680/railway'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config["UPLOAD_FOLDER"] = "uploads"
#app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://swiss_user:pRF2UGRYcncpoB7byrGFn1c6RrVnMwio@dpg-d0q4qqmuk2gs73a8ba50-a.singapore-postgres.render.com/swissdb'


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

@app.route("/event/<int:event_id>/standings")
def standings(event_id):
    standings_list = calculate_standings(event_id)
    return render_template("standings.html", standings=standings_list, event_id=event_id)


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

    all_events = Event.query.order_by(Event.date).all()

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

    print("DEBUG standings:", standings)

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

        new_teams = 0
        for name in df["team_name"]:
            if not Team.query.filter_by(name=name, event_id=event_id).first():
                db.session.add(Team(name=name, event_id=event_id))
                new_teams += 1
        db.session.commit()

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


@app.route('/event/<int:event_id>/add_team', methods=['POST'])
@roles_required('admin')  # เพิ่มบรรทัดนี้
def add_team_route(event_id):

    
    # เช็คสถานะล็อกแมตช์
    locked_match = Match.query.filter_by(event_id=event_id, is_locked=True).first()
    if locked_match:
        flash('ไม่สามารถเพิ่มทีมหลังจากเริ่มจับคู่แล้ว', 'danger')
        return redirect(url_for('event_detail', event_id=event_id))

    team_name = request.form.get('team_name')
    if not team_name or team_name.strip() == '':
        flash('กรุณากรอกชื่อทีม', 'danger')
        return redirect(url_for('event_detail', event_id=event_id))

    existing_team = Team.query.filter_by(name=team_name.strip(), event_id=event_id).first()
    if existing_team:
        flash('ชื่อทีมนี้มีอยู่แล้ว', 'warning')
        return redirect(url_for('event_detail', event_id=event_id))

    new_team = Team(name=team_name.strip(), event_id=event_id)
    db.session.add(new_team)
    db.session.commit()
    flash('เพิ่มทีมเรียบร้อย', 'success')
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
    event = Event.query.get(event_id)
    if event is None:
        flash("ไม่พบรายการแข่งขันนี้", "warning")
        return redirect(url_for("event.html"))

    existing_matches = Match.query.filter_by(event_id=event_id, round=1).count()
    if existing_matches > 0:
        flash("มีการจับคู่รอบแรกแล้ว", "warning")
        return redirect(url_for("event_detail", event_id=event_id))

    teams = Team.query.filter_by(event_id=event_id).all()
    if len(teams) < 2:
        flash("ต้องมีทีมอย่างน้อย 2 ทีมในการจับคู่", "warning")
        return redirect(url_for("event_detail", event_id=event_id))

    separate_same_name = request.form.get('separate_same_name') == 'on'

    import random
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
            if separate_same_name and team1.name == team2.name:
                continue  # ข้ามถ้าชื่อซ้ำ
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

    if existing_matches > 0:
        flash('ไม่สามารถลบทีมได้เนื่องจากมีการจับคู่แล้ว', 'danger')
        return redirect(url_for('index'))

    # ถ้ายังไม่มีแมตช์ที่ประกบคู่ทีมนี้ ลบได้เลย
    Match.query.filter(
        ((Match.team1_id == team_id) | (Match.team2_id == team_id)) &
        (Match.event_id == event_id)
    ).delete()

    db.session.delete(team)
    db.session.commit()
    flash('ลบทีมเรียบร้อยแล้ว', 'success')
    return redirect(url_for('event_detail', event_id=event_id))

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


# app.py

# ... (ส่วน import ต่างๆ ของคุณด้านบน)

@app.route('/event/<int:event_id>/pair_next_round', methods=['POST'])
@login_required
@roles_required('admin', 'superadmin')
def pair_next_round(event_id):
    event = Event.query.get_or_404(event_id)
    if not event.is_active:
        flash('ไม่สามารถจับคู่รอบถัดไปได้ เนื่องจากรายการแข่งขันนี้ปิดแล้ว', 'danger')
        return redirect(url_for('event_detail', event_id=event.id))

    current_round = event.current_round  # รอบปัจจุบัน
    next_round_num = current_round + 1

    # ตรวจสอบว่ามีทีมลงทะเบียนหรือไม่
    teams_in_event = Team.query.filter_by(event_id=event.id).all()
    if not teams_in_event:
        flash('ไม่มีทีมลงทะเบียนสำหรับรายการแข่งขันนี้', 'warning')
        return redirect(url_for('event_detail', event_id=event.id))

    # ดึงข้อมูลการจับคู่ที่ผ่านมาสำหรับตรวจสอบ
    past_matches = Match.query.filter_by(event_id=event.id).all()
    past_opponents = defaultdict(set) # เก็บว่าทีมไหนเคยเจอทีมไหนแล้ว
    for match in past_matches:
        if match.team1_id and match.team2_id:
            past_opponents[match.team1_id].add(match.team2_id)
            past_opponents[match.team2_id].add(match.team1_id)

    # ดึงทีมที่เคยได้ BYE ในรอบที่แล้ว
    bye_teams_ids = set()
    last_round_matches = Match.query.filter_by(event_id=event.id, round_num=current_round).all()
    for match in last_round_matches:
        if match.team1_id is None and match.team2_id:
            bye_teams_ids.add(match.team2_id)
        elif match.team2_id is None and match.team1_id:
            bye_teams_ids.add(match.team1_id)

    # แปลง teams_in_event ให้เป็น list ของ team_id เพื่อส่งให้ generate_pairings
    team_ids_in_event = [t.id for t in teams_in_event]
    
    try:
        # สร้างคู่แข่งขันสำหรับรอบถัดไป
        # generate_pairings จะคืนค่าเป็น list ของ tuple (team1_id, team2_id) โดยที่ team2_id จะเป็น None ถ้าเป็น BYE
        pairings = generate_pairings(event_id, next_round_num, team_ids_in_event, past_opponents, bye_teams_ids)

        if not pairings: # หากไม่มีคู่แข่งขัน (อาจเกิดจากมีทีมเดียวที่ไม่ได้จับคู่ หรือเกิดข้อผิดพลาดในการจับคู่)
            flash('ไม่สามารถจับคู่ได้ในรอบนี้ อาจมีปัญหาเรื่องจำนวนทีมหรือกฎการจับคู่', 'warning')
            return redirect(url_for('round_matches', event_id=event_id, round=current_round))

        # บันทึกคู่แข่งขันใหม่ลงฐานข้อมูล
        for team1_id, team2_id in pairings:
            score1 = None
            score2 = None

            # ตรวจสอบว่าเป็นคู่ BYE หรือไม่ และกำหนดคะแนน
            if team2_id is None: # ถ้า team2_id เป็น None แสดงว่า team1_id ได้ BYE
                score1 = 13  # ทีมที่ได้ BYE ได้ 13 คะแนน
                score2 = 7   # กำหนดคะแนนให้คู่ต่อสู้เสมือน (คะแนน BYE)
            # กรณีที่ team1_id เป็น None ไม่น่าจะเกิดขึ้นจากการ generate_pairings ของคุณ
            # เพราะ swiss_logic.py จะใส่ทีมที่ได้ BYE ไว้ในตำแหน่งแรกของ tuple (team_id, None)

            new_match = Match(
                event_id=event_id,
                round_num=next_round_num,
                team1_id=team1_id,
                team2_id=team2_id, # จะเป็น None ถ้าเป็น BYE
                team1_score=score1, # กำหนดคะแนนตามที่คำนวณไว้
                team2_score=score2, # กำหนดคะแนนตามที่คำนวณไว้
                field=None # สามารถกำหนดฟิลด์สำหรับ BYE หรือปล่อยให้เป็น None
            )
            db.session.add(new_match)

        # อัปเดตรอบปัจจุบันของ Event
        event.current_round = next_round_num
        db.session.commit()

        flash(f'จับคู่สำหรับรอบที่ {next_round_num} สำเร็จแล้ว!', 'success')
        return redirect(url_for('round_matches', event_id=event_id, round=next_round_num))

    except Exception as e:
        db.session.rollback() # ถ้ามีข้อผิดพลาด ให้ย้อนกลับการเปลี่ยนแปลง
        flash(f'เกิดข้อผิดพลาดในการจับคู่: {str(e)}', 'danger')
        return redirect(url_for('event_detail', event_id=event.id))




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

                if match.team2_id is not None and score2 is not None:
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
    app.run(debug=True)
