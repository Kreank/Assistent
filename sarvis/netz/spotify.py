"""Die einmalige Spotify-Anmeldung -- ueber Sarvis' eigene Adresse.

Spotify verlangt den OAuth-Weg mit Weiterleitung: Der Nutzer meldet sich
bei Spotify an, Spotify schickt ihn mit einem Code zurueck, und aus dem
Code wird ein Token. Dafuer braucht es eine erreichbare Rueckadresse --
und die hat Sarvis ohnehin.

    https://sarvis.tech-artist.de/spotify        die Anmeldung anstossen
    https://sarvis.tech-artist.de/spotify/zurueck  wo Spotify hinschickt

Beides ist im Developer-Portal als Redirect URI zu hinterlegen (die
zweite Adresse). Danach einmal die erste im Browser aufrufen, und der
Zugang haelt sich mit dem Auffrischtoken selbst am Leben.

WARUM DIESE ZWEI WEGE OHNE GERAETESCHLUESSEL ERREICHBAR SIND

Der Rest des Endpunkts verlangt eine Anmeldung. Diese beiden koennen es
nicht: Spotify ruft die Rueckadresse auf, und Spotify hat keinen
Geraeteschluessel.

Was stattdessen schuetzt:

  Der Zustandswert. Beim Anstossen wird eine Zufallszeichenkette erzeugt
  und gemerkt; kommt sie nicht unveraendert zurueck, wird der Code
  verworfen. Ohne das koennte jemand einen fremden Code unterschieben
  und Sarvis mit SEINEM Spotify-Konto verbinden.

  Die Einmaligkeit. Der Zustandswert gilt fuer genau einen Rueckruf und
  hoechstens ZUSTAND_FRIST Sekunden. Ein abgefangener Link nuetzt danach
  nichts mehr.

  Und: Ohne hinterlegte Client-Daten passiert gar nichts. Wer die
  Adresse ohne Anlass aufruft, bekommt einen Satz und keinen Fluss.

Was NICHT geschuetzt ist: Wer in genau dem Zeitfenster zwischen Anstossen
und Rueckkehr die Adresse errrraet, koennte den Fluss stoeren. Er
bekaeme dabei nichts -- der Code gehoert zu Saschas Anmeldung, nicht zu
seiner --, es waere nur ein misslungener Versuch. Das ist der uebliche
Zuschnitt bei OAuth-Rueckadressen.
"""
import logging
import secrets
import time

import httpx
from aiohttp import web

from .. import config
from ..werkzeuge import musik

log = logging.getLogger("sarvis.spotify")

AUTORISIEREN = "https://accounts.spotify.com/authorize"

# Wie lange ein angestossener Anmeldevorgang gilt. Grosszuegig, weil
# dazwischen ein Mensch sein Passwort sucht -- aber nicht unbegrenzt.
ZUSTAND_FRIST = 900.0

_offen: dict[str, float] = {}


def _rueckadresse(anfrage: web.Request) -> str:
    """Die Adresse, an die Spotify zurueckschickt.

    Aus dem Host-Kopf gebaut statt fest eingetragen: Hinter Caddy ist
    das die oeffentliche Adresse, beim Ausprobieren auf dem Rechner die
    oertliche. Eine fest verdrahtete Adresse waere genau einmal richtig.
    """
    wirt = anfrage.headers.get("X-Forwarded-Host") or anfrage.host
    schema = anfrage.headers.get("X-Forwarded-Proto") or "https"
    return f"{schema}://{wirt}/spotify/zurueck"


def _aufraeumen() -> None:
    jetzt = time.monotonic()
    for k in [k for k, t in _offen.items() if jetzt - t > ZUSTAND_FRIST]:
        _offen.pop(k, None)


def _seite(titel: str, text: str, gut: bool = True) -> web.Response:
    farbe = "#7ee2a0" if gut else "#ff8a80"
    return web.Response(content_type="text/html", text=f"""<!doctype html>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Sarvis · Spotify</title>
<style>
 body{{margin:0;min-height:100vh;display:flex;align-items:center;
   justify-content:center;background:#04080f;color:#e8f1fd;
   font:15px/1.6 "Segoe UI",system-ui,sans-serif;padding:24px}}
 div{{max-width:420px;text-align:center}}
 h1{{font-size:15px;letter-spacing:.2em;text-transform:uppercase;
   font-weight:600;color:{farbe};margin:0 0 14px}}
 p{{opacity:.75;margin:0}}
</style>
<div><h1>{titel}</h1><p>{text}</p></div>""")


async def anstossen(anfrage: web.Request) -> web.Response:
    """Schickt den Nutzer zu Spotify."""
    paar = musik.zugang()
    if not paar:
        return _seite("Kein Zugang hinterlegt",
                      "In der .env fehlen SPOTIFY_CLIENT_ID und "
                      "SPOTIFY_CLIENT_SECRET.", gut=False)
    _aufraeumen()
    zustand = secrets.token_urlsafe(24)
    _offen[zustand] = time.monotonic()
    from urllib.parse import urlencode
    ziel = AUTORISIEREN + "?" + urlencode({
        "client_id": paar[0],
        "response_type": "code",
        "redirect_uri": _rueckadresse(anfrage),
        "scope": musik.RECHTE,
        "state": zustand,
        # Damit Spotify auch dann fragt, wenn schon eine Sitzung besteht
        # -- sonst laesst sich nicht auf ein anderes Konto wechseln.
        "show_dialog": "true",
    })
    raise web.HTTPFound(ziel)


async def zurueck(anfrage: web.Request) -> web.Response:
    """Wo Spotify den Nutzer wieder abliefert."""
    fehler = anfrage.query.get("error")
    if fehler:
        return _seite("Abgebrochen", f"Spotify meldet: {fehler}", gut=False)

    zustand = anfrage.query.get("state") or ""
    _aufraeumen()
    if zustand not in _offen:
        # Entweder abgelaufen, schon benutzt, oder untergeschoben. Alle
        # drei sehen von hier gleich aus und werden gleich behandelt.
        return _seite("Nicht mehr gültig",
                      "Der Anmeldevorgang ist abgelaufen oder wurde schon "
                      "benutzt. Fang noch einmal an.", gut=False)
    _offen.pop(zustand, None)

    code = anfrage.query.get("code")
    paar = musik.zugang()
    if not code or not paar:
        return _seite("Etwas fehlt", "Kein Code oder kein Zugang.", gut=False)

    try:
        with httpx.Client(timeout=musik.ZEITGRENZE) as c:
            a = c.post(musik.TOKEN_URL, data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": _rueckadresse(anfrage),
                "client_id": paar[0],
                "client_secret": paar[1],
            })
    except httpx.HTTPError as e:
        return _seite("Spotify antwortet nicht", str(e)[:120], gut=False)

    if a.status_code != 200:
        return _seite("Spotify lehnt ab",
                      f"HTTP {a.status_code}. Stimmt die Rückadresse im "
                      f"Developer-Portal? Sie muss genau "
                      f"{_rueckadresse(anfrage)} sein.", gut=False)

    d = a.json()
    musik._token_sichern({
        "access_token": d.get("access_token"),
        "refresh_token": d.get("refresh_token"),
        "laeuft_ab": time.time() + int(d.get("expires_in") or 3600),
    })
    log.info("Spotify angemeldet")
    return _seite("Verbunden",
                  "Sarvis kann jetzt deine Musik steuern. Das Fenster "
                  "kannst du zumachen — beim nächsten Start sind die "
                  "Werkzeuge da.")


def anmelden(app: web.Application) -> None:
    """Die beiden Wege eintragen."""
    app.router.add_get("/spotify", anstossen)
    app.router.add_get("/spotify/zurueck", zurueck)
