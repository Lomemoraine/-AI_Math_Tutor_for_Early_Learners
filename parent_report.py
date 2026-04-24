"""
parent_report.py
Generates a 1-page weekly parent report from local SQLite store.
Designed for low-literacy parents: icons, bars, minimal text.
Run: python parent_report.py --learner child_001
"""

import argparse
import json
from datetime import date, timedelta
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))

from tutor.store import ProgressStore

SKILL_ICONS = {
    "counting":      "🔢",
    "number_sense":  "🧠",
    "addition":      "➕",
    "subtraction":   "➖",
    "word_problem":  "📖",
}

LEVEL_ICONS = {
    (0.0, 0.3):  ("🔴", "Needs help"),
    (0.3, 0.6):  ("🟡", "Getting there"),
    (0.6, 0.85): ("🟢", "Doing well"),
    (0.85, 1.1): ("⭐", "Mastered!"),
}


def _level(score: float):
    for (lo, hi), (icon, label) in LEVEL_ICONS.items():
        if lo <= score < hi:
            return icon, label
    return "⭐", "Mastered!"


def _bar(score: float, width: int = 10) -> str:
    filled = int(score * width)
    return "█" * filled + "░" * (width - filled)


def generate_report(learner_id: str, db_path: str = None,
                    week_start: date = None, output_format: str = "text") -> str:
    store = ProgressStore(db_path) if db_path else ProgressStore()
    summary = store.weekly_summary(learner_id, week_start)
    store.close()

    skills = summary["skills"]
    n_sessions = summary["sessions"]
    week = summary["week_starting"]

    best_skill = max(skills, key=lambda s: skills[s]["current"])
    worst_skill = min(skills, key=lambda s: skills[s]["current"])

    best_score = skills[best_skill]["current"]
    worst_score = skills[worst_skill]["current"]

    overall = sum(v["current"] for v in skills.values()) / len(skills)
    overall_arrow = "📈" if overall >= 0.5 else ("📉" if overall < 0.3 else "➡️")

    if output_format == "json":
        report_data = {
            "learner_id": learner_id,
            "week_starting": week,
            "sessions": n_sessions,
            "skills": skills,
            "icons_for_parent": {
                "overall_arrow": overall_arrow,
                "best_skill": f"{SKILL_ICONS[best_skill]} {best_skill}",
                "needs_help": f"{SKILL_ICONS[worst_skill]} {worst_skill}",
            },
            "voiced_summary_audio": f"reports/{learner_id}_{week}_summary.wav",
        }
        return json.dumps(report_data, indent=2)

    # ── Text / terminal report ──────────────────────────────────────────────
    lines = []
    lines.append("=" * 52)
    lines.append(f"  📋 WEEKLY MATH REPORT  |  Week of {week}")
    lines.append(f"  👤 Learner: {learner_id}")
    lines.append("=" * 52)
    lines.append(f"  📅 Sessions this week:  {n_sessions}")
    lines.append(f"  {overall_arrow}  Overall progress:    {_bar(overall)}  {int(overall*100)}%")
    lines.append("")
    lines.append("  ── Skills ──────────────────────────────────")

    for skill, data in skills.items():
        score = data["current"]
        attempts = data.get("attempts", 0)
        icon = SKILL_ICONS[skill]
        lvl_icon, lvl_label = _level(score)
        bar = _bar(score)
        lines.append(
            f"  {icon} {skill.replace('_',' ').title():14s}  {bar}  {lvl_icon} {lvl_label}"
        )

    lines.append("")
    lines.append("  ── Summary ─────────────────────────────────")
    best_icon, _ = _level(best_score)
    worst_icon, _ = _level(worst_score)
    lines.append(f"  {best_icon} Best skill:    {SKILL_ICONS[best_skill]} {best_skill.replace('_',' ').title()}")
    lines.append(f"  {worst_icon} Needs support: {SKILL_ICONS[worst_skill]} {worst_skill.replace('_',' ').title()}")
    lines.append("")

    # Dyscalculia early warning check
    if worst_score < 0.2 and n_sessions >= 3:
        lines.append("  ⚠️  TEACHER NOTE: Your child may need extra support")
        lines.append(f"      in {worst_skill.replace('_',' ')}. Please talk to their teacher.")
        lines.append("")

    lines.append("  🔊 Audio summary: scan QR code on printed report")
    lines.append("  🔒 Data stored privately on this device only")
    lines.append("=" * 52)

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Generate weekly parent report")
    parser.add_argument("--learner", default="child_001", help="Learner ID")
    parser.add_argument("--db", default=None, help="Path to SQLite DB")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--week", default=None, help="Week start YYYY-MM-DD")
    args = parser.parse_args()

    week_start = date.fromisoformat(args.week) if args.week else None
    report = generate_report(args.learner, args.db, week_start, args.format)
    print(report)

    # Also save to file
    out_dir = Path("reports")
    out_dir.mkdir(exist_ok=True)
    week_str = (week_start or date.today()).isoformat()
    ext = "json" if args.format == "json" else "txt"
    out_path = out_dir / f"{args.learner}_{week_str}.{ext}"
    out_path.write_text(report)
    print(f"\n[Report saved to {out_path}]")


if __name__ == "__main__":
    main()