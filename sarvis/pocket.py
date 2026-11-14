"""Pocket TTS (Kyutai) -- Sarvis' Stimme seit 14.11.2026.

Warum diese Stimme: In der Hoerprobe vom 14.11. (stimmproben/2026-11-14)
hob das grosse deutsche Modell (german_24l, Stimme "juergen") das
Frageende in 6 von 12 Laeufen, Thorsten/Piper nur in 3 von 12, und die
Rueckerkennung fand keinen einzigen Fehler. Sascha: "um einiges besser".

Was man wissen muss:
- Laeuft NUR auf der CPU. Die Grafikkarte bleibt fuer Whisper frei.
- Rechnet knapp schneller als Echtzeit (gemessen RTF 0,86 bei 4 Threads,
  0,90 bei einem; mehr als 6 Threads macht es langsamer). Deshalb wird
  GESTREAMT: Der erste Ton geht nach ~0,25 s raus, der Rest laeuft hinter
  der Wiedergabe her. Einen ganzen Satz vorher fertig zu rechnen, kostete
  bei einem langen Satz fuenf Sekunden Stille.
- Liest KEINE Ziffern ("8 bis 12 Grad" wurde Kauderwelsch). Was hier
  ankommt, ist durch aussprache.alles_ausschreiben gegangen.
- Nicht threadsicher (sagt Kyutai selbst) -- daher das Schloss.
- Das Modell kommt beim ersten Start von Hugging Face (HF_HOME, rund
  0,5 GB) und liegt danach im Cache.

Faellt hier irgendetwas um, spricht Mund mit Piper weiter.
"""
import logging
import threading
import time

import numpy as np

from . import config

# Stueckgroessen sind Rechnung, nicht Geschmack. Pocket braucht fuer 1 s
# Ton ~0,86 s (RTF). Stueck k+1 ist fertig nach (a1 + ... + b)*0,86, wird
# gebraucht, wenn alles davor verklungen ist. Der Vorsprung fuer das
# zweite Stueck ist also a1 - 0,86*b -- ein grosses zweites Stueck hinter
# einem kleinen ersten heisst Luecke mitten im Satz (erste Fassung
# 0,4/1,0 s: -0,46 s, haette gestottert). Mit 0,48/0,24 s: +0,27 s
# Vorsprung gegen Netzschwankungen, und er waechst mit jedem Stueck.
# Pocket liefert intern ~80-ms-Happen.
ERSTES_STUECK_S = 0.48
STUECK_S = 0.24


class Pocket:
    def __init__(self):
        t = time.perf_counter()
        # Pocket meldet jeden Satz mit RTF auf INFO -- das ist Laerm im Log.
        logging.getLogger("pocket_tts").setLevel(logging.WARNING)
        import torch
        from pocket_tts import TTSModel
        # pocket_tts setzt beim Import selbst torch.set_num_threads(1) --
        # deshalb erst danach.
        torch.set_num_threads(getattr(config, "POCKET_THREADS", 4))
        self.sprache = getattr(config, "POCKET_SPRACHE", "german_24l")
        self.name = getattr(config, "POCKET_STIMME", "juergen")
        self.modell = TTSModel.load_model(language=self.sprache)
        self.zustand = self.modell.get_state_for_audio_prompt(self.name)
        self.rate = int(self.modell.sample_rate)
        self._schloss = threading.Lock()
        self.modell.generate_audio(self.zustand, "Bereit.")
        print(f"  Pocket TTS bereit nach {time.perf_counter() - t:.1f}s "
              f"({self.sprache}, Stimme {self.name}, "
              f"{torch.get_num_threads()} Threads)")

    def strom(self, text: str):
        """Gibt float32-Bloecke heraus, sobald sie fertig sind."""
        # Bricht der Aufrufer ab (Not-Aus, Reinreden), schliesst Python
        # diesen Generator -- dann soll Pocket auch aufhoeren zu rechnen.
        halt = threading.Event()
        with self._schloss:
            try:
                yield from self._bloecke(text, halt)
            finally:
                halt.set()

    def _bloecke(self, text: str, halt: threading.Event):
        puffer, menge = [], 0
        grenze = int(self.rate * ERSTES_STUECK_S)
        for happen in self.modell.generate_audio_stream(
                self.zustand, text, stop=halt):
            a = happen.reshape(-1).float().numpy()
            puffer.append(a)
            menge += len(a)
            if menge >= grenze:
                yield np.concatenate(puffer).astype("float32")
                puffer, menge = [], 0
                grenze = int(self.rate * STUECK_S)
        if puffer:
            yield np.concatenate(puffer).astype("float32")
