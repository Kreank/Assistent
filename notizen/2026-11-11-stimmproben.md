# Stimmproben 11.11.2026 — Betonung

Hörproben, Messwerte und Empfehlung liegen in `/srv/data/sarvis/stimmproben/2026-11-11/`
(`index.html`, `vergleich.md`, eine MP3 je Kandidat, `alle-hintereinander.mp3`, `skripte/`).
In der Ablage: „Stimmproben 11.11. – Vergleich“ (Blatt) und „… – alle zum Anhören“ (MP3).

Kurz:
- Belegt: Thorsten/Piper hebt die Stimme am Ende einer Frage nur zufällig (3 von 12 Durchgängen mit
  der heutigen Einstellung, 1 von 12 mit der Werkseinstellung). Betonung/Rhythmus zu drehen ändert das nicht.
  Keine andere Piper-Stimme ist besser; mls-medium und ramona-low sind fehlerhaft.
- Favorit: ElevenLabs „Michael Danisch“ (87AwpS6yC86wa2WglbsK, deutsch), Modell eleven_flash_v2_5:
  erster Ton 0,28–0,43 s, Frage steigt, ≈0,2 Credits/Zeichen (≈32k/Monat bei Ø-Nutzung; Starter-Limit 35.745).
  Zweitens dieselbe Stimme mit eleven_multilingual_v2 (0,5–0,9 s, ≈0,4 Credits/Zeichen, sprengt Starter).
- Umstellen wäre nur config.py (STIMME_DIENST, ELEVENLABS_STIMME, ELEVENLABS_MODELL) + Neustart; Piper bleibt Rückfall.
  Veraltet: Kommentar „nur premade-Stimmen“ in eleven.py/config.py — mit Starter-Tarif geht die Bibliotheksstimme.
- Lokal kein Kandidat: XTTS-v2 (RTF 2), Chatterbox (RTF 3,8), F5 German (RTF 9,7) auf CPU zu langsam, GPU nicht frei.
- Nicht getestet (Hugging Face zugangsbeschränkt): NeuTTS Nano German (CPU-tauglich laut Hersteller), Kartoffelbox.
