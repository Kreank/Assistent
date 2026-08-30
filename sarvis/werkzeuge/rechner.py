"""Etwas auf dem Rechner tun, vor dem der Nutzer sitzt.

DAS PROBLEM

Sarvis konnte auf dem Dev-PC Programme starten und Musik steuern -- er
lief ja auf demselben Rechner. Auf dem Server geht das nicht mehr, und
zwar grundsaetzlich: Dort ist kein Spotify installiert, kein Bildschirm
angeschlossen und niemand, der etwas hoeren wuerde. Gemessen:

    programme.py  -> FileNotFoundError: 'powershell.exe'
    medien.py     -> AttributeError: ctypes hat kein 'windll'

Zwoelf Werkzeuge, die nur noch scheitern konnten. Und das ist die
schlechteste Art zu scheitern: Sarvis bietet sie an, versucht es, und
sagt hinterher "ging nicht". Wer das dreimal hoert, fragt nicht mehr.

DIE LOESUNG IST EINE UMKEHRUNG

Nicht Sarvis fuehrt den Befehl aus, sondern die Oberflaeche, die vor dem
richtigen Rechner steht. Er schickt ihn nur hin -- wie er auch eine
Kachel oder eine Adresse hinschickt.

Damit wird aus einem Verlust sogar ein Gewinn: Vorher ging es nur auf
dem einen Rechner, auf dem Sarvis lief. Jetzt geht es auf jedem, an dem
gerade jemand sitzt, und man kann vom Handy aus sagen "mach mal Musik
an im Wohnzimmer" -- vorausgesetzt, dort laeuft eine Oberflaeche.

WAS DAFUER NOETIG IST

Eine Oberflaeche, die solche Befehle annimmt. Die Weboberflaeche im
Browser kann das NICHT -- ein Browser darf keine Programme starten, und
das ist gut so. Es braucht eine native App auf dem Rechner; ihre
Bauanleitung steht in einsatz/APP-BAUEN.md.

Solange es keine gibt, sagen diese Werkzeuge das auch. Ehrlich und in
einem Satz, statt es zu versuchen und zu scheitern -- der Unterschied
ist der zwischen "das kann ich hier nicht" und "keine Ahnung, warum das
nicht ging".
"""
from claude_agent_sdk import tool

from .. import anzeige as anzeige_modul

# Was eine Oberflaeche koennen muss, damit sie hier zaehlt. Ein Browser
# meldet das nicht; eine native App tut es bei der Anmeldung.
FAEHIGKEIT = "kann_rechner"


def werkzeuge(protokoll, leuchten=None):
    sicht = anzeige_modul.aktuelle()

    def vermerken(was: str) -> None:
        if protokoll is not None:
            protokoll.merken(was)

    def keine_oberflaeche(was: str) -> dict:
        """Der ehrliche Fehlschlag.

        Bewusst mit Grund und mit einem Weg nach vorn: Ein "ging nicht"
        ohne beides laesst den Nutzer raten, ob es an ihm liegt.
        """
        return {"content": [{"type": "text", "text":
                f"{was} kann ich von hier aus nicht -- ich laufe auf dem "
                f"Server, und dort gibt es weder das Programm noch einen "
                f"Bildschirm. Dafür bräuchte es die Sarvis-App auf deinem "
                f"Rechner; im Browser geht es nicht, der darf keine "
                f"Programme starten."}], "is_error": True}

    @tool(
        "programm_am_rechner",
        "Ein Programm auf dem Rechner starten, vor dem der Nutzer sitzt "
        "(Spotify, Browser, Editor). Nur möglich, wenn dort die "
        "Sarvis-App läuft -- im Browser nicht. Sag den Programmnamen so, "
        "wie ein Mensch ihn nennt.",
        {
            "type": "object",
            "properties": {
                "name": {"type": "string",
                         "description": "z.B. 'Spotify', 'Notepad'"},
                "was": {"type": "string",
                        "description": "Optional: was danach geschehen "
                                       "soll, z.B. ein Suchbegriff"},
            },
            "required": ["name"],
        },
    )
    async def programm_am_rechner(args):
        name = (args.get("name") or "").strip()
        if not name:
            return {"content": [{"type": "text", "text":
                    "Welches Programm denn?"}], "is_error": True}
        if not sicht.kann(FAEHIGKEIT):
            return keine_oberflaeche(f"{name} starten")
        sicht.befehl("programm", name=name, was=(args.get("was") or "").strip())
        if leuchten:
            leuchten("Programme")
        vermerken(f"programm_am_rechner: {name}")
        return {"content": [{"type": "text", "text":
                f"{name} müsste jetzt aufgehen."}]}

    @tool(
        "musik_am_rechner",
        "Musik auf dem Rechner des Nutzers steuern: Wiedergabe an/aus, "
        "weiter, zurück, lauter, leiser, stumm. Wirkt auf das, was "
        "gerade Ton macht -- Spotify, YouTube, was auch immer. Nur "
        "möglich, wenn dort die Sarvis-App läuft.",
        {
            "type": "object",
            "properties": {
                "was": {"type": "string",
                        "enum": ["pause", "weiter", "zurueck", "stop",
                                 "lauter", "leiser", "stumm"]},
            },
            "required": ["was"],
        },
    )
    async def musik_am_rechner(args):
        was = (args.get("was") or "").strip()
        if not sicht.kann(FAEHIGKEIT):
            return keine_oberflaeche("Musik steuern")
        sicht.befehl("medien", was=was)
        if leuchten:
            leuchten("Musik")
        # Kein vermerken(): Lauter zu drehen hat keine bleibende Wirkung,
        # die nach einem Abbruch nachgetragen werden muesste.
        return {"content": [{"type": "text", "text": "Erledigt."}]}

    return [programm_am_rechner, musik_am_rechner]
