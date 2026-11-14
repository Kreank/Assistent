"""Sarvis' Denken sichtbar machen (seit 14.11.2026).

Sascha: "Es waere cool, wenn ich sein Denken sehen koennte ... wie im Web
das Denken aufklappen und sehen, was gerade gemacht wird. Natuerlich
sauber ausgegeben."

Pro Zug EIN Verlaufseintrag (wer "sarvis", sorte "denken"), der sich
waehrend der Arbeit fuellt -- dieselbe id, neuer Stand, wie die
Auftragskarte. Die Schritte:

    gedanke   die Zusammenfassung seines Denkens (thinking display
              "summarized"; ohne die Einstellung kommt der Block leer)
    werkzeug  welches Werkzeug, mit was -- in Worten, nicht als JSON;
              wenn die Rueckgabe da ist: ok/fehler und ein kurzer Auszug

Hier steht nur, wie aus SDK-Bloecken lesbare Schritte werden. Wann der
Eintrag geschrieben wird, entscheidet main.py.
"""
import re

from .werkzeuge import kurzer_name

# Eingebaute Werkzeuge haben englische Namen.
_EINGEBAUT = {
    "WebSearch": "Websuche", "WebFetch": "Webseite lesen",
    "Read": "Datei lesen", "Write": "Datei schreiben", "Edit": "Datei ändern",
    "Glob": "Dateien suchen", "Grep": "In Dateien suchen", "Bash": "Befehl",
    "PowerShell": "Befehl", "Agent": "Unter-Arbeiter", "Task": "Unter-Arbeiter",
    "ToolSearch": "Werkzeug holen", "TodoWrite": "Aufgabenliste",
}

# Woerter in Werkzeugnamen, die ohne Umlaut geschrieben sind. Bewusst eine
# Liste statt "ae -> ä": sonst wird aus "neue" "neü".
_UMLAUT = {
    "oeffnen": "öffnen", "loeschen": "löschen", "aendern": "ändern",
    "anhaengen": "anhängen", "gedaechtnis": "Gedächtnis",
    "dauerauftraege": "Daueraufträge", "empfaenger": "Empfänger",
    "guenstig": "günstig", "rueckfragen": "Rückfragen",
    "auftrag": "Auftrag", "termin": "Termin", "termine": "Termine",
    "mail": "Mail", "mails": "Mails", "wetter": "Wetter", "musik": "Musik",
    "kalender": "Kalender", "notiz": "Notiz", "timer": "Timer",
    "datei": "Datei", "blatt": "Blatt", "kachel": "Kachel",
    "projekt": "Projekt", "verlauf": "Verlauf", "finanzen": "Finanzen",
    "tabelle": "Tabelle", "dokument": "Dokument", "kontakt": "Kontakt",
    "aufgabe": "Aufgabe", "aufgaben": "Aufgaben", "person": "Person",
    "radio": "Radio", "programm": "Programm", "web": "Web",
    "vorschau": "Vorschau", "route": "Route", "ort": "Ort",
    "nachrichten": "Nachrichten", "eingang": "Eingang",
}

# Welche Eingabe ein Werkzeug am besten beschreibt -- die erste, die da ist.
_BESCHREIBEND = (
    "description", "titel", "betreff", "query", "frage", "suche", "name",
    "text", "url", "adresse", "pfad", "file_path", "pattern", "command",
    "ort", "wann", "von", "an", "prompt",
)

GEDANKE_MAX = 2000
AUSZUG_MAX = 220


def werkzeugname(roh: str) -> str:
    """'mcp__sarvis__termine_ansehen' -> 'Termine ansehen'."""
    name = kurzer_name(str(roh or ""))
    if name in _EINGEBAUT:
        return _EINGEBAUT[name]
    worte = [_UMLAUT.get(w, w) for w in name.split("_") if w]
    if not worte:
        return name
    satz = " ".join(worte)
    return satz[:1].upper() + satz[1:]


def _kurz(text: str, grenze: int) -> str:
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    return text if len(text) <= grenze else text[: grenze - 1].rstrip() + "…"


def eingabe_kurz(eingabe) -> str:
    """Das Wichtigste aus der Werkzeugeingabe in einer Zeile."""
    if not isinstance(eingabe, dict) or not eingabe:
        return ""
    for schluessel in _BESCHREIBEND:
        wert = eingabe.get(schluessel)
        if isinstance(wert, (str, int, float)) and str(wert).strip():
            return _kurz(wert, 140)
    # Sonst die ersten zwei einfachen Werte.
    teile = [f"{k}: {v}" for k, v in eingabe.items()
             if isinstance(v, (str, int, float, bool)) and str(v).strip()][:2]
    return _kurz(" · ".join(teile), 140)


