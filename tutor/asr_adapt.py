import numpy as np
from pathlib import Path
from typing import Optional, Tuple

# ---------------------------------------------------------------------------
# Whisper-tiny loader (lazy — only loads if transformers is available)
# ---------------------------------------------------------------------------
_whisper_model = None
_whisper_processor = None

def load_whisper(model_id: str = "openai/whisper-tiny"):
    """Lazy-load whisper-tiny. Cache globally."""
    global _whisper_model, _whisper_processor
    if _whisper_model is not None:
        return _whisper_model, _whisper_processor
    try:
        from transformers import WhisperProcessor, WhisperForConditionalGeneration
        print(f"[ASR] Loading {model_id} ...")
        _whisper_processor = WhisperProcessor.from_pretrained(model_id)
        _whisper_model = WhisperForConditionalGeneration.from_pretrained(model_id)
        _whisper_model.eval()
        print("[ASR] Whisper-tiny loaded.")
        return _whisper_model, _whisper_processor
    except ImportError:
        print("[ASR] transformers not available — using text-input fallback.")
        return None, None
    except Exception as e:
        print(f"[ASR] Could not load model: {e}")
        return None, None


def transcribe(audio_array: np.ndarray, sample_rate: int = 16000,
               language: str = "en") -> str:
    """
    Transcribe child audio using whisper-tiny.
    Falls back to empty string if model unavailable.
    """
    model, processor = load_whisper()
    if model is None or processor is None:
        return ""
    try:
        import torch
        lang_map = {"en": "english", "fr": "french", "kin": "kinyarwanda"}
        whisper_lang = lang_map.get(language, "english")

        inputs = processor(
            audio_array,
            sampling_rate=sample_rate,
            return_tensors="pt"
        )
        forced_decoder_ids = processor.get_decoder_prompt_ids(
            language=whisper_lang, task="transcribe"
        )
        with torch.no_grad():
            predicted_ids = model.generate(
                inputs["input_features"],
                forced_decoder_ids=forced_decoder_ids,
            )
        transcription = processor.batch_decode(predicted_ids, skip_special_tokens=True)
        return transcription[0].strip().lower() if transcription else ""
    except Exception as e:
        print(f"[ASR] Transcription error: {e}")
        return ""


# ---------------------------------------------------------------------------
# Pitch-shift augmentation for child voice simulation
# ---------------------------------------------------------------------------
def pitch_shift_semitones(audio: np.ndarray, sr: int, semitones: float) -> np.ndarray:
    """
    Simple pitch shift via resampling (no librosa required).
    Positive semitones = higher pitch (child-like).
    """
    factor = 2 ** (semitones / 12.0)
    original_len = len(audio)
    indices = np.round(np.arange(0, original_len, factor)).astype(int)
    indices = indices[indices < original_len]
    shifted = audio[indices]
    # Pad or trim to original length
    if len(shifted) < original_len:
        shifted = np.pad(shifted, (0, original_len - len(shifted)))
    else:
        shifted = shifted[:original_len]
    return shifted.astype(audio.dtype)


def augment_for_child(audio: np.ndarray, sr: int,
                      semitones: float = 4.0,
                      noise_level: float = 0.005) -> np.ndarray:
    """
    Apply child-voice augmentation:
    - Pitch shift (+3 to +6 semitones as per brief)
    - Light classroom noise overlay
    """
    shifted = pitch_shift_semitones(audio, sr, semitones)
    # Add Gaussian noise to simulate classroom
    noise = np.random.randn(len(shifted)).astype(np.float32) * noise_level
    augmented = shifted + noise
    # Normalize
    max_val = np.abs(augmented).max()
    if max_val > 0:
        augmented = augmented / max_val * 0.9
    return augmented


# ---------------------------------------------------------------------------
# Text-mode fallback (used in Gradio text-input demo)
# ---------------------------------------------------------------------------
def process_text_response(text: str) -> Tuple[str, str]:
    """
    When audio is not available, process typed/pasted text response.
    Returns (cleaned_text, detected_language).
    """
    from tutor.lang_detect import detect_language, get_reply_language
    cleaned = text.strip().lower()
    detection = detect_language(cleaned)
    lang = get_reply_language(detection)
    return cleaned, lang


# ---------------------------------------------------------------------------
# Audio file loader
# ---------------------------------------------------------------------------
def load_audio(path: str, target_sr: int = 16000) -> Tuple[Optional[np.ndarray], int]:
    """Load audio file to float32 numpy array at target sample rate."""
    try:
        import soundfile as sf
        audio, sr = sf.read(path, dtype="float32")
        if audio.ndim > 1:
            audio = audio.mean(axis=1)  # mono
        if sr != target_sr:
            # Simple linear resampling
            duration = len(audio) / sr
            n_samples = int(duration * target_sr)
            indices = np.linspace(0, len(audio) - 1, n_samples)
            audio = np.interp(indices, np.arange(len(audio)), audio).astype(np.float32)
        return audio, target_sr
    except ImportError:
        print("[ASR] soundfile not available.")
        return None, target_sr
    except Exception as e:
        print(f"[ASR] Could not load audio {path}: {e}")
        return None, target_sr


if __name__ == "__main__":
    print("[ASR] Testing text-mode fallback...")
    tests = ["five", "cinq", "eshanu", "7", "neuf"]
    for t in tests:
        cleaned, lang = process_text_response(t)
        print(f"  Input: {t!r} → cleaned: {cleaned!r}, lang: {lang}")