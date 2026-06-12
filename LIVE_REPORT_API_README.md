# Live Report Board API ที่เพิ่มให้ Tournoi

เพิ่ม endpoint public สำหรับเว็บรายงานผล:

- `/api/public/events` รายการอีเวนต์
- `/api/public/event/<event_id>/live` คะแนนสด/ผลล่าสุด แยกตามรอบได้ด้วย `?round=1`
- `/api/public/event/<event_id>/standings` ตารางคะแนน Swiss
- `/api/public/event/<event_id>/playoffs` playoff/bracket
- `/api/public/event/<event_id>/report` รวมข้อมูลสำหรับ Report Board

เพิ่ม CORS และอนุญาต iframe แล้วใน `after_request`
