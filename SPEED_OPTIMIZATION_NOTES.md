# SPEED_OPTIMIZATION_NOTES

ปรับให้หน้าแรกโหลดเร็วขึ้น

## จุดที่แก้
- `app.py`
  - เปลี่ยนหน้า `/` จากเดิมที่ดึง `Event` ทั้งหมดแล้ววน query `Match` ทีละรายการ
  - ใช้ subquery หา event ที่ยังมี match ไม่ล็อกอยู่
  - จำกัดรายการกำลังแข่งขัน/ยังไม่จบไว้ 12 รายการ
  - รายการที่จบแล้วใช้ pagination ค่าเริ่มต้น 20 รายการต่อหน้า
  - เพิ่ม `_ensure_speed_indexes()` เพื่อสร้าง index ให้ฐานข้อมูลเดิมอัตโนมัติ
- `templates/index.html`
  - เพิ่ม pagination
  - เพิ่มตัวเลือกจำนวนรายการต่อหน้า 10/20/30/50
- `models.py`
  - เพิ่ม index สำหรับ `events.date`
  - เพิ่ม index สำหรับ `matches.event_id`, `round`, `is_locked`

## ผลที่คาดหวัง
หน้าแรกจะไม่ render รายการทั้งหมดและไม่ยิง query ซ้ำทีละ event แล้ว จึงควรตอบสนองเร็วขึ้นชัดเจน โดยเฉพาะบน Railway + SQLite
