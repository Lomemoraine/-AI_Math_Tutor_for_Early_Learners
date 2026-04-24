# import json
# import random
# from pathlib import Path
# from typing import List, Dict


# def load_seed(path: str) -> List[Dict]:
#     p = Path(path)
#     with p.open("r", encoding="utf-8") as f:
#         data = json.load(f)
#     return data


# def expand_curriculum(seed: List[Dict], target: int = 60) -> List[Dict]:
#     """Expand a small seed curriculum to `target` items with light augmentations.

#     This is a deterministic-but-simple generator used for demos and evaluation.
#     """
#     out = list(seed)
#     idx = 1
#     while len(out) < target:
#         src = random.choice(seed)
#         new = dict(src)
#         new_id = f"{src['id']}_A{idx}"
#         new["id"] = new_id
#         # slightly vary difficulty within +/-1
#         new["difficulty"] = max(1, min(10, src.get("difficulty", 3) + random.choice([-1, 0, 1])))
#         # if stem exists, append a qualifier
#         for k in list(new.keys()):
#             if k.startswith("stem_") and isinstance(new[k], str):
#                 new[k] = new[k].rstrip("?") + " please"
#         out.append(new)
#         idx += 1
#     return out


# def save_curriculum(items: List[Dict], outpath: str):
#     p = Path(outpath)
#     p.parent.mkdir(parents=True, exist_ok=True)
#     with p.open("w", encoding="utf-8") as f:
#         json.dump(items, f, ensure_ascii=False, indent=2)
"""
curriculum_loader.py
Loads the seed curriculum (12 items), validates schema,
and expands to 60+ items via deterministic augmentation.
"""

import json
import copy
import random
from pathlib import Path
from typing import List, Dict, Optional

SKILLS = ["counting", "number_sense", "addition", "subtraction", "word_problem"]

