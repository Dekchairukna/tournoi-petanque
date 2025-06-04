@app.route("/event/<int:event_id>/pair_next_round", methods=['POST'])
@login_required
@roles_required('admin')
def pair_next_round(event_id):
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