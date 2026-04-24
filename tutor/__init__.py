"""
tutor — AI Math Tutor for Early Learners
AIMS KTT Hackathon · S2.T3.1
"""

from tutor.curriculum_loader import CurriculumLoader
from tutor.adaptive import BKTTracker, EloTracker, AdaptiveSelector, evaluate
from tutor.lang_detect import detect_language, extract_numeric_answer, build_feedback
from tutor.store import ProgressStore
from tutor.asr_adapt import process_text_response

__all__ = [
    "CurriculumLoader",
    "BKTTracker", "EloTracker", "AdaptiveSelector", "evaluate",
    "detect_language", "extract_numeric_answer", "build_feedback",
    "ProgressStore",
    "process_text_response",
]