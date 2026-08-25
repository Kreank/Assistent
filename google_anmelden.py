# -*- coding: utf-8 -*-
"""Einmalige Google-Anmeldung.

    .venv\\Scripts\\python.exe google_anmelden.py

Öffnet den Browser, du bestätigst einmal, danach liegt `google_token.json`
im Projektordner und Sarvis meldet sich damit selbst an.

WICHTIG zu `google_token.json`: Die Datei ist so viel wert wie der Zugang
zu Kalender, Postfach, Kontakten und Drive. Sie steht in der .gitignore
und gehört weder in ein Repository noch in eine Sicherung, die andere
lesen können. Verloren gegangen? Unter myaccount.google.com →
Sicherheit → Drittanbieter-Apps den Zugriff entziehen, dann hier neu
anmelden.

Im Testing-Modus läuft der Zugang nach sieben Tagen ab. Dann meldet
Sarvis das beim Start, und du führst dieses Skript nochmal aus.
"""
import sys

from sarvis import config
from sarvis.werkzeuge.google import BEREICHE, anmelden_interaktiv


def main() -> int:
    if not config.GOOGLE_ZUGANG.exists():
        print(f"\n  Die Datei {config.GOOGLE_ZUGANG.name} fehlt.")
        print("  Sie kommt aus der Google Cloud Console:")
        print("  Anmeldedaten → OAuth-Client-ID → Desktop-App → JSON laden.\n")
        return 1

    print("\n  Google-Anmeldung für Sarvis")
    print("  " + "-" * 46)
    print(f"  Zugangsdaten : {config.GOOGLE_ZUGANG.name}")
    print(f"  Token kommt nach: {config.GOOGLE_TOKEN.name}")
    print("\n  Angefragt wird:")
    for bereich in BEREICHE:
        print(f"    {bereich.rsplit('/', 1)[-1]}")
    print("\n  Gleich öffnet sich der Browser. Bestätige dort einmal.")
    print("  Google warnt, die App sei nicht überprüft — das ist im")
    print("  Testing-Modus normal. Über 'Erweitert' weiter.\n")

    try:
        dienste = anmelden_interaktiv()
    except Exception as e:
        print(f"\n  Anmeldung fehlgeschlagen: {type(e).__name__}: {e}\n")
        return 1

    print("\n  Geschafft. Kurze Probe:\n")
    for name, zeile in dienste:
        print(f"    {name:12s} {zeile}")
    print("\n  Fertig. google_token.json bleibt liegen — nicht weitergeben.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
