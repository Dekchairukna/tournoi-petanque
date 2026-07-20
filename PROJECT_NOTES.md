# Tournoi Petanque — Project Notes

รวมบันทึกการพัฒนาเดิมทั้งหมด 36 รายการ (ตัดไฟล์ซ้ำตามเนื้อหาแล้ว)

---

## BETA EVENT IMPORT EDIT NOTES

> ที่มาเดิม: `BETA_EVENT_IMPORT_EDIT_NOTES 2.md`

# BETA: Import หลายอีเว้นท์ + แก้ไขอีเว้นท์

## สิ่งที่เพิ่ม

1. ปุ่ม `โหลดเทมเพลต`
   - ดาวน์โหลดไฟล์ `event_import_template.xlsx`
   - ใช้เป็นตัวอย่างหัวตารางสำหรับสร้างหลายอีเว้นท์

2. ปุ่ม `Import หลายอีเว้นท์`
   - อัปโหลด Excel แล้วสร้างอีเว้นท์หลายรายการพร้อมทีม/นักกีฬา
   - แถวที่มี `event_key` เดียวกันจะถูกนับเป็นอีเว้นท์เดียว
   - แต่ละแถวใน event_key เดียวกันใช้ `team_name` เป็นทีม/นักกีฬาที่เข้าร่วม
   - ระบบข้ามชื่อทีมซ้ำภายในอีเว้นท์เดียวกัน

3. ปุ่ม `แก้ไข`
   - เพิ่มในหน้ารายการอีเว้นท์ทั้งรายการที่ยังไม่จบและจบแล้ว
   - แก้ชื่อรายการ จำนวนรอบ วันที่ สถานที่ ประเภท เพศ รุ่น และตั้งค่าสนามได้
   - เพิ่มโลโก้ใหม่ได้ โดยไม่ลบโลโก้เดิม

## คอลัมน์ Excel ที่รองรับ

- `event_key` รหัสอีเว้นท์ ใช้รวมหลายแถวให้เป็นรายการเดียว
- `event_name` ชื่อรายการ
- `rounds` จำนวนรอบ
- `date` วันที่ เช่น 2026-07-08 หรือ 08/07/2026
- `location` สถานที่
- `category` ประเภท เช่น เดี่ยว/คู่/ทีม/คู่ผสม
- `sex` เพศ เช่น ชาย/หญิง/ผสม
- `age_group` รุ่น
- `field_prefix` คำนำหน้าสนาม เช่น A
- `field_start` สนามเริ่ม
- `field_max` จำนวนสนาม
- `field_exclude` สนามที่เว้น เช่น 3,7,11
- `team_name` ชื่อทีม/ชื่อนักกีฬา

## หมายเหตุ

ไม่ได้แก้ระบบ live, คะแนน, ประกบคู่ หรือโครงสร้างฐานข้อมูลเดิม เพิ่มเฉพาะส่วนสร้างหลายอีเว้นท์และแก้ไขอีเว้นท์สำหรับเบต้า

---

## BETA MULTI DETAILED STANDING NEXT SYSTEM NOTES

> ที่มาเดิม: `BETA_MULTI_DETAILED_STANDING_NEXT_SYSTEM_NOTES.md`

# BETA_MULTI_DETAILED_STANDING_NEXT_SYSTEM_NOTES

ปรับตามคำขอรอบนี้:

1. หน้า `/multi-manage`
- เพิ่มตารางจัดการ Standing/ทีมเข้ารอบแบบแยกอีเว้นท์เป็นแถว ๆ
- แต่ละอีเว้นท์เลือกได้เองว่า:
  - อันดับดีสุดเข้ารอบอัตโนมัติกี่ทีม
  - อันดับถัดไปเอาไปจัดต่อกี่ทีม
  - ระบบจัดต่อเป็น Knockout / Double Knockout / Swiss ใหม่ / A/B Ladder / A/B คัดตัวแทน
  - วิธีวางคู่ ตามอันดับ / Bracket / สุ่ม
  - ชื่อรอบใหม่
  - จำนวนทีมกลุ่ม A สำหรับ A/B
  - จำนวนรอบ Swiss ใหม่
  - เติม BYE / เอาอันดับดีสุดลงแข่งด้วย / อนุญาตสร้างซ้ำ
- เพิ่มปุ่ม “สร้างระบบจัดต่อจาก Standing” เพื่อทำหลายอีเว้นท์พร้อมกัน แต่ค่าควบคุมแยกตามแถว
- ถ้าอีเว้นท์ยังล็อกผลไม่ครบ ระบบจะข้าม
- ถ้าอีเว้นท์มีเพลย์ออฟเดิมแล้ว ระบบจะข้าม เว้นแต่ติ๊กสร้างซ้ำได้

2. หน้า `/multi-score`
- เลือกรอบ/ครั้งแยกต่ออีเว้นท์ได้แล้ว
- เลือกอีเว้นท์มาคีย์แล้วกำหนด U12 ครั้งที่ 2, U14 ครั้งที่ 3 ได้ในหน้าเดียว
- ตารางแสดงคู่เรียงเป็นอีเว้นท์ต่ออีเว้นท์ และแสดงครั้งที่ของคู่ในแถว
- บันทึกคะแนนยังลง Match ระบบหลักเหมือนเดิม

3. ไฟล์หลักที่แก้
- `app.py`
- `templates/multi_event_manager.html`
- `templates/multi_score_center.html`

หมายเหตุ: ระบบ MANUAL ยังไม่รวมในปุ่มสร้างหลายอีเว้นท์ เพราะ manual ต้องจิ้มคู่ทีละรายการ ถ้าเลือกแบบหลายอีเว้นท์พร้อมกันจะควบคุมยากและเสี่ยงผิดหน้างาน

---

## BETA MULTI EVENT MANAGER NOTES

> ที่มาเดิม: `BETA_MULTI_EVENT_MANAGER_NOTES 2.md`

