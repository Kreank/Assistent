"""Realistische Kette: Piper spricht deutschen Text, Whisper hoert ihn,
Claude antwortet. Misst jede Stufe einzeln -- ohne Mikrofon."""
import asyncio, time, numpy as np
from sarvis.ohren import Ohren
from sarvis.mund import Mund
from sarvis.hirn import Hirn
from sarvis import config

def umtasten(x, von, nach):
    """Neuabtastung ueber die Fourier-Transformierte.

    Lineare Interpolation waere hier falsch: 22050 auf 16000 herunter ohne
    Tiefpass erzeugt Aliasing, und der verhoerte sich in den Messungen als
    schlechtere Erkennung ("Zahnarzttermin" wurde zu "Senatstermin"). Das
    ist ein Fehler des Messaufbaus, nicht der Kette -- am echten Mikrofon
    wird direkt mit 16000 aufgenommen, da wird nie umgetastet.
    """
    n = int(round(len(x) * nach / von))
    spektrum = np.fft.rfft(x)
    behalten = min(len(spektrum), n // 2 + 1)
    neu = np.zeros(n // 2 + 1, dtype=complex)
    neu[:behalten] = spektrum[:behalten]
    return (np.fft.irfft(neu, n) * (n / len(x))).astype("float32")

SAETZE = [
    "Trag mir bitte am Donnerstag um fuenfzehn Uhr einen Zahnarzttermin ein.",
    "Wie wird das Wetter morgen in Hamburg?",
    "Schick der Anna eine Nachricht, dass ich eine halbe Stunde spaeter komme.",
]

print("\n  Laden ...")
t = time.perf_counter(); mund = Mund(); print(f"  Piper   {time.perf_counter()-t:.1f}s")
t = time.perf_counter(); ohren = Ohren(); print(f"  Whisper {time.perf_counter()-t:.1f}s (aus dem Cache)")
ohren.aufwaermen(); mund.aufwaermen()

async def lauf():
    hirn = Hirn()
    t = time.perf_counter(); await hirn.start()
    print(f"  Claude  {time.perf_counter()-t:.1f}s\n")
    print(f"  {'Audio':>6} {'Whisper':>8} {'1.Wort':>8} {'1.Ton':>8}   Text")
    print("  " + "-"*72)
    for satz in SAETZE:
        proben, rate = mund.sprechen(satz)
        audio = umtasten(proben, rate, config.ABTASTRATE)
        dauer = len(audio)/config.ABTASTRATE

        t0 = time.perf_counter()
        gehoert = ohren.hoeren(audio)
        t_stt = time.perf_counter()-t0

        erst = None; teile=[]
        async for s in hirn.fragen(gehoert):
            if erst is None: erst = time.perf_counter()-t0
            teile.append(s)
        antwort = "".join(teile).strip()

        # erster Ton = erstes Wort + Zeit, den ersten Satz zu synthetisieren
        t1 = time.perf_counter()
        mund.sprechen(antwort.split(".")[0] + ".")
        ton = erst + (time.perf_counter()-t1)

        print(f"  {dauer:5.1f}s {t_stt:7.2f}s {erst:7.2f}s {ton:7.2f}s   >> {gehoert}")
        print(f"  {'':>32}   << {antwort}")
    await hirn.stopp()

asyncio.run(lauf())
print()
