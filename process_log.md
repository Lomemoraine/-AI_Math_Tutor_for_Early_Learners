# process_log.md
**AIMS KTT Hackathon · S2.T3.1 · AI Math Tutor for Early Learners**

---

## Hour-by-Hour Timeline

| Time | Activity |
|---|---|
| 0:00–0:15 | Read brief, analysed seed files (curriculum_seed.json, diagnostic_probes_seed.csv, child_utt_sample_seed.csv, parent_report_schema.json, child_utt_index.md). Planned architecture. |
| 0:15–0:35 | Built `tutor/curriculum_loader.py` — loads seed, expands to 60+ items via deterministic augmentation across 5 sub-skills. |
| 0:35–0:60 | Built `tutor/adaptive.py` — BKT per-skill tracker, Elo baseline, AdaptiveSelector, AUC evaluation harness. |
| 1:00–1:15 | Built `tutor/lang_detect.py` — rule-based EN/FR/KIN lexicon matching, code-switch detection, number word extraction, multilingual feedback. |
| 1:15–1:30 | Built `tutor/store.py` — encrypted SQLite with Fernet AES-128, session management, weekly summary queries, DP-noised aggregate stats (ε=1.0 Laplace). |
| 1:30–1:45 | Built `tutor/asr_adapt.py` — Whisper-tiny loader, pitch-shift augmentation, text-mode fallback. |
| 1:45–2:00 | Built `demo.py` (Gradio) — child-facing chat UI with language selector, learner ID, adaptive item presentation, mastery progress bars. |
| 2:00–2:10 | Built `parent_report.py` — icon-based weekly report, dyscalculia flag, JSON and text output. |
| 2:10–2:20 | Built `kt_eval.py` — BKT vs Elo AUC evaluation over 20 simulated learners. |
| 2:20–2:35 | Wrote `product_adaptation.md` — first 90 seconds UX, shared tablet deployment, non-literate parent report design, risks & mitigations. |
| 2:35–2:45 | Wrote `README.md`, `requirements.txt`. |
| 2:45–3:00 | Testing, debugging imports, final review. |

---

## LLM / Tool Usage

| Tool | Why used |
|---|---|
| Claude (Anthropic) | Primary coding assistant — pair programming all modules, architecture decisions, code review |

---

## Three Sample Prompts Actually Sent

**Prompt 1 (used):**
> "Build the BKT update step in Python. Inputs: p_know, p_learn, p_guess, p_slip, correct (bool). Return updated P(Learned) after Bayesian update then learning transition. No external libraries."



**Prompt 2 (used):**
> "Design a rule-based language detector for short child responses in English, French, and Kinyarwanda. Input: a string like 'eshanu' or 'five' or 'cinq'. Output: dominant language and any number extracted. Needs to handle code-switching."


**Prompt 3 (used):**
> "Write a SQLite schema and Python class for storing per-learner BKT states and response logs. Encrypt sensitive fields with Fernet. Add a weekly_summary() method that returns per-skill accuracy for a date range."



**Prompt discarded:**
> "Use scikit-learn's BayesianGaussianMixture to model learner knowledge states."



---