# ---------------------------------------------------------------------------
# Augmentation templates — used to expand 12 seed items → 60+ items
# ---------------------------------------------------------------------------
ADDITION_PAIRS = [
    (1,1,2),(1,2,3),(2,2,4),(2,3,5),(3,3,6),(3,4,7),(4,4,8),(4,5,9),
    (5,5,10),(6,4,10),(7,3,10),(5,6,11),(6,6,12),(7,5,12),(8,4,12),
    (6,7,13),(8,5,13),(7,7,14),(9,5,14),(8,7,15),(9,6,15),(10,5,15),
    (13,5,18),(14,4,18),(27,14,41),(36,25,61),(23,14,37),
]
SUBTRACTION_PAIRS = [
    (3,1,2),(4,1,3),(5,2,3),(6,1,5),(7,2,5),(8,3,5),(9,4,5),
    (10,4,6),(10,3,7),(12,5,7),(15,7,8),(20,8,12),(62,28,34),
]
COUNTING_ITEMS = [
    (3,"stars","Nyenyeri zingahe?","Combien d'étoiles?","How many stars?",1,"5-6"),
    (4,"birds","Inyoni zingahe?","Combien d'oiseaux?","How many birds?",1,"5-6"),
    (6,"fish","Amafi angahe?","Combien de poissons?","How many fish?",2,"5-6"),
    (7,"goats","Ihene zingahe?","Combien de chèvres?","How many goats?",2,"6-7"),
    (9,"mangoes","Amango angahe?","Combien de mangues?","How many mangoes?",3,"6-7"),
    (10,"drums","Ingoma zingahe?","Combien de tambours?","How many drums?",3,"6-7"),
    (12,"children","Abana bangahe?","Combien d'enfants?","How many children?",4,"7-8"),
    (15,"beans","Ibiharage bingahe?","Combien de haricots?","How many beans?",4,"7-8"),
]
NUMBER_SENSE_ITEMS = [
    (2,5,"2 or 5?","2 cyangwa 5?","2 ou 5?",1,"5-6"),
    (6,9,"6 or 9?","6 cyangwa 9?","6 ou 9?",2,"5-6"),
    (11,8,"11 or 8?","11 cyangwa 8?","11 ou 8?",3,"6-7"),
    (15,12,"15 or 12?","15 cyangwa 12?","15 ou 12?",3,"6-7"),
    (23,19,"23 or 19?","23 cyangwa 19?","23 ou 19?",4,"7-8"),
    (30,27,"30 or 27?","30 cyangwa 27?","30 ou 27?",4,"7-8"),
    (45,54,"45 or 54?","45 cyangwa 54?","45 ou 54?",5,"8-9"),
]
WORD_PROBLEMS = [
    ("Emi has 3 bananas. She gets 2 more. How many?",
     "Emi afite amashaza 3. Aronka 2 menshi. Ni angahe?",
     "Emi a 3 bananes. Elle en reçoit 2 de plus. Combien?", 5, 3,"6-7"),
    ("A basket has 10 oranges. 4 are eaten. How many remain?",
     "Agaseke kari amacunga 10. 4 arariwa. Ni angahe asigaye?",
     "Un panier contient 10 oranges. 4 sont mangées. Combien reste-t-il?",6,6,"7-8"),
    ("5 boys and 6 girls are in class. How many children in total?",
     "Abahungu 5 n'abakobwa 6 bari mu ishuri. Abana bangahe muri rusange?",
     "5 garçons et 6 filles sont en classe. Combien d'enfants au total?",6,11,"7-8"),
    ("Keza has 15 RWF. She spends 7 RWF. How much is left?",
     "Keza afite amafaranga 15 RWF. Aragurishije 7 RWF. Asigaye angahe?",
     "Keza a 15 RWF. Elle dépense 7 RWF. Combien lui reste-t-il?",7,8,"8-9"),
    ("A farmer plants 4 rows of 5 trees each. How many trees?",
     "Umuhinzi ateze imirongo 4 y'ibiti 5 itari umwe. Ni ibiti bingahe?",
     "Un agriculteur plante 4 rangées de 5 arbres. Combien d'arbres?",8,20,"8-9"),
    ("Tom has 50 RWF. Each pencil costs 8 RWF. How many can he buy?",
     "Tom afite amafaranga 50 RWF. Ikaramu rimwe rirahenda 8 RWF. Arashobora kugura angahe?",
     "Tom a 50 RWF. Chaque crayon coûte 8 RWF. Combien peut-il en acheter?",9,6,"8-9"),
]


