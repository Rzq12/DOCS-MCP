import sqlite3
from .config import settings

def connection():
    db = sqlite3.connect(settings.codegraph_db)
    db.row_factory = sqlite3.Row
    db.executescript("CREATE TABLE IF NOT EXISTS nodes (id INTEGER PRIMARY KEY, kind TEXT, name TEXT, file_path TEXT, line_number INTEGER, UNIQUE(kind,name,file_path)); CREATE TABLE IF NOT EXISTS edges (source_id INTEGER, relation TEXT, target_id INTEGER, UNIQUE(source_id,relation,target_id));")
    return db

def node(db, kind, name, file_path="", line_number=None):
    db.execute("INSERT OR IGNORE INTO nodes(kind,name,file_path,line_number) VALUES(?,?,?,?)", (kind, name, file_path, line_number))
    return db.execute("SELECT id FROM nodes WHERE kind=? AND name=? AND file_path=?", (kind, name, file_path)).fetchone()[0]

def edge(db, source, relation, target):
    db.execute("INSERT OR IGNORE INTO edges(source_id,relation,target_id) VALUES(?,?,?)", (source, relation, target))