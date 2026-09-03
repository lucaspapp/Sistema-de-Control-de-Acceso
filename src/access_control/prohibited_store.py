"""Almacenamiento local de perfiles restringidos y alertas de acceso."""

import sqlite3
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_DIR = PROJECT_ROOT / "runtime" / "access_control"
DATABASE = RUNTIME_DIR / "goldenjack.db"
FACES_DIR = RUNTIME_DIR / "restricted_faces"


def connection():
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    FACES_DIR.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    return db


def initialize() -> None:
    with connection() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                reset_token TEXT,
                reset_expires_at TEXT,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS people (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                reason TEXT,
                reported_by TEXT,
                effective_date TEXT,
                kind TEXT NOT NULL CHECK(kind IN ('prohibited', 'excluded')),
                image_path TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY,
                person_id INTEGER,
                person_name TEXT NOT NULL,
                camera TEXT,
                score REAL,
                image_path TEXT,
                detected_at TEXT NOT NULL,
                FOREIGN KEY(person_id) REFERENCES people(id)
            );
        """)
        columns = {row[1] for row in db.execute("PRAGMA table_info(people)")}
        if "reported_by" not in columns:
            db.execute("ALTER TABLE people ADD COLUMN reported_by TEXT")
        if "effective_date" not in columns:
            db.execute("ALTER TABLE people ADD COLUMN effective_date TEXT")


def prohibited_people():
    with connection() as db:
        return db.execute(
            "SELECT * FROM people WHERE kind = 'prohibited' AND active = 1 ORDER BY name COLLATE NOCASE"
        ).fetchall()


def people_by_kind(kind: str):
    with connection() as db:
        return db.execute(
            "SELECT * FROM people WHERE kind = ? AND active = 1 ORDER BY name COLLATE NOCASE", (kind,)
        ).fetchall()


def person_for_recognition():
    with connection() as db:
        return db.execute(
            "SELECT * FROM people WHERE kind IN ('prohibited', 'excluded') AND active = 1 ORDER BY name COLLATE NOCASE"
        ).fetchall()


def find_person_by_name(name: str):
    with connection() as db:
        return db.execute(
            "SELECT * FROM people WHERE name = ? AND kind IN ('prohibited', 'excluded') AND active = 1 LIMIT 1", (name,)
        ).fetchone()


def get_person(person_id: int):
    with connection() as db:
        return db.execute("SELECT * FROM people WHERE id = ?", (person_id,)).fetchone()


def delete_person(person_id: int):
    """Borra el perfil y sus alertas; retorna rutas para eliminar sus imágenes."""
    with connection() as db:
        person = db.execute("SELECT * FROM people WHERE id = ?", (person_id,)).fetchone()
        if person is None:
            return None, []
        alerts = db.execute("SELECT image_path FROM alerts WHERE person_id = ?", (person_id,)).fetchall()
        db.execute("DELETE FROM alerts WHERE person_id = ?", (person_id,))
        db.execute("DELETE FROM people WHERE id = ?", (person_id,))
        return person, [row["image_path"] for row in alerts if row["image_path"]]


def record_alert(name: str, camera: str, score: float, image_path: str | None) -> None:
    person = find_person_by_name(name)
    with connection() as db:
        db.execute(
            "INSERT INTO alerts(person_id, person_name, camera, score, image_path, detected_at) VALUES (?, ?, ?, ?, ?, ?)",
            (person["id"] if person else None, name, camera, score, image_path, datetime.now().isoformat()),
        )


def latest_alert():
    with connection() as db:
        return db.execute("""
            SELECT a.*, p.reason FROM alerts a
            LEFT JOIN people p ON p.id = a.person_id
            ORDER BY a.detected_at DESC LIMIT 1
        """).fetchone()


def alert_history(limit: int = 100):
    """Alertas recientes con su captura original y datos del perfil."""
    with connection() as db:
        return db.execute("""
            SELECT a.*, p.reason FROM alerts a
            LEFT JOIN people p ON p.id = a.person_id
            ORDER BY a.detected_at DESC LIMIT ?
        """, (limit,)).fetchall()
