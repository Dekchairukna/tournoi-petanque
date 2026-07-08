# SPEED_CLICK_REALTIME_FIX

แพตช์นี้แก้ให้หน้า round เบาลงและยังคงคะแนน realtime แบบไม่ refresh หน้า

## ตัด/ปิด
- ไม่คำนวณ Standing อัตโนมัติทุกครั้งที่เปิดหน้า round
- ปิด round_live_refresh.js เก่า ไม่ให้สั่ง reload หน้า
- ไม่ emit คะแนนซ้ำถ้าคะแนนเดิมไม่ได้เปลี่ยน
- ลด console log ฝั่ง browser
- ลด request ซ้อนจาก input คะแนน 2 ช่อง ให้ debounce ต่อคู่แข่งขัน

## เหลือ
- Socket.IO realtime คะแนน
- join ห้องเฉพาะ event/round
- กรอกคะแนนแล้วอีกเครื่องเห็นคะแนนโดยไม่ refresh
- ปุ่มโหลดตารางคะแนนเมื่ออยากดู Standing

## ไฟล์ที่ต้องทับ
- app.py
- Procfile
- templates/round_matches.html
- static/js/round_live_refresh.js
