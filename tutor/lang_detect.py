"""
lang_detect.py
Lightweight rule-based language detector for child responses.
Handles EN / FR / KIN / mixed (code-switched) input.
No external API — fully offline.
"""

import re
from typing import Dict, Tuple

# ---------------------------------------------------------------------------
# Lexicons (number words + common response words per language)
# ---------------------------------------------------------------------------
EN_WORDS = {
    "zero","one","two","three","four","five","six","seven","eight","nine","ten",
    "eleven","twelve","thirteen","fourteen","fifteen","sixteen","seventeen",
    "eighteen","nineteen","twenty","thirty","forty","fifty","hundred",
    "yes","no","more","less","bigger","smaller","equal","plus","minus","and",
}
FR_WORDS = {
    "zéro","un","une","deux","trois","quatre","cinq","six","sept","huit","neuf",
    "dix","onze","douze","treize","quatorze","quinze","seize","vingt","trente",
    "quarante","cinquante","cent","oui","non","plus","moins","égal","et",
}
KIN_WORDS = {
    "zeru","imwe","ebyiri","eshatu","enye","eshanu","gatandatu","karindwi",
    "umunani","icyenda","icumi","cumi","makumyabiri","mirongo","ijana",
    "yego","oya","menshi","bike","nini","ntoya","angahe","zingahe","bangahe",
    "esheshatu","twewenti","nindwi","icyumi",
}

# Digit pattern
DIGIT_RE = re.compile(r'\b\d+\b')


def _tokenize(text: str):
    return re.findall(r"[a-zA-ZÀ-ÿ]+", text.lower())


def detect_language(text: str) -> Dict:
    """
    Returns:
        {
          "dominant": "en" | "fr" | "kin" | "mixed",
          "scores": {"en": float, "fr": float, "kin": float},
          "languages_present": [...],
          "number_words": [...],   # number words found
          "digits": [...]          # digit strings found
        }
    """
    tokens = _tokenize(text)
    digits = DIGIT_RE.findall(text)

    scores = {"en": 0.0, "fr": 0.0, "kin": 0.0}
    present_langs = set()
    number_words = []

    for tok in tokens:
        matched = []
        if tok in EN_WORDS:
            matched.append("en")
        if tok in FR_WORDS:
            matched.append("fr")
        if tok in KIN_WORDS:
            matched.append("kin")
        for lang in matched:
            scores[lang] += 1.0
            present_langs.add(lang)
        if matched:
            number_words.append(tok)

    total = sum(scores.values()) or 1.0
    norm = {lang: round(scores[lang] / total, 3) for lang in scores}

    langs_found = [lang for lang in scores if scores[lang] > 0]
    if len(langs_found) == 0 and digits:
        # Pure digit response — treat as language-neutral, default to en
        dominant = "en"
    elif len(langs_found) == 0:
        dominant = "en"  # fallback
    elif len(langs_found) == 1:
        dominant = langs_found[0]
    else:
        # Mixed — dominant = highest score, flag as mixed
        dominant = max(scores, key=lambda l: scores[l])
        if len(langs_found) >= 2:
            dominant = "mixed"

    return {
        "dominant": dominant,
        "scores": norm,
        "languages_present": sorted(present_langs),
        "number_words": number_words,
        "digits": digits,
    }


def get_reply_language(detection: Dict, fallback: str = "en") -> str:
    """
    Returns the language to reply in.
    For mixed: use dominant scored language.
    """
    dom = detection["dominant"]
    if dom == "mixed":
        scores = detection["scores"]
        return max(scores, key=lambda l: scores[l])
    return dom if dom in ("en", "fr", "kin") else fallback


def extract_numeric_answer(text: str) -> int | None:
    """
    Try to extract a numeric answer from child response.
    Handles digits and number words.
    """
    # Try digits first
    digits = DIGIT_RE.findall(text)
    if digits:
        return int(digits[0])

    # Try EN number words
    en_map = {
        "zero":0,"one":1,"two":2,"three":3,"four":4,"five":5,"six":6,
        "seven":7,"eight":8,"nine":9,"ten":10,"eleven":11,"twelve":12,
        "thirteen":13,"fourteen":14,"fifteen":15,"sixteen":16,"seventeen":17,
        "eighteen":18,"nineteen":19,"twenty":20,"thirty":30,"forty":40,
        "fifty":50,"hundred":100,
    }
    fr_map = {
        "zéro":0,"un":1,"une":1,"deux":2,"trois":3,"quatre":4,"cinq":5,
        "six":6,"sept":7,"huit":8,"neuf":9,"dix":10,"onze":11,"douze":12,
        "treize":13,"quatorze":14,"quinze":15,"seize":16,"vingt":20,
        "trente":30,"quarante":40,"cinquante":50,"cent":100,
    }
    kin_map = {
        "zeru":0,"imwe":1,"ebyiri":2,"eshatu":3,"enye":4,"eshanu":5,
        "gatandatu":6,"karindwi":7,"umunani":8,"icyenda":9,"icumi":10,
        "cumi":10,
    }
    tokens = _tokenize(text)
    for tok in tokens:
        if tok in en_map:
            return en_map[tok]
        if tok in fr_map:
            return fr_map[tok]
        if tok in kin_map:
            return kin_map[tok]
    return None


def build_feedback(correct: bool, lang: str, answer: int) -> str:
    """Return feedback string in the learner's dominant language."""
    if lang == "kin":
        if correct:
            return f"Byiza cyane! Igisubizo ni {answer}. ✅"
        else:
            return f"Ongera ugerageze. Igisubizo ni {answer}. 💪"
    elif lang == "fr":
        if correct:
            return f"Très bien! La réponse est {answer}. ✅"
        else:
            return f"Essaie encore. La réponse est {answer}. 💪"
    else:  # en default
        if correct:
            return f"Well done! The answer is {answer}. ✅"
        else:
            return f"Good try! The answer is {answer}. 💪"


if __name__ == "__main__":
    tests = [
        "five",
        "cinq",
        "eshanu",
        "three plus four",
        "neuf",
        "esheshatu",   # from child_utt_sample_seed
        "twewenti",    # from child_utt_sample_seed
        "7",
        "tu",          # French "two" (informal child speech)
        "ebyiri na eshatu",  # KIN "two and three" code-switch
    ]
    for t in tests:
        det = detect_language(t)
        num = extract_numeric_answer(t)
        print(f"{t!r:30s} → lang={det['dominant']:6s}  num={num}  present={det['languages_present']}")