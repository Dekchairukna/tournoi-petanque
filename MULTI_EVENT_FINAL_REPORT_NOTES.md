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
