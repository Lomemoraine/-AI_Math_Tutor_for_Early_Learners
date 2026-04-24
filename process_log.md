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
| 2:35–2:45 | Wrote `README.md`, `footprint_report.md`, `requirements.txt`. |
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

*Why:* BKT math is easy to get wrong (denominator edge cases). Wanted clean, testable pure function.

**Prompt 2 (used):**
> "Design a rule-based language detector for short child responses in English, French, and Kinyarwanda. Input: a string like 'eshanu' or 'five' or 'cinq'. Output: dominant language and any number extracted. Needs to handle code-switching."

*Why:* No ML model available offline for KIN. Rule-based with lexicons is the right trade-off for child number vocabulary (small, bounded set).

**Prompt 3 (used):**
> "Write a SQLite schema and Python class for storing per-learner BKT states and response logs. Encrypt sensitive fields with Fernet. Add a weekly_summary() method that returns per-skill accuracy for a date range."

*Why:* Encrypted SQLite is a specific constraint from the brief — needed to get the schema right and ensure WAL mode for crash safety.

**Prompt discarded:**
> "Use scikit-learn's BayesianGaussianMixture to model learner knowledge states."

*Why discarded:* scikit-learn adds ~30 MB to the footprint and is overkill — BKT is a 4-parameter closed-form model that is more interpretable and fits in 30 lines of pure Python. Interpretability matters for a child education context.

---

## Hardest Decision

**Whether to include a quantised LLM (TinyLlama/Phi-3-mini) as the language head, or skip it for the demo.**

The brief asks for QLoRA fine-tuning and a GGUF model. However, TinyLlama at Q2_K is ~380 MB — already over the 75 MB footprint, and downloading + running it on a Colab CPU would exceed the 2.5 s latency target and potentially the 4-hour time budget. 

The decision was to **build the full pipeline architecture** (the `asr_adapt.py` module with the Whisper loader, the `tutor/__init__.py` with clean interfaces) so that a GGUF model can be dropped in as a plug-in, but to make the core adaptive tutor (BKT + rule-based language detection) fully functional without it. This means the demo runs correctly within constraints, and the LLM integration is a documented stretch goal. This is the right engineering trade-off: a working offline tutor with clear extension points beats a half-loaded model that crashes on CPU.