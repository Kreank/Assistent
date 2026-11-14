"""Kalender und Ordner fuer die Seitenleiste der App (seit 14.11.2026).

Saschas Wunsch an die App: "den Google-Kalender mit drin, dass ich nicht
immer in meine Kalender-App wechseln muss" -- ansehen UND bearbeiten --
und "die Ordner strukturiert aufgelistet, zu denen Sarvis Zugang hat
(ich bin ein Mensch und sehe gerne visuell)".

Beides sind Handlungen des Menschen in seinen eigenen Sachen, wie das
Loeschen einer geplanten Aufgabe oder eines Gedaechtniseintrags: Sie
laufen mit dem Geraeteschluessel und ohne Rueckfrage, das Hirn ist nicht
beteiligt.

KALENDER

Derselbe Google-Zugang wie werkzeuge/google.py (dort _hole). Anders als
die Werkzeuge arbeitet die App mit der Termin-ID, nicht mit dem Titel:
Sie hat den Termin vor Augen, es muss nichts gesucht und nichts
zurueckgefragt werden.

ORDNER

Nur Namen, Groessen und Zeiten -- keine Inhalte. Welche Wurzeln es gibt
und was Sarvis dort darf, kommt aus orte.py/schutz.py selbst, nicht aus
einer zweiten Liste hier: Die Anzeige soll zeigen, was WIRKLICH gilt.
Wo Sarvis vor dem Hinsehen fragen muss (.ssh, .claude, das
Browserprofil ...), zeigt auch die App nicht hinein.

Vertrag: einsatz/DRAHT.md, Abschnitte "Kalender" und "Ordner".
"""
import asyncio
import logging
import os
from datetime import date, datetime, timedelta
from pathlib import Path

from aiohttp import web

from .. import config, schutz

log = logging.getLogger("sarvis.netz")

TAGE_MAX = 62
TERMINE_JE_KALENDER = 250
EINTRAEGE_MAX = 500


def _json(daten, status: int = 200) -> web.Response:
    return web.json_response(daten, status=status,
                             headers={"Cache-Control": "no-store"})


async def _koerper(anfrage: web.Request) -> dict:
    try:
        k = await anfrage.json()
    except Exception:
        return {}
    return k if isinstance(k, dict) else {}


# --- Kalender ---------------------------------------------------------------

async def _dienst():
    from ..werkzeuge import google
    if not google.bereit():
        return None
    return await google._hole("calendar", "v3")


def _kein_google() -> web.Response:
    return _json({"fehler": "Google ist nicht angemeldet"}, 503)


def _zeit_lesen(roh) -> datetime | None:
    """"2026-11-14T10:00" (Ortszeit) oder mit Versatz -> datetime mit Zone."""
    roh = str(roh or "").strip()
    if not roh:
        return None
    try:
        t = datetime.fromisoformat(roh.replace("Z", "+00:00"))
    except ValueError:
        return None
    return t.astimezone() if t.tzinfo else t.astimezone()


def _datum_lesen(roh) -> date | None:
    try:
        return date.fromisoformat(str(roh or "").strip()[:10])
    except ValueError:
        return None


def _ortszeit(roh) -> str:
    """Google antwortet teils in UTC ("...Z"); die App bekommt Ortszeit."""
    t = _zeit_lesen(roh)
    return t.isoformat(timespec="minutes") if t else str(roh or "")


def _termin_aus(e: dict, kal: dict) -> dict:
    """Ein Google-Termin in der Form, die die App bekommt.

    Ganztaegig: beginn/ende sind Daten (JJJJ-MM-TT), ende ist der LETZTE
    Tag (einschliesslich) -- Google zaehlt ihn ausschliesslich, und ein
    eintaegiger Termin vom 14. "bis zum 15." liest sich falsch.
    """
    s, z = e.get("start") or {}, e.get("end") or {}
    ganztags = "date" in s and "dateTime" not in s
    if ganztags:
        beginn = s.get("date", "")
        ende_d = _datum_lesen(z.get("date"))
        ende = ((ende_d - timedelta(days=1)).isoformat()
                if ende_d else beginn)
    else:
        beginn, ende = _ortszeit(s.get("dateTime")), _ortszeit(z.get("dateTime"))
    return {
        "id": e.get("id", ""),
        "kalender": kal["id"],
        "titel": e.get("summary") or "",
        "beginn": beginn,
        "ende": ende,
        "ganztags": ganztags,
        "ort": e.get("location") or "",
        "notiz": e.get("description") or "",
        "farbe": kal.get("farbe", ""),
        "serie": bool(e.get("recurringEventId")),
        "schreiben": kal.get("schreiben", False),
        "link": e.get("htmlLink") or "",
    }


