# -*- coding: utf-8 -*-
"""Spielt die Zustandsmaschine der Anmeldewache durch.

    docker compose exec sarvis python wache_test.py

Geprüft wird die Flankenlogik von anmeldung.wache(): wann gewarnt wird,
wann geschwiegen und wann Entwarnung kommt. Die Anmeldung selbst und der
Mailversand werden dabei von außen gesteuert — anders ließe sich der
wichtigste Fall gar nicht herbeiführen: ein Zugang, der gerade kippt.

Der Melde-WEG ist damit ausdrücklich nicht geprüft. Der wurde einmal
echt verschickt, und das gehört auch so: Eine Attrappe, die eine Mail
nur behauptet, beweist über den Posteingang nichts.

Warum überhaupt: Die Wache meldet höchstens einmal im Jahr etwas. Bis
dahin fällt an ihr kein Fehler auf — außer hier.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sarvis import anmeldung

zustaende = []
versendet = []
sende_erfolg = True


async def gesteuertes_pruefen():
    if not zustaende:
        raise asyncio.CancelledError
    return zustaende.pop(0), "test"


async def gesteuertes_melden(betreff, text):
    if not sende_erfolg:
        return None
    # Ohne den Zeitstempel, den der Betreff seit dem 31.08.2026 trägt:
    # Geprüft wird, WELCHE Nachricht rausging, nicht wann.
    versendet.append(betreff.split(" (")[0])
    return "Test"


async def durchlauf(folge, erfolg=True, abstand=0.001):
    global zustaende, versendet, sende_erfolg
    zustaende = list(folge)
    versendet = []
    sende_erfolg = erfolg
    anmeldung.pruefen = gesteuertes_pruefen
    anmeldung.hinausmelden = gesteuertes_melden
    anmeldung.WACHE_ABSTAND_SEK = abstand
    try:
        await anmeldung.wache()
    except asyncio.CancelledError:
        pass
    return list(versendet)


def pruefe(name, ist, soll):
    zeichen = "ok  " if ist == soll else "FEHLER"
    print(f"  {zeichen}  {name}")
    if ist != soll:
        print(f"           erwartet: {soll}")
        print(f"           bekommen: {ist}")
    return ist == soll


async def haupt():
    gut = []
    W, E = "Sarvis kann nicht mehr denken", "Sarvis denkt wieder"

    gut.append(pruefe(
        "gesunder Start meldet nichts",
        await durchlauf([True, True, True]), []))

    gut.append(pruefe(
        "Ausfall meldet genau einmal, nicht bei jedem Durchgang",
        await durchlauf([False, False, False, False]), [W]))

    gut.append(pruefe(
        "Rueckkehr gibt Entwarnung",
        await durchlauf([False, False, True, True]), [W, E]))

    gut.append(pruefe(
        "zweiter Ausfall warnt wieder",
        await durchlauf([False, True, False, False]), [W, E, W]))

    gut.append(pruefe(
        "Rueckkehr ohne vorherige Warnung gibt keine Entwarnung",
        await durchlauf([True, True]), []))

    # Der Fall, der die Nachbesserung ausgeloest hat.
    gut.append(pruefe(
        "gescheiterter Versand versucht es erneut statt zu schweigen",
        await durchlauf([False, False, False], erfolg=False), []))

    print()
    if all(gut):
        print(f"  Alle {len(gut)} Faelle wie erwartet.")
        return 0
    print(f"  {sum(1 for g in gut if not g)} von {len(gut)} Faellen falsch.")
    return 1


sys.exit(asyncio.run(haupt()))
