#!/bin/zsh
cd "${0:A:h}" || exit 1
if /usr/bin/curl --max-time 2 --silent --fail --output /dev/null http://127.0.0.1:5001/; then
  echo 'ระบบเปิดอยู่แล้ว: http://127.0.0.1:5001/kku2026'
  exit 0
fi
if [ ! -x .venv/bin/python ]; then
  echo 'ยังไม่มี .venv — กำลังติดตั้งครั้งแรก...'
  ./setup_mac.command || exit 1
fi
exec ./.venv/bin/python app.py