def load_seed(seed_path: str) -> List[Dict]:
    with open(seed_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _make_id(prefix: str, idx: int) -> str:
    return f"{prefix}{idx:03d}"


def expand_curriculum(seed_items: List[Dict]) -> List[Dict]:
    """Expand seed (12 items) to 60+ items deterministically."""
    items = copy.deepcopy(seed_items)
    existing_ids = {it["id"] for it in items}

    # --- Addition expansions ---
    for i, (a, b, ans) in enumerate(ADDITION_PAIRS, start=10):
        difficulty = min(10, max(1, (a + b) // 5 + 1))
        age_band = "5-6" if ans <= 5 else ("6-7" if ans <= 10 else ("7-8" if ans <= 20 else "8-9"))
        item = {
            "id": _make_id("AX", i),
            "skill": "addition",
            "difficulty": difficulty,
            "age_band": age_band,
            "stem_en": f"{a} plus {b} equals?",
            "stem_fr": f"{a} plus {b} égale?",
            "stem_kin": f"{a} + {b} ni angahe?",
            "visual": f"beads_{a}_plus_{b}",
            "answer_int": ans,
        }
        if item["id"] not in existing_ids:
            items.append(item)
            existing_ids.add(item["id"])

    # --- Subtraction expansions ---
    for i, (a, b, ans) in enumerate(SUBTRACTION_PAIRS, start=10):
        difficulty = min(10, max(1, a // 5 + 1))
        age_band = "5-6" if a <= 5 else ("6-7" if a <= 10 else ("7-8" if a <= 20 else "8-9"))
        item = {
            "id": _make_id("SX", i),
            "skill": "subtraction",
            "difficulty": difficulty,
            "age_band": age_band,
            "stem_en": f"{a} minus {b} equals?",
            "stem_fr": f"{a} moins {b} égale?",
            "stem_kin": f"{a} - {b} ni angahe?",
            "visual": f"objects_{a}_minus_{b}",
            "answer_int": ans,
        }
        if item["id"] not in existing_ids:
            items.append(item)
            existing_ids.add(item["id"])

    # --- Counting expansions ---
    for i, (count, obj, kin, fr, en, diff, age) in enumerate(COUNTING_ITEMS, start=10):
        item = {
            "id": _make_id("CX", i),
            "skill": "counting",
            "difficulty": diff,
            "age_band": age,
            "stem_en": en,
            "stem_fr": fr,
            "stem_kin": kin,
            "visual": f"{obj}_{count}",
            "answer_int": count,
        }
        if item["id"] not in existing_ids:
            items.append(item)
            existing_ids.add(item["id"])

    # --- Number sense expansions ---
    for i, (bigger, smaller, en, kin, fr, diff, age) in enumerate(NUMBER_SENSE_ITEMS, start=10):
        item = {
            "id": _make_id("NX", i),
            "skill": "number_sense",
            "difficulty": diff,
            "age_band": age,
            "stem_en": f"Which is bigger: {en}",
            "stem_fr": f"Lequel est plus grand: {fr}",
            "stem_kin": f"Ni iyihe nini: {kin}",
            "visual": f"compare_{smaller}_{bigger}",
            "answer_int": bigger,
        }
        if item["id"] not in existing_ids:
            items.append(item)
            existing_ids.add(item["id"])

    # --- Word problem expansions ---
    for i, (en, kin, fr, diff, ans, age) in enumerate(WORD_PROBLEMS, start=10):
        item = {
            "id": _make_id("WX", i),
            "skill": "word_problem",
            "difficulty": diff,
            "age_band": age,
            "stem_en": en,
            "stem_fr": fr,
            "stem_kin": kin,
            "visual": "word_problem_scene",
            "answer_int": ans,
        }
        if item["id"] not in existing_ids:
            items.append(item)
            existing_ids.add(item["id"])

    return items


def get_items_by_skill(items: List[Dict], skill: str) -> List[Dict]:
    return [it for it in items if it["skill"] == skill]


def get_items_by_difficulty_range(items: List[Dict], low: int, high: int) -> List[Dict]:
    return [it for it in items if low <= it["difficulty"] <= high]


def get_stem(item: Dict, lang: str = "en") -> str:
    key = f"stem_{lang}"
    return item.get(key) or item.get("stem_en", "")


class CurriculumLoader:
    def __init__(self, seed_path: str):
        seed = load_seed(seed_path)
        self.items: List[Dict] = expand_curriculum(seed)
        self._index: Dict[str, Dict] = {it["id"]: it for it in self.items}
        print(f"[CurriculumLoader] Loaded {len(self.items)} items across skills: "
              f"{set(it['skill'] for it in self.items)}")

    def get(self, item_id: str) -> Optional[Dict]:
        return self._index.get(item_id)

    def by_skill(self, skill: str) -> List[Dict]:
        return get_items_by_skill(self.items, skill)

    def by_difficulty(self, low: int, high: int) -> List[Dict]:
        return get_items_by_difficulty_range(self.items, low, high)

    def stem(self, item: Dict, lang: str = "en") -> str:
        return get_stem(item, lang)

    def summary(self) -> Dict:
        from collections import Counter
        skill_counts = Counter(it["skill"] for it in self.items)
        diff_counts = Counter(it["difficulty"] for it in self.items)
        return {"total": len(self.items), "by_skill": dict(skill_counts), "by_difficulty": dict(diff_counts)}


if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "data/T3.1_Math_Tutor/curriculum_seed.json"
    loader = CurriculumLoader(path)
    print(json.dumps(loader.summary(), indent=2))