"""Medientasten -- Wiedergabe steuern, ohne irgendein Konto.

Windows hat globale Tasten fuer Play/Pause, Vor, Zurueck und Lautstaerke.
Die wirken auf das Programm, das gerade Ton macht: Spotify, YouTube im
Browser, VLC, alles.

Der Vorteil gegenueber der Spotify-API ist nicht Funktionsumfang, sondern
das Gegenteil davon: kein Konto, kein OAuth, kein Premium, keine
Einrichtung -- und es funktioniert auch bei allem, was nicht Spotify ist.

Was hier NICHT geht: einen bestimmten Titel ansagen. Dafuer braeuchte es
die Web-API und damit Premium.
"""
import ctypes
import time

from claude_agent_sdk import tool

# Virtuelle Tastencodes der Medientasten. Diese Tasten gibt es auf jeder
# Windows-Installation, auch wenn sie auf der Tastatur fehlen.
TASTEN = {
    "abspielen_pause": 0xB3,   # VK_MEDIA_PLAY_PAUSE
    "weiter":          0xB0,   # VK_MEDIA_NEXT_TRACK
    "zurueck":         0xB1,   # VK_MEDIA_PREV_TRACK
    "stopp":           0xB2,   # VK_MEDIA_STOP
    "lauter":          0xAF,   # VK_VOLUME_UP
    "leiser":          0xAE,   # VK_VOLUME_DOWN
    "stumm":           0xAD,   # VK_VOLUME_MUTE
}

_TASTE_LOS = 0x0002


def _druecken(code: int, mal: int = 1) -> None:
    """Tastendruck an Windows melden -- kurz gedrueckt, dann losgelassen."""
    nutzer = ctypes.windll.user32
    for i in range(max(1, mal)):
        nutzer.keybd_event(code, 0, 0, 0)
        nutzer.keybd_event(code, 0, _TASTE_LOS, 0)
        if i + 1 < mal:
            time.sleep(0.02)


def werkzeuge(protokoll=None, leuchten=None) -> list:
    def blinken():
        if leuchten:
            leuchten("Musik")

    @tool(
        "medien_steuern",
        "Steuert die Wiedergabe von allem, was gerade Ton macht — Spotify, "
        "YouTube, VLC. Für 'Pause', 'nächster Titel', 'lauter', 'Musik aus'. "
        "Einen bestimmten Titel abspielen kann das nicht.",
        {
            "type": "object",
            "properties": {
                "was": {
                    "type": "string",
                    "enum": ["abspielen_pause", "weiter", "zurueck", "stopp",
                             "lauter", "leiser", "stumm"],
                    "description": "Was getan werden soll. 'abspielen_pause' "
                                   "schaltet um — für 'Pause' und für "
                                   "'weiter hören'.",
                },
                "schritte": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 10,
                    "description": "Nur bei lauter/leiser/weiter/zurück: wie "
                                   "oft. Ein Lautstärkeschritt sind zwei "
                                   "Prozent, für 'deutlich lauter' also "
                                   "etwa fünf.",
                },
            },
            "required": ["was"],
        },
    )
    async def medien_steuern(args):
        was = (args.get("was") or "").strip()
        code = TASTEN.get(was)
        if code is None:
            return {"content": [{"type": "text", "text":
                    f"{was!r} kenne ich nicht."}], "is_error": True}

        mal = int(args.get("schritte") or 1)
        if was in ("abspielen_pause", "stopp", "stumm"):
            mal = 1          # umschalten macht man nicht fuenfmal
        try:
            _druecken(code, mal)
        except Exception as e:
            return {"content": [{"type": "text", "text":
                    f"Ging nicht: {e}"}], "is_error": True}

        blinken()
        if protokoll is not None and was in ("stopp", "stumm"):
            protokoll.merken(f"medien_steuern: {was}")
        gesagt = {
            "abspielen_pause": "Umgeschaltet.",
            "weiter": "Weiter." if mal == 1 else f"{mal} Titel weiter.",
            "zurueck": "Zurück." if mal == 1 else f"{mal} Titel zurück.",
            "stopp": "Gestoppt.",
            "lauter": "Lauter.",
            "leiser": "Leiser.",
            "stumm": "Ton umgeschaltet.",
        }
        return {"content": [{"type": "text", "text": gesagt.get(was, "Erledigt.")}]}

    return [medien_steuern]
