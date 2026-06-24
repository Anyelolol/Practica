import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "database.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS Usuario (
            uid       INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre    TEXT NOT NULL,
            correo    TEXT NOT NULL UNIQUE,
            token     TEXT NOT NULL,
            last_init DATETIME
        );

        CREATE TABLE IF NOT EXISTS Robot (
            roid   INTEGER PRIMARY KEY,
            nombre TEXT,
            estado TEXT DEFAULT 'offline'
        );

        CREATE TABLE IF NOT EXISTS Encargado (
            eid        INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre     TEXT NOT NULL,
            token      TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS Conexion (
            cid      INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha    DATETIME DEFAULT CURRENT_TIMESTAMP,
            time_use REAL,
            time_con REAL,
            uid      INTEGER REFERENCES Usuario(uid),
            roid     INTEGER REFERENCES Robot(roid)
        );

        CREATE TABLE IF NOT EXISTS Registro (
            rid     INTEGER PRIMARY KEY AUTOINCREMENT,
            log_use TEXT,
            log_err TEXT,
            fecha   DATETIME DEFAULT CURRENT_TIMESTAMP,
            uid     INTEGER REFERENCES Usuario(uid)
        );

        CREATE TABLE IF NOT EXISTS Telemetria (
            tid        INTEGER PRIMARY KEY AUTOINCREMENT,
            video_ruta TEXT,
            audio_ruta TEXT,
            fecha      DATETIME DEFAULT CURRENT_TIMESTAMP,
            rid        INTEGER REFERENCES Registro(rid)
        );
    """)

    conn.commit()
    conn.close()
