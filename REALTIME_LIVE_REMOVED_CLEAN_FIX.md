# REALTIME LIVE REMOVED CLEAN FIX

แก้เฉพาะระบบ realtime/ความเร็วจากไฟล์ tournoi-petanque-main(13).zip

## เปลี่ยนแล้ว
- ตัดการพึ่ง live-version / reload หน้าออกจาก flow คะแนน
- คะแนนยัง link หากันผ่าน Socket.IO โดยไม่ refresh หน้าจอ
- เพิ่ม join_round เพื่อให้แต่ละหน้าเข้าห้อง event/round ของตัวเอง
- ส่ง score_updated / pending_score_updated เฉพาะห้อง event/round ไม่ broadcast ทั้งระบบ
- เปลี่ยน Procfile เป็น eventlet สำหรับ Socket.IO บน Railway
- ลด request ซ้อนจากช่องคะแนน: debounce 800ms และไม่ยิงตอนช่องว่าง
- ถ้าคะแนนเดิมซ้ำ ไม่ commit DB ซ้ำ

## ไฟล์ที่ต้องทับ
- app.py
- Procfile
- templates/round_matches.html

## เช็กหลังทับ
```bash
grep -R "broadcast=True\|live-version\|live_version\|round_live_refresh" -n app.py templates static Procfile || true
grep -R "join_round\|_emit_round\|worker-class eventlet" -n app.py templates/round_matches.html Procfile
```
