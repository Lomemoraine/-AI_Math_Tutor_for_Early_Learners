"""ASR adaptation utilities: pitch/tempo augmentation and noise overlay."""

from pathlib import Path
import numpy as np

try:
    import librosa
    import soundfile as sf
except Exception:
    librosa = None
    sf = None


def pitch_shift_audio(src_path: str, semitones: float, out_path: str):
    if librosa is None:
        raise RuntimeError("librosa is required for pitch shifting")
    y, sr = librosa.load(src_path, sr=None)
    y2 = librosa.effects.pitch_shift(y, sr, semitones)
    sf.write(out_path, y2, sr)


def tempo_change(src_path: str, rate: float, out_path: str):
    if librosa is None:
        raise RuntimeError("librosa is required for time-stretching")
    y, sr = librosa.load(src_path, sr=None)
    y2 = librosa.effects.time_stretch(y, rate)
    sf.write(out_path, y2, sr)


def add_noise(src_path: str, noise_path: str, snr_db: float, out_path: str):
    if librosa is None:
        raise RuntimeError("librosa is required for noise overlay")
    y, sr = librosa.load(src_path, sr=None)
    n, _ = librosa.load(noise_path, sr=sr)
    # trim or tile noise to length
    if len(n) < len(y):
        n = np.tile(n, int(np.ceil(len(y) / len(n))))[: len(y)]
    else:
        n = n[: len(y)]

    # scale noise to desired SNR
    sig_power = np.mean(y ** 2)
    noise_power = np.mean(n ** 2)
    target_noise_power = sig_power / (10 ** (snr_db / 10.0))
    if noise_power == 0:
        scaled_n = n
    else:
        scaled_n = n * np.sqrt(target_noise_power / (noise_power + 1e-12))

    out = y + scaled_n
    sf.write(out_path, out, sr)
