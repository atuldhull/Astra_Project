# ASTRA — Rehearsal & Demo-Day Guide

> The code is done. The deck is drafted. This document is about your **performance** on stage. Read it once, then rehearse three times.

---

## CORE RULE

**You are the demo.** The slides are a prop. The app is a prop. Eye contact, pacing, and confidence win the pitch — not the mAP number.

If you rehearse nothing else, rehearse **eye contact** and **landing the closing line**.

---

## REHEARSAL METHOD — 3 timed runs, ~1 hour total

### Setup for every run
- Phone: timer at **3:00** — start it when you begin, note the time remaining when you finish the closing line
- Speak at **half the volume of a conversation** — stage acoustics double it
- Stand (don't sit). You pitch standing
- Record yourself (voice memo on phone) for runs 1 and 3 so you can compare

---

### RUN 1 — Cold read *(target: just get through it)*

**Goal:** validate the deck content flows logically, find where you stumble.

1. Open [docs/pitch-deck.md](pitch-deck.md) speaker notes
2. Have the app running at http://localhost:5173 as a secondary visual
3. Deliver all 5 slides + demo back-to-back, **no pauses to correct**
4. Note where you forgot the next line, where timing felt off

**Afterward:** spend 10 minutes fixing the 2-3 roughest transitions. Don't try to memorize — **understand the beats** so you can improvise the exact words.

**Common Run-1 issues:**
- "Architecture" slide feels cold → add a gesture: sweep hand top-to-bottom as you describe each layer
- Demo sequence mismatch → stick rigidly to **Mission → Map → Alerts → Audit → Benchmark** (top-to-bottom in sidebar)
- Closing feels abrupt → practice the three-beat close: *"Sovereign."* [pause] *"Explainable."* [pause] *"Ready."* — each word gets a full second

---

### RUN 2 — With timer + critical listener *(target: 2:45 - 3:00)*

**Goal:** hit the time window, identify filler words.

1. Have a friend/parent/roommate listen
2. Give them **one specific thing to watch for**:
   - "Count how many times I say 'um', 'uh', 'basically', 'actually'"
   - OR "Tell me the one moment you zoned out"
3. Deliver the full pitch + 1 Q&A question (ask them to pick one from the [pitch-deck.md Q&A section](pitch-deck.md))

**Target metrics after Run 2:**
| Metric | Good | Red flag |
|---|---|---|
| Total length | 2:45-3:00 | < 2:30 (too rushed) or > 3:15 (will get cut off) |
| Filler words | ≤ 5 | ≥ 10 |
| Zone-out moment | at most one | multiple |

**Fixes between Run 2 and Run 3:**
- If you're running long: cut the architecture slide speaker notes by 30%
- If you're running short: add a 3-second dwell on the slider-drag during the demo
- If filler words are high: **name the next section** out loud at each transition ("Next — the numbers") — this forces a deliberate handoff

---

### RUN 3 — Stage simulation *(target: flawless)*

**Goal:** exact conditions. Build muscle memory.

1. Stand in front of a mirror (or a real audience if possible)
2. Project the slides to a second monitor if you have one — simulate the projector
3. Use a clicker / arrow key to advance slides — don't touch the laptop mid-pitch
4. Deliver pitch + **answer 3 Q&A questions** pulled at random from the deck
5. Record yourself (phone camera, landscape) — watch it back for body language

**What to check in the video:**
- Are you looking AT the screen or PAST the screen at the judges?
- Hands: what are they doing? (gesturing = good, in pockets = bad, death-grip on laptop = very bad)
- Facial expression: are you tense or present?
- Breathing: any obvious gasps between sentences?

**If Run 3 feels good, stop rehearsing.** Over-practicing makes delivery robotic.

---

## COMMON PITFALLS — catch them in rehearsal

### 🚨 You're reading slide text aloud
**Symptom:** judges' eyes drift to the screen, not you.
**Fix:** slides are captions, not scripts. Look at the audience while the slide does its job in the background.

### 🚨 You rush through the demo
**Symptom:** demo finishes in 60 seconds instead of 90; slider drag happens in a blink.
**Fix:** dwell on the wow moments. The judges need 2+ seconds to register what they're seeing. Count to 3 silently on each big UI transition.

### 🚨 You caveat too much
**Symptom:** "well, so basically, um, this is just a student project, it's not really production-ready..."
**Fix:** self-deprecation burns credibility. Own the work. If a limitation exists, state it neutrally *once*, pivot to roadmap.

Good: *"0.515 mAP on a 6GB laptop in 2 hours is where we are. Cloud hardware doubles this."*
Bad: *"I mean, 0.515 is kinda low but, you know, we didn't really have time..."*

### 🚨 You answer Q&A before the judge finishes asking
**Symptom:** cutting off judges mid-sentence.
**Fix:** force a 1-second pause after they stop talking. Let it land. Then answer.

### 🚨 You don't know an answer
**Symptom:** panic, hand-wave, make something up.
**Fix:** the perfect response is:
> *"Honest answer: I haven't tested that. Here's what I'd test first to find out: [concrete method]. My current hypothesis is [reasoned guess]."*
>
> That signals scientific rigor. Never bullshit — judges catch it instantly.

### 🚨 You underestimate the close
**Symptom:** pitch tails off into nothing.
**Fix:** the last 3 words are what they remember. The [pitch-deck tagline](pitch-deck.md) is your mic-drop. Don't say anything after "Ready." until the judges speak.

---

## DEMO-DAY MORNING — the checklist that matters

### The night before
- [ ] Slides exported to PDF → on laptop AND USB stick
- [ ] Demo video recorded → in `docs/astra-demo.mp4` AND USB stick AND Google Drive
- [ ] Pitch text on phone (in case laptop dies)
- [ ] Power brick packed
- [ ] HDMI-to-USB-C adapter packed (many projectors are HDMI, some laptops are USB-C only)
- [ ] Water bottle ready
- [ ] Alarm set for 2 hours before pitch

### Morning of (2 hours before)
- [ ] Eat. A real meal. Blood sugar affects your voice and thinking
- [ ] 10-minute walk outside. Physical activity calms nerves better than caffeine
- [ ] Laptop check: fully charged + plugged in
- [ ] Run the full stack **once** — verify nothing broke overnight:
  - `docker ps` → postgres + redis healthy
  - `/health` → model_loaded: true
  - http://localhost:5173 → loads, upload a test image, see boxes
- [ ] Demo video plays end-to-end (open it, scrub through)
- [ ] Close every app you don't need — Docker Desktop can stay, nothing else
- [ ] Browser: one tab on http://localhost:5173 (Mission page), second tab on /benchmark

### 15 minutes before pitch
- [ ] Bathroom
- [ ] Water sip
- [ ] Turn on Focus Assist / DND
- [ ] Deep breath × 3 (inhale 4s, hold 4s, exhale 6s — this calms the nervous system)
- [ ] Glance at the pitch tagline one more time — **don't rehearse the full pitch here**, you'll overthink

---

## STAGE-SETUP DISASTER RECOVERY

### "The projector won't display my laptop"
**First:** don't panic. 30 seconds of setup friction is normal, judges expect it.

**Try in order:**
1. Unplug + replug the HDMI/display cable
2. Windows key + P → "Duplicate" (not "Extend")
3. If using USB-C → HDMI: try a different adapter if you have one
4. If still dead: **"I'll run from my laptop screen — can everyone see this from where they sit?"** → turn the laptop toward judges. They'll wave you on.

### "Wifi's gone"
Your demo runs on **localhost**. Wifi doesn't matter for the live demo at all. Say: *"For reliability I'm running everything locally — no external dependencies. Here's the system."*

### "Docker Desktop isn't running"
Open it. Wait 30 seconds. Containers auto-start. If they don't: `docker compose up -d` in a terminal. If that fails: **play the video**, skip the live part.

### "The model loaded but inference takes 20 seconds"
You forgot to warm it. Quietly upload an image 10 seconds before you hit your Mission-page moment. Judges won't notice the warmup if you talk during it.

### "The backend crashed mid-demo"
Acknowledge calmly: *"Well — hackathon gremlins. Let me show you the recorded version — same system, same model."* → play `docs/astra-demo.mp4`. Do not try to fix the backend live on stage.

### "A judge interrupts mid-pitch"
Pause, listen, answer briefly, ask: *"Shall I continue the demo?"* — most judges will say yes. If they say no, you're in Q&A — adapt.

---

## Q&A TACTICS

### The three judge archetypes

**The Skeptic** — attacks your mAP / accuracy / "this is just YOLO"
→ Own the number, cite the hardware constraint, pivot to the architecture story.

**The Technologist** — asks deep questions (why YOLO, why nano, why this dataset)
→ Engage. They're rooting for you. Show your reasoning, not just answers.

**The Pragmatist** — "how would you deploy this?" / "what's the cost?"
→ Time to talk concrete numbers. $400 Jetson, zero cloud bill, air-gapped ops. [Pitch deck](pitch-deck.md) Q&A section has the script.

### The universal Q&A opener
> *"Great question."* [0.5s pause]
>
> Buys 2 seconds of thinking time without sounding fake.

### The universal Q&A close
End every answer with a forward-looking hook:
> *"...which is why the v1.2 roadmap includes [thing]."*
>
> Shows you've already thought past this.

---

## MENTAL PREP — don't skip this

### 10-minute wind-down the night before
Not rehearsal. Just:
- Laptop away
- Phone away
- Lights low
- Lie down, close eyes, imagine delivering the pitch from start to finish — just visualize it working
- Imagine answering one hostile question — imagine yourself composed

Studies on performance psychology show visualization alone improves public-speaking quality by ~20%. Cheap investment.

### The one thought to hold on stage
> **"I know this better than anyone in this room. I built it."**

It's true. You trained the model, wrote the backend, wrote the frontend, understand every line. That's a real advantage over any polished corporate pitch — authenticity beats polish in front of technical judges.

---

## POST-PITCH

### Right after you step off
- Drink water
- Don't check reactions immediately — you'll read into neutral faces
- Sit down, breathe
- If anyone asks follow-ups off-stage, answer briefly and take their contact

### What to do with the emotional crash
Post-adrenaline dip is real. You'll feel weirdly flat 15 minutes after. Plan for it:
- Eat something substantial
- Don't doomscroll to distract
- Talk to one supportive person (friend, family) for 10 min

### Independent of outcome
You built a full-stack AI defence platform in a week. That's a real artifact you can show employers, put in a portfolio, ship open-source, extend to a real product. The pitch is just one moment — the build is the win.

---

## FINAL ONE-LINER (in case you forget everything else)

> **"Sovereign, explainable, edge-deployable AI for aerial target recognition —**
> **trained on a student laptop in under 2 hours,**
> **ready for Jetson tomorrow."**

Say it. Mean it. Land it.

🫡
