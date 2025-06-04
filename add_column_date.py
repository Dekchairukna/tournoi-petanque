import sqlite3

db_path = "your_database.db"  # แก้ชื่อไฟล์ให้ตรงกับของคุณ เช่น "app.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    cursor.execute("ALTER TABLE events ADD COLUMN date DATE;")
    print("✅ Added column 'date' to events table.")
except sqlite3.OperationalError as e:
    print("⚠️ Error:", e)

conn.commit()
conn.close()
