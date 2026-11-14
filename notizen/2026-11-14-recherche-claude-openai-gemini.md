# Recherche: Claude, OpenAI (ChatGPT/Codex/dots), Gemini — was Sarvis fehlt (14.11.2026)

Drei Subagenten, je ein Anbieter, Primärquellen + Abgleich mit dem Sarvis-Code. Baut auf
2026-11-10-recherche-zielbild.md auf. Vollständige Einzelberichte: siehe Abschnitte unten (gekürzt).

## Korrekturen am Selbstbild
- Geplante Aufgaben verfallen NICHT mehr nach 7 Tagen: CronCreate ist seit 13.11. gesperrt
  (config.PLANUNG_GESPERRT), Sarvis' eigener Wecker (werkzeuge/zeit.py, timer.json) wiederholt dauerhaft.
- Auch Google beendet Sprecherrunden per Stille-VAD (500–800 ms) — der Vorsprung liegt im Unterbrechen,
  im "nicht gemeint"-Filter und im nativen Audiomodell, nicht in Zauberei beim Satzende.
- OpenAI "dots" (dauerhaft laufender Agent mit Cloud-Rechner, Telefon, nur-lesende Erkundung,
  Selbst-Wiedervorlage) ist das nächste Vorbild für Sarvis. ChatGPT agent eingestellt, Pulse → Scheduled tasks.

## Wo alle drei übereinstimmen (Kandidaten, priorisiert)
1. Satzende-Modell statt fester Stille: Pipecat Smart Turn v3 (BSD-2, CPU/ONNX, 12–60 ms, Deutsch dabei,
   Genauigkeit DE unbelegt → an den 12 abgeschnittenen Sätzen messen). Erwartet 0,3–0,7 s schneller.
2. Unterbrechen wie Realtime/Live: Ton sofort stoppen, Hirn erfährt "abgebrochen nach: <zuletzt gehörter Satz>",
   offene Werkzeugaufrufe verwerfen; "nicht für mich"-Zeichen im Auto (Proactive-Audio-Muster).
3. Lokale Stimme mit Satzmelodie: Kyutai Pocket TTS (CPU, ~200 ms, Lizenz Gewichte prüfen),
   Qwen3-TTS 0.6B/1.7B (Apache-2.0, per Anweisung steuerbar, GPU 4–6 GB → Konflikt Whisper).
   Sofortlösung: Tonhöhe am Fragenende anheben (Hörprobe 13.11. liegt vor).
4. Proaktive Schicht: Ereignis-Auslöser (Mail von X, x Min. vor Termin) als billiger Abfrage-Lauf ohne Modell,
   Bedingung "nur melden, wenn wichtig", Werkzeug wiedervorlage(wann, warum), Obergrenzen + Ruhezeiten.
5. Arbeiter: git worktree statt checkout -b (mehrere Aufträge je Projekt), bubblewrap-Sandbox,
   Gesundheitscheck + einmal neu versuchen bei Anmeldefehler, CLAUDE.md/AGENTS.md des Projekts laden,
   Plan zur Freigabe vor großen Aufträgen, Rücksprungpunkt vor Dateiänderungen.
6. Gedächtnis-Nachlauf (Codex-Muster): nach Leerlauf/nachts Fäden auswerten → nur "beobachtet",
   Geheimnisse schwärzen, zusammenführen, versionieren; Verlaufssuche SQLite FTS5 statt LIKE.
7. Tempo messen statt raten (Claude-Bericht): cache_read/cache_creation + Zeit bis erstes Textstück je Runde
   loggen; Opus 5 vs 5.5, Fast Mode (kostet Zusatzguthaben → Saschas Entscheidung); Sammelwerkzeuge
   (z. B. Tagesüberblick) statt 3–4 Werkzeugrunden; SDK-Hooks: große Ausgaben kürzen, Fremdtext als Daten markieren.
8. Freigabe-Prüfer (Haiku) vor Rückfragen + Regeln in Klartext in der App (OpenAI Auto-review / dots Controls).

## Bewusst nicht
- Tool Search / Skills (kosten je Nutzung eine Modellrunde — genau das gemessene Problem).
- Lokales Speech-to-Speech: für Deutsch auf 8 GB kein offenes Modell (PersonaPlex nur Englisch).
- Cloud-Stimme / Realtime-API / Gemini Live als Dauerlösung (Vorgabe: Stimme lokal).
- Live-Kamera (Claude ist kein Videomodell).

## Wichtige Quellen
- Claude: code.claude.com/docs (memory, hooks, subagents, fast-mode, permission-modes),
  platform.claude.com context-editing, anthropic.com/engineering/advanced-tool-use
- OpenAI: learn.chatgpt.com/docs (memories, automations, dots, sandboxing, auto-review, worktrees, agents-md),
  developers.openai.com/api/docs/guides/realtime-vad + realtime-conversations
- Gemini: aistudio.google.com/docs/live-api/capabilities, aistudio.google.com/docs/deep-research,
  support.google.com/gemini 16316416 + 17094710 (Scheduled Actions, Gmail-Monitore),
  geminicli.com/docs/cli/checkpointing, jules.google/docs
- Lokal: github.com/pipecat-ai/smart-turn, github.com/kyutai-labs/pocket-tts, github.com/QwenLM/Qwen3-TTS,
  arxiv.org/abs/2602.11298 (Voxtral Realtime)
