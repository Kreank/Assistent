# -*- coding: utf-8 -*-
"""Google-Anmeldung fuer den Sarvis AUF DEM SERVER.

Der Server hat keinen Bildschirm und keinen Browser -- die Windows-Datei
google_anmelden.bat kann hier also nicht laufen. Sie wuerde den Zugang
ausserdem in Saschas Projektordner schreiben, gebraucht wird er aber in
/srv/data/sarvis.

Deshalb in zwei Schritten:

    python google_anmelden_server.py link      -> gibt den Link aus
    python google_anmelden_server.py code "<zurueckkopierte URL>"

Zwischen beiden Schritten wird der PKCE-Pruefwert gemerkt; ohne ihn
lehnt Google den zweiten Schritt ab.
"""
import json
import sys
from pathlib import Path

from google_auth_oauthlib.flow import Flow

ZUGANG = Path("/srv/data/sarvis/google_zugang.json")
TOKEN = Path("/srv/data/sarvis/google_token.json")
MERKER = Path("/srv/data/sarvis/.google_anmeldung_offen.json")
UMLEITUNG = "http://localhost:8123/"
BEREICHE = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/tasks",
    "https://www.googleapis.com/auth/contacts",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
]


def _fluss() -> Flow:
    return Flow.from_client_secrets_file(
        str(ZUGANG), BEREICHE, redirect_uri=UMLEITUNG)


def link() -> int:
    fluss = _fluss()
    adresse, _ = fluss.authorization_url(
        access_type="offline", prompt="consent", include_granted_scopes="true")
    MERKER.write_text(json.dumps({"pruefwert": fluss.code_verifier}),
                      encoding="utf-8")
    print("\n  Diesen Link im Browser oeffnen und bestaetigen:\n")
    print(adresse)
    print("\n  Google warnt, die App sei nicht ueberprueft -- im Testing-")
    print("  Modus normal. Ueber 'Erweitert' -> 'Weiter zu ...'.\n")
    print("  Danach landet der Browser auf einer FEHLERSEITE")
    print("  (localhost:8123 -- die gibt es auf deinem Rechner nicht).")
    print("  Das ist richtig so. Die Adresszeile kopieren und hier her.\n")
    return 0


def code(rueck: str) -> int:
    if not MERKER.exists():
        print("\n  Kein offener Vorgang. Erst 'link' ausfuehren.\n")
        return 1
    pruefwert = json.loads(MERKER.read_text(encoding="utf-8"))["pruefwert"]
    fluss = _fluss()
    fluss.code_verifier = pruefwert
    # Die zurueckkopierte Adresse ist http://localhost:8123 -- oauthlib
    # verweigert sie sonst mit "OAuth 2 MUST utilize https". Unbedenklich:
    # Ueber diese Adresse laeuft nichts, sie traegt nur den Code zu uns.
    # Am 10.11.2026 genau daran gescheitert.
    import os
    os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")
    try:
        fluss.fetch_token(authorization_response=rueck)
    except Exception as e:
        print(f"\n  Eintausch fehlgeschlagen: {type(e).__name__}: {e}\n")
        return 1
    TOKEN.write_text(fluss.credentials.to_json(), encoding="utf-8")
    MERKER.unlink(missing_ok=True)

    from googleapiclient.discovery import build
    print("\n  Geschafft. Kurze Probe:\n")
    for name, fassung, probe in (
        ("calendar", "v3", lambda d: f"{len(d.calendarList().list().execute().get('items', []))} Kalender"),
        ("gmail", "v1", lambda d: d.users().getProfile(userId='me').execute().get('emailAddress', '')),
        ("tasks", "v1", lambda d: f"{len(d.tasklists().list().execute().get('items', []))} Aufgabenliste(n)"),
        ("drive", "v3", lambda d: f"{len(d.files().list(pageSize=1).execute().get('files', []))} Datei sichtbar"),
    ):
        try:
            d = build(name, fassung, credentials=fluss.credentials,
                      cache_discovery=False)
            print(f"    {name:10s} {probe(d)}")
        except Exception as e:
            print(f"    {name:10s} FEHLER {type(e).__name__}")
    print("\n  Sarvis merkt die neue Datei von selbst -- kein Neustart noetig.\n")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in ("link", "code"):
        print(__doc__)
        raise SystemExit(1)
    if sys.argv[1] == "link":
        raise SystemExit(link())
    if len(sys.argv) < 3:
        print("\n  Die zurueckkopierte Adresse fehlt.\n")
        raise SystemExit(1)
    raise SystemExit(code(sys.argv[2]))
