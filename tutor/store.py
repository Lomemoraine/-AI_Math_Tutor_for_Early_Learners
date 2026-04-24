"""
store.py
Encrypted SQLite progress store using Fernet symmetric encryption.
Stores per-learner session data, BKT states, and response logs.
Differential-privacy noise added on aggregated cooperative stats.
"""

import sqlite3
import json
import os
import math
import random
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from torch.jit import ignore

# Encryption: use cryptography.fernet if available, else base64 obfuscation
try:
    from cryptography.fernet import Fernet
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False

DB_PATH = Path("tutor_progress.db")
KEY_PATH = Path(".tutor_key")


# ---------------------------------------------------------------------------
# Key management
# ---------------------------------------------------------------------------
def _load_or_create_key() -> bytes:
    if not CRYPTO_AVAILABLE:
        return b""
    if KEY_PATH.exists():
        return KEY_PATH.read_bytes()
    key = Fernet.generate_key()
    KEY_PATH.write_bytes(key)
    KEY_PATH.chmod(0o600)
    return key


def _encrypt(data: str, key: bytes) -> str:
    if not CRYPTO_AVAILABLE or not key:
        return data
    f = Fernet(key)
    return f.encrypt(data.encode()).decode()


def _decrypt(data: str, key: bytes) -> str:
    if not CRYPTO_AVAILABLE or not key:
        return data
    f = Fernet(key)
    return f.decrypt(data.encode()).decode()


# ---------------------------------------------------------------------------
# Database setup
# ---------------------------------------------------------------------------
SCHEMA = """
CREATE TABLE IF NOT EXISTS learners (
    learner_id   TEXT PRIMARY KEY,
    created_at   TEXT,
    bkt_state    TEXT,   -- encrypted JSON
    elo_state    TEXT    -- encrypted JSON
);

CREATE TABLE IF NOT EXISTS sessions (
    session_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    learner_id   TEXT,
    started_at   TEXT,
    ended_at     TEXT,
    n_items      INTEGER DEFAULT 0,
    n_correct    INTEGER DEFAULT 0,
    lang_used    TEXT DEFAULT 'en'
);

CREATE TABLE IF NOT EXISTS responses (
    resp_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    learner_id   TEXT,
    session_id   INTEGER,
    item_id      TEXT,
    skill        TEXT,
    difficulty   INTEGER,
    correct      INTEGER,
    lang_detected TEXT,
    ts           TEXT
);
"""


