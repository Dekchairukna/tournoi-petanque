# Performance fix: หลายอีเวนต์พร้อมกันแล้วบันทึกคะแนนช้า

แก้จุดหลักที่ทำให้ระบบดีเลย์เมื่อเปิดหลายอีเวนต์/หลายสนามพร้อมกัน

## สิ่งที่แก้

1. เปลี่ยน Socket.IO จาก `threading` เป็น `eventlet`
   - Railway/Gunicorn รองรับงาน realtime ได้ดีกว่า gthread
   - แก้ Procfile เป็น `--worker-class eventlet`

2. ลด broadcast ทั้งระบบ
   - เดิม `score_updated` และ `pending_score_updated` ส่งให้ทุกหน้าทุกอีเวนต์
   - แก้ให้ส่งเฉพาะห้อง `event_<id>_round_<round>`
   - เวลาแข่งหลายอีเวนต์พร้อมกัน จะไม่ลากทุกเครื่องให้รับ event ที่ไม่เกี่ยวข้อง

3. ให้หน้า round join room ทันทีเมื่อ socket connect
   - เพื่อรับคะแนนสดเฉพาะรอบที่เปิดอยู่

4. ลดการยิงบันทึกถี่เกินไป
   - ช่องคะแนนหน้า round debounce จาก 500ms เป็น 900ms
   - autosave สกอร์การ์ดออนไลน์จะไม่ commit ถ้าข้อมูลไม่เปลี่ยน

5. เพิ่ม index ฐานข้อมูล
   - `matches(event_id, round)`
   - `matches(event_id, field)`
   - `teams(event_id)`

6. ถ้าใช้ SQLite
   - เปิด WAL
   - ตั้ง `busy_timeout=5000`
   - ลดอาการล็อกฐานข้อมูลเมื่อหลายคนบันทึกพร้อมกัน

7. ลด polling หน้า playoff
   - จากทุก 1.2 วินาที เป็น 3 วินาที

## วิธีอัปเดตขึ้น GitHub / Railway

```bash
cd ~/Downloads/tournoi-petanque-main
# แตกไฟล์นี้ทับโปรเจกต์เดิม หรือคัดลอกไฟล์ที่แก้ไปแทน

git status
git add app.py templates/round_matches.html templates/playoff_detail.html Procfile PERFORMANCE_FIX_NOTES.md
git commit -m "fix realtime performance for multiple events"
git push
```

## หมายเหตุสำคัญ

ถ้าใช้งานจริงหลายสนามพร้อมกันมาก ๆ แนะนำใช้ PostgreSQL แทน SQLite เพราะ SQLite เขียนพร้อมกันได้จำกัด แม้เปิด WAL แล้วก็ยังไม่เหมาะกับงาน realtime หลายเครื่องมาก ๆ