async def _kalenderliste(dienst) -> list[dict]:
    from ..werkzeuge import google
    roh = await google._kalender_holen(dienst)
    raus = []
    for k in roh:
        raus.append({
            "id": k.get("id", ""),
            "name": k.get("summaryOverride") or k.get("summary") or "",
            "farbe": k.get("backgroundColor") or "",
            "haupt": bool(k.get("primary")),
            "schreiben": k.get("accessRole") in ("owner", "writer"),
            "sichtbar": bool(k.get("selected", k.get("primary"))),
        })
    raus.sort(key=lambda k: (not k["haupt"], k["name"].casefold()))
    return raus


def _zeitkoerper(k: dict, alt: dict | None = None) -> tuple[dict, str]:
    """start/end fuer Google aus dem, was die App schickt.

    Gibt (koerper, fehler) zurueck. Fehlt beginn ganz, bleibt der Koerper
    leer -- beim Aendern heisst das: Zeit unveraendert.
    """
    if "beginn" not in k and "ende" not in k and "ganztags" not in k:
        return {}, ""
    alt = alt or {}
    ganztags = bool(k.get("ganztags", alt.get("ganztags", False)))
    if ganztags:
        b = _datum_lesen(k.get("beginn", alt.get("beginn")))
        if b is None:
            return {}, "beginn muss JJJJ-MM-TT sein"
        e = _datum_lesen(k.get("ende")) or b
        if e < b:
            return {}, "ende liegt vor beginn"
        return {"start": {"date": b.isoformat(), "dateTime": None},
                "end": {"date": (e + timedelta(days=1)).isoformat(),
                        "dateTime": None}}, ""
    b = _zeit_lesen(k.get("beginn", alt.get("beginn")))
    if b is None:
        return {}, "beginn muss JJJJ-MM-TTTHH:MM sein"
    e = _zeit_lesen(k.get("ende"))
    if e is None:
        dauer = k.get("dauer_minuten")
        if dauer is None and alt.get("beginn") and alt.get("ende") \
                and not alt.get("ganztags"):
            # Nur der Beginn wurde verschoben: Dauer behalten.
            a0, a1 = _zeit_lesen(alt["beginn"]), _zeit_lesen(alt["ende"])
            dauer = int((a1 - a0).total_seconds() // 60) if a0 and a1 else 60
        try:
            dauer = max(5, min(int(dauer or 60), 7 * 1440))
        except (TypeError, ValueError):
            return {}, "dauer_minuten muss eine Zahl sein"
        e = b + timedelta(minutes=dauer)
    if e <= b:
        return {}, "ende liegt nicht nach beginn"
    return {"start": {"dateTime": b.isoformat(), "date": None},
            "end": {"dateTime": e.isoformat(), "date": None}}, ""


def _textfelder(k: dict) -> dict:
    koerper = {}
    for feld, google_feld in (("titel", "summary"), ("ort", "location"),
                              ("notiz", "description")):
        if feld in k:
            koerper[google_feld] = str(k.get(feld) or "")[:8000]
    return koerper


def kalender_routen(wer):
    """Die Kalender-Wege. `wer` prueft den Geraeteschluessel."""

    async def kalender(anfrage: web.Request) -> web.Response:
        if await wer(anfrage) is None:
            return _json({"fehler": "kein Zugang"}, 401)
        dienst = await _dienst()
        if dienst is None:
            return _kein_google()
        try:
            return _json({"kalender": await _kalenderliste(dienst)})
        except Exception as fehler:
            log.warning("kalender: %s", fehler)
            return _json({"fehler": "Google antwortet nicht"}, 502)

    async def termine(anfrage: web.Request) -> web.Response:
        if await wer(anfrage) is None:
            return _json({"fehler": "kein Zugang"}, 401)
        q = anfrage.query
        try:
            tage = max(1, min(int(q.get("tage") or 7), TAGE_MAX))
        except ValueError:
            return _json({"fehler": "tage muss eine Zahl sein"}, 400)
        if q.get("von"):
            d = _datum_lesen(q["von"])
            if d is None:
                return _json({"fehler": "von muss JJJJ-MM-TT sein"}, 400)
        else:
            d = date.today()
        von = datetime(d.year, d.month, d.day).astimezone()
        bis = von + timedelta(days=tage)
        dienst = await _dienst()
        if dienst is None:
            return _kein_google()
        try:
            alle = await _kalenderliste(dienst)
        except Exception as fehler:
            log.warning("termine: %s", fehler)
            return _json({"fehler": "Google antwortet nicht"}, 502)
        gewuenscht = [x for x in (q.get("kalender") or "").split(",") if x]
        if gewuenscht:
            auswahl = [k for k in alle if k["id"] in gewuenscht]
        else:
            auswahl = [k for k in alle if k["sichtbar"]]

        def holen_alle():
            # Nacheinander in EINEM Faden: Der Google-Dienst haengt an
            # httplib2, und das ist nicht threadsicher -- parallel kamen
            # alle drei Kalender als Fehler zurueck (gemessen 14.11.2026).
            raus = []
            for kal in auswahl:
                try:
                    raus.append(dienst.events().list(
                        calendarId=kal["id"], timeMin=von.isoformat(),
                        timeMax=bis.isoformat(), singleEvents=True,
                        orderBy="startTime", maxResults=TERMINE_JE_KALENDER,
                    ).execute())
                except Exception as f:
                    log.warning("termine %s: %s", kal["name"], f)
                    raus.append(f)
            return raus

        ergebnisse = await asyncio.to_thread(holen_alle)
        liste, fehler = [], []
        for kal, erg in zip(auswahl, ergebnisse):
            if isinstance(erg, Exception):
                fehler.append(kal["name"])
                continue
            liste += [_termin_aus(e, kal) for e in erg.get("items", [])
                      if e.get("status") != "cancelled"]

        def ordnung(t):
            # Ganztaegige zuerst am Tag, dann nach Uhrzeit.
            return (t["beginn"][:10], not t["ganztags"], t["beginn"])
        liste.sort(key=ordnung)
        return _json({"von": von.date().isoformat(),
                      "bis": (bis - timedelta(days=1)).date().isoformat(),
                      "termine": liste, "nicht_erreicht": fehler})

    async def _kal_finden(dienst, kennung: str):
        alle = await _kalenderliste(dienst)
        if not kennung or kennung == "primary":
            return next((k for k in alle if k["haupt"]), None)
        return next((k for k in alle if k["id"] == kennung), None)

    async def anlegen(anfrage: web.Request) -> web.Response:
        geraet = await wer(anfrage)
        if geraet is None:
            return _json({"fehler": "kein Zugang"}, 401)
        k = await _koerper(anfrage)
        titel = str(k.get("titel") or "").strip()
        if not titel:
            return _json({"fehler": "titel fehlt"}, 400)
        if "beginn" not in k:
            return _json({"fehler": "beginn fehlt"}, 400)
        zeit, fehler = _zeitkoerper(k)
        if fehler:
            return _json({"fehler": fehler}, 400)
        dienst = await _dienst()
        if dienst is None:
            return _kein_google()
        kal = await _kal_finden(dienst, str(k.get("kalender") or ""))
        if kal is None:
            return _json({"fehler": "diesen Kalender gibt es nicht"}, 404)
        if not kal["schreiben"]:
            return _json({"fehler": "in diesen Kalender darf man nicht "
                                    "schreiben"}, 403)
        koerper = {**_textfelder(k), **_ohne_none(zeit)}
        try:
            neu = await asyncio.to_thread(
                lambda: dienst.events().insert(calendarId=kal["id"],
                                               body=koerper).execute())
        except Exception as f:
            log.warning("termin anlegen: %s", f)
            return _json({"fehler": "Google hat abgelehnt"}, 502)
        log.info("termin %r angelegt von %s", titel, geraet)
        return _json({"gut": True, "termin": _termin_aus(neu, kal)})

    async def aendern(anfrage: web.Request) -> web.Response:
        geraet = await wer(anfrage)
        if geraet is None:
            return _json({"fehler": "kein Zugang"}, 401)
        k = await _koerper(anfrage)
        kennung = str(k.get("id") or "")
        if not kennung:
            return _json({"fehler": "id fehlt"}, 400)
        dienst = await _dienst()
        if dienst is None:
            return _kein_google()
        kal = await _kal_finden(dienst, str(k.get("kalender") or ""))
        if kal is None:
            return _json({"fehler": "diesen Kalender gibt es nicht"}, 404)
        if not kal["schreiben"]:
            return _json({"fehler": "in diesen Kalender darf man nicht "
                                    "schreiben"}, 403)
        try:
            alt_roh = await asyncio.to_thread(
                lambda: dienst.events().get(calendarId=kal["id"],
                                            eventId=kennung).execute())
        except Exception:
            return _json({"fehler": "diesen Termin gibt es nicht"}, 404)
        zeit, fehler = _zeitkoerper(k, _termin_aus(alt_roh, kal))
        if fehler:
            return _json({"fehler": fehler}, 400)
        # patch statt update: Eingeladene, Erinnerungen, Farbe bleiben.
        koerper = {**_textfelder(k), **zeit}
        if not koerper:
            return _json({"gut": True, "termin": _termin_aus(alt_roh, kal)})
        try:
            neu = await asyncio.to_thread(
                lambda: dienst.events().patch(calendarId=kal["id"],
                                              eventId=kennung,
                                              body=koerper).execute())
        except Exception as f:
            log.warning("termin aendern: %s", f)
            return _json({"fehler": "Google hat abgelehnt"}, 502)
        log.info("termin %s geaendert von %s", kennung, geraet)
        return _json({"gut": True, "termin": _termin_aus(neu, kal)})

    async def loeschen(anfrage: web.Request) -> web.Response:
        geraet = await wer(anfrage)
        if geraet is None:
            return _json({"fehler": "kein Zugang"}, 401)
        k = await _koerper(anfrage)
        kennung = str(k.get("id") or "")
        if not kennung:
            return _json({"fehler": "id fehlt"}, 400)
        dienst = await _dienst()
        if dienst is None:
            return _kein_google()
        kal = await _kal_finden(dienst, str(k.get("kalender") or ""))
        if kal is None:
            return _json({"fehler": "diesen Kalender gibt es nicht"}, 404)
        if not kal["schreiben"]:
            return _json({"fehler": "in diesem Kalender darf man nicht "
                                    "löschen"}, 403)
        try:
            await asyncio.to_thread(
                lambda: dienst.events().delete(calendarId=kal["id"],
                                               eventId=kennung).execute())
        except Exception:
            return _json({"fehler": "diesen Termin gibt es nicht"}, 404)
        log.info("termin %s geloescht von %s", kennung, geraet)
        return _json({"gut": True})

    return kalender, termine, anlegen, aendern, loeschen


def _ohne_none(zeit: dict) -> dict:
    """Beim Anlegen braucht Google keine leeren Gegenstuecke."""
    return {seite: {k: v for k, v in teil.items() if v is not None}
            for seite, teil in zeit.items()}


# --- Ordner -----------------------------------------------------------------

def wurzeln() -> list[dict]:
    """Die Orte, an die Sarvis kommt -- mit dem, was er dort darf.

    Die Stufen kommen aus schutz.py: "frei" (ohne Rueckfrage), "fragen"
    (er fragt vorher). Was gar nicht geht, steht hier nicht.
    """
    orte = [
        ("Projekte", config.PROJEKT_ORTE["arbeit"],
         "Alle Projekte auf dem Server"),
        ("Benutzerordner", config.PROJEKT_ORTE["privat"],
         "Dein Ordner auf dem Server"),
        ("Sandkasten", config.PROJEKTE,
         "Sarvis' eigene Projekte, hier baut er frei"),
        ("Erzeugt", config.ABLAGE,
         "Berichte, Seiten und Dateien, die Sarvis gemacht hat"),
        ("Eingang", config.EINGANG,
         "Was du Sarvis geschickt hast"),
        ("Sarvis' Daten", config.DATEN,
         "Gedächtnis, Gespräche, Einstellungen"),
    ]
    handbuch = Path("/opt/handbuch")
    if handbuch.is_dir():
        orte.append(("Handbuch", handbuch,
                     "Anleitungen für Sarvis' Arbeiter, nur lesen"))
    raus = []
    for name, pfad, beschreibung in orte:
        p = Path(pfad)
        if not p.is_dir():
            continue
        probe = str(p / "neue-datei")
        raus.append({
            "name": name, "pfad": str(p), "beschreibung": beschreibung,
            "darf": {"lesen": schutz.lesen_stufe(str(p)),
                     "schreiben": schutz.schreiben_stufe(probe),
                     "durchsuchen": schutz.durchsuchen_stufe(str(p))},
        })
    return raus


def _wurzel_von(p: Path, alle: list[dict]) -> dict | None:
    """Die ENGSTE Wurzel, unter der p liegt (Sandkasten vor Sarvis' Daten)."""
    passend = []
    for w in alle:
        wp = Path(w["pfad"]).resolve()
        if p == wp or wp in p.parents:
            passend.append((len(wp.parts), w))
    return max(passend, key=lambda t: t[0])[1] if passend else None


def _auflisten(pfad_roh: str) -> tuple[dict, int]:
    alle = wurzeln()
    try:
        p = Path(pfad_roh).resolve()
    except (OSError, ValueError):
        return {"fehler": "ungültiger Pfad"}, 400
    wurzel = _wurzel_von(p, alle)
    if wurzel is None:
        return {"fehler": "dieser Ort gehört nicht zu Sarvis' Ordnern"}, 403
    if schutz.auflisten_stufe(str(p)) != "frei":
        return {"fehler": "hier sieht Sarvis nur nach Rückfrage hinein"}, 403
    if not p.is_dir():
        return {"fehler": "diesen Ordner gibt es nicht"}, 404
    try:
        kinder = list(os.scandir(p))
    except OSError:
        return {"fehler": "der Ordner lässt sich nicht lesen"}, 403
    eintraege = []
    for d in kinder:
        voll = os.path.join(p, d.name)
        stufe = schutz.auflisten_stufe(voll)
        if stufe == "nie":
            continue
        try:
            ist_ordner = d.is_dir()
            st = d.stat()
            groesse, zeit = (0 if ist_ordner else st.st_size), st.st_mtime
        except OSError:
            ist_ordner, groesse, zeit = False, 0, 0
        eintraege.append({
            "name": d.name, "pfad": voll, "ordner": ist_ordner,
            "bytes": groesse, "geaendert": zeit,
            "versteckt": d.name.startswith("."),
            "verknuepfung": d.is_symlink(),
            # Hier fragt Sarvis vorher -- die App zeigt den Namen, oeffnet
            # aber nicht (und /ordner verweigert es ohnehin).
            "geschuetzt": stufe != "frei" or (not ist_ordner
                                              and schutz.heikel(voll)),
        })
    eintraege.sort(key=lambda e: (not e["ordner"], e["versteckt"],
                                  e["name"].casefold()))
    mehr = len(eintraege) > EINTRAEGE_MAX
    wp = Path(wurzel["pfad"]).resolve()
    return {"pfad": str(p), "wurzel": wurzel["name"],
            "oben": None if p == wp else str(p.parent),
            "darf": wurzel["darf"],
            "eintraege": eintraege[:EINTRAEGE_MAX], "mehr": mehr}, 200


def ordner_route(wer):
    async def ordner(anfrage: web.Request) -> web.Response:
        if await wer(anfrage) is None:
            return _json({"fehler": "kein Zugang"}, 401)
        pfad = anfrage.query.get("pfad", "").strip()
        if not pfad:
            return _json({"wurzeln": await asyncio.to_thread(wurzeln)})
        daten, status = await asyncio.to_thread(_auflisten, pfad)
        return _json(daten, status)
    return ordner


def anmelden(app: web.Application, wer) -> None:
    kalender, termine, anlegen, aendern, loeschen = kalender_routen(wer)
    app.router.add_get("/kalender", kalender)
    app.router.add_get("/termine", termine)
    app.router.add_post("/termin/anlegen", anlegen)
    app.router.add_post("/termin/aendern", aendern)
    app.router.add_post("/termin/loeschen", loeschen)
    app.router.add_get("/ordner", ordner_route(wer))
