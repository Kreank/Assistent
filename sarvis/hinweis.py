"""Windows-Benachrichtigungen.

Der Unterschied zum gesprochenen Hinweis ist nicht der Ton, sondern die
Haltbarkeit: Ein gesprochener Satz ist weg, wenn man nicht am Rechner sass.
Eine Benachrichtigung steht danach im Info-Center und wartet.

Damit sie als "Sarvis" erscheint und nicht als "Python", braucht Windows
eine registrierte Anwendungskennung (AppUserModelID). Die haengt an einer
Verknuepfung im Startmenue -- einmal anlegen mit `python einrichten.py`.
"""
import sys
import threading

from . import config

KENNUNG = "Sarvis.Assistent"   # AppUserModelID


def _moeglich() -> bool:
    return sys.platform == "win32" and config.TOAST


def zeigen(titel: str, text: str, still: bool = False) -> None:
    """Benachrichtigung anzeigen. Kehrt sofort zurueck.

    Laeuft in einem eigenen Faden: Die Windows-Schnittstelle baut intern
    eine eigene Ereignisschleife auf, und die hat in Sarvis' Schleife
    nichts verloren.
    """
    if not _moeglich():
        return

    def arbeiten():
        try:
            # Reihenfolge ist hier kein Stilfrage, sondern Pflicht:
            # Wird win11toast (und damit die Windows-Runtime) vor
            # onnxruntime geladen, stirbt dessen Initialisierung mit
            # "DLL load failed ... onnxruntime_pybind11_state" -- und
            # damit Piper, also Sarvis' Stimme. Nachgestellt und bestaetigt.
            # Deshalb: erst onnxruntime sichern, dann erst der Toast.
            try:
                import onnxruntime  # noqa: F401
            except Exception:
                pass
            from win11toast import notify

            args = {
                "title": titel,
                "body": text,
                "app_id": KENNUNG,
                "audio": {"silent": "true"} if still else None,
            }
            if config.SYMBOL.exists():
                args["icon"] = {
                    "src": str(config.SYMBOL),
                    "placement": "appLogoOverride",
                    "hint-crop": "circle",
                }
            notify(**{k: v for k, v in args.items() if v is not None})
        except Exception as e:
            print(f"  (Benachrichtigung fehlgeschlagen: {e})")

    threading.Thread(target=arbeiten, daemon=True).start()


def eingerichtet() -> bool:
    """Gibt es die Startmenue-Verknuepfung, an der die Kennung haengt?"""
    return config.VERKNUEPFUNG.exists()
