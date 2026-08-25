# -*- coding: utf-8 -*-
"""Zeigt live, was der Weckwort-Horcher hört und entscheidet.

    .venv\\Scripts\\python.exe weckwort_test.py

Läuft parallel zu einem laufenden Sarvis. Sag "Hey Sarvis, wie spät ist
es" und schau, an welcher Stelle es hakt:

  kein Balken       -> das Mikrofon liefert nichts (falsches Gerät?)
  Balken, kein Text -> Whisper bekommt zu wenig oder VAD schneidet falsch
  Text, kein WECKT  -> der Name wurde verhört; die Zeile zeigt womit
"""
import sys
import time

import numpy as np
import sounddevice as sd

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from openwakeword.vad import VAD          # noqa: E402
from sarvis import config                 # noqa: E402
from sarvis.ohren import Ohren            # noqa: E402
from sarvis.weckwort import BLOCK, RATE, erkennen, _klingt_wie_name  # noqa: E402


def main() -> int:
    print("\n  Mikrofone:")
    try:
        ein = sd.query_devices(kind="input")
        print(f"    Standard-Eingang: {ein['name']}  "
              f"({ein['max_input_channels']} Kanäle, {int(ein['default_samplerate'])} Hz)")
    except Exception as e:
        print(f"    FEHLER: {e}")
        return 1

    print("\n  Whisper lädt ...")
    ohren = Ohren()
    ohren.aufwaermen()
    vad = VAD()

    print(f"\n  Einstellungen: Name={config.NAME!r}  "
          f"Ähnlichkeit≥{config.WECKWORT_AEHNLICHKEIT}  "
          f"VAD≥{config.VAD_SCHWELLE}  "
          f"Stille={config.WECKWORT_STILLE_SEK}s")
    print("\n" + "=" * 66)
    print("  Sprich jetzt.  Strg+C beendet.")
    print("=" * 66 + "\n")

    puffer, redet, stille, zuletzt = [], False, 0.0, 0.0
    try:
        with sd.InputStream(samplerate=RATE, channels=1, dtype="float32",
                            blocksize=BLOCK) as strom:
            while True:
                block, ueberlauf = strom.read(BLOCK)
                b = block[:, 0].copy()
                pcm = (np.clip(b, -1.0, 1.0) * 32767).astype(np.int16)
                p = float(vad.predict(pcm, frame_size=BLOCK))
                pegel = float(np.sqrt(np.mean(b ** 2)))

                jetzt = time.perf_counter()
                if jetzt - zuletzt > 0.25:
                    zuletzt = jetzt
                    balken = "#" * int(min(1.0, pegel * 12) * 24)
                    print(f"\r  Pegel |{balken:<24}| VAD {p:4.2f} "
                          f"{'REDET' if redet else '     '}"
                          f"  (Pegelschwelle {config.WECKWORT_MIN_PEGEL})", end="")

                spricht = (p >= config.VAD_SCHWELLE
                           and pegel >= config.WECKWORT_MIN_PEGEL)
                if spricht:
                    redet = True
                    stille = 0.0
                    puffer.append(b)
                    continue

                if not redet:
                    continue

                puffer.append(b)
                stille += BLOCK / RATE
                if stille < config.WECKWORT_STILLE_SEK:
                    continue

                audio = np.concatenate(puffer)
                dauer = len(audio) / RATE
                puffer, redet, stille = [], False, 0.0
                vad.reset_states()
                if dauer < config.WECKWORT_MIN_SEK:
                    print(f"\r  (nur {dauer:.2f}s — zu kurz){' ' * 30}")
                    continue

                t = time.perf_counter()
                text = ohren.hoeren(
                    audio, hinweise=f"Hey {config.NAME.capitalize()}"
                )
                gebraucht = time.perf_counter() - t
                print(f"\r{' ' * 60}\r", end="")
                print(f"  {dauer:.1f}s Audio, Whisper {gebraucht:.2f}s")
                print(f"    verstanden: {text!r}")

                if not text:
                    print("    -> nichts erkannt\n")
                    continue

                worte = text.lower().split()
                if worte:
                    from difflib import SequenceMatcher
                    w = "".join(c for c in worte[0] if c.isalnum())
                    print(f"    erstes Wort {w!r} vs {config.NAME!r}: "
                          f"{SequenceMatcher(None, w, config.NAME).ratio():.2f}"
                          f"  (Name? {_klingt_wie_name(w)})")
                    if len(worte) > 1:
                        w2 = "".join(c for c in worte[1] if c.isalnum())
                        print(f"    zweites Wort {w2!r} vs {config.NAME!r}: "
                              f"{SequenceMatcher(None, w2, config.NAME).ratio():.2f}"
                              f"  (Name? {_klingt_wie_name(w2)})")

                zuruf = erkennen(text)
                if zuruf is None:
                    print("    -> WECKT NICHT\n")
                else:
                    print(f"    -> WECKT, Zuruf: {zuruf!r}\n")
    except KeyboardInterrupt:
        print("\n\n  Beendet.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
