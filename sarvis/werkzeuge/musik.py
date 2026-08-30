"""Spotify -- suchen, abspielen, wissen was laeuft.

WARUM ES DIE MEDIENTASTEN NICHT TUN

`musik_am_rechner` drueckt die virtuellen Medientasten am Rechner des
Nutzers. Das reicht fuer Pause und weiter und braucht kein Konto -- das
Signal geht ans Betriebssystem, und wer gerade Ton macht, reagiert.

Was es nicht kann: irgendetwas Bestimmtes abspielen. "Spiel mir das
neue Album von X" braucht jemanden, der weiss, welches Album das ist.
Und "von wem ist das gerade?" braucht jemanden, der die Wiedergabe
sieht. Beides kann nur der Dienst selbst.

SPOTIFY CONNECT IST DER EIGENTLICHE GEWINN

Die API steuert nicht "den Spotify-Client auf diesem Rechner", sondern
das Konto. Damit laesst sich vom Handy aus die Musik am Rechner
starten, vom Rechner aus die Box im Wohnzimmer -- und Sarvis muss dafuer
auf keinem der Geraete laufen. Er sagt dem Dienst, was passieren soll,
und der Dienst sagt es dem Geraet.

Der Preis: Es muss irgendwo ein Geraet WACH sein. Spotify kann keins
aufwecken, das aus ist, und die API antwortet dann mit 404 "kein
aktives Geraet". Das wird hier nicht als Fehler durchgereicht, sondern
als Satz, der sagt, was zu tun ist -- ein Assistent, der "HTTP 404"
sagt, hilft niemandem.

WAS AN ZUGAENGEN NOETIG IST

    SPOTIFY_CLIENT_ID       aus dem Developer-Portal
    SPOTIFY_CLIENT_SECRET   ebenda
    /srv/data/sarvis/spotify_token.json   entsteht bei der Anmeldung

Die Anmeldung laeuft einmal ueber den Browser (siehe netz/spotify.py);
danach haelt sich der Zugang mit dem Auffrischtoken selbst am Leben.

Ohne Client-ID werden diese Werkzeuge gar nicht erst gebaut -- lieber
keine als sechs, die nur "kein Zugang" sagen koennen. Das ist dieselbe
Entscheidung wie bei den Finanz-Werkzeugen.
"""
import json
import time

import httpx
from claude_agent_sdk import tool

from .. import config

API = "https://api.spotify.com/v1"
TOKEN_URL = "https://accounts.spotify.com/api/token"

# Was Sarvis darf. Bewusst nicht mehr: Kein Loeschen von Playlists, kein
# Folgen/Entfolgen, kein Zugriff auf die Bibliothek als Ganzes. Was er
# nicht braucht, soll er auch nicht duerfen -- ein Zugang, der weniger
# kann, ist im Verlustfall weniger wert.
RECHTE = " ".join((
    "user-read-playback-state",
    "user-modify-playback-state",
    "user-read-currently-playing",
    "playlist-read-private",
    "playlist-modify-private",
))

ZEITGRENZE = 15.0


def _token_datei():
    return config.DATEN / "spotify_token.json"


def zugang() -> tuple[str, str] | None:
    """(client_id, client_secret) aus der .env, oder None."""
    werte = config._env_werte()
    kennung = werte.get("SPOTIFY_CLIENT_ID")
    geheim = werte.get("SPOTIFY_CLIENT_SECRET")
    return (kennung, geheim) if kennung and geheim else None


def bereit() -> bool:
    """Zugangsdaten UND eine abgeschlossene Anmeldung."""
    return zugang() is not None and _token_datei().exists()


