# -*- coding: utf-8 -*-
"""Microsoft-Anmeldung fuer Sarvis (Outlook, Kalender, OneDrive).

Einmalig, im Container:

    docker exec -it sarvis python3 /srv/storage/projects/sarvis/einsatz/microsoft_anmelden.py

Zeigt einen Code. Auf https://microsoft.com/devicelogin (Handy oder PC)
eingeben, mit dem Hotmail-Konto anmelden, Zugriff erlauben. Das Skript
wartet und legt das Token in /srv/data/sarvis/microsoft_token.json ab.
Danach Sarvis neu starten -- die Werkzeuge werden nur gebaut, wenn das
Token da ist.

Voraussetzung: MICROSOFT_CLIENT_ID in /srv/data/sarvis/.env (App-
Registrierung bei Microsoft Entra, "Nur persoenliche Microsoft-Konten",
"Oeffentliche Clientflows zulassen" = Ja).
"""
import sys
import time

import httpx

sys.path.insert(0, "/srv/storage/projects/sarvis")
from sarvis.werkzeuge import microsoft  # noqa: E402


def main() -> int:
    kennung = microsoft.client_id()
    if not kennung:
        print("\n  MICROSOFT_CLIENT_ID fehlt in /srv/data/sarvis/.env.\n")
        return 1
    r = httpx.post(f"{microsoft.BEHOERDE}/devicecode",
                   data={"client_id": kennung, "scope": microsoft.BEREICHE},
                   timeout=30)
    if r.status_code != 200:
        print(f"\n  Microsoft lehnt ab: {r.text[:400]}\n")
        return 1
    d = r.json()
    print(f"\n  {d.get('message')}\n")
    pause = int(d.get("interval", 5))
    ende = time.time() + int(d.get("expires_in", 900))
    while time.time() < ende:
        time.sleep(pause)
        t = httpx.post(f"{microsoft.BEHOERDE}/token", data={
            "client_id": kennung,
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            "device_code": d["device_code"]}, timeout=30)
        antwort = t.json()
        fehler = antwort.get("error")
        if fehler == "authorization_pending":
            continue
        if fehler == "slow_down":
            pause += 5
            continue
        if fehler:
            print(f"\n  Abgebrochen: {antwort.get('error_description', fehler)[:400]}\n")
            return 1
        microsoft.token_speichern(antwort)
        ich = httpx.get(f"{microsoft.GRAPH}/me", headers={
            "Authorization": f"Bearer {antwort['access_token']}"}, timeout=30).json()
        print(f"\n  Angemeldet als {ich.get('displayName')}. Token liegt in "
              f"{microsoft.TOKEN_DATEI}.\n  Jetzt Sarvis neu starten.\n")
        return 0
    print("\n  Zeit abgelaufen. Noch einmal starten.\n")
    return 1


if __name__ == "__main__":
    sys.exit(main())
