"""Nur der Endpunkt und die Oberflaeche -- Sarvis selbst haengt noch nicht dran.

Damit laesst sich pruefen, was ohne ihn pruefbar ist: Passt das Layout
auf dem Geraet, faellt die Sprechtaste richtig, laesst sich die Seite auf
den Startbildschirm legen, haelt die Verbindung ueber Mobilfunk.

Auf einen Zuruf antwortet er, was wahr ist -- naemlich dass er noch nicht
verdrahtet ist. Eine erfundene Antwort waere hier das Schlimmste: Sie
sieht aus wie ein Erfolg und ist keiner.
"""
import asyncio, logging, sys
sys.path.insert(0, "/srv/storage/projects/sarvis")
from sarvis.netz import server
from sarvis.netz.traeger import NetzTraeger

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

async def haupt():
    t = NetzTraeger(asyncio.get_running_loop())

    async def zuruf_an(text, geraet):
        t.senden({"art": "untertitel", "wer": "du", "text": text, "strom": ""})
        await asyncio.sleep(0.6)
        t.senden({"art": "zustand", "zustand": "denkt", "strom": ""})
        await asyncio.sleep(1.2)
        t.senden({"art": "zustand", "zustand": "spricht", "strom": ""})
        t.senden({"art": "untertitel", "wer": "sarvis", "strom": "",
                  "text": "Ich habe dich gehört — aber mein Kopf hängt noch "
                          "nicht dran. Die Verbindung steht, der Rest kommt."})
        await asyncio.sleep(3.0)
        t.senden({"art": "zustand", "zustand": "ruhig", "strom": ""})
        t.senden({"art": "nachhoeren", "sekunden": 18.0})

    async def sprache_an(proben, geraet):
        sek = len(proben) / 16000
        t.senden({"art": "untertitel", "wer": "du", "strom": "",
                  "text": f"({sek:.1f} Sekunden aufgenommen und angekommen)"})
        await asyncio.sleep(0.8)
        t.senden({"art": "zustand", "zustand": "spricht", "strom": ""})
        t.senden({"art": "untertitel", "wer": "sarvis", "strom": "",
                  "text": "Deine Stimme ist hier angekommen. Verstehen kann "
                          "ich sie noch nicht — Whisper fehlt noch."})
        t.senden({"art": "werkzeug", "name": "Websuche", "aktiv": True, "strom": ""})
        await asyncio.sleep(3.5)
        t.senden({"art": "zustand", "zustand": "ruhig", "strom": ""})

    e = server.Endpunkt(zuruf_an=zuruf_an, sprache_an=sprache_an)
    await server.starten(e, t, hafen=8900)
    print("Vorschau läuft auf 127.0.0.1:8900", flush=True)
    while True:
        await asyncio.sleep(3600)

asyncio.run(haupt())
