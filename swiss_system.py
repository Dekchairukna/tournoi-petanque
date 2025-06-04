import sqlite3
from datetime import datetime
import random


DB_NAME = "swiss.db"
def init_db():
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            rounds INTEGER NOT NULL,
            location TEXT,
            category TEXT,
            age_group TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS players (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            FOREIGN KEY(event_id) REFERENCES events(id)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            round_number INTEGER NOT NULL,
            player1_id INTEGER,
            player2_id INTEGER,
            score1 INTEGER DEFAULT 0,
            score2 INTEGER DEFAULT 0,
            finished INTEGER DEFAULT 0,
            FOREIGN KEY(event_id) REFERENCES events(id),
            FOREIGN KEY(player1_id) REFERENCES players(id),
            FOREIGN KEY(player2_id) REFERENCES players(id)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS standings (
            event_id INTEGER,
            player_id INTEGER,
            points INTEGER DEFAULT 0,
            buchholz INTEGER DEFAULT 0,
            PRIMARY KEY(event_id, player_id),
            FOREIGN KEY(event_id) REFERENCES events(id),
            FOREIGN KEY(player_id) REFERENCES players(id)
        )
    """)
    conn.commit()
    conn.close()

def get_connection():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    conn.row_factory = sqlite3.Row  # ให้ผลลัพธ์เป็น dict-like
    return conn

def get_players(event_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM players WHERE event_id=?", (event_id,))
    players = c.fetchall()
    conn.close()
    return players

def get_teams(event_id):
    """
    ดึงรายชื่อทีม (players) ของ event_id
    คืนค่า list ของ dict เช่น [{'id': 1, 'name': 'ทีมA'}, ...]
    """
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT id, name FROM players WHERE event_id=?", (event_id,))
    rows = c.fetchall()
    conn.close()
    if rows:
        return [dict(row) for row in rows]
    else:
        return []

def generate_random_pairs(event_id, fields=None):
    """
    สุ่มจับคู่ทีมสำหรับ event_id
    fields: รายชื่อสนาม (list) เช่น ['สนาม1', 'สนาม2']
    คืนค่า list ของคู่ เช่น
    [
        {'team1': 'ทีมA', 'team2': 'ทีมB', 'field': 'สนาม1'},
        {'team1': 'ทีมC', 'team2': 'ทีมD', 'field': 'สนาม2'},
        ...
    ]
    """
    teams = get_teams(event_id)
    if not teams:
        return []  # ไม่มีทีมในรายการ

    team_names = [team['name'] for team in teams]

    random.shuffle(team_names)
    
    pairs = []
    for i in range(0, len(team_names) - 1, 2):
        field = None
        if fields:
            # หมุนเวียนสนาม ถ้า fields กำหนดมา
            field = fields[(i // 2) % len(fields)]
        pairs.append({
            'team1': team_names[i],
            'team2': team_names[i+1],
            'field': field
        })

    # ถ้าจำนวนทีมเป็นคี่ อาจมีทีมสุดท้ายไม่ได้คู่
    if len(team_names) % 2 == 1:
        pairs.append({
            'team1': team_names[-1],
            'team2': None,
            'field': None
        })
    return pairs

def save_match(event_id, round_number, team1_name, team2_name, score1, score2, field):
    conn = get_connection()
    c = conn.cursor()

    c.execute("SELECT id FROM players WHERE event_id=? AND name=?", (event_id, team1_name))
    player1 = c.fetchone()
    player1_id = player1['id'] if player1 else None

    if team2_name:
        c.execute("SELECT id FROM players WHERE event_id=? AND name=?", (event_id, team2_name))
        player2 = c.fetchone()
        player2_id = player2['id'] if player2 else None
    else:
        player2_id = None

    c.execute("""
        INSERT INTO matches (event_id, round_number, player1_id, player2_id, score1, score2, finished)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (event_id, round_number, player1_id, player2_id, score1 or 0, score2 or 0, 1))

    conn.commit()
    conn.close()


def get_connection():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    conn.row_factory = sqlite3.Row  # ให้ผลลัพธ์เป็น dict-like
    return conn

def get_teams(event_id):
    """
    ดึงรายชื่อทีม (players) ของ event_id
    คืนค่า list ของ dict เช่น [{'id': 1, 'name': 'ทีมA'}, ...]
    """
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT id, name FROM players WHERE event_id=?", (event_id,))
    rows = c.fetchall()
    conn.close()
    if rows:
        return [dict(row) for row in rows]
    else:
        return []

def generate_random_pairs(event_id, fields=None):
    """
    สุ่มจับคู่ทีมสำหรับ event_id
    fields: รายชื่อสนาม (list) เช่น ['สนาม1', 'สนาม2']
    คืนค่า list ของคู่ เช่น
    [
        {'team1': 'ทีมA', 'team2': 'ทีมB', 'field': 'สนาม1'},
        {'team1': 'ทีมC', 'team2': 'ทีมD', 'field': 'สนาม2'},
        ...
    ]
    """
    teams = get_teams(event_id)
    if not teams:
        return []  # ไม่มีทีมในรายการ

    team_names = [team['name'] for team in teams]

    random.shuffle(team_names)
    
    pairs = []
    for i in range(0, len(team_names) - 1, 2):
        field = None
        if fields:
            # หมุนเวียนสนาม ถ้า fields กำหนดมา
            field = fields[(i // 2) % len(fields)]
        pairs.append({
            'team1': team_names[i],
            'team2': team_names[i+1],
            'field': field
        })

    # ถ้าจำนวนทีมเป็นคี่ อาจมีทีมสุดท้ายไม่ได้คู่
    if len(team_names) % 2 == 1:
        pairs.append({
            'team1': team_names[-1],
            'team2': None,
            'field': None
        })
    return pairs



def add_event(name, rounds, location, category, age_group):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "INSERT INTO events (name, rounds, location, category, age_group) VALUES (?, ?, ?, ?, ?)",
        (name, rounds, location, category, age_group)
    )
    event_id = c.lastrowid
    conn.commit()
    conn.close()
    return event_id

def get_events():
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM events ORDER BY created_at DESC")
    events = c.fetchall()
    conn.close()
    return events

def add_player(event_id, player_name):
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT INTO players (event_id, name) VALUES (?, ?)", (event_id, player_name))
    conn.commit()
    player_id = c.lastrowid
    conn.close()
    return player_id

def get_players(event_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM players WHERE event_id=?", (event_id,))
    players = c.fetchall()
    conn.close()
    return players

def edit_player(player_id, event_id, new_name):
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE players SET name=? WHERE id=? AND event_id=?", (new_name, player_id, event_id))
    conn.commit()
    conn.close()

def delete_player(player_id, event_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM players WHERE id=? AND event_id=?", (player_id, event_id))
    conn.commit()
    conn.close()

def clear_players(event_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM players WHERE event_id=?", (event_id,))
    conn.commit()
    conn.close()
