"""SQLite 连接与建库。

数据不出墙：库文件默认在仓库 data/ 下，路径可用 STEWARD_DB 环境变量覆盖
（测试与多部署场景用）。
"""

import sqlite3
from pathlib import Path

SCHEMA_VERSION = 2

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_DB_PATH = _REPO_ROOT / "data" / "steward.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  type TEXT NOT NULL,
  occurred_at TEXT NOT NULL,
  raw_text TEXT,
  payload TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_type_time ON events(type, occurred_at);

CREATE TABLE IF NOT EXISTS schema_version (
  version INTEGER NOT NULL
);

-- v2: mod-fitness 周期型目标
CREATE TABLE IF NOT EXISTS goals (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  kind TEXT NOT NULL DEFAULT 'workout',
  metric TEXT NOT NULL,
  target REAL NOT NULL,
  period TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'active',
  superseded_by INTEGER REFERENCES goals(id),
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_goals_lookup ON goals(kind, metric, period, status);
"""


def default_db_path() -> Path:
    import os

    return Path(os.environ.get("STEWARD_DB", DEFAULT_DB_PATH))


def connect(db_path: Path | str | None = None) -> sqlite3.Connection:
    """打开连接。调用方负责 close()。"""
    path = Path(db_path) if db_path is not None else default_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """建表（幂等）。空库写入当前版本号；旧库版本号向上升级。"""
    conn.executescript(_SCHEMA)
    (count,) = conn.execute("SELECT COUNT(*) FROM schema_version").fetchone()
    if count == 0:
        conn.execute("INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,))
        conn.commit()
        return
    (version,) = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()
    if version < SCHEMA_VERSION:
        conn.execute("UPDATE schema_version SET version = ?", (SCHEMA_VERSION,))
        conn.commit()
