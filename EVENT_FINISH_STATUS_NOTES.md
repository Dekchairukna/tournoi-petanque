# EVENT FINISH STATUS NOTES

เพิ่มสถานะจบอีเว้นท์แบบกดเอง เพื่อกันอีเว้นท์โดดไปกลุ่มจบแล้วเองหลังคีย์/ล็อกรอบล่าสุดครบ

## สิ่งที่เพิ่ม
- เพิ่มคอลัมน์ใน `events`
  - `is_finished` boolean default false
  - `finished_at`
  - `finished_by_id`
- เพิ่ม runtime migration ใน `ensure_runtime_columns()` สำหรับ SQLite/PostgreSQL
- หน้าแรกแยกกลุ่มจาก `event.is_finished` เท่านั้น
  - ไม่เดาจาก `all(matches.is_locked)` แล้ว
- เพิ่มปุ่มล่างสุดในหน้าอีเว้นท์
  - `จบอีเว้นท์`
  - `เปิดกลับมาแข่งต่อ`
- สิทธิ์: admin / superadmin

## ผลลัพธ์
- รายการที่เพิ่งคีย์ครบบางรอบจะไม่โดดลงรายการจบแล้วเอง
- จะย้ายไปกลุ่ม “รายการแข่งขันที่จบแล้ว” เฉพาะเมื่อกดปุ่มจบอีเว้นท์เท่านั้น
