from collections import defaultdict
from datetime import datetime, timedelta
import random
import time

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from models import db, Event, Team, Match, EventRoundRobinConfig, EventRoundRobinGroup, EventRoundRobinMember

rr_bp = Blueprint("rr_event", __name__)
_socketio = None
_timer_states = {}

def _admin():
    return current_user.is_authenticated and current_user.role in {"admin", "superadmin"}

def _config(event):
    cfg = EventRoundRobinConfig.query.filter_by(event_id=event.id).first()
    if not cfg:
        cfg = EventRoundRobinConfig(event_id=event.id)
        db.session.add(cfg)
        db.session.flush()
    return cfg

def _sizes(n, g):
    g=max(1,min(g,n or 1)); base=n//g; rem=n%g
    return [base+(1 if i<rem else 0) for i in range(g)]

def _pair_pattern(n):
    if n == 5:
        return [[(1,2),(3,4),(5,None)],[(1,3),(2,5),(4,None)],[(1,5),(2,4),(3,None)],[(1,4),(3,5),(2,None)],[(2,3),(4,5),(1,None)]]
    values=list(range(1,n+1))
    if n%2: values.append(None)
    rounds=[]
    for _ in range(len(values)-1):
        pairs=[]
        for i in range(len(values)//2):
            a,b=values[i],values[-1-i]
            if a is None: a,b=b,a
            if a is not None and b is not None and a>b: a,b=b,a
            pairs.append((a,b))
        pairs.sort(key=lambda p:(p[1] is None,p[0] or 999))
        rounds.append(pairs)
        values=[values[0],values[-1],*values[1:-1]]
    return rounds

def _assign(event,cfg,method):
    teams=Team.query.filter_by(event_id=event.id).order_by(Team.id.asc()).all()
    if method=='random': random.shuffle(teams)
    elif method=='seed': teams.sort(key=lambda t:t.id)
    elif method=='snake': teams.sort(key=lambda t:t.id)
    old_groups=EventRoundRobinGroup.query.filter_by(event_id=event.id).all()
    for old_group in old_groups:
        db.session.delete(old_group)
    db.session.flush()
    sizes=_sizes(len(teams),cfg.group_count)
    groups=[]
    if method=='snake':
        buckets=[[] for _ in sizes]
        direction=1; gi=0
        for team in teams:
            buckets[gi].append(team)
            if direction==1:
                if gi==len(buckets)-1: direction=-1
                else: gi+=1
            else:
                if gi==0: direction=1
                else: gi-=1
        group_teams=buckets
    else:
        group_teams=[]; p=0
        for size in sizes:
            group_teams.append(teams[p:p+size]); p+=size
    for idx,items in enumerate(group_teams):
        group=EventRoundRobinGroup(event_id=event.id,name=chr(65+idx),position=idx+1)
        db.session.add(group); db.session.flush()
        for slot,team in enumerate(items,start=1):
            db.session.add(EventRoundRobinMember(group_id=group.id,team_id=team.id,slot_no=slot))
        groups.append(group)
    db.session.flush(); return groups

def _assign_manual(event,cfg,form):
    teams=Team.query.filter_by(event_id=event.id).order_by(Team.id.asc()).all()
    parsed=[]; used=set()
    for team in teams:
        raw=(form.get(f'manual_{team.id}') or '').strip().upper().replace(' ','')
        if not raw:
            raise ValueError(f'ยังไม่ได้กำหนดตำแหน่งให้ {team.name}')
        import re
        match=re.match(r'^([A-Z]+)(\d+)$',raw)
        if not match:
            raise ValueError(f'ตำแหน่ง {raw} ไม่ถูกต้อง ใช้รูปแบบ A1, A2, B1')
        key=(match.group(1),int(match.group(2)))
        if key in used:
            raise ValueError(f'ตำแหน่ง {raw} ซ้ำ')
        used.add(key); parsed.append((team,key[0],key[1]))
    old_groups=EventRoundRobinGroup.query.filter_by(event_id=event.id).all()
    for old_group in old_groups: db.session.delete(old_group)
    db.session.flush()
    grouped=defaultdict(list)
    for team,name,slot in parsed: grouped[name].append((slot,team))
    groups=[]
    for pos,name in enumerate(sorted(grouped),start=1):
        slots=sorted(grouped[name])
        expected=list(range(1,len(slots)+1))
        actual=[slot for slot,_ in slots]
        if actual!=expected: raise ValueError(f'สาย {name} ต้องเรียงเลขต่อกันตั้งแต่ 1')
        group=EventRoundRobinGroup(event_id=event.id,name=name,position=pos)
        db.session.add(group); db.session.flush()
        for slot,team in slots: db.session.add(EventRoundRobinMember(group_id=group.id,team_id=team.id,slot_no=slot))
        groups.append(group)
    cfg.group_count=len(groups)
    db.session.flush(); return groups

def _generate(event,cfg,groups):
    Match.query.filter_by(event_id=event.id).delete(synchronize_session=False)
    start=datetime.strptime(cfg.first_time or '09:00','%H:%M')
    field=event.field_start or 1
    excluded={int(x) for x in (event.field_exclude or '').split(',') if x.strip().isdigit()}
    max_field=event.field_max or 16
    def next_field(v):
        while v in excluded: v+=1
        if v>max_field: v=event.field_start or 1
        while v in excluded: v+=1
        return v
    max_round=max((len(_pair_pattern(len(g.members))) for g in groups),default=0)
    for round_no in range(1,max_round+1):
        field_cursor=field
        for group in groups:
            pattern=_pair_pattern(len(group.members))
            if round_no>len(pattern): continue
            members={m.slot_no:m for m in group.members}
            for a,b in pattern[round_no-1]:
                m1=members.get(a); m2=members.get(b) if b else None
                match=Match(event_id=event.id,round=round_no,team1_id=m1.team_id,team2_id=m2.team_id if m2 else None,team1_score=0,team2_score=0,is_locked=False,is_manual=False)
                if m2 and event.auto_field_enabled:
                    field_cursor=next_field(field_cursor)
                    match.field=field_cursor
                    field_cursor+=1
                db.session.add(match)
        start += timedelta(minutes=cfg.match_minutes+cfg.break_minutes)
    event.rounds=max_round

def _stats(group, matches, advance):
    """คำนวณอันดับ Round Robin ตามเกณฑ์ที่ตกลงไว้

    1) คะแนนรวม = จำนวนชนะทั้งหมด
    2) ถ้าเสมอ 2 ทีม ใช้ผลพบกันโดยตรง
    3) ถ้าเสมอ 3 ทีมขึ้นไป ใช้คะแนนคู่กรณี (จำนวนชนะเฉพาะกลุ่มเสมอ)
    4) คะแนนสุทธิคู่กรณี = แต้มได้ - แต้มเสีย เฉพาะกลุ่มเสมอ
    5) หากยังเสมอ ใช้ผลต่างคะแนนรวม
    """
    rows = {
        member.team_id: {
            'team_id': member.team_id,
            'team_name': member.team.name,
            'slot': f'{group.name}{member.slot_no}',
            'wins': 0,
            'losses': 0,
            'pf': 0,
            'pa': 0,
            'diff': 0,
            'opponent_score': 0,
            'opponent_pf': 0,
            'opponent_pa': 0,
            'opponent_diff': 0,
            'rank': 0,
            'qualified': False,
        }
        for member in group.members
    }
    ids = set(rows)
    locked_matches = []

    for match in matches:
        if (
            match.team2_id is None
            or not match.is_locked
            or match.team1_id not in ids
            or match.team2_id not in ids
        ):
            continue

        s1 = int(match.team1_score or 0)
        s2 = int(match.team2_score or 0)
        locked_matches.append(match)

        rows[match.team1_id]['pf'] += s1
        rows[match.team1_id]['pa'] += s2
        rows[match.team2_id]['pf'] += s2
        rows[match.team2_id]['pa'] += s1

        if s1 > s2:
            rows[match.team1_id]['wins'] += 1
            rows[match.team2_id]['losses'] += 1
        elif s2 > s1:
            rows[match.team2_id]['wins'] += 1
            rows[match.team1_id]['losses'] += 1

    for row in rows.values():
        row['diff'] = row['pf'] - row['pa']

    # แบ่งกลุ่มทีมที่คะแนนรวมเท่ากัน และคำนวณเฉพาะผลระหว่างคู่กรณี
    buckets = defaultdict(list)
    for row in rows.values():
        buckets[row['wins']].append(row)

    tie_groups = []
    for bucket in buckets.values():
        if len(bucket) <= 1:
            continue

        tie_ids = {row['team_id'] for row in bucket}
        tie_groups.append(tie_ids)

        for match in locked_matches:
            if match.team1_id not in tie_ids or match.team2_id not in tie_ids:
                continue

            s1 = int(match.team1_score or 0)
            s2 = int(match.team2_score or 0)
            r1 = rows[match.team1_id]
            r2 = rows[match.team2_id]

            r1['opponent_pf'] += s1
            r1['opponent_pa'] += s2
            r2['opponent_pf'] += s2
            r2['opponent_pa'] += s1

            if s1 > s2:
                r1['opponent_score'] += 1
            elif s2 > s1:
                r2['opponent_score'] += 1

        for row in bucket:
            row['opponent_diff'] = row['opponent_pf'] - row['opponent_pa']

    def head_to_head_value(team_id, tied_ids):
        """ใช้เฉพาะกรณีเสมอกัน 2 ทีม"""
        if len(tied_ids) != 2:
            return 0
        for match in locked_matches:
            if {match.team1_id, match.team2_id} != tied_ids:
                continue
            s1 = int(match.team1_score or 0)
            s2 = int(match.team2_score or 0)
            if s1 == s2:
                return 0
            winner = match.team1_id if s1 > s2 else match.team2_id
            return 1 if winner == team_id else -1
        return 0

    ordered = []
    # เรียงกลุ่มคะแนนรวมจากมากไปน้อยก่อน แล้วจัดอันดับภายในกลุ่มเสมอ
    for total_wins in sorted(buckets.keys(), reverse=True):
        bucket = buckets[total_wins]
        tied_ids = {row['team_id'] for row in bucket}

        if len(bucket) == 1:
            ordered.extend(bucket)
        elif len(bucket) == 2:
            bucket.sort(
                key=lambda row: (
                    -head_to_head_value(row['team_id'], tied_ids),
                    -row['diff'],
                    -row['pf'],
                    row['team_name'],
                )
            )
            ordered.extend(bucket)
        else:
            bucket.sort(
                key=lambda row: (
                    -row['opponent_score'],
                    -row['opponent_diff'],
                    -row['diff'],
                    -row['pf'],
                    row['team_name'],
                )
            )
            ordered.extend(bucket)

    for index, row in enumerate(ordered, start=1):
        row['rank'] = index
        row['qualified'] = index <= advance
        # ชื่อฟิลด์ให้ตรงกับหัวตาราง Matrix ที่ตกลงกัน
        row['total_score'] = row['wins']
        row['case_score'] = row['opponent_score']
        row['case_net_score'] = row['opponent_diff']

    return ordered

def _view(event,cfg):
    groups=EventRoundRobinGroup.query.filter_by(event_id=event.id).order_by(EventRoundRobinGroup.position).all()
    matches=Match.query.filter_by(event_id=event.id).order_by(Match.round,Match.field,Match.id).all()
    by_round=defaultdict(list)
    group_of={m.team_id:g.name for g in groups for m in g.members}
    slots={m.team_id:f'{g.name}{m.slot_no}' for g in groups for m in g.members}
    for m in matches:
        by_round[m.round].append({'match':m,'group':group_of.get(m.team1_id,'-'),'slot1':slots.get(m.team1_id,'-'),'slot2':slots.get(m.team2_id,'-') if m.team2_id else '-'})
    standings={}; matrices={}
    for g in groups:
        rows=_stats(g,matches,cfg.advance_per_group); standings[g.name]=rows
        ids={m.team_id for m in g.members}; scores={}
        for m in matches:
            if m.is_locked and m.team2_id and m.team1_id in ids and m.team2_id in ids:
                scores[(m.team1_id,m.team2_id)]=f'{m.team1_score}-{m.team2_score}'
                scores[(m.team2_id,m.team1_id)]=f'{m.team2_score}-{m.team1_score}'
        buckets=defaultdict(list)
        for r in rows: buckets[r['wins']].append(r)
        tie_ids=set(); tie_pairs=set()
        for bucket in buckets.values():
            if len(bucket)>1:
                ids2={r['team_id'] for r in bucket}; tie_ids|=ids2
                tie_pairs|={(a,b) for a in ids2 for b in ids2 if a!=b}
        matrices[g.name]={'members':g.members,'scores':scores,'stats':{r['team_id']:r for r in rows},'tie_pairs':tie_pairs,'tie_names':[r['team_name'] for r in rows if r['team_id'] in tie_ids]}
    return groups,dict(by_round),standings,matrices

@rr_bp.route('/event/<int:event_id>/round-robin',methods=['GET','POST'])
def round_robin_event(event_id):
    event=Event.query.get_or_404(event_id)
    if (event.competition_format or 'swiss')!='round_robin': return redirect(url_for('event_detail',event_id=event.id))
    cfg=_config(event)
    if request.method=='POST':
        if not _admin(): return redirect(url_for('rr_event.round_robin_event',event_id=event.id))
        action=request.form.get('action','generate')
        cfg.group_count=max(1,request.form.get('group_count',type=int) or cfg.group_count)
        cfg.advance_per_group=max(1,request.form.get('advance_per_group',type=int) or cfg.advance_per_group)
        cfg.pairing_method=request.form.get('pairing_method') or cfg.pairing_method
        cfg.first_time=request.form.get('first_time') or cfg.first_time
        cfg.match_minutes=max(1,request.form.get('match_minutes',type=int) or cfg.match_minutes)
        cfg.break_minutes=max(0,request.form.get('break_minutes',type=int) or cfg.break_minutes)
        event.auto_field_enabled = request.form.get('auto_field_enabled') == '1'
        event.field_prefix = (request.form.get('field_prefix') or '').strip()
        event.field_start = max(1, request.form.get('field_start', type=int) or event.field_start or 1)
        event.field_max = max(event.field_start, request.form.get('field_max', type=int) or event.field_max or 16)
        event.field_exclude = (request.form.get('field_exclude') or '').strip()
        if action=='settings':
            db.session.commit(); flash('บันทึกการตั้งค่า Round Robin แล้ว','success')
        else:
            if Match.query.filter_by(event_id=event.id).filter(Match.is_locked.is_(True)).first() and request.form.get('confirm_reset')!='1':
                flash('มีคะแนนแล้ว กรุณาติ๊กยืนยันก่อนสร้างตารางใหม่','warning')
                return redirect(url_for('rr_event.round_robin_event',event_id=event.id))
            try:
                groups=_assign_manual(event,cfg,request.form) if cfg.pairing_method=='manual' else _assign(event,cfg,cfg.pairing_method); _generate(event,cfg,groups); db.session.commit(); flash('แบ่งกลุ่มและสร้างตาราง Round Robin แล้ว','success')
            except Exception as exc:
                db.session.rollback(); flash(f'สร้างตารางไม่สำเร็จ: {exc}','danger')
        return redirect(url_for('rr_event.round_robin_event',event_id=event.id))
    teams=Team.query.filter_by(event_id=event.id).order_by(Team.name).all()
    groups,rounds,standings,matrices=_view(event,cfg)
    active_group=request.args.get('group') or (groups[0].name if groups else None)
    try: event.logo_list=__import__('json').loads(event.logo_filename) if event.logo_filename else []
    except Exception: event.logo_list=[]
    return render_template('event_round_robin.html',event=event,teams=teams,cfg=cfg,groups=groups,rounds=rounds,standings=standings,matrices=matrices,active_group=active_group,has_matches=Match.query.filter_by(event_id=event.id).first() is not None)


@rr_bp.route('/event/<int:event_id>/round-robin/print-pairings')
@login_required
def round_robin_print_pairings(event_id):
    event=Event.query.get_or_404(event_id)
    cfg=_config(event)
    groups,rounds,standings,matrices=_view(event,cfg)
    selected_round=request.args.get('round',type=int)
    if selected_round:
        rounds={selected_round:rounds.get(selected_round,[])}
    base_time = datetime.strptime(cfg.first_time or '09:00', '%H:%M')
    round_times = {
        round_no: (base_time + timedelta(minutes=(round_no - 1) * (cfg.match_minutes + cfg.break_minutes))).strftime('%H:%M')
        for round_no in rounds.keys()
    }
    return render_template(
        'round_robin_print_pairings.html',
        event=event,
        rounds=rounds,
        selected_round=selected_round,
        round_times=round_times,
        cfg=cfg,
    )

@rr_bp.route('/event/<int:event_id>/round-robin/live-data')
def round_robin_live_data(event_id):
    event=Event.query.get_or_404(event_id)
    cfg=_config(event)
    groups,rounds,standings,matrices=_view(event,cfg)
    return jsonify({
        'ok':True,
        'standings':standings,
        'matrices':{
            name:{
                'scores':{f'{a}:{b}':v for (a,b),v in data['scores'].items()},
                'stats':data['stats'],
                'tie_names':data['tie_names']
            } for name,data in matrices.items()
        }
    })

@rr_bp.route('/event/<int:event_id>/round-robin/score/<int:match_id>',methods=['POST'])
@login_required
def round_robin_score(event_id,match_id):
    if not _admin(): return jsonify({'ok':False}),403
    match=Match.query.filter_by(id=match_id,event_id=event_id).first_or_404()
    data=request.get_json(silent=True) or request.form
    try: s1=int(data.get('team1_score')); s2=int(data.get('team2_score'))
    except Exception: return jsonify({'ok':False,'error':'คะแนนไม่ถูกต้อง'}),400
    match.team1_score=s1; match.team2_score=s2; match.is_locked=True; db.session.commit()
    if _socketio:
        _socketio.emit('round_robin_score_updated',{'event_id':event_id,'match_id':match.id,'team1_score':s1,'team2_score':s2},to=f'event_{event_id}_all')
    return jsonify({'ok':True})

def register_round_robin_event(app,socketio):
    global _socketio
    _socketio=socketio
    app.register_blueprint(rr_bp)

    @socketio.on('round_robin_timer_request')
    def round_robin_timer_request(data):
        event_id = int((data or {}).get('event_id') or 0)
        if not event_id:
            return
        cfg = EventRoundRobinConfig.query.filter_by(event_id=event_id).first()
        default_seconds = max(1, int((cfg.match_minutes if cfg else 60) or 60)) * 60
        state = _timer_states.get(event_id) or {'running': False, 'remaining': default_seconds, 'end_at': None, 'version': 0}
        socketio.emit('round_robin_timer_state', {'event_id': event_id, **state}, to=request.sid)

    @socketio.on('round_robin_timer_command')
    def round_robin_timer_command(data):
        event_id = int((data or {}).get('event_id') or 0)
        command = (data or {}).get('command')
        if not event_id or command not in {'start', 'pause', 'reset'}:
            return
        now = time.time()
        cfg = EventRoundRobinConfig.query.filter_by(event_id=event_id).first()
        default_seconds = max(1, int((cfg.match_minutes if cfg else 60) or 60)) * 60
        old = _timer_states.get(event_id) or {'running': False, 'remaining': default_seconds, 'end_at': None, 'version': 0}
        remaining = max(0, int(round((old.get('end_at') or now) - now))) if old.get('running') else max(0, int(old.get('remaining') or 0))
        if command == 'start':
            if remaining <= 0:
                remaining = default_seconds
            state = {'running': True, 'remaining': remaining, 'end_at': now + remaining, 'version': int(old.get('version') or 0) + 1}
        elif command == 'pause':
            state = {'running': False, 'remaining': remaining, 'end_at': None, 'version': int(old.get('version') or 0) + 1}
        else:
            state = {'running': False, 'remaining': default_seconds, 'end_at': None, 'version': int(old.get('version') or 0) + 1}
        _timer_states[event_id] = state
        socketio.emit('round_robin_timer_state', {'event_id': event_id, **state}, to=f'event_{event_id}_all')
