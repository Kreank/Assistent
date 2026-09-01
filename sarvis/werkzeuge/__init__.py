"""Sarvis' Werkzeuge.

Alles laeuft als In-Process-Server: kein Unterprozess, keine Startzeit.
Die 2,4 Sekunden, die externe MCP-Server gekostet haben, entstehen hier
nicht.

Erlaubnisstufen stehen in config.WERKZEUG_STUFEN:
  "still"   laeuft ohne Nachfrage durch
  "fragen"  Sarvis fragt laut nach und wartet auf ja oder nein
  alles Uebrige wird abgelehnt -- nicht aufgezaehlt zu sein heisst nein.
"""
from claude_agent_sdk import create_sdk_mcp_server

from .. import config

from . import (auftrag, bericht, dokument, erinnern, fachdaten, finanzen,
               google, kacheln, lesen, medien, musik, programme, projekte,
               rechner, telegram, unterwegs, verlauf, wetter, zeit)

SERVER = "sarvis"


class Protokoll:
    """Was in diesem Zug schon wirklich passiert ist.

    Hintergrund: Ein Abbruch stoppt nur das Reden. Werkzeuge, die vorher
    gelaufen sind, haben ihre Wirkung schon getan -- und Sarvis wusste
    danach nichts mehr davon. In der Praxis hiess das: Wecker auf 10:13
    gestellt, unterbrochen, "doch auf 10:14" gesagt -- und es klingelte
    zweimal, weil der erste nie erwaehnt wurde.

    Nur Werkzeuge mit bleibender Wirkung landen hier. Ein Blick in die
    Timerliste veraendert nichts und muss nicht nachgetragen werden.
    """

    def __init__(self):
        self.eintraege: list[str] = []

    def merken(self, zusammenfassung: str) -> None:
        self.eintraege.append(zusammenfassung)

    def leeren(self) -> None:
        self.eintraege = []

    def nachtrag(self) -> str:
        """Der Hinweis, der nach einem Abbruch mitgeschickt wird."""
        if not self.eintraege:
            return ""
        liste = "\n".join(f"- {e}" for e in self.eintraege)
        return (
            "[Hinweis: Deine vorige Antwort wurde vom Nutzer unterbrochen. "
            "Folgendes war zu dem Zeitpunkt aber schon ausgeführt und wirkt "
            f"weiter:\n{liste}\n"
            "Berücksichtige das. Wenn der Nutzer seine Anweisung jetzt "
            "korrigiert, ändere oder lösche das Bestehende, statt zusätzlich "
            "etwas Neues anzulegen. Erwähne diesen Hinweis nicht.]"
        )


def bauen(sagen, leuchten=None, melden=None):
    """Baut den Werkzeugserver.

    sagen(text)          -- Sarvis spricht von sich aus (Timer abgelaufen)
    leuchten(name)       -- Werkzeug im Anzeigenkranz aufleuchten lassen
    melden(titel, text)  -- Windows-Benachrichtigung
    """
    protokoll = Protokoll()
    wecker = zeit.Wecker(sagen=sagen, leuchten=leuchten, melden=melden)
    werkstatt = auftrag.Werkstatt(sagen=sagen, melden=melden, leuchten=leuchten)
    alle = (zeit.werkzeuge(wecker, protokoll)
            + erinnern.werkzeuge(protokoll, leuchten)
            + verlauf.werkzeuge(protokoll, leuchten))
    alle += kacheln.werkzeuge(protokoll, leuchten)
    alle += bericht.werkzeuge(protokoll, leuchten)
    # Blaetter und Dateien -- dieselbe Familie wie Kachel und
    # Seite, nur groesser beziehungsweise zum Behalten.
    alle += dokument.werkzeuge(protokoll, leuchten)
    alle += projekte.werkzeuge(protokoll, leuchten)
    alle += programme.werkzeuge(protokoll, leuchten)
    alle += medien.werkzeuge(protokoll, leuchten)
    # Die vier Nachschlagewerke. Alle lesen nur, keines braucht einen
    # Zugang -- ausser den zwei Tank-Werkzeugen, die sich in
    # unterwegs.werkzeuge() selbst wegbauen, wenn der Schluessel fehlt.
    alle += wetter.werkzeuge(protokoll, leuchten)
    alle += unterwegs.werkzeuge(protokoll, leuchten)
    alle += lesen.werkzeuge(protokoll, leuchten)
    alle += fachdaten.werkzeuge(protokoll, leuchten)
    # Was auf dem Rechner des Nutzers geschehen soll, nicht hier.
    alle += rechner.werkzeuge(protokoll, leuchten)
    if config.finanz_schluessel():
        # Ohne Schluessel gaebe es acht Werkzeuge, die nur "kein
        # Zugang" sagen koennen -- das verwirrt mehr, als es nuetzt.
        alle += finanzen.werkzeuge(protokoll, leuchten)
    alle += auftrag.werkzeuge(werkstatt, protokoll, leuchten)
    if musik.bereit():
        # Ohne Zugang gar nicht erst bauen -- lieber keine Werkzeuge als
        # fuenf, die nur "kein Zugang" sagen koennen. Dieselbe
        # Entscheidung wie bei Finanzen und Google.
        alle += musik.werkzeuge(protokoll, leuchten)
    if google.bereit():
        alle += google.werkzeuge(protokoll, leuchten)
    if config.telegram_bereit():
        alle += telegram.werkzeuge(protokoll, leuchten)
    server = create_sdk_mcp_server(name=SERVER, version="1.0.0", tools=alle)
    namen = [f"mcp__{SERVER}__{w.name}" for w in alle]
    return server, namen, wecker, protokoll, werkstatt


def unterbrochen_zeile(werkstatt) -> str:
    """Auftraege, die ein Neustart mittendrin erwischt hat.

    Gehoert ins Arbeitsgedaechtnis und nicht in eine Erinnerung: Sarvis
    kann nicht wissen, dass er neu gestartet wurde -- der Arbeiter ist
    einfach weg. Ohne diese Zeile fragt er den Nutzer, was zu tun sei,
    waehrend halbfertige Arbeit auf einem Zweig liegt.
    """
    if werkstatt is None:
        return ""
    offen = werkstatt.unterbrochene()
    if not offen:
        return ""
    teile = []
    for a in offen:
        stand = f" -- {a.stand_text}" if getattr(a, "stand_text", "") else ""
        teile.append(f"Auftrag {a.nummer} ({a.projekt}){stand}")
    return ("[Von einem Neustart unterbrochen und NICHT fertig geworden: "
            + "; ".join(teile)
            + ". Biete an, ihn mit auftrag_fortsetzen dort weiterlaufen zu "
              "lassen, wo er war -- oder den Zweig zu verwerfen. Entscheide "
              "das NICHT selbst.]")


def zustand_zeile(wecker) -> str:
    """Was gerade laeuft, als eine Zeile fuer den Vorspann.

    Arbeitsgedaechtnis statt Erinnerung: Sarvis muss nicht wissen, dass er
    vor drei Zuegen einen Wecker gestellt hat -- er sieht die laufenden bei
    jedem Zuruf. Erinnerung kann truegen, besonders nach einem Abbruch;
    eine Zustandszeile kann es nicht.
    """
    offen = wecker.alle()
    if not offen:
        return ""
    from datetime import datetime, timedelta
    jetzt = datetime.now()
    teile = []
    for t in offen:
        faellig = (jetzt + timedelta(seconds=t["rest"])).strftime("%H:%M")
        teile.append(
            f"Timer {t['nummer']}"
            + (f" ({t['was']})" if t["was"] else "")
            + f" um {faellig}"
        )
    return "[Läuft gerade: " + "; ".join(teile) + "]"


def voller_name(kurz: str) -> str:
    return f"mcp__{SERVER}__{kurz}"


def kurzer_name(voll: str) -> str:
    marke = f"mcp__{SERVER}__"
    return voll[len(marke):] if voll.startswith(marke) else voll
