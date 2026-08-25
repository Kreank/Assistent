# -*- coding: utf-8 -*-
"""Erzeugt Hoerproben aller Stimmen-Kandidaten mit demselben Satz.
Ergebnis liegt in stimmen/proben/ -- einfach der Reihe nach anhoeren."""
import sys, wave
import numpy as np
from pathlib import Path
from piper import PiperVoice, SynthesisConfig
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SATZ = ("Guten Morgen. Sarvis ist bereit. "
        "Dein nächster Termin ist heute um vierzehn Uhr dreißig, "
        "und draußen sind achtzehn Grad.")

# (Datei, Name, Sprecher-ID, Tempo)  -- Tempo < 1.0 = schneller
PROBEN = [
    ("de_DE-thorsten-medium",           "1-thorsten-medium-normal",   None, 1.00),
    ("de_DE-thorsten-medium",           "2-thorsten-medium-flott",    None, 0.88),
    ("de_DE-thorsten-high",             "3-thorsten-high-flott",      None, 0.92),
    ("de_DE-thorsten_emotional-medium", "4-emotional-amused",         0,    0.92),
    ("de_DE-thorsten_emotional-medium", "5-emotional-surprised",      6,    0.92),
    ("de_DE-thorsten_emotional-medium", "6-emotional-neutral",        4,    0.92),
    ("de_DE-kerstin-low",               "7-kerstin-weiblich",         None, 0.95),
]

ziel = Path("stimmen/proben"); ziel.mkdir(parents=True, exist_ok=True)
geladen = {}
for datei, name, sprecher, tempo in PROBEN:
    pfad = Path("stimmen") / f"{datei}.onnx"
    if not pfad.exists():
        print(f"  fehlt: {pfad}"); continue
    if datei not in geladen:
        geladen[datei] = PiperVoice.load(pfad)
    stimme = geladen[datei]
    cfg = SynthesisConfig(length_scale=tempo)
    if sprecher is not None:
        cfg.speaker_id = sprecher
    teile, rate = [], 22050
    for br in stimme.synthesize(SATZ, syn_config=cfg):
        teile.append(br.audio_float_array); rate = br.sample_rate
    audio = np.concatenate(teile)
    pcm = (np.clip(audio, -1, 1) * 32767).astype("<i2")
    aus = ziel / f"{name}.wav"
    with wave.open(str(aus), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
        w.writeframes(pcm.tobytes())
    print(f"  {name:28s} {len(audio)/rate:4.1f}s  {aus}")
print(f"\n  Alle Proben in: {ziel.resolve()}")
