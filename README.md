# 🧮 AI Math Tutor for Early Learners
**AIMS KTT Hackathon · S2.T3.1**

> An offline, adaptive, multilingual math tutor for children aged 5–9. Teaches counting, number sense, addition, subtraction, and word problems. Works fully on-device with no internet connection.

---

## Quick Start (2 commands)

```bash
pip install -r requirements.txt
python demo.py
```

Open `http://localhost:7860` in your browser. Select a language (English / Français / Ikinyarwanda) and start learning.

---

## Repository Structure

```
AI_Math_Tutor/
├── tutor/
│   ├── __init__.py
│   ├── curriculum_loader.py   # Loads + expands seed to 60+ items
│   ├── adaptive.py            # BKT + Elo knowledge tracing + item selector
│   ├── lang_detect.py         # EN/FR/KIN language detection (offline)
│   ├── asr_adapt.py           # Whisper-tiny ASR adapter for child voices
│   └── store.py               # Encrypted SQLite progress store + DP sync
├── data/
│   └── T3.1_Math_Tutor/
│       ├── curriculum_seed.json
│       ├── diagnostic_probes_seed.csv
│       ├── child_utt_sample_seed.csv
│       ├── child_utt_index.md
│       └── parent_report_schema.json
├── demo.py                    # Gradio child-facing UI
├── parent_report.py           # Weekly parent report generator
├── kt_eval.py                 # BKT vs Elo AUC evaluation
├── requirements.txt
├── process_log.md
├── SIGNED.md
└── LICENSE
```

---

## Components

### 1. Curriculum (`tutor/curriculum_loader.py`)
- Loads 12-item seed and expands to **60+ items** across 5 sub-skills
- Schema: `id, skill, difficulty (1-10), age_band, stem_en/fr/kin, visual, answer_int`
- `CurriculumLoader` provides `by_skill()`, `by_difficulty()`, `stem(item, lang)` APIs

### 2. Adaptive Knowledge Tracing (`tutor/adaptive.py`)
- **BKT** (Bayesian Knowledge Tracing) per skill: P(init), P(learn), P(guess), P(slip)
- **Elo baseline**: item difficulty mapped to Elo rating scale
- `AdaptiveSelector`: picks next item targeting the learner's weakest unmastered skill at the appropriate difficulty frontier
- `evaluate()`: runs 20-learner simulation and computes AUC for BKT vs Elo

### 3. Language Detection (`tutor/lang_detect.py`)
- Rule-based lexicon matching for EN / FR / KIN number words and common responses
- Handles code-switching: detects dominant language, mirrors it in reply
- `extract_numeric_answer()`: converts number words in any language to int
- `build_feedback()`: generates encouraging feedback in the learner's language

### 4. ASR Adaptation (`tutor/asr_adapt.py`)
- Base: `openai/whisper-tiny` (39M params)
- Child-voice augmentation: pitch shift (+3 to +6 semitones) + classroom noise overlay
- Graceful fallback to text input when audio unavailable (used in Gradio demo)

### 5. Progress Store (`tutor/store.py`)
- Encrypted SQLite (Fernet symmetric encryption)
- Tables: `learners`, `sessions`, `responses`
- `weekly_summary()`: aggregates per-skill accuracy for parent report
- `dp_aggregate_stats()`: Laplace-noise DP on cooperative aggregate stats
  - ε = 1.0 per learner per week, sensitivity = 1/n_learners

### 6. Parent Report (`parent_report.py`)
- Icon-based, bar-chart progress display readable in 60 seconds
- Dyscalculia early warning: flags 3+ sessions with low progress
- QR code placeholder for voiced summary audio
- Text and JSON output formats

---

## Running the Evaluation

```bash
python kt_eval.py
```

Outputs BKT AUC vs Elo AUC on 20 simulated learner replays.
Results saved to `reports/kt_eval_results.json`.

To convert to Jupyter notebook:
```bash
pip install jupytext
jupytext --to notebook kt_eval.py -o kt_eval.ipynb
```

---

## Parent Report

```bash
python parent_report.py --learner child_001
python parent_report.py --learner child_001 --format json
```

---

## Footprint

See `footprint_report.md` for full component breakdown.
Target: ≤ 75 MB (excluding TTS cache).

---


## Product & Business Adaptation

See `product_adaptation.md` for:
- First 90 seconds UX for a 6-year-old Kinyarwanda speaker
- Shared tablet deployment model (3 children, community centre)
- Non-literate parent report design

---

## License
MIT — see `LICENSE`