# Product & Business Adaptation
**AIMS KTT Hackathon · S2.T3.1 · AI Math Tutor for Early Learners**

---

## 1. First 90 Seconds — A 6-Year-Old Kinyarwanda Speaker

**Context:** Amina, age 6, speaks Kinyarwanda at home and is transitioning to English at school.  
She has never used this app before. The tablet is shared at a community centre.

### What happens step by step:

**0–5 sec — Auto language detection**
The app launches and displays 3 flag icons: 🇷🇼 🇫🇷 🇬🇧 with a voice prompt in Kinyarwanda:
> *"Muraho! Hitamo ururimi rwawe."* ("Hello! Choose your language.")

Large icons, no reading required. Amina taps 🇷🇼.

**5–15 sec — Name entry via tap, not typing**
A grid of 6 common Rwandan children's names appears as large picture cards (name + face illustration).
A "type my name" option is also available. Amina taps "Amina."

> *"Muraho Amina! Ndi Tutor. Tuziga imibare hamwe!"*
> ("Hello Amina! I am Tutor. Let's learn math together!")

An animated character (simple, low-bandwidth SVG) waves.

**15–45 sec — Diagnostic probe (item P001: counting, difficulty 2)**
Screen shows 4 illustrated goats. Audio plays:
> *"Ihene zingahe? Shyira urutoki ku nimero."* ("How many goats? Point to the number.")

Buttons 1, 2, 3, 4, 5 displayed as large coloured circles. No text labels.
Amina taps **4**.

**45–55 sec — Immediate positive feedback**
> *"Byiza cyane Amina! ★★★"* ("Very well done!")
Stars animate. Gentle chime sound.

**55–90 sec — Second item, adaptive**
BKT initialises. Because Amina answered correctly at difficulty 2, selector moves to difficulty 3.
A new item appears: addition with illustrated mangoes.

### What happens if the child is silent for 10 seconds?
1. **First silence (10 sec):** Gentle audio prompt: *"Fata umwanya! Reba neza."* ("Take your time! Look carefully.") The visual animates — objects gently bounce.
2. **Second silence (20 sec total):** Audio counts slowly out loud: *"Imwe… ebyiri… eshatu… enye…"* while highlighting each object. A hint.
3. **Third silence (30 sec total):** The answer button glows softly. No pressure message: *"Gerageza! Nta kibazo."* ("Try! No problem.") The child can tap any button without penalty — it records as a hint-assisted response, not a failure.

**Design principle:** No anxiety, no countdown, no "wrong" sound. Silence = needs support, not failure.

---

## 2. Shared Tablet Deployment — 3 Children, Community Centre

**Hardware:** Low-cost Android tablet (e.g. Tecno PAD 10, ~$70), 2GB RAM, shared among 3 children.

### Learner switching
- Home screen shows 3 large portrait cards, each with a child's drawn avatar and name.
- Each child has a 4-dot PIN (coloured circles, not digits) known only to them and their teacher.
- Switching takes < 5 seconds — tap your avatar, tap your PIN colours.
- No text required anywhere in the switching flow.

### Privacy preservation
- Each learner's BKT state, session history, and responses are stored in separate encrypted SQLite rows keyed by `learner_id`.
- Fernet AES-128 encryption; each learner's key is derived from their PIN + device ID.
- The app never shows one child's progress to another.
- The parent report for child A is only accessible via child A's PIN.

### Graceful degradation on reboot
| Scenario | Behaviour |
|---|---|
| Tablet reboots mid-session | Session ends cleanly; partial responses logged as `incomplete`; BKT state was saved after each response |
| Power cuts during SQLite write | WAL (Write-Ahead Log) mode ensures atomic commits; no corruption |
| App crashes | On next launch, app detects orphaned session (`ended_at` is NULL) and closes it before starting new one |
| Storage full | App warns teacher via parent report flag; pauses new session logging; core tutor still works in memory-only mode |

### Battery & bandwidth
- No network calls at runtime — fully offline.
- TTS audio cached to disk on first run; never re-downloaded.
- Low-power mode: if battery < 20%, app reduces animation frame rate and disables background tasks.

---

## 3. Weekly Parent Report — Non-Literate Parent

**Goal:** A parent who cannot read must understand their child's progress in 60 seconds.

### Design principles
- **No sentences** — only icons, bars, and numbers (1–5 stars).
- **Colour coding** consistent: 🔴 needs help, 🟡 getting there, 🟢 doing well, ⭐ mastered.
- **One clear hero message** at the top: a large arrow (📈 / ➡️ / 📉) with a star count.

### Report layout (portrait A5, printable or screen)

```
┌─────────────────────────────────────────┐
│  📋 Amina · Week 21 April 2026          │
│                                         │
│  📅 5 sessions this week                │
│                                         │
│       📈  ★★★★☆  Getting better!        │
│                                         │
│  🔢 Counting    ████████░░  🟢          │
│  🧠 Numbers     ██████░░░░  🟡          │
│  ➕ Adding      ███████░░░  🟢          │
│  ➖ Subtracting ████░░░░░░  🟡          │
│  📖 Word probs  ██░░░░░░░░  🔴          │
│                                         │
│  ⭐ Best:    ➕ Adding                   │
│  💪 Help:    📖 Word problems            │
│                                         │
│  🔊 ████  [Scan for voice summary]      │
│                                         │
│  🔒 Stored privately on this device     │
└─────────────────────────────────────────┘
```

### Voice summary (QR code)
- A 20-second MP3 is generated locally using Piper TTS in the parent's language:
  > *"Amina azize neza iki cyumweru. Imibare yo guteranya imeze neza. Agerageze cyane ibibazo by'amagambo."*
  > ("Amina did well this week. Addition is going well. She should practise word problems more.")
- The QR code links to a local file path (no internet) or encodes the audio as a base64 data URI.
- A parent with a low-end phone can scan and listen without internet.

### Dyscalculia early warning
If a child plateaus for 3+ sessions (BKT P(known) < 0.2 despite difficulty dropping):
- A gentle flag appears on the report: ⚠️ with a teacher icon.
- Message (icon + simple words): *"Talk to the teacher"*  
- No medical language, no alarm — just a referral prompt.
- The flag is only shown to the teacher-facing summary, not the child's screen.

---

## 4. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Child uses wrong language | Language auto-detected per response; reply mirrors dominant language |
| Tablet shared — data leak | Per-learner encryption; PIN-gated access |
| No teacher support | Dyscalculia flag in parent report; teacher dashboard (future work) |
| Low literacy parents can't interpret report | Icon-first design; QR → voice summary |
| Model wrong for local numeracy culture | Curriculum uses local items (RWF, goats, mangoes, beans) |
| Power intermittency | WAL SQLite; state saved after every response, not only at session end |
| 75 MB footprint exceeded | Whisper-tiny 39MB; quantised LLM head optional; TTS cache excluded |