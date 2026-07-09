# BETA: Multi Event Print Reuse Original Templates

ปรับหน้า print รวมให้ใช้หน้าตาและ CSS จากของเดิมให้มากที่สุด

## ที่ปรับ
- `/multi-manage/print-pairings` ใช้โครง/หัวตาราง/สี/โลโก้/ช่องคะแนน/ปุ่มเสียงแบบ `match_pairs.html`
- `/multi-manage/print-score-sheets` ใช้โครง/ขนาดช่อง/ลายเซ็น/QR/โลโก้แบบ `score_sheet.html`
- ยังเป็นหน้า print รวมหลายอีเว้นท์ตามที่เลือกจาก `/multi-manage`
- ไม่แก้ logic การจับคู่หรือคีย์คะแนนเดิม

## ไฟล์ที่แก้
- `templates/multi_event_print_pairings.html`
- `templates/multi_event_print_score_sheets.html`
- `app.py` เพิ่ม `team_count` ในข้อมูลที่ส่งไปหน้า print รวม
