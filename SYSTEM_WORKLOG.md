# บันทึกการปรับระบบและการตั้งค่า

อัปเดต: 20 กรกฎาคม 2026

## สิทธิ์ผู้ใช้

- `superadmin`: ใช้คีย์หลายอีเว้นท์, จัดการหลายอีเว้นท์, คีย์เพลย์ออฟหลายอีเว้นท์, นำเข้าหลายอีเว้นท์ และสร้างอีเว้นท์ที่ไม่ใช่ Swiss
- `admin`: จัดการอีเว้นท์ปกติและสร้างอีเว้นท์ Swiss
- `user`: ใช้งานส่วนกรอกผลที่ได้รับอนุญาต
- บัญชี `yagami` เป็นบัญชีเจ้าของระบบแบบ `superadmin` ถาวร ระบบสร้าง/ซ่อมสิทธิ์ให้อัตโนมัติเมื่อเริ่มแอป ซ่อนจากหน้าจัดการผู้ใช้ และป้องกันการแก้ไขหรือลบ
- รหัสเริ่มต้นของบัญชีเจ้าของระบบอ่านจาก `YAGAMI_SUPERADMIN_PASSWORD`; ถ้าไม่ตั้ง environment variable จะใช้ค่าที่กำหนดไว้ในระบบ

## การตั้งค่ามัลติอีเว้นท์

- แสดงช่องจำนวนสนามทั้งรอบปกติและเพลย์ออฟ ค่าเริ่มต้น 27 แต่กรอกจำนวนมากกว่านั้นได้ และระบบใช้ค่าที่กรอกจริง
- วิธีจับสลากใช้ชื่อชุดเดียวกับหน้า Standing: `seed`, `national_qualifier`, `random`, `manual`, `bracket`
- หน้าคีย์คะแนนหลายอีเว้นท์แสดงครั้งอย่างน้อย 1–10 และเปลี่ยนครั้งของรายการที่ติ๊กเลือกพร้อมกันได้
- หมวด 5 ตรวจความพร้อมของผลทุก 3 วินาทีและเปิดปุ่มจับสลากในหน้าเดิมเมื่อผลครบ
- ข้อความจาก `flash()` แสดงเป็นหน้าต่างกลางจอ ไม่เพิ่มกล่องข้อความด้านบนหน้า

## กลุ่มเร้าหลักใน app.py

- `/`, `/event/*`, `/tournament/*`: หน้าแรก อีเว้นท์ ทีม รอบแข่งขัน และทัวร์นาเมนต์
- `/multi-score`: คีย์คะแนน Swiss หลายอีเว้นท์ (superadmin)
- `/multi-manage`: จัดคู่ จัดสนาม Standing และจับสลากเพลย์ออฟหลายอีเว้นท์ (superadmin)
- `/multi-playoff-score`: คีย์คะแนนเพลย์ออฟหลายอีเว้นท์ (superadmin)
- `/api/multi-playoff-readiness`: ส่งสถานะพร้อมจับสลากให้หมวด 5 แบบไม่รีเฟรช (superadmin)
- `/admin/users/*`: เพิ่ม แก้ไข ลบ และแสดงผู้ใช้ตามสิทธิ์
- `/playoff/*`, `/event/*/knockout/*`, `/event/*/double-knockout/*`: ระบบเพลย์ออฟและรายงาน
- `/scorecard/*`, `/api/*`, Socket.IO: สกอร์การ์ด การอัปเดตผล และข้อมูลเรียลไทม์

## เร้าที่ตรวจและลบ

- ลบ `/users` และ `/users/add` รุ่นเก่า เพราะซ้ำกับ `/admin/users` และไม่มีตัวตรวจสิทธิ์
- ลบเร้าแก้ชื่อทีมที่ประกาศ URL ซ้ำ เหลือ `edit_teams_route` จุดเดียวซึ่งรองรับทั้งหน้าอีเว้นท์และ Round Robin
- เร้าอื่นที่ยังมีการอ้างอิงจากเทมเพลต การ redirect, JavaScript, API หรือรายงานถูกเก็บไว้เพื่อไม่ให้ลิงก์เดิมเสีย

## งานหน้าเว็บ

- หน้า Round Robin ใช้หัวอีเว้นท์แบบเรียบ และนาฬิกาจับเวลาซิงก์ผ่าน Socket.IO ให้ทุกเครื่องในอีเว้นท์เดียวกันเห็นเริ่ม/พัก/เริ่มใหม่พร้อมกัน
- ใบประกบคู่ Double Knockout: เลือก 1 = A4 แนวนอนเต็มหน้า, เลือก 2 = A4 แนวตั้งสองสายบน–ล่าง, เลือก 4 = A4 แนวนอน 2×2 สำหรับ 3–4 สาย แต่ละสายวางกึ่งกลางพื้นที่ ไม่มีโลโก้และไม่มีกรอบครอบหัว/ข้อมูลรอบ/ทีมเข้ารอบ เหลือกรอบเฉพาะตาราง โดยไม่เปลี่ยนตรรกะคู่แข่งขัน
- คืนระบบรายการที่กำลังดำเนินการแข่งขันแบบเลื่อนเดือนบนหน้า Index มีลูกศรซ้าย–ขวา รองรับการปัดมือถือ และทำงานร่วมกับตัวกรองค้นหา
- หน้า index ใช้น้ำหนักตัวอักษร navbar ให้ตรงกับหน้าอื่น
- การแก้ชื่อทีมทำและบันทึกได้ตรงในหน้าอีเว้นท์ ไม่ต้องเปิดหน้าแก้ไขชื่อทีมแยก
- ซ่อนตัวเลือกระบบที่ไม่ใช่ Swiss จาก admin และตรวจซ้ำฝั่งเซิร์ฟเวอร์

## ตรวจสอบก่อนนำขึ้นใช้งาน

1. ตั้ง `YAGAMI_SUPERADMIN_PASSWORD` ในระบบ production หากต้องการเปลี่ยนจากค่าเริ่มต้น
2. สำรองฐานข้อมูลก่อนอัปเดต
3. เปิดแอปหนึ่งครั้งเพื่อให้ระบบสร้าง/ซ่อมบัญชีเจ้าของระบบ
4. ทดสอบด้วย admin ว่าเห็นเฉพาะ Swiss และด้วย superadmin ว่าเห็นทุกระบบ
5. ทดสอบหมวด 5 โดยเปิดหน้าไว้ แล้วบันทึกผลเพลย์ออฟจากอีกหน้าหนึ่ง สถานะควรเปลี่ยนภายในประมาณ 3 วินาที
# Security hardening (2026-07-22)

- Removed predictable `SECRET_KEY` and all source-code default account creation.
- Protected owner password is no longer reset on every application restart.
- Added mandatory rotation checks for formerly exposed default credentials.
- Disabled debug mode by default and made the runtime port configurable.
- Enabled global CSRF protection for forms and same-origin fetch requests.
- Changed event deletion from destructive GET to CSRF-protected POST.
- Added cross-owner write protection for Event, Tournament and Playoff routes.
- Added Playoff/Round/Slot relationship validation against ID manipulation.
- Added login throttling and generic invalid-credential responses.
- Restricted CORS/Socket.IO origins and added browser security headers.
- Added secure cookie settings and a 16 MiB request/upload limit.
- Limited user administration to superadmin.
- Added `.env.example` and `SECURITY.md` deployment instructions.
