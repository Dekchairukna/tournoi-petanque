# Live-version removed

ตัดระบบ live-version ออกแล้วเพื่อลดอาการหน่วงเวลาเปิดหลายอีเวนต์พร้อมกัน

สิ่งที่เอาออก/ปิด:
- endpoint `/event/<event_id>/round/<round_no>/live-version`
- endpoint `/event/<event_id>/live-version`
- การคำนวณ fingerprint/hash ของ match ทุกครั้งที่เปิดหน้า
- `round_live_refresh.js`
- script ที่สั่ง reload หน้าอัตโนมัติจาก live-version
- การส่ง `live_version` เข้า template

สิ่งที่ยังคงไว้:
- Socket.IO สำหรับอัปเดตคะแนนในหน้า round เฉพาะรอบนั้น
- `join_round` room เพื่อจำกัด score update เฉพาะ event/round
- การบันทึกคะแนนแบบไม่ reload ทั้งหน้า

ผลที่คาดหวัง:
- หน้า round/score sheet/match pairs ไม่ยิง request ตรวจ version ซ้ำ ๆ
- กดคะแนนแล้วไม่เกิดการ reload ทั้งหน้า
- ลด query หนักในฐานข้อมูลเมื่อมีหลายอีเวนต์เปิดพร้อมกัน

หมายเหตุ:
- หลังสลับคู่ในหน้า swith หรือแก้เลขสนาม ผู้ใช้ที่เปิดหน้า round ค้างอยู่ควรกด refresh เองถ้าต้องการเห็นคู่/สนามล่าสุด
- ถ้ายังช้าเมื่อหลายสนามบันทึกพร้อมกัน คอขวดถัดไปคือ SQLite write lock ควรย้ายไป PostgreSQL
