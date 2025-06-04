from models import db
from sqlalchemy import text

with db.engine.connect() as conn:
    conn.execute(text("ALTER TABLE matches ADD COLUMN is_manual BOOLEAN DEFAULT 0"))
    conn.commit()