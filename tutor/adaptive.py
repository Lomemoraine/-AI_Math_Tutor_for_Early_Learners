"""
adaptive.py
Bayesian Knowledge Tracing (BKT) per skill + Elo-style baseline.
Provides next-item selection and AUC evaluation utilities.
"""

import math
import json
import random
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field, asdict

# ---------------------------------------------------------------------------
# BKT Parameters (per skill, learned from literature defaults)
# ---------------------------------------------------------------------------
DEFAULT_BKT_PARAMS = {
    "counting":      {"p_init": 0.3, "p_learn": 0.15, "p_guess": 0.25, "p_slip": 0.10},
    "number_sense":  {"p_init": 0.25, "p_learn": 0.12, "p_guess": 0.20, "p_slip": 0.10},
    "addition":      {"p_init": 0.20, "p_learn": 0.13, "p_guess": 0.20, "p_slip": 0.12},
    "subtraction":   {"p_init": 0.18, "p_learn": 0.11, "p_guess": 0.18, "p_slip": 0.12},
    "word_problem":  {"p_init": 0.10, "p_learn": 0.09, "p_guess": 0.15, "p_slip": 0.15},
}

SKILLS = list(DEFAULT_BKT_PARAMS.keys())
MASTERY_THRESHOLD = 0.80   # p(mastery) above which skill is considered mastered
ELO_K = 32
ELO_BASE = 400.0


# ---------------------------------------------------------------------------
# BKT Model
# ---------------------------------------------------------------------------
@dataclass
class BKTState:
    skill: str
    p_know: float = 0.0          # current P(Learned)
    p_init: float = 0.3
    p_learn: float = 0.15
    p_guess: float = 0.25
    p_slip: float = 0.10
    n_attempts: int = 0
    n_correct: int = 0

    def __post_init__(self):
        self.p_know = self.p_init

    def update(self, correct: bool) -> float:
        """BKT update step. Returns updated P(Learned)."""
        p_k = self.p_know
        # P(correct | known) = 1 - p_slip
        # P(correct | not known) = p_guess
        if correct:
            p_correct_given_k = 1.0 - self.p_slip
            p_correct_given_nk = self.p_guess
        else:
            p_correct_given_k = self.p_slip
            p_correct_given_nk = 1.0 - self.p_guess

        # Bayes update
        numerator = p_correct_given_k * p_k
        denominator = numerator + p_correct_given_nk * (1.0 - p_k)
        if denominator < 1e-9:
            p_k_given_obs = p_k
        else:
            p_k_given_obs = numerator / denominator

        # Learning transition
        p_k_new = p_k_given_obs + (1.0 - p_k_given_obs) * self.p_learn

        self.p_know = min(1.0, p_k_new)
        self.n_attempts += 1
        if correct:
            self.n_correct += 1
        return self.p_know

    def predict_correct(self) -> float:
        """P(next response is correct) under current BKT state."""
        return self.p_know * (1.0 - self.p_slip) + (1.0 - self.p_know) * self.p_guess

    @property
    def mastered(self) -> bool:
        return self.p_know >= MASTERY_THRESHOLD


class BKTTracker:
    """Tracks BKT state across all skills for one learner."""

    def __init__(self, params: Dict = None): #type: ignore
        params = params or DEFAULT_BKT_PARAMS
        self.states: Dict[str, BKTState] = {
            skill: BKTState(skill=skill, **params[skill])
            for skill in SKILLS
        }

    def update(self, skill: str, correct: bool) -> float:
        return self.states[skill].update(correct)

    def predict(self, skill: str) -> float:
        return self.states[skill].predict_correct()

    def p_know(self, skill: str) -> float:
        return self.states[skill].p_know

    def mastery_profile(self) -> Dict[str, float]:
        return {s: st.p_know for s, st in self.states.items()}

    def weakest_skill(self) -> str:
        return min(self.states, key=lambda s: self.states[s].p_know)

    def to_dict(self) -> Dict:
        return {s: asdict(st) for s, st in self.states.items()}

    @classmethod
    def from_dict(cls, d: Dict) -> "BKTTracker":
        tracker = cls.__new__(cls)
        tracker.states = {}
        for skill, sd in d.items():
            st = BKTState(**sd)
            tracker.states[skill] = st
        return tracker


# ---------------------------------------------------------------------------
# Elo Baseline
# ---------------------------------------------------------------------------
@dataclass
class EloState:
    rating: float = ELO_BASE
    n_attempts: int = 0

    def expected_score(self, item_difficulty: int) -> float:
        """Expected P(correct) given item difficulty mapped to Elo rating."""
        item_rating = 200.0 + item_difficulty * 50.0
        return 1.0 / (1.0 + 10 ** ((item_rating - self.rating) / 400.0))

    def update(self, item_difficulty: int, correct: bool) -> float:
        expected = self.expected_score(item_difficulty)
        actual = 1.0 if correct else 0.0
        self.rating += ELO_K * (actual - expected)
        self.n_attempts += 1
        return self.rating


class EloTracker:
    def __init__(self):
        self.skills: Dict[str, EloState] = {s: EloState() for s in SKILLS}

    def update(self, skill: str, difficulty: int, correct: bool) -> float:
        return self.skills[skill].update(difficulty, correct)

    def predict(self, skill: str, difficulty: int) -> float:
        return self.skills[skill].expected_score(difficulty)

    def to_dict(self) -> Dict:
        return {s: asdict(st) for s, st in self.skills.items()}


# ---------------------------------------------------------------------------
# Adaptive Item Selector
# ---------------------------------------------------------------------------
class AdaptiveSelector:
    """
    Selects next curriculum item based on BKT state.
    Strategy:
      1. Focus on weakest unmastered skill.
      2. Within skill, target items near current estimated difficulty frontier.
      3. Avoid recently seen items (recency buffer).
    """

    def __init__(self, curriculum_items: List[Dict], window: int = 5):
        self.items = curriculum_items
        self.window = window          # recency buffer size
        self.seen_ids: List[str] = []

    def _difficulty_target(self, p_know: float) -> Tuple[int, int]:
        """Map P(known) to a target difficulty range."""
        if p_know < 0.20:
            return 1, 3
        elif p_know < 0.40:
            return 2, 5
        elif p_know < 0.60:
            return 4, 7
        elif p_know < 0.80:
            return 5, 9
        else:
            return 7, 10

    def select(self, bkt: BKTTracker, lang: str = "en") -> Optional[Dict]:
        weakest = bkt.weakest_skill()
        p_know = bkt.p_know(weakest)
        d_low, d_high = self._difficulty_target(p_know)

        recent = set(self.seen_ids[-self.window:])
        candidates = [
            it for it in self.items
            if it["skill"] == weakest
            and d_low <= it["difficulty"] <= d_high
            and it["id"] not in recent
        ]

        if not candidates:
            # Relax: any item for that skill not recently seen
            candidates = [it for it in self.items
                          if it["skill"] == weakest and it["id"] not in recent]
        if not candidates:
            candidates = self.items  # full fallback

        # Pick item closest to midpoint of target range
        mid = (d_low + d_high) / 2.0
        candidates.sort(key=lambda x: abs(x["difficulty"] - mid))
        chosen = candidates[0]
        self.seen_ids.append(chosen["id"])
        return chosen

    def record_response(self, item_id: str, correct: bool,
                        bkt: BKTTracker, elo: EloTracker,
                        skill: str, difficulty: int):
        bkt.update(skill, correct)
        elo.update(skill, difficulty, correct)


# ---------------------------------------------------------------------------
# AUC Evaluation
# ---------------------------------------------------------------------------
def simulate_learner_replay(curriculum_items: List[Dict],
                             n_steps: int = 40,
                             seed: int = 42) -> List[Dict]:
    """
    Simulate a learner session for evaluation.
    Returns list of {skill, difficulty, correct, bkt_pred, elo_pred}.
    """
    rng = random.Random(seed)
    bkt = BKTTracker()
    elo = EloTracker()
    selector = AdaptiveSelector(curriculum_items)

    true_mastery = {s: rng.uniform(0.1, 0.6) for s in SKILLS}
    records = []

    for _ in range(n_steps):
        item = selector.select(bkt)
        if item is None:
            break
        skill = item["skill"]
        diff = item["difficulty"]

        # Simulate correctness: true mastery + noise
        p_correct_true = true_mastery[skill] + rng.gauss(0, 0.1)
        p_correct_true = max(0.05, min(0.95, p_correct_true))
        correct = rng.random() < p_correct_true

        bkt_pred = bkt.predict(skill)
        elo_pred = elo.predict(skill, diff)

        records.append({
            "skill": skill,
            "difficulty": diff,
            "correct": int(correct),
            "bkt_pred": bkt_pred,
            "elo_pred": elo_pred,
        })

        selector.record_response(item["id"], correct, bkt, elo, skill, diff)
        # Slowly improve true mastery (learning effect)
        true_mastery[skill] = min(0.95, true_mastery[skill] + 0.015)

    return records


def roc_auc(y_true: List[int], y_score: List[float]) -> float:
    """Compute ROC-AUC without sklearn."""
    pairs = sorted(zip(y_score, y_true), reverse=True)
    n_pos = sum(y_true)
    n_neg = len(y_true) - n_pos
    if n_pos == 0 or n_neg == 0:
        return 0.5
    tp = fp = auc = prev_fp = prev_tp = 0
    prev_score = None
    for score, label in pairs:
        if score != prev_score and prev_score is not None:
            auc += (fp - prev_fp) * (tp + prev_tp) / 2.0
            prev_fp, prev_tp = fp, tp
        if label == 1:
            tp += 1
        else:
            fp += 1
        prev_score = score
    auc += (fp - prev_fp) * (tp + prev_tp) / 2.0
    return auc / (n_pos * n_neg)


def evaluate(curriculum_items: List[Dict], n_learners: int = 20) -> Dict:
    """Run evaluation across n_learners simulated replays."""
    bkt_preds, elo_preds, labels = [], [], []

    for seed in range(n_learners):
        records = simulate_learner_replay(curriculum_items, n_steps=40, seed=seed)
        for r in records:
            labels.append(r["correct"])
            bkt_preds.append(r["bkt_pred"])
            elo_preds.append(r["elo_pred"])

    bkt_auc = roc_auc(labels, bkt_preds)
    elo_auc = roc_auc(labels, elo_preds)

    return {
        "n_learners": n_learners,
        "n_observations": len(labels),
        "BKT_AUC": round(bkt_auc, 4),
        "Elo_AUC": round(elo_auc, 4),
        "BKT_wins": bkt_auc > elo_auc,
    }


if __name__ == "__main__":
    import sys
    sys.path.insert(0, ".")
    from tutor.curriculum_loader import CurriculumLoader
    seed_path = sys.argv[1] if len(sys.argv) > 1 else "data/T3.1_Math_Tutor/curriculum_seed.json"
    loader = CurriculumLoader(seed_path)
    results = evaluate(loader.items)
    print(json.dumps(results, indent=2))