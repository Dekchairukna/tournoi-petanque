#!/bin/zsh
# สร้าง Python environment สำหรับโปรเจกต์ (รันครั้งเดียว หรือรันใหม่เมื่อ venv เสีย)
# ใช้ .venv.nosync เพื่อไม่ให้ iCloud ย้ายไฟล์ขึ้นคลาวด์ แล้วทำลิงก์ .venv ให้ VS Code หาเจอ
cd "${0:A:h}" || exit 1
PY=/Library/Frameworks/Python.framework/Versions/3.12/bin/python3
[ -x "$PY" ] || PY=$(command -v python3.12 || command -v python3)
echo "ใช้ Python: $PY ($($PY --version))"
rm -rf .venv .venv.nosync venv
"$PY" -m venv .venv.nosync || exit 1
ln -s .venv.nosync .venv
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/pip install -r requirements.txt || exit 1
echo ""
echo "เสร็จแล้ว — เปิด VS Code แล้วกด F5 (Run Petanque) หรือรัน ./run_local.command"
