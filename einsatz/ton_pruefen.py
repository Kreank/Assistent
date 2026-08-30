#!/usr/bin/env python3
"""Holt Sarvis' gesprochene Antwort und schreibt sie als WAV.

Damit laesst sich die Frage "liegt es am Server oder an meiner App?"
in einem Schritt beantworten: Spielt die entstandene Datei ab, sind die
Daten in Ordnung, und der Fehler liegt in der App.

    python einsatz/ton_pruefen.py <geraeteschluessel> ["Was er sagen soll"]

Braucht nur aiohttp. Der WAV-Kopf wird von Hand gebaut -- 44 Byte, und
so sieht man gleich, was die App auch tun muesste, wenn sie einen
Decoder benutzt statt die Samples direkt zu schreiben.
"""
import asyncio
import base64
import json
import struct
import sys
import time

import aiohttp

DRAHT = "ws://127.0.0.1:8900/draht"


def wav_kopf(anzahl_bytes: int, rate: int) -> bytes:
    """Der 44-Byte-Kopf fuer mono, 16 Bit."""
    return (b"RIFF" + struct.pack("<I", 36 + anzahl_bytes) + b"WAVEfmt "
            + struct.pack("<IHHIIHH", 16, 1, 1, rate, rate * 2, 2, 16)
            + b"data" + struct.pack("<I", anzahl_bytes))


async def haupt(schluessel: str, frage: str) -> int:
    stuecke, rate, gesagt = [], 22050, ""
    async with aiohttp.ClientSession() as s:
        ws = await s.ws_connect(DRAHT)
        await ws.send_str(json.dumps({"schluessel": schluessel,
                                      "kann_browser": False}))
        erste = await asyncio.wait_for(ws.receive(), 15)
        m = json.loads(erste.data) if erste.type is aiohttp.WSMsgType.TEXT else {}
        if m.get("art") != "willkommen":
            print("Der Schlüssel gilt nicht.")
            return 1
        print(f"angemeldet als '{m.get('geraet')}'\n  Du: {frage}")
        await ws.send_str(json.dumps({"art": "zuruf", "text": frage}))

        ende = time.monotonic() + 90
        while time.monotonic() < ende:
            try:
                n = await asyncio.wait_for(ws.receive(), 5)
            except asyncio.TimeoutError:
                continue
            if n.type is not aiohttp.WSMsgType.TEXT:
                break
            d = json.loads(n.data)
            if d.get("art") == "ton":
                roh = base64.b64decode(d.get("daten") or "")
                rate = int(d.get("rate") or rate)
                stuecke.append(roh)
                print(f"    Ton {len(stuecke)}: {len(roh)//1024} KB, "
                      f"{rate} Hz, Runde {d.get('runde')}, "
                      f"{len(roh)/2/rate:.2f}s")
            elif d.get("art") == "untertitel" and d.get("wer") == "sarvis":
                gesagt = d.get("text", "")
            elif (d.get("art") == "zustand"
                  and d.get("zustand") == "ruhig" and gesagt):
                break
        await ws.close()

    if not stuecke:
        print("\nKEIN TON angekommen. Dann liegt es NICHT an der App.")
        return 1
    daten = b"".join(stuecke)
    ziel = "sarvis-antwort.wav"
    with open(ziel, "wb") as f:
        f.write(wav_kopf(len(daten), rate))
        f.write(daten)
    print(f"\n  Sarvis: {gesagt}")
    print(f"  -> {ziel} ({len(daten)//1024} KB, {len(daten)/2/rate:.1f}s)")
    print("\nSpielt die Datei ab? Dann sind die Daten in Ordnung,")
    print("und der Fehler liegt in der App. Siehe TON-IN-DER-APP.md.")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        raise SystemExit(2)
    raise SystemExit(asyncio.run(haupt(
        sys.argv[1],
        sys.argv[2] if len(sys.argv) > 2
        else "Zähl bitte langsam von eins bis fünf.")))
