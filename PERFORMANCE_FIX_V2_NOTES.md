# PERFORMANCE FIX V2 - ลดดีเลย์ตอนหลายอีเวนต์บันทึกคะแนนพร้อมกัน

แก้คอขวดหลักที่ทำให้ระบบช้าเวลาเปิดหลายอีเวนต์/หลายสนามพร้อมกัน:

1. หยุด reload ทั้งหน้าเวลากดคะแนน
   - เดิม live_version เอาคะแนนไปรวมด้วย ทำให้กดคะแนนแล้วหน้า round reload ทั้งหน้า
   - แก้ให้ live_version ใช้เฉพาะการเปลี่ยนประกบคู่/สนาม/ทีมเท่านั้น
   - คะแนนอัปเดตเฉพาะช่องคะแนนผ่าน Socket.IO

2. จำกัด realtime ตามห้องของอีเวนต์/รอบ
   - score_updated / pending_score_updated ส่งเฉพาะ room: event_<id>_round_<round>
   - ไม่ broadcast ไปทุกหน้า/ทุกอีเวนต์

3. ลดการเขียนฐานข้อมูลซ้ำ
   - autosave สกอร์การ์ดไม่ commit ถ้าคะแนนเดิมเหมือนเดิม
   - หน้า playoff ไม่ DELETE/INSERT ถ้าคะแนนเดิมไม่เปลี่ยน
   - ช่องสนาม playoff ไม่ UPDATE ถ้าค่าเดิมเหมือนเดิม

4. ลด request จากหน้าเว็บ
   - debounce คะแนน round จาก 500ms เป็น 900ms
   - ส่งคะแนนเฉพาะเมื่อกรอกครบสองฝั่งและค่าต่างจากครั้งล่าสุด
   - online scorecard กัน autosave ซ้อนกันและรวม request
   - playoff polling จาก 1.2 วินาที เป็น 5 วินาที
   - autosave playoff จาก 350ms เป็น 900ms

5. ปรับ server realtime
   - Procfile ใช้ eventlet worker
   - SocketIO async_mode เป็น eventlet

6. เพิ่ม index ฐานข้อมูล
   - matches(event_id, round)
   - matches(event_id, field)
   - teams(event_id)
   - SQLite เปิด WAL + busy_timeout

หมายเหตุสำคัญ:
ถ้าระบบยังใช้ SQLite และมีหลายเครื่องเขียนคะแนนพร้อมกันมาก ๆ ยังมีโอกาสล็อก/ดีเลย์ได้ งานจริงควรใช้ PostgreSQL บน Railway เพื่อรองรับ concurrent writes ให้ดีกว่า