# BETA: Multi Event Manager

เพิ่มหน้าใหม่สำหรับบริหารจัดการหลายอีเว้นท์พร้อมกัน โดยไม่รื้อระบบเดิม

## หน้าใหม่
- `/multi-manage` — บริหารจัดการอีเว้นท์รวม
- `/multi-manage/print-pairings` — ปริ้นใบประกบคู่รวมตามอีเว้นท์ที่เลือก
- `/multi-manage/print-score-sheets` — ปริ้นสกอร์ชีทรวมตามอีเว้นท์ที่เลือก

## ฟังก์ชันหลัก
1. เลือกอีเว้นท์หลายรายการ
2. เลือกครั้ง/รอบ 1, 2, 3, 4
3. จับคู่รอบแรกให้หลายอีเว้นท์พร้อมกัน
   - อีเว้นท์ที่มีคู่รอบแรกแล้วจะถูกข้าม ไม่ลบทิ้ง
4. ระบุสนามให้คู่แข่งขันของครั้งที่เลือก
   - ใส่สนามเริ่ม
   - ใส่จำนวนสนาม
   - เว้นสนามบางหมายเลขได้ เช่น `3,7,11`
5. จับคู่รอบแรก + ใส่สนามในปุ่มเดียว
6. ปริ้นใบประกบคู่ทั้งหมดของอีเว้นท์ที่เลือก
7. ปริ้นสกอร์ชีททั้งหมดของอีเว้นท์ที่เลือก

## ไฟล์ที่เพิ่ม/แก้
- `app.py`
- `templates/base.html`
- `templates/index.html`
- `templates/multi_event_manager.html`
- `templates/multi_event_print_pairings.html`
- `templates/multi_event_print_score_sheets.html`

## หมายเหตุ
- หน้าใหม่ไม่แตะ logic หน้าคีย์คะแนนเดิม
- ไม่ลบคู่รอบแรกเดิม ถ้าอีเว้นท์เคยจับคู่แล้วจะข้าม
- การใส่สนามทำกับรอบที่เลือกเท่านั้น

---

## BETA MULTI EVENT MANAGER ROUND DELETE FIX NOTES

> ที่มาเดิม: `BETA_MULTI_EVENT_MANAGER_ROUND_DELETE_FIX_NOTES 2.md`

# BETA_MULTI_EVENT_MANAGER_ROUND_DELETE_FIX_NOTES

แก้หน้า `/multi-manage` ตามงานหน้างานจริง

## แก้ Internal Server Error
- ปรับ query รายการอีเว้นท์ให้ไม่ใช้ `nullslast()` ในหน้าบริหารรวม เพื่อลดปัญหาบน SQLite/Railway บางเวอร์ชัน
- ปรับการเรียงพิมพ์รวมให้เรียงด้วย Python แทน `field.asc().nullslast()`

## จัดการหลายอีเว้นท์แม้คนละรอบ
- ตารางอีเว้นท์ที่เลือกมีช่อง `จัดการรอบ` แยกต่ออีเว้นท์
- ใช้ได้กับปุ่ม:
  - จับคู่ตามรอบที่เลือก
  - ระบุสนามตามรอบที่เลือก
  - จับคู่ + ใส่สนาม
  - ปริ้นใบประกบคู่ทั้งหมด
  - ปริ้นสกอร์ชีททั้งหมด
- เหมาะกับกรณีบางอีเว้นท์อยู่ครั้งที่ 2 แต่บางอีเว้นท์อยู่ครั้งที่ 3

## ลบ/เลือกใหม่
- เพิ่มปุ่ม `ล้างเลขสนาม` ล้างเฉพาะสนาม ไม่ลบคู่ ไม่ลบคะแนน
- เพิ่มปุ่ม `ลบคู่รอบที่เลือก` สำหรับลบคู่ในรอบที่เลือกเพื่อจับใหม่
- ถ้ามีคู่ที่ล็อกผลแล้ว ระบบจะไม่ลบให้โดยอัตโนมัติ
- ถ้าจำเป็นต้องลบคู่ที่ล็อกผลแล้ว ต้องติ๊ก `อนุญาตให้ลบคู่ที่ล็อกผลแล้วด้วย`

## สนามและ BYE
- ยังคงจัดสนามรวมข้ามอีเว้นท์ สนามเดียวกันไม่ชนกัน
- คู่ BYE ไม่กินเลขสนาม และไม่ถูกนับเป็นยังไม่เลือกสนาม

---

## BETA MULTI EVENT SCORE CENTER NOTES

> ที่มาเดิม: `BETA_MULTI_EVENT_SCORE_CENTER_NOTES 2.md`

# BETA: Multi Event Score Center

เพิ่มหน้าใหม่สำหรับคนเดียวคีย์คะแนนหลายอีเว้นท์จากหน้าเดียว โดยไม่แก้ logic หน้าเดิม

## URL

- `/multi-score`

## สิ่งที่เพิ่ม

- เมนูบน Navbar: `คีย์หลายอีเว้นท์`
- ปุ่มในหน้ารายการอีเว้นท์: `คีย์หลายอีเว้นท์`
- เลือกอีเว้นท์ได้หลายรายการพร้อมกัน
- เลือกครั้ง/รอบได้ 1, 2, 3, 4
- แสดงชื่ออีเว้นท์ + เลขสนาม + ทีมซ้าย/ขวา + ช่องคะแนน รวมทุกอีเว้นท์ในหน้าเดียว
- กรองสถานะได้: ทั้งหมด / ยังไม่คีย์ / กรอกแล้ว / คู่เสมอ
- ค้นหาเลขสนามได้
- บันทึกคะแนนแบบทยอยได้ แถวที่ว่างจะถูกข้าม
- ปุ่ม `บันทึก + ล็อกคู่ที่กรอกแล้ว` สำหรับล็อกเฉพาะคู่ที่กรอกคะแนนครบ

## ความปลอดภัยกับระบบเดิม

- ไม่แก้หน้า `round_matches` เดิม
- ไม่แก้ระบบประกบคู่ Swiss เดิม
- ไม่แก้ระบบ live เดิม
- เมื่อบันทึกจากหน้านี้ จะ emit สัญญาณให้หน้าเดิมอัปเดตตาม

---

## BETA MULTI FIELD BYE NO COURT NOTES

> ที่มาเดิม: `BETA_MULTI_FIELD_BYE_NO_COURT_NOTES 2.md`

# Beta multi field BYE no court

ปรับหน้า `/multi-manage` สำหรับการจัดสนามหลายอีเว้นท์รวม

## สิ่งที่แก้
- คู่ที่เจอ BYE (`team2_id` ว่าง) จะไม่ถูกใส่เลขสนาม
- ถ้าคู่ BYE เคยมีเลขสนามจากเวอร์ชันก่อน หน้า assign fields จะล้างเลขสนามออกให้
- คู่ BYE จะไม่ถูกนับเป็น `ยังไม่เลือกสนาม`
- จำนวนสนามที่ใช้จริงจะนับเฉพาะคู่ที่มี 2 ทีมแข่งกันจริง
- ระบบยังคงกันสนามชนกันข้ามอีเว้นท์ และยังพยายามเลี่ยงทีมกลับไปเล่นสนามเดิมเหมือนเดิม

## ไฟล์ที่แก้
- app.py

---

## BETA MULTI FIELD GLOBAL FIX NOTES

> ที่มาเดิม: `BETA_MULTI_FIELD_GLOBAL_FIX_NOTES 2.md`

# BETA_MULTI_FIELD_GLOBAL_FIX_NOTES

## ปรับแก้
- แก้ระบบระบุสนามในหน้า `/multi-manage` ให้จัดสนามแบบรวมทุกอีเว้นท์ที่เลือก ไม่ใช่เริ่มสนาม 1 ใหม่ทุกอีเว้นท์
- สนาม 1 สนาม ใช้ได้แค่ 1 คู่ต่อครั้งที่เลือก เพื่อกันหลายอีเว้นท์ชนสนามกัน
- ถ้าจำนวนคู่มากกว่าจำนวนสนาม ระบบจะไม่วนสนามซ้ำ แต่ปล่อยคู่ที่เกินเป็น `ยังไม่เลือกสนาม`
- ยังคงพยายามเลี่ยงไม่ให้ทีมเดิมกลับไปเล่นสนามที่เคยเล่นในอีเว้นท์นั้น
- หน้า `/multi-manage` เพิ่มสรุปจำนวนสนามใช้ได้ และจำนวนคู่ที่ยังไม่เลือกสนาม
- แสดง badge `ยังไม่เลือก` รายอีเว้นท์ เพื่อให้รู้ว่ารายการไหนยังไม่มีสนาม

## หลักการใช้งาน
ถ้าเลือกหลายอีเว้นท์พร้อมกันและมีสนาม 1-27 ระบบจะจัดได้สูงสุด 27 คู่พร้อมกันเท่านั้น
คู่ที่เกินต้องรอรอบสนามว่าง หรือแยกเลือกอีเว้นท์ชุดถัดไปแล้วกดระบุสนามอีกครั้ง

---

## BETA MULTI FIELD STANDINGS SUPERADMIN FIX NOTES

> ที่มาเดิม: `BETA_MULTI_FIELD_STANDINGS_SUPERADMIN_FIX_NOTES 2.md`

# BETA_MULTI_FIELD_STANDINGS_SUPERADMIN_FIX_NOTES

ปรับตามคำขอรอบนี้

## 1) จัดสนามหลายอีเว้นท์แบบเลขเรียงต่อกัน
- หน้า `/multi-manage` เพิ่มช่อง `เริ่มสนาม` รายอีเว้นท์
- ถ้าไม่กรอก ระบบจะจัดเลขสนามต่อกันอัตโนมัติเป็นบล็อกอีเว้นท์ต่ออีเว้นท์
- คู่ BYE ไม่กินเลขสนาม
- ถ้ากรอกเริ่มสนามเอง เช่น อีเว้นท์ A เริ่ม 1, อีเว้นท์ B เริ่ม 12 ระบบจะใช้ตามนั้น และกันเลขที่ถูกใช้ไปแล้วไม่ให้ชนกัน

## 2) หน้า `/multi-score` เรียงอีเว้นท์ก่อนสนาม
- ลดอาการเลขสนามกระโดดไปมาระหว่างอีเว้นท์
- แสดงเป็นอีเว้นท์ต่ออีเว้นท์ แล้วค่อยเรียงสนาม/คู่ในอีเว้นท์นั้น

## 3) แก้สกอร์ชีทรวมมีหน้าขาว
- ปรับ `multi_event_print_score_sheets.html`
- ตัด page-break ภายในที่ทำให้ขึ้นหน้าว่างเมื่อจบอีเว้นท์หนึ่งแล้วต่ออีเว้นท์ใหม่

## 4) จัดการสแตนดิ้งหลายอีเว้นท์
- เพิ่มปุ่ม `ปริ้นสแตนดิ้งที่เลือก` ใน `/multi-manage`
- ตั้งจำนวนอันดับดีสุด/อันดับถัดไป/กลุ่ม A ได้
- ใช้ `calculate_standings()` เดิมของระบบ ไม่แยกคำนวณใหม่
- เพิ่มหน้า `/multi-manage/print-standings`

## 5) จำกัดสิทธิ์เฉพาะ superadmin
จำกัดเฉพาะ superadmin สำหรับ:
- Import หลายอีเว้นท์
- โหลดเทมเพลต import หลายอีเว้นท์
- คีย์หลายอีเว้นท์ `/multi-score`
- จัดการอีเว้นท์รวม `/multi-manage`
- พิมพ์รวมจากหน้า multi

## 6) เพิ่มทีมทีหลังแล้วมีทีมเดียว
- ถ้ามีการจับคู่แล้ว เพิ่มทีมมาแค่ทีมเดียว และคู่เดิมของรอบนั้นลงผล/ล็อกครบแล้ว ระบบจะให้ BYE อัตโนมัติ
- BYE ไม่กินเลขสนาม
- ไม่กระทบคู่เดิม

---

## BETA MULTI NEXT ROUND NOTES

> ที่มาเดิม: `BETA_MULTI_NEXT_ROUND_NOTES 2.md`

# Beta: Multi Event Manager - Pair Selected Round

เพิ่มความสามารถในหน้า `/multi-manage`

## ที่เพิ่ม
- ปุ่ม `จับคู่ครั้งที่เลือก`
- ปุ่ม `จับคู่ครั้งที่เลือก + ใส่สนาม`
- ใช้ dropdown ครั้ง/รอบ 1, 2, 3, 4 ได้
- ครั้งที่ 1 ใช้ logic จับรอบแรกเดิมของหน้า beta
- ครั้งที่ 2 ขึ้นไปใช้ logic `swiss_pairing` เดิมของระบบ

## กันพัง
- ถ้าอีเว้นท์มีคู่ในครั้งที่เลือกอยู่แล้ว ระบบจะข้าม ไม่ลบคู่เดิม
- ถ้ารอบก่อนหน้ายังไม่มีคู่ ระบบจะข้าม
- ถ้ารอบก่อนหน้าลงคะแนน/ล็อกผลไม่ครบ ระบบจะข้ามพร้อมแจ้งจำนวนคู่ที่เหลือ
- ถ้าเกินจำนวนรอบที่ตั้งไว้ในอีเว้นท์ ระบบจะข้าม

## การใส่สนาม
ปุ่ม `จับคู่ครั้งที่เลือก + ใส่สนาม` จะจับคู่ก่อน แล้วนำคู่จากทุกอีเว้นท์ที่เลือกมาเรียงใส่สนามต่อกันตามสนามเริ่ม/จำนวนสนาม/สนามที่เว้น

---

## BETA MULTI PRINT REUSE NOTES

> ที่มาเดิม: `BETA_MULTI_PRINT_REUSE_NOTES 2.md`

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

---

## BETA MULTI STANDING PLAYOFF ROUNDROBIN FINAL NOTES

> ที่มาเดิม: `BETA_MULTI_STANDING_PLAYOFF_ROUNDROBIN_FINAL_NOTES 2.md`

# BETA_MULTI_STANDING_PLAYOFF_ROUNDROBIN_FINAL_NOTES

ปรับบนระบบ tournoi-petanque เท่านั้น

## เพิ่ม/แก้

1. หน้า `/multi-manage`
   - เพิ่มกล่อง "ตั้งค่าทั้งหมด" สำหรับกรอกครั้งเดียวแล้วใช้กับทุกอีเว้นท์
   - ค่า bulk: อันดับดีสุด, อันดับถัดไป, ระบบจัดต่อ, วิธีวางคู่, ชื่อรอบใหม่, จำนวน A/B, Swiss รอบ
   - เพิ่มตัวเลือก Round Robin ในระบบจัดต่อ
   - เพิ่มปุ่ม "คีย์เพลย์ออฟรวม"

2. หน้าสแตนดิ้งรวม `/multi-manage/print-standings`
   - รองรับค่ารายอีเว้นท์จากตาราง ไม่บังคับใช้ค่าแรกอย่างเดียว
   - เพิ่มปุ่มบันทึกภาพสแตนดิ้งรวมเป็น PNG

3. หน้าใหม่ `/multi-playoff-score`
   - เลือกหลายอีเว้นท์
   - ดึง playoff ล่าสุดของแต่ละอีเว้นท์
   - แสดงคู่ที่ต้องคีย์รวมหน้าเดียว
   - บันทึกคะแนนกลับตาราง playoff_scores ของระบบหลัก

4. Round Robin
   - เปิดตัวเลือก Round Robin จากหน้า Standing และหน้า multi-manage
   - สร้างพบกันหมดแบบเป็นรอบจริงด้วย circle method
   - ทีมคี่พัก BYE แต่ไม่สร้างคู่ BYE เป็นแมตช์จริง
   - ใช้ playoff tables เดิมเพื่อให้ใช้หน้ารายงาน/คีย์รวมร่วมกับระบบเดิม

## หมายเหตุ
- จำกัดสิทธิ์หน้า multi สำคัญด้วย superadmin ตามเดิม
- ไม่แตะ logic คีย์คะแนน Swiss หลัก
- ไม่แก้โครงสร้างฐานข้อมูลถาวร เพิ่มเฉพาะ route/template/function

---

## BETA MULTI SYNC FIELD AVOID NOTES

> ที่มาเดิม: `BETA_MULTI_SYNC_FIELD_AVOID_NOTES 2.md`

# BETA_MULTI_SYNC_FIELD_AVOID_NOTES

ปรับเพิ่มตามคำขอสำหรับหน้าใช้งานหลายอีเว้นท์

## 1) คีย์คะแนนหน้ารวมแล้วขึ้นระบบหลักทันที
- หน้า `/multi-score` บันทึกลงตาราง `matches` เดียวกับระบบหลัก (`team1_score`, `team2_score`)
- หลังบันทึกจะส่งสัญญาณ realtime เหมือนระบบหลัก เพื่อให้หน้าประกบคู่/หน้าคะแนนที่เปิดอยู่เห็นคะแนนใหม่
- เพิ่มการกันคะแนนทับกัน: ถ้าเปิดหน้ารวมไว้ แล้วมีอีกเครื่อง/อีกแท็บคีย์คะแนนคู่เดียวกันไปก่อน ระบบจะไม่บันทึกทับ แต่แจ้งให้รีเฟรชตรวจคะแนนก่อน

## 2) ลดปัญหาทีมได้เล่นสนามเดิมซ้ำ
- ตอนกด “ระบุสนามให้ครั้งที่เลือก” หรือ “จับคู่ครั้งที่เลือก + ใส่สนาม” ระบบจะดูประวัติสนามของทีมในอีเว้นท์นั้น
- ถ้าเลือกได้ จะไม่ให้ทีมกลับไปเล่นสนามที่เคยเล่นแล้ว
- ถ้าสนามไม่พอจริง ๆ ระบบจะยอมซ้ำเฉพาะเท่าที่จำเป็น เพื่อไม่ให้คู่ตกหล่น

## 3) ช่องสถานะสนามในหน้าบริหารรวม
- หน้า `/multi-manage` เพิ่มคอลัมน์ “สนามครั้งนี้” แสดงว่าอีเว้นท์นั้นใช้สนามไหนในครั้งที่เลือก
- เพิ่มคอลัมน์ “เตือนสนามซ้ำ” ถ้าพบทีมที่ได้สนามซ้ำกับสนามที่เคยเล่น จะขึ้นจำนวนคู่ที่ซ้ำ

## ไฟล์ที่แก้
- `app.py`
- `templates/multi_score_center.html`
- `templates/multi_event_manager.html`

---

## BETA ROUND ROBIN EXCEL STYLE NOTES

> ที่มาเดิม: `BETA_ROUND_ROBIN_EXCEL_STYLE_NOTES 2.md`

# BETA Round Robin Excel Style

เพิ่มระบบ Round Robin แบบตาราง Excel ในระบบ tournoi-petanque

## สิ่งที่เพิ่ม

- หน้าใหม่ `/event/<event_id>/round-robin`
- ปุ่ม “จัด Round Robin” ในหน้าอีเว้นท์
- ตั้งค่าแบบกลุ่มเดียว หรือแบ่งกลุ่ม A/B/...
- กำหนดจำนวนทีมต่อกลุ่ม สนามเริ่ม จำนวนสนาม prefix และสนามที่ต้องเว้น
- จัดกลุ่มทีมเป็นแถว ๆ แก้กลุ่ม/ลำดับเองได้
- สร้างตารางพบกันหมดแบบ circle method
- ทีมคี่มี BYE/พัก แต่ไม่สร้างแมตช์ BYE และไม่กินเลขสนาม
- คีย์คะแนน Round Robin จากหน้าเดียว
- Matrix แบบ Excel แสดงผลเจอกันทั้งหมดในกลุ่ม
- Standing ในแต่ละกลุ่ม พร้อมคำนวณชนะ/แพ้/คู่กรณี/สุทธิคู่กรณี/ได้เสีย/คะแนนได้
- พิมพ์รายงาน และบันทึกภาพสแตนดิ้งรวมเป็น PNG

## หมายเหตุ

- ระบบใช้ตาราง `matches` เดิมสำหรับคะแนน เพื่อให้ไม่แยกฐานข้อมูล
- ตาราง helper ที่เพิ่มเองอัตโนมัติคือ `round_robin_settings` และ `round_robin_groups`
- ถ้าสร้างตารางใหม่และมีผลล็อกอยู่ ต้องติ๊ก “ยืนยันล้างผลที่ล็อกแล้ว”
- สนามในแต่ละครั้งจะเรียงรวมทุกกลุ่ม ไม่ให้กลุ่ม A/B ชนสนามกันในครั้งเดียวกัน

---

## BETA ROUND ROBIN MULTI GROUP MATRIX FIX NOTES

> ที่มาเดิม: `BETA_ROUND_ROBIN_MULTI_GROUP_MATRIX_FIX_NOTES 2.md`

# BETA_ROUND_ROBIN_MULTI_GROUP_MATRIX_FIX

ปรับระบบ Round Robin ใน tournoi-petanque

- เปลี่ยนตัวเลือกจาก “แบ่งกลุ่ม A/B” เป็น “แบ่งหลายกลุ่มอัตโนมัติ”
- ตั้งจำนวนทีมต่อกลุ่มได้ เช่น 4 ทีม/กลุ่ม แล้วระบบเติม A, B, C, D... อัตโนมัติ
- เพิ่มปุ่ม “เติมกลุ่มตามจำนวนทีม/กลุ่ม” ในตารางทีม
- เพิ่มปุ่มลัด “ดู Matrix แบบ Excel” ด้านบนหน้า Round Robin
- ทำให้ส่วน Matrix / Standing แบบ Excel แสดงชัดขึ้นเป็น section ของตัวเอง
- Matrix แสดงช่องว่างเป็น — เพื่อให้ไม่ดูเหมือนหาย
- ยังใช้ Match/Standing เดิมของระบบ ไม่กระทบ Swiss เดิม

---

## CLEANUP MANIFEST

> ที่มาเดิม: `CLEANUP_MANIFEST 2.md`

# Cleanup manifest

Removed obvious unused duplicate/backup files and macOS metadata.

- Removed `__MACOSX` and `.DS_Store` artifacts.
- Removed root duplicate files ending with ` 2`.
- Removed old patch/change-note markdown files.
- Removed template backup files `*.bak*`.
- Kept all primary source files, templates, static assets, and data spreadsheets.

Functional changes:

- Swiss voice announcement now says `ประกาศผลการประกบคู่ / การแข่งขันครั้งที่ X`.
- Playoff next-round dropdown always shows A/B, Double knockout, Knockout, Swiss, and disabled Round Robin.

Additional cleanup:

- Removed root Thai/manual `.txt` note dumps that are not imported by Flask. Kept `requirements.txt`.
- Removed temporary snippet file `1.py` and empty file `main`.

---

## DOUBLE KNOCKOUT GROUP COUNT NATIVE ROUTE FIX

> ที่มาเดิม: `DOUBLE_KNOCKOUT_GROUP_COUNT_NATIVE_ROUTE_FIX.md`

# Double Knockout group-count and native route fix

- Added required number-of-groups input for initial Double Knockout setup.
- Validates that every group contains 3–4 real teams.
- Random, seed, and manual setup respect the selected group count.
- After creation, redirects to the event-native Double Knockout/Knockout route instead of `/playoff/<id>`.
- Initial round name remains `รอบแรก`.

---

## DOUBLE KNOCKOUT PLAYOFF ENTRY NOTES

> ที่มาเดิม: `DOUBLE_KNOCKOUT_PLAYOFF_ENTRY_NOTES 2.md`

# Double Knockout / Knockout entry flow

- Uses Event team management.
- Random, Seed, or Manual setup on the Event page.
- Manual uses the original Playoff manual pairing page.
- Existing Playoff engine remains responsible for realtime scores, score sheets, QR, reports, printing, and next rounds.
- Supports optional X/BYE and best-effort same-base-name separation.
- Previous Playoff records remain available for reports.

---

## EVENT CREATE FORMAT SELECTION NOTES

> ที่มาเดิม: `EVENT_CREATE_FORMAT_SELECTION_NOTES 2.md`

# Event create format selection

ปรับหน้าสร้างอีเวนต์:
- ตัดช่องจำนวนรอบออกจาก Modal
- เพิ่มรูปแบบการแข่งขัน: Swiss, Round Robin, Double Knockout, Knockout
- จำนวนรอบ/จำนวนกลุ่ม/ทีมผ่านเข้ารอบ ตั้งในหน้าอีเวนต์ภายหลัง
- เพิ่มคอลัมน์ events.competition_format พร้อม runtime migration สำหรับ SQLite/PostgreSQL
- หลังสร้างสำเร็จพาเข้าอีเวนต์ทันที
- ค่าเริ่มต้นจำนวนรอบ: Swiss=3, รูปแบบอื่น=1 เพื่อรักษาความเข้ากันได้กับระบบเดิม

---

## EVENT FINISH STATUS NOTES

> ที่มาเดิม: `EVENT_FINISH_STATUS_NOTES 2.md`

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

---

## EVENT HOME ROW LAYOUT NOTES

> ที่มาเดิม: `EVENT_HOME_ROW_LAYOUT_NOTES 2.md`

# EVENT HOME ROW LAYOUT

- เปลี่ยนการแสดงรายการอีเวนต์จากการ์ดหลายคอลัมน์เป็นรายการแนวนอนแบบแถว
- คงระบบแยกปี เดือน สไลด์ ค้นหา ตัวกรอง และสถิติรายเดือนไว้เหมือนเดิม
- Desktop แสดงชื่อ ข้อมูล ป้ายสถานะ จำนวนทีม/แมตช์ และปุ่มในแถวเดียว
- Tablet จัดปุ่มด้านขวาและข้อมูลแบ่งสองบรรทัด
- Mobile เรียงข้อมูลลงแนวตั้งเพื่อให้อ่านง่าย
- แก้เฉพาะ templates/index.html และเพิ่มไฟล์บันทึกนี้

---

## EVENT HOME YEAR MONTH SLIDER NOTES

> ที่มาเดิม: `EVENT_HOME_YEAR_MONTH_SLIDER_NOTES 2.md`

# หน้าแรกแยกปี/เดือนแบบสไลด์

แก้เฉพาะ:
- app.py: route index() จัดกลุ่มอีเว้นท์ตามปีและเดือน พร้อมสถิติ
- templates/index.html: การ์ดอีเว้นท์, ค้นหา/กรอง, ปีแบบแท็บ, เดือนแบบสไลด์

ไม่ได้แก้ฐานข้อมูล ระบบคะแนน การจับคู่ Round Robin, Swiss, Playoff หรือ Multi Event

---

## EVENT LATEST MONTH SORT NOTES

> ที่มาเดิม: `EVENT_LATEST_MONTH_SORT_NOTES 2.md`

# Event latest/month sorting

- อีเว้นท์กำลังดำเนินการเรียงวันที่ล่าสุดขึ้นก่อน
- แยกอีเว้นท์กำลังดำเนินการเป็นรายเดือน
- เดือนล่าสุดเปิดก่อน และเลื่อนเดือนด้วยปุ่มซ้าย/ขวาหรือปัดบนมือถือ
- ภายในแต่ละเดือนเรียงวันที่ล่าสุดและ id ล่าสุดขึ้นก่อน
- ประวัติการแข่งขันยังแยกปี/เดือนและเรียงล่าสุดก่อนเหมือนเดิม
- ไม่แก้ฐานข้อมูล ระบบคะแนน การประกบคู่ หรือ Multi Event

---

## EVENT PAGE SWISS DETAILS RESTORED

> ที่มาเดิม: `EVENT_PAGE_SWISS_DETAILS_RESTORED 2.md`

# Event page Swiss details restored

- คืนรายละเอียดหน้า Event เดิมสำหรับ Swiss ครบ
- คืนตัวเลือกห้ามทีมชื่อฐานเดียวกันเจอกันทั้งรอบแรกและรอบถัดไป
- คืนการเพิ่มทีมภายหลัง, อัปโหลด Excel, แก้ชื่อ/ลบทีม, ตารางคะแนน BHN/fBHN และสถานะอีเวนต์
- Round Robin ยังใช้โมดูลใหม่ผ่าน route rr_event
- Double Knockout / Knockout ใช้เครื่องยนต์ Playoff เดิม

---

## LIVE REPORT API README

> ที่มาเดิม: `LIVE_REPORT_API_README 2.md`

# Live Report Board API ที่เพิ่มให้ Tournoi

เพิ่ม endpoint public สำหรับเว็บรายงานผล:

- `/api/public/events` รายการอีเวนต์
- `/api/public/event/<event_id>/live` คะแนนสด/ผลล่าสุด แยกตามรอบได้ด้วย `?round=1`
- `/api/public/event/<event_id>/standings` ตารางคะแนน Swiss
- `/api/public/event/<event_id>/playoffs` playoff/bracket
- `/api/public/event/<event_id>/report` รวมข้อมูลสำหรับ Report Board

เพิ่ม CORS และอนุญาต iframe แล้วใน `after_request`

---

## LIVE VERSION REMOVED NOTES

> ที่มาเดิม: `LIVE_VERSION_REMOVED_NOTES 2.md`

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

---

## MATRIX WORDING AND TIEBREAK FIX

> ที่มาเดิม: `MATRIX_WORDING_AND_TIEBREAK_FIX 2.md`

# Matrix wording and tie-break fix

แก้หัวตาราง Matrix ให้ตรงตามแบบ Excel:
- คะแนนรวม
- คะแนนคู่กรณี
- คะแนนสุทธิคู่กรณี
- อันดับที่

แก้การคำนวณ:
1. คะแนนรวม = จำนวนชนะทั้งหมด
2. เสมอ 2 ทีม ใช้ผลพบกันโดยตรง
3. เสมอ 3 ทีมขึ้นไป ใช้จำนวนชนะเฉพาะคู่กรณี
4. ถ้ายังเท่ากัน ใช้ผลต่างแต้มเฉพาะคู่กรณี
5. ถ้ายังเท่ากัน ใช้ผลต่างคะแนนรวม

เพิ่มสรุปการแพ้ชนะของทีมคู่กรณีใต้ Matrix และรักษาโครงสร้าง stats ให้มีครบแม้ยังไม่มีคะแนน

---

## MULTI EVENT FINAL REPORT NOTES

> ที่มาเดิม: `MULTI_EVENT_FINAL_REPORT_NOTES 2.md`

# Multi Event Final Report

เพิ่มฟังก์ชันรายงานผลรวมหลายอีเว้นท์ โดยใช้ข้อมูลและรูปแบบเดียวกับหน้า Print Report เดิม

## สิ่งที่เพิ่ม
- Route: `/multi-manage/print-final-reports`
- ปุ่ม `รายงานผลรวมทุกอีเว้นท์` ในหน้า Multi Event Manager
- รวมรายงานล่าสุดของทุกอีเว้นท์ที่เลือกเป็นหน้าเดียว เพื่อพิมพ์หรือบันทึก PDF ครั้งเดียว
- เลือกส่วนรายงานได้: ทั้งหมด, รายชื่อ, Standing, Swiss, Playoff, Final
- หน้าปกและสารบัญรายชื่ออีเว้นท์
- แจ้งอีเว้นท์ที่ยังไม่มีระบบจัดต่อ/Print Report และไม่นำมารวม

## หลักการแก้ไข
- แยกการเตรียมข้อมูล Print Report เป็น helper กลาง `_playoff_print_report_context`
- หน้า Print Report เดิมและหน้ารายงานรวมใช้ partial เดียวกัน `_playoff_report_sections.html`
- ไม่แก้ logic การคำนวณผล, Standing, Swiss, Playoff หรือ Final

---

## NATIVE DOUBLE KNOCKOUT AND PAIRING PRINT NOTES

> ที่มาเดิม: `NATIVE_DOUBLE_KNOCKOUT_AND_PAIRING_PRINT_NOTES.md`

- Initial Double Knockout/Knockout round title defaults to "รอบแรก".
- Initial Double Knockout and Knockout now open dedicated event URLs instead of /playoff/<id>.
- Dedicated pages reuse the complete existing Playoff engine and template features.
- Playoff remains available for post-first-stage competitions from Swiss/Round Robin/etc.
- Round Robin pairing print no longer forces one round per sheet.
- Each round displays its calculated start time from first_time + match/break duration.

---

## NATIVE DOUBLE KNOCKOUT LABEL FIX

> ที่มาเดิม: `NATIVE_DOUBLE_KNOCKOUT_LABEL_FIX.md`

# Native Double Knockout / Knockout labels

- Event page no longer calls native Double Knockout or Knockout rounds “Playoff”.
- Native event cards now show “รอบ Double Knockout ที่สร้างไว้” or “รอบ Knockout ที่สร้างไว้”.
- Native buttons now show “ไปหน้ารอบที่ 1” (or the latest round number).
- Swiss/Round Robin generated post-stage Playoff links retain the existing Playoff wording.

---

## NATIVE EVENT FORMATS COMPLETE NOTES

> ที่มาเดิม: `NATIVE_EVENT_FORMATS_COMPLETE_NOTES 2.md`

# Native Event Formats Complete

ปรับตามข้อสรุปล่าสุด:

- ทุกอีเวนต์ใช้ระบบ Team เดิมของ Event
- Round Robin มีเพิ่มทีม, Excel, แก้ชื่อ, ลบรายทีม, ลบทั้งหมดในหน้าเดียว
- หากแก้ทีมหลังสร้าง Round Robin ระบบเตือนและต้องยืนยันล้างกลุ่ม ตาราง และคะแนนเดิม
- Round Robin ใช้สกอร์ชีตออนไลน์/QR ของ Match เดิมทุกคู่
- คะแนน Round Robin ยังคง Realtime ผ่าน Socket.IO
- Double Knockout / Knockout เลือก Random / Seed / Manual
- ปุ่มใช้ข้อความ “จับสลากและสร้างสายการแข่งขัน”
- Manual ใช้หน้าจัดสายเดิมของ Playoff
- เมื่อสร้างสายแล้ว ใช้ระบบคะแนน Realtime, สกอร์ชีตออนไลน์, QR และรายงาน/พิมพ์ Playoff เดิม
- Swiss เดิมและตัวเลือกแยกทีมชื่อฐานเดียวกันไม่ถูกตัดออก

---

## NATIVE EVENT FORMAT INTEGRATION NOTES

> ที่มาเดิม: `NATIVE_EVENT_FORMAT_INTEGRATION_NOTES 2.md`

# Native Event Format Integration

- Removed Tournament Center registration and menu.
- Event creation stores only name/details + competition format; rounds placeholder is always 1.
- Swiss settings now live on Event page.
- New Round Robin is attached directly to Event using native event_rr tables.
- Double Knockout and Knockout start from Event page and use the existing Playoff engine.
- Legacy Tournament Center database tables are left untouched for database compatibility, but no route/menu/template uses them.

---

## PERFORMANCE FIX V2 NOTES

> ที่มาเดิม: `PERFORMANCE_FIX_V2_NOTES 2.md`

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

---

## REALTIME LIVE REMOVED CLEAN FIX

> ที่มาเดิม: `REALTIME_LIVE_REMOVED_CLEAN_FIX 2.md`

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

---

## SPEED CLICK REALTIME FIX

> ที่มาเดิม: `SPEED_CLICK_REALTIME_FIX 2.md`

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

---

## TOURNAMENT CENTER V1 1 MATRIX RESTORED

> ที่มาเดิม: `TOURNAMENT_CENTER_V1_1_MATRIX_RESTORED 2.md`

# Tournament Center V1.1 — Matrix Restored

- คืนตาราง Matrix แบบ Excel ของ Round Robin ใหม่
- แยกแท็บสาย A/B/C/...
- แสดงผลพบกัน, คะแนนรวม, คู่กรณี, ผลต่างคู่กรณี และอันดับ
- ขีดกรอบสีแดงเฉพาะช่องผลพบกันของทีมที่ชนะเท่ากัน
- แสดงสรุปการแพ้ชนะของคู่กรณีใต้ตาราง
- บันทึกภาพและพิมพ์เฉพาะสายที่กำลังเปิด
- ใช้คะแนนและกติกาจัดอันดับจาก Round Robin ใหม่ใน Tournament Center

---

## TOURNAMENT CENTER V1 NOTES

> ที่มาเดิม: `TOURNAMENT_CENTER_V1_NOTES 2.md`

# Tournament Center V1

## โครงสร้างใหม่

- Tournament = งานแข่งขันใหญ่
- Tournament Event = อีเวนต์ภายในงาน
- Competition Stage = รอบ/Playoff ของอีเวนต์
- แต่ละ Stage เลือกรูปแบบได้อิสระ:
  - Round Robin ใหม่
  - Swiss เดิม
  - Double Elimination เดิม
  - Knockout เดิม

## ฟังก์ชันที่ทำแล้ว

1. สร้าง Tournament พร้อมสถานที่ วันที่ และการตั้งค่าสนาม
2. อัปโหลด/วางรายชื่อทีมกลางครั้งเดียว
3. เพิ่มและลบอีเวนต์ ตั้งชื่อได้อิสระ
4. ทุกทีมถูกเลือกเข้าแต่ละอีเวนต์ไว้ก่อน แล้วเอาทีมที่ไม่ส่งออก
5. เลือกรูปแบบรอบแรกแยกอีเวนต์ได้
6. Random รายการที่พร้อมทั้งหมด โดยใช้เครื่องยนต์ของแต่ละรูปแบบ
7. Round Robin ใหม่:
   - หลายกลุ่ม A/B/C
   - Random / Seed / Snake / Manual
   - ตาราง 5 ทีมตามลำดับที่กำหนดไว้
   - BYE อยู่แถวล่าง ไม่มีสนาม
   - จัดสนามและเวลาอัตโนมัติ
   - คะแนน Realtime ผ่าน Socket.IO เดิมของ Tournoi
   - ตารางคะแนนตามกติกาคู่กรณี
   - Matrix
   - ตัวจับเวลาและเสียงนาฬิกาปลุก
   - เลือกทีมเข้ารอบ
8. ดึงทีมจาก Stage ใดก็ได้ไปสร้าง Stage/Playoff รูปแบบใหม่
9. Swiss ใช้เครื่องยนต์ Swiss เดิม
10. Double Elimination และ Knockout ใช้เครื่องยนต์ Playoff เดิม
11. Round Robin เดิมปิดการสร้างใหม่ และนำผู้ใช้ไป Round Robin Center ใหม่
12. ข้อมูล Round Robin เก่ายังเปิดอ่านได้ เพื่อไม่ลบประวัติ

## การอัปเกรดฐานข้อมูล

ใช้โมเดล SQLAlchemy ใหม่และ `db.create_all()` เดิมของระบบ จึงสร้างตารางต่อไปนี้อัตโนมัติเมื่อเปิดระบบครั้งแรก:

- tournaments
- tournament_events
- tournament_master_teams
- tournament_event_entries
- competition_stages
- round_robin_groups
- round_robin_group_members

ไม่มีการลบหรือแก้ข้อมูล Event/Team/Match/Playoff เดิม

## การทดสอบที่ผ่าน

- Import แอปและสร้างตารางใหม่
- สร้าง Tournament
- เพิ่มทีมกลาง
- สร้าง 4 อีเวนต์: Round Robin / Swiss / Double / Knockout
- Random พร้อมกันครบ 4 รูปแบบ
- Round Robin 2 กลุ่ม กลุ่มละ 4 ทีม สร้าง 12 คู่ครบ
- บันทึกคะแนนผ่าน API Realtime
- เปิดตารางคะแนนและ Matrix
- ดึงทีมจาก Round Robin ไปสร้าง Swiss Stage ถัดไป
- สร้าง Knockout/Double ผ่าน Playoff เดิม

## หมายเหตุ

- ไฟล์ `instance/tournoi.db` ในชุดส่งเป็นฐานข้อมูลเดิม ไม่มีข้อมูลทดสอบที่สร้างระหว่างพัฒนา
- ควรสำรองฐานข้อมูลจริงก่อน Deploy ทุกครั้ง