def _token_laden() -> dict:
    try:
        with _token_datei().open(encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _token_sichern(d: dict) -> None:
    datei = _token_datei()
    datei.parent.mkdir(parents=True, exist_ok=True)
    neben = datei.with_suffix(".json.neu")
    with neben.open("w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
    neben.chmod(0o600)
    neben.replace(datei)


def _frisches_token() -> str | None:
    """Ein gueltiges Zugriffstoken -- notfalls neu geholt.

    Spotify-Zugriffstoken gelten eine Stunde. Das Auffrischtoken bleibt
    dabei gueltig und wird NICHT ersetzt (anders als bei manchen anderen
    Diensten) -- deshalb ist hier auch kein Kopier-Problem moeglich wie
    bei der Claude-Anmeldung.
    """
    d = _token_laden()
    if not d:
        return None
    if d.get("laeuft_ab", 0) > time.time() + 60:
        return d.get("access_token")

    paar = zugang()
    auffrischen = d.get("refresh_token")
    if not paar or not auffrischen:
        return None
    kennung, geheim = paar
    try:
        with httpx.Client(timeout=ZEITGRENZE) as c:
            a = c.post(TOKEN_URL, data={
                "grant_type": "refresh_token",
                "refresh_token": auffrischen,
                "client_id": kennung,
                "client_secret": geheim,
            })
        if a.status_code != 200:
            return None
        neu = a.json()
    except httpx.HTTPError:
        return None
    d["access_token"] = neu.get("access_token")
    d["laeuft_ab"] = time.time() + int(neu.get("expires_in") or 3600)
    # Spotify schickt ein neues Auffrischtoken nur manchmal mit.
    if neu.get("refresh_token"):
        d["refresh_token"] = neu["refresh_token"]
    _token_sichern(d)
    return d["access_token"]


def _rufen(methode: str, weg: str, **args) -> tuple[int, dict]:
    """Ein API-Aufruf. (status, inhalt) -- inhalt notfalls leer."""
    token = _frisches_token()
    if not token:
        return 401, {}
    kopf = {"Authorization": f"Bearer {token}"}
    try:
        with httpx.Client(timeout=ZEITGRENZE) as c:
            a = c.request(methode, f"{API}{weg}", headers=kopf, **args)
        if a.status_code == 204 or not a.content:
            return a.status_code, {}
        return a.status_code, a.json()
    except (httpx.HTTPError, ValueError):
        return 0, {}


def _kein_geraet() -> dict:
    """Der haeufigste Fehlschlag, als Satz statt als Zahl.

    Spotify kann kein Geraet aufwecken, das aus ist. Wer "404" liest,
    sucht den Fehler bei Sarvis; wer diesen Satz hoert, macht Spotify
    auf und es geht.
    """
    return {"content": [{"type": "text", "text":
            "Es läuft gerade auf keinem Gerät Spotify. Mach es "
            "irgendwo auf — auf dem Rechner, dem Handy oder einer Box —, "
            "dann kann ich dort abspielen."}], "is_error": True}


def _dauer(ms) -> str:
    try:
        s = int(ms) // 1000
        return f"{s // 60}:{s % 60:02d}"
    except (TypeError, ValueError):
        return ""


def _titelzeile(t: dict) -> str:
    wer = ", ".join(k.get("name", "") for k in (t.get("artists") or []))
    return f"{t.get('name', '?')} von {wer}" if wer else t.get("name", "?")


def werkzeuge(protokoll, leuchten=None):

    def vermerken(was: str) -> None:
        if protokoll is not None:
            protokoll.merken(was)

    def leuchte() -> None:
        if leuchten:
            leuchten("Musik")

    # --- Was läuft ------------------------------------------------------

    @tool(
        "musik_laeuft",
        "Was gerade auf Spotify läuft: Titel, Interpret, Album, wie weit "
        "und auf welchem Gerät. Auch nützlich, um zu prüfen, ob überhaupt "
        "irgendwo Spotify offen ist.",
        {"type": "object", "properties": {}},
    )
    async def musik_laeuft(args):
        stand, d = _rufen("GET", "/me/player")
        leuchte()
        if stand == 204 or not d:
            return {"content": [{"type": "text", "text":
                    "Gerade läuft nichts."}]}
        if stand != 200:
            return _kein_geraet() if stand == 404 else {
                "content": [{"type": "text", "text":
                             "Spotify antwortet nicht."}], "is_error": True}
        t = d.get("item") or {}
        geraet = (d.get("device") or {}).get("name", "?")
        wo = _dauer(d.get("progress_ms"))
        ganz = _dauer(t.get("duration_ms"))
        laeuft = "läuft" if d.get("is_playing") else "pausiert"
        album = (t.get("album") or {}).get("name", "")
        return {"content": [{"type": "text", "text":
                f"{_titelzeile(t)}"
                + (f", vom Album {album}" if album else "")
                + f". {laeuft} auf {geraet}"
                + (f", bei {wo} von {ganz}" if wo and ganz else "") + "."}]}

    # --- Abspielen ------------------------------------------------------

    @tool(
        "musik_abspielen",
        "Etwas Bestimmtes auf Spotify abspielen. Sag, was gesucht werden "
        "soll — ein Titel, ein Album, ein Interpret oder eine Playlist. "
        "Ohne Suchbegriff wird die pausierte Wiedergabe fortgesetzt.",
        {
            "type": "object",
            "properties": {
                "was": {"type": "string",
                        "description": "z.B. 'Bohemian Rhapsody', "
                                       "'Album Random Access Memories', "
                                       "'Playlist Entspannen'"},
                "art": {"type": "string",
                        "enum": ["titel", "album", "interpret", "playlist"],
                        "description": "Was gesucht werden soll. Ohne "
                                       "Angabe: Titel."},
                "geraet": {"type": "string",
                           "description": "Optional: Name des Geräts, "
                                          "z.B. 'Wohnzimmer'"},
            },
        },
    )
    async def musik_abspielen(args):
        was = (args.get("was") or "").strip()
        leuchte()

        ziel_id = None
        if args.get("geraet"):
            stand, d = _rufen("GET", "/me/player/devices")
            gesucht = args["geraet"].strip().lower()
            for g in (d.get("devices") or []):
                if gesucht in (g.get("name") or "").lower():
                    ziel_id = g.get("id")
                    break
            if ziel_id is None:
                namen = ", ".join(g.get("name", "?")
                                  for g in (d.get("devices") or []))
                return {"content": [{"type": "text", "text":
                        f"Ein Gerät namens {args['geraet']} finde ich nicht."
                        + (f" Da sind: {namen}." if namen
                           else " Es ist gerade gar keines wach.")}],
                        "is_error": True}

        weg = "/me/player/play" + (f"?device_id={ziel_id}" if ziel_id else "")

        if not was:
            stand, _ = _rufen("PUT", weg)
            if stand == 404:
                return _kein_geraet()
            return {"content": [{"type": "text", "text": "Läuft wieder."}]}

        sorte = {"titel": "track", "album": "album",
                 "interpret": "artist", "playlist": "playlist"}.get(
                     args.get("art") or "titel", "track")
        stand, d = _rufen("GET", "/search",
                          params={"q": was, "type": sorte, "limit": 1})
        treffer = ((d.get(sorte + "s") or {}).get("items") or [])
        if not treffer:
            return {"content": [{"type": "text", "text":
                    f"Zu {was} finde ich nichts."}], "is_error": True}
        erster = treffer[0]

        # Ein einzelner Titel geht als "uris", alles andere als
        # "context_uri" -- Spotify unterscheidet das, und mit dem
        # falschen Feld passiert schlicht nichts.
        koerper = ({"uris": [erster["uri"]]} if sorte == "track"
                   else {"context_uri": erster["uri"]})
        stand, _ = _rufen("PUT", weg, json=koerper)
        if stand == 404:
            return _kein_geraet()
        if stand not in (200, 202, 204):
            return {"content": [{"type": "text", "text":
                    "Das Abspielen ging nicht. Braucht Spotify Premium?"}],
                    "is_error": True}

        name = (_titelzeile(erster) if sorte == "track"
                else erster.get("name", was))
        vermerken(f"musik_abspielen: {name}")
        return {"content": [{"type": "text", "text":
                f"Läuft: {name}"
                + (f" auf {args['geraet']}" if args.get("geraet") else "")
                + "."}]}

    # --- Steuern --------------------------------------------------------

    @tool(
        "musik_steuern",
        "Die laufende Spotify-Wiedergabe steuern: pausieren, fortsetzen, "
        "nächster oder vorheriger Titel, Lautstärke, Zufall, Wiederholen.",
        {
            "type": "object",
            "properties": {
                "was": {"type": "string",
                        "enum": ["pause", "weiter", "naechster", "vorheriger",
                                 "lauter", "leiser", "zufall_an", "zufall_aus",
                                 "wiederholen_an", "wiederholen_aus"]},
            },
            "required": ["was"],
        },
    )
    async def musik_steuern(args):
        was = args.get("was") or ""
        leuchte()

        if was in ("lauter", "leiser"):
            stand, d = _rufen("GET", "/me/player")
            jetzt = ((d.get("device") or {}).get("volume_percent")
                     if d else None)
            if jetzt is None:
                return _kein_geraet()
            neu = max(0, min(100, jetzt + (15 if was == "lauter" else -15)))
            stand, _ = _rufen("PUT", "/me/player/volume",
                              params={"volume_percent": neu})
            return {"content": [{"type": "text", "text":
                    f"Lautstärke auf {neu} Prozent."}]}

        weg, methode = {
            "pause":            ("/me/player/pause", "PUT"),
            "weiter":           ("/me/player/play", "PUT"),
            "naechster":        ("/me/player/next", "POST"),
            "vorheriger":       ("/me/player/previous", "POST"),
            "zufall_an":        ("/me/player/shuffle?state=true", "PUT"),
            "zufall_aus":       ("/me/player/shuffle?state=false", "PUT"),
            "wiederholen_an":   ("/me/player/repeat?state=context", "PUT"),
            "wiederholen_aus":  ("/me/player/repeat?state=off", "PUT"),
        }.get(was, (None, None))
        if weg is None:
            return {"content": [{"type": "text", "text":
                    f"{was} kenne ich nicht."}], "is_error": True}

        stand, _ = _rufen(methode, weg)
        if stand == 404:
            return _kein_geraet()
        if stand not in (200, 202, 204):
            return {"content": [{"type": "text", "text":
                    "Ging nicht."}], "is_error": True}
        return {"content": [{"type": "text", "text": "Erledigt."}]}

    # --- Geräte ---------------------------------------------------------

    @tool(
        "musik_geraete",
        "Welche Spotify-Geräte gerade wach sind und auf welchem die "
        "Wiedergabe läuft.",
        {"type": "object", "properties": {}},
    )
    async def musik_geraete(args):
        stand, d = _rufen("GET", "/me/player/devices")
        leuchte()
        geraete = d.get("devices") or []
        if not geraete:
            return {"content": [{"type": "text", "text":
                    "Es ist gerade kein Gerät wach."}]}
        zeilen = []
        for g in geraete:
            zeilen.append(g.get("name", "?")
                          + (" (aktiv)" if g.get("is_active") else ""))
        return {"content": [{"type": "text", "text":
                "Wach sind: " + ", ".join(zeilen) + "."}]}

    # --- Suchen ohne abzuspielen ---------------------------------------

    @tool(
        "musik_suchen",
        "Auf Spotify suchen, ohne etwas abzuspielen. Für Fragen wie "
        "'auf welchem Album ist das?' oder wenn mehrere Treffer zur "
        "Auswahl stehen sollen.",
        {
            "type": "object",
            "properties": {
                "was": {"type": "string"},
                "art": {"type": "string",
                        "enum": ["titel", "album", "interpret", "playlist"]},
                "anzahl": {"type": "integer",
                           "description": "Höchstens 10, Vorgabe 5"},
            },
            "required": ["was"],
        },
    )
    async def musik_suchen(args):
        sorte = {"titel": "track", "album": "album", "interpret": "artist",
                 "playlist": "playlist"}.get(args.get("art") or "titel",
                                             "track")
        wie_viele = max(1, min(10, int(args.get("anzahl") or 5)))
        stand, d = _rufen("GET", "/search",
                          params={"q": args.get("was") or "", "type": sorte,
                                  "limit": wie_viele})
        leuchte()
        treffer = ((d.get(sorte + "s") or {}).get("items") or [])
        if not treffer:
            return {"content": [{"type": "text", "text": "Nichts gefunden."}]}
        zeilen = []
        for t in treffer:
            if sorte == "track":
                album = (t.get("album") or {}).get("name", "")
                zeilen.append(_titelzeile(t)
                              + (f" (Album {album})" if album else ""))
            elif sorte == "album":
                wer = ", ".join(k.get("name", "")
                                for k in (t.get("artists") or []))
                zeilen.append(f"{t.get('name')} von {wer}")
            else:
                zeilen.append(t.get("name", "?"))
        return {"content": [{"type": "text", "text": "; ".join(zeilen) + "."}]}

    return [musik_laeuft, musik_abspielen, musik_steuern, musik_geraete,
            musik_suchen]
