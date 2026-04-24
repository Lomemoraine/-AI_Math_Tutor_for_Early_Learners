"""
parent_report.py
Generate a weekly parent report from the tutor_progress.db
Run: python parent_report.py
"""

import sqlite3
from datetime import date, timedelta
from pathlib import Path

DB_PATH = Path("tutor_progress.db")

def weekly_summary(conn, learner_id, week_start=None):
    if week_start is None:
        week_start = date.today() - timedelta(days=date.today().weekday())
    week_end = week_start + timedelta(days=7)

    cur = conn.cursor()
    rows = cur.execute(
        """SELECT skill, correct FROM responses
           WHERE learner_id=? AND ts >= ? AND ts < ?""",
        (learner_id, week_start.isoformat(), week_end.isoformat())
    ).fetchall()

    sessions_row = cur.execute(
        """SELECT COUNT(*) as cnt FROM sessions
           WHERE learner_id=? AND started_at >= ? AND started_at < ?""",
        (learner_id, week_start.isoformat(), week_end.isoformat())
    ).fetchone()
    n_sessions = sessions_row[0] if sessions_row else 0

    skill_correct = {}
    skill_total = {}
    for skill, correct in rows:
        skill_total[skill] = skill_total.get(skill, 0) + 1
        skill_correct[skill] = skill_correct.get(skill, 0) + correct

    skills_report = {}
    for s in ["counting", "number_sense", "addition", "subtraction", "word_problem"]:
        total = skill_total.get(s, 0)
        correct = skill_correct.get(s, 0)
        accuracy = (correct / total) if total > 0 else 0.0
        skills_report[s] = {"accuracy": round(accuracy * 100, 1), "attempts": total}

    return {
        "learner_id": learner_id,
        "week_starting": week_start.isoformat(),
        "sessions": n_sessions,
        "skills": skills_report,
    }

def main():
    if not DB_PATH.exists():
        print("No progress database found.")
        return

    conn = sqlite3.connect(str(DB_PATH))
    learners = [row[0] for row in conn.execute("SELECT learner_id FROM learners").fetchall()]

    if not learners:
        print("No learners found in the database.")
        return

    print("=== Parent Report ===\n")
    for lid in learners:
        summary = weekly_summary(conn, lid)
        print(f"Learner: {summary['learner_id']}")
        print(f"Week starting: {summary['week_starting']}")
        print(f"Sessions: {summary['sessions']}")
        print("Skills:")
        for skill, data in summary["skills"].items():
            print(f"  {skill:15s} Accuracy: {data['accuracy']}%  Attempts: {data['attempts']}")
        print("-" * 40)

    conn.close()

if __name__ == "__main__":
    main()
