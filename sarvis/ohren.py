"""Ohren: Sprache zu Text, lokal auf der Grafikkarte."""
import os
import sys
import time
from pathlib import Path


def _cuda_dlls_finden() -> None:
    """CUDA-Bibliotheken aus den pip-Paketen auffindbar machen.

    Ohne das laedt das Modell zwar, aber die erste echte Rechnung stirbt mit
    "cublas64_12.dll is not found". Muss vor dem Import von faster_whisper
    passieren.
    """
    if sys.platform != "win32":
        return
    import sysconfig

    kandidaten = {
        sysconfig.get_paths().get("purelib"),
        sysconfig.get_paths().get("platlib"),
    }
    for pfad in filter(None, kandidaten):
        nvidia = Path(pfad) / "nvidia"
        if not nvidia.is_dir():
            continue
        for ordner in nvidia.glob("*/bin"):
            try:
                os.add_dll_directory(str(ordner))
            except OSError:
                pass
            # CTranslate2 laedt cuBLAS/cuDNN nicht ueber die DLL-Verzeichnisse,
            # sondern klassisch ueber den PATH. Beides setzen.
            pfad = os.environ.get("PATH", "")
            if str(ordner) not in pfad:
                os.environ["PATH"] = f"{ordner}{os.pathsep}{pfad}"


_cuda_dlls_finden()

import numpy as np  # noqa: E402
from faster_whisper import WhisperModel  # noqa: E402

from . import config  # noqa: E402


class Ohren:
    def __init__(self):
        print(f"  Whisper laedt ({config.WHISPER_MODELL} auf {config.WHISPER_GERAET}) ...")
        t = time.perf_counter()
        try:
            self.modell = WhisperModel(
                config.WHISPER_MODELL,
                device=config.WHISPER_GERAET,
                compute_type=config.WHISPER_GENAUIGKEIT,
            )
            self.geraet = config.WHISPER_GERAET
        except Exception as e:
            print(f"  GPU ging nicht ({e}) - falle auf die CPU zurueck.")
            self.modell = WhisperModel(
                config.WHISPER_MODELL, device="cpu", compute_type="int8"
            )
            self.geraet = "cpu"
        print(f"  Whisper bereit nach {time.perf_counter() - t:.1f}s ({self.geraet})")

    def hoeren(self, proben: np.ndarray, hinweise: str | None = None) -> str:
        """hinweise: Woerter, die Whisper erwarten soll.

        Ohne das schreibt es den Namen als "Salvis", "Salas" oder
        "Service" -- gemessen. Mit Hinweis trifft es ihn deutlich
        oefter, und das ist der saubere Weg: Man senkt nicht die
        Erkennungsschwelle, man verbessert die Erkennung.
        """
        stuecke, _ = self.modell.transcribe(
            proben,
            language=config.SPRACHE,
            beam_size=1,          # Tempo vor letztem Prozent Genauigkeit
            vad_filter=True,      # Stille am Rand wegschneiden
            condition_on_previous_text=False,
            hotwords=hinweise or config.HOTWORDS or None,
        )
        return " ".join(s.text.strip() for s in stuecke).strip()

    def aus_datei(self, pfad, hinweise: str | None = None) -> str:
        """Eine Tondatei verschriften -- Sprachnachrichten von anderen.

        faster-whisper dekodiert selbst (ueber PyAV), es braucht also
        weder ffmpeg im Bild noch einen Umweg ueber ein numpy-Array.
        Damit versteht es auch das OGG/Opus, in dem Telegram
        Sprachnachrichten verschickt.

        Anders als hoeren() OHNE vad_filter: Der schneidet Stille am Rand
        weg, was bei einem kurzen Zuruf ans Mikrofon richtig ist. Eine
        fremde Sprachnachricht faengt aber oft mit einer Pause an, und
        wer erst nach zwei Sekunden loslegt, verliert damit sein erstes
        Wort.
        """
        stuecke, _ = self.modell.transcribe(
            str(pfad),
            language=config.SPRACHE,
            beam_size=1,
            vad_filter=False,
            condition_on_previous_text=False,
            hotwords=hinweise or config.HOTWORDS or None,
        )
        return " ".join(s.text.strip() for s in stuecke).strip()

    def aufwaermen(self) -> None:
        """Erster Durchlauf ist immer langsam. Den zahlen wir beim Start.

        Wichtig: ohne Stille-Filter und mit echtem Signal. Mit Stille davor
        verwirft der Filter alles, der Encoder laeuft nie -- das Aufwaermen
        meldet dann in Sekundenbruchteilen Erfolg und der erste richtige
        Zuruf zahlt trotzdem die vollen acht Sekunden CUDA-Aufbau.
        """
        rauschen = (
            np.random.default_rng(0).standard_normal(config.ABTASTRATE * 2) * 0.05
        ).astype("float32")
        stuecke, _ = self.modell.transcribe(
            rauschen,
            language=config.SPRACHE,
            beam_size=1,
            vad_filter=False,
            condition_on_previous_text=False,
        )
        list(stuecke)  # der Generator rechnet erst beim Auslesen