def ergebnis_kurz(inhalt) -> str:
    """Rueckgabe eines Werkzeugs als kurzer Auszug (Text, keine Bilder)."""
    if isinstance(inhalt, list):
        teile = []
        for t in inhalt:
            if isinstance(t, dict) and t.get("type") == "text":
                teile.append(str(t.get("text") or ""))
            elif isinstance(t, dict) and t.get("type") == "image":
                teile.append("[Bild]")
        inhalt = " ".join(teile)
    return _kurz(inhalt or "", AUSZUG_MAX)


def gedanke(text: str) -> dict | None:
    text = str(text or "").strip()
    if not text:
        return None
    if len(text) > GEDANKE_MAX:
        text = text[: GEDANKE_MAX - 1].rstrip() + "…"
    return {"art": "gedanke", "text": text}


def werkzeug(block) -> dict:
    return {"art": "werkzeug", "id": str(getattr(block, "id", "") or ""),
            "titel": werkzeugname(getattr(block, "name", "")),
            "text": eingabe_kurz(getattr(block, "input", None)),
            "stand": "läuft"}


def zusammenfassung(schritte: list, sekunden: float | None, fertig: bool) -> str:
    """Die Zeile im zugeklappten Zustand."""
    werkzeuge = sum(1 for s in schritte if s.get("art") == "werkzeug")
    if not fertig:
        return "Denkt nach …"
    teile = ["Gedanken"]
    if werkzeuge:
        teile.append(f"{werkzeuge} Schritt" + ("" if werkzeuge == 1 else "e"))
    if sekunden is not None:
        teile.append(f"{sekunden:.0f} s" if sekunden >= 1 else "unter 1 s")
    return " · ".join(teile)


# --- Uebersetzen -------------------------------------------------------------
#
# Die Denk-Zusammenfassung kommt auf ENGLISCH, auch wenn Systemprompt und
# Gespraech deutsch sind -- gemessen 14.11.2026, auch mit der ausdruecklichen
# Bitte "denke auf Deutsch". Sascha liest Deutsch. Also uebersetzt das
# kleine Modell (config.TITEL_MODELL) jeden Gedanken, im Hintergrund: Die
# Antwort wartet darauf nicht, die Karte wird nur kurz danach ersetzt.
#
# Die Sitzungen dieser Aufrufe beginnen mit UEBERSETZ_KOPF -- daran
# erkennt verlauf_nachschlagen sie und ueberspringt sie (wie die
# Titel-Sitzungen), sonst faende Sarvis seine eigenen Gedanken als
# "Gespraech" wieder.

UEBERSETZ_KOPF = "Gedanke übersetzen: "

_DEUTSCH = re.compile(r"\b(der|die|das|und|ich|nicht|ist|ein|eine|mit|für|auf)\b", re.I)
_ENGLISCH = re.compile(r"\b(the|and|i'm|is|to|of|that|with|for|it|this|be)\b", re.I)


def ist_englisch(text: str) -> bool:
    return len(_ENGLISCH.findall(text)) > len(_DEUTSCH.findall(text))


def uebersetzen(text: str) -> str:
    """Englischen Gedanken ins Deutsche. Leer, wenn es nicht klappt.

    Blockiert (eigene Ereignisschleife) -- nur aus einem Faden rufen."""
    import asyncio

    from claude_agent_sdk import (AssistantMessage, ClaudeAgentOptions,
                                  TextBlock, query)

    from . import config

    async def fragen() -> str:
        opt = ClaudeAgentOptions(
            model=config.TITEL_MODELL, allowed_tools=[], max_turns=1,
            setting_sources=[],
            system_prompt=(
                "Uebersetze die Notiz eines Assistenten ueber sein eigenes "
                "Nachdenken ins Deutsche. Natuerlich und knapp, Ich-Form "
                "beibehalten, nichts hinzufuegen, nichts weglassen, keine "
                "Einleitung. Fachbegriffe, Namen, Befehle und Dateinamen "
                "bleiben wie sie sind. Antworte nur mit der Uebersetzung."))
        aus = ""
        async for m in query(prompt=UEBERSETZ_KOPF + text, options=opt):
            if isinstance(m, AssistantMessage):
                aus += "".join(b.text for b in m.content
                               if isinstance(b, TextBlock))
        return aus.strip()

    try:
        return asyncio.run(fragen())
    except Exception as e:
        print(f"  (Gedanke nicht uebersetzt: {e})")
        return ""