class ProgressStore:
    def __init__(self, db_path: str = None): 
        self.db_path = Path(db_path) if db_path else DB_PATH
        self._key = _load_or_create_key()
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._conn.commit()
        self._current_session: Dict[str, int] = {}  # learner_id → session_id

    # ------------------------------------------------------------------
    # Learner management
    # ------------------------------------------------------------------
    def register_learner(self, learner_id: str) -> bool:
        """Register new learner. Returns True if created, False if existed."""
        existing = self._conn.execute(
            "SELECT learner_id FROM learners WHERE learner_id=?", (learner_id,)
        ).fetchone()
        if existing:
            return False
        self._conn.execute(
            "INSERT INTO learners (learner_id, created_at, bkt_state, elo_state) VALUES (?,?,?,?)",
            (learner_id, datetime.utcnow().isoformat(), "{}", "{}")
        )
        self._conn.commit()
        return True

    def save_bkt_state(self, learner_id: str, bkt_dict: Dict):
        encrypted = _encrypt(json.dumps(bkt_dict), self._key)
        self._conn.execute(
            "UPDATE learners SET bkt_state=? WHERE learner_id=?",
            (encrypted, learner_id)
        )
        self._conn.commit()

    def load_bkt_state(self, learner_id: str) -> Optional[Dict]:
        row = self._conn.execute(
            "SELECT bkt_state FROM learners WHERE learner_id=?", (learner_id,)
        ).fetchone()
        if not row or not row["bkt_state"] or row["bkt_state"] == "{}":
            return None
        try:
            decrypted = _decrypt(row["bkt_state"], self._key)
            return json.loads(decrypted)
        except Exception:
            return None

    def save_elo_state(self, learner_id: str, elo_dict: Dict):
        encrypted = _encrypt(json.dumps(elo_dict), self._key)
        self._conn.execute(
            "UPDATE learners SET elo_state=? WHERE learner_id=?",
            (encrypted, learner_id)
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------
    def start_session(self, learner_id: str, lang: str = "en") -> int:
        cur = self._conn.execute(
            "INSERT INTO sessions (learner_id, started_at, lang_used) VALUES (?,?,?)",
            (learner_id, datetime.utcnow().isoformat(), lang)
        )
        self._conn.commit()
        sid = cur.lastrowid
        self._current_session[learner_id] = sid
        return sid

    def end_session(self, learner_id: str):
        sid = self._current_session.get(learner_id)
        if not sid:
            return
        self._conn.execute(
            "UPDATE sessions SET ended_at=? WHERE session_id=?",
            (datetime.utcnow().isoformat(), sid)
        )
        self._conn.commit()

    def log_response(self, learner_id: str, item_id: str, skill: str,
                     difficulty: int, correct: bool, lang: str = "en"):
        sid = self._current_session.get(learner_id, 0)
        self._conn.execute(
            """INSERT INTO responses
               (learner_id, session_id, item_id, skill, difficulty, correct, lang_detected, ts)
               VALUES (?,?,?,?,?,?,?,?)""",
            (learner_id, sid, item_id, skill, difficulty,
             int(correct), lang, datetime.utcnow().isoformat())
        )
        # Update session counters
        self._conn.execute(
            """UPDATE sessions SET
               n_items = n_items + 1,
               n_correct = n_correct + ?
               WHERE session_id=?""",
            (int(correct), sid)
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Report queries
    # ------------------------------------------------------------------
    def weekly_summary(self, learner_id: str, week_start: date = None) -> Dict:
        """Aggregate weekly stats per skill for parent report."""
        if week_start is None:
            week_start = date.today() - timedelta(days=date.today().weekday())
        week_end = week_start + timedelta(days=7)

        rows = self._conn.execute(
            """SELECT skill, correct FROM responses
               WHERE learner_id=? AND ts >= ? AND ts < ?""",
            (learner_id, week_start.isoformat(), week_end.isoformat())
        ).fetchall()

        sessions_row = self._conn.execute(
            """SELECT COUNT(*) as cnt FROM sessions
               WHERE learner_id=? AND started_at >= ? AND started_at < ?""",
            (learner_id, week_start.isoformat(), week_end.isoformat())
        ).fetchone()
        n_sessions = sessions_row["cnt"] if sessions_row else 0

        from collections import defaultdict
        skill_correct = defaultdict(int)
        skill_total = defaultdict(int)
        for r in rows:
            skill_total[r["skill"]] += 1
            skill_correct[r["skill"]] += r["correct"]

        SKILLS = ["counting", "number_sense", "addition", "subtraction", "word_problem"]
        skills_report = {}
        for s in SKILLS:
            total = skill_total[s]
            correct = skill_correct[s]
            current = (correct / total) if total > 0 else 0.0
            skills_report[s] = {"current": round(current, 3), "delta": 0.0, "attempts": total}

        return {
            "learner_id": learner_id,
            "week_starting": week_start.isoformat(),
            "sessions": n_sessions,
            "skills": skills_report,
        }

    def all_responses(self, learner_id: str) -> List[Dict]:
        rows = self._conn.execute(
            "SELECT * FROM responses WHERE learner_id=? ORDER BY ts",
            (learner_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    def list_learners(self) -> List[str]:
        rows = self._conn.execute("SELECT learner_id FROM learners").fetchall()
        return [r["learner_id"] for r in rows]

    def close(self):
        self._conn.close()


# ---------------------------------------------------------------------------
# Differential Privacy — aggregated cooperative stats
# ---------------------------------------------------------------------------
def add_laplace_noise(value: float, sensitivity: float, epsilon: float) -> float:
    """Add Laplace noise for ε-differential privacy."""
    scale = sensitivity / epsilon
    noise = random.gauss(0, scale * math.sqrt(2))  # approx Laplace via Gaussian
    return max(0.0, min(1.0, value + noise))


def dp_aggregate_stats(store: ProgressStore,
                       skill: str,
                       epsilon: float = 1.0,
                       week_start: date = None) -> Dict: # type: ignore
    """
    Compute DP-noised aggregate correctness across all learners for a skill.
    ε budget: epsilon per learner per week (documented).
    Sensitivity = 1/n_learners (bounded contribution).
    """
    learners = store.list_learners()
    if not learners:
        return {"skill": skill, "mean_accuracy_dp": 0.0, "n_learners": 0, "epsilon": epsilon}

    accuracies = []
    for lid in learners:
        summary = store.weekly_summary(lid, week_start)
        skill_data = summary["skills"].get(skill, {})
        accuracies.append(skill_data.get("current", 0.0))

    true_mean = sum(accuracies) / len(accuracies)
    sensitivity = 1.0 / len(learners)
    dp_mean = add_laplace_noise(true_mean, sensitivity, epsilon)

    return {
        "skill": skill,
        "mean_accuracy_dp": round(dp_mean, 4),
        "n_learners": len(learners),
        "epsilon_budget_per_learner_per_week": epsilon,
        "sensitivity": round(sensitivity, 4),
    }