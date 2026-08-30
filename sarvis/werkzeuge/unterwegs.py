# -*- coding: utf-8 -*-
"""Verkehr und Spritpreise -- was zaehlt, solange der Motor laeuft.

WARUM DAS EIN EIGENES MODUL IST

Sascha faehrt jeden Tag zu Baustellen. Was er unterwegs wissen will, ist
schmal und immer dasselbe: Steht auf meiner Autobahn etwas? Und wo tanke
ich guenstig? Beides kommt aus amtlichen Quellen, beide antworten in
Sekunden, und beide sind reines Lesen -- deshalb liegen sie zusammen und
laufen ohne Rueckfrage durch.

Zwei Quellen, zwei ganz verschiedene Bedingungen:

    Autobahn GmbH des Bundes    offen, ohne Schluessel, ohne Grenze
    Tankerkoenig (Bundeskartellamt)  Schluessel noetig, eine Anfrage/Minute

Deswegen wird das eine immer gebaut und das andere nur, wenn der
Schluessel da ist -- dieselbe Entscheidung wie bei Spotify und Finanzen.

ES WIRD IM AUTO GEHOERT, NICHT GELESEN

Das ist die eigentliche Arbeit hier, nicht das Abrufen. Die Autobahn-API
liefert fuer die A2 an einem ruhigen Abend 87 Baustellen und dazu jede
Meldung dreimal als Text, als Symbolkette und als Linienzug. Wer das
vorliest, hat nach der vierten Baustelle einen Fahrer verloren, der
nichts mehr mitbekommt.

Also wird hier zusammengefasst, und zwar nach dem, was am Steuer zaehlt:

    1. Nach Richtung getrennt. Ein Stau auf der Gegenfahrbahn ist keine
       Nachricht. Die API trennt das sauber im Feld `subtitle`.
    2. Das Schlimmste zuerst -- gesperrt vor Stillstand vor zaeh, und
       innerhalb dessen nach Zeitverlust.
    3. Hoechstens zwei Meldungen je Richtung im Klartext, der Rest als
       Zahl. "Und vier weitere" ist eine brauchbare Information; vier
       weitere Ortsnamen sind es nicht.

Was daraus faellt, faellt bewusst: Koordinaten, Linienzuege,
Symbolketten, die Bauphasen-Nummern der Autobahnmeisterei.

WAS ES NICHT GIBT UND WARUM

Webcams stehen in der API, sind aber leer -- auf A1, A2, A7, A9 und A99
nachgemessen, ueberall null Eintraege. Ein Werkzeug, das nie etwas
findet, ist schlechter als keins.

Ladesaeulen stehen ebenfalls drin und haben brauchbare Daten. Nur faehrt
Sascha einen Diesel-Transporter, und ohne Standort liesse sich die Liste
nicht einmal nach Naehe sortieren -- es kaeme eine alphabetische
Aufzaehlung von 27 Rastplaetzen heraus. Kommt ein E-Fahrzeug, ist das in
zwanzig Zeilen nachgebaut; vorher waere es Ballast.

WOHER DIE KOORDINATEN KOMMEN

Tankerkoenig will Laenge und Breite, Sarvis hat kein GPS und Sascha
sagt "in Sarstedt". Dazwischen steht Nominatim (OpenStreetMap), einmal
je Ort und danach gemerkt. Bewusst nicht das Modell raten lassen: Eine
halluzinierte Koordinate liefert klaglos Tankstellen -- nur eben die
falschen, und man merkt es nie.

WAS AN ZUGAENGEN NOETIG IST

    TANKERKOENIG_KEY   aus der .env, kostenlos beantragt bei
                       tankerkoenig.de

Ohne diesen Schluessel werden die beiden Tank-Werkzeuge gar nicht erst
gebaut. Die Autobahn-Werkzeuge laufen davon unberuehrt weiter.

DIE AUFLAGEN VON TANKERKOENIG SIND KEINE BITTE

Hoechstens 25 km Radius, hoechstens eine Anfrage je Minute, und die
Quelle muss genannt werden. Wer das reisst, verliert den Schluessel.
Deshalb steht die Minutensperre hier als Code und nicht als Kommentar:
Der Radius wird hart gedeckelt, und eine zweite Anfrage innerhalb der
Minute kommt gar nicht erst hinaus -- entweder aus dem Zwischenspeicher
beantwortet, wenn es dieselbe Frage war, oder abgelehnt mit der
Restzeit. Ein Assistent, der auf Zuruf reagiert, wird sonst zwangslaeufig
mehrfach in derselben Minute gefragt.
"""
import re
import time

import httpx
from claude_agent_sdk import tool

from .. import config

# --- Autobahn GmbH des Bundes --------------------------------------------
# Offene Daten, kein Schluessel, keine Registrierung, keine Grenze.
AUTOBAHN = "https://verkehr.autobahn.de/o/autobahn"

# --- Tankerkoenig ---------------------------------------------------------
TANKER = "https://creativecommons.tankerkoenig.de/json"
TANKER_SCHLUESSEL_NAME = "TANKERKOENIG_KEY"

# Auflage des Betreibers: hoechstens 25 km. Wird gedeckelt, nicht geprueft
# -- eine Fehlermeldung waere hier nur laestig, der Nutzer meint es ja gut.
TANKER_RADIUS_MAX = 25.0

# Auflage des Betreibers: hoechstens eine Anfrage je Minute.
TANKER_ABSTAND = 60.0

# --- Nominatim ------------------------------------------------------------
NOMINATIM = "https://nominatim.openstreetmap.org/search"
# Nominatim verlangt eine erkennbare Kennung; anonyme Anfragen werden
# gesperrt. Das ist deren Nutzungsbedingung, kein Hoeflichkeitsakt.
NOMINATIM_KENNUNG = "Sarvis-Sprachassistent/1.0 (privat, geringe Last)"

ZEITGRENZE = 15.0

# Wie viele Richtungen und wie viele Meldungen je Richtung im Klartext
# vorkommen. Alles Weitere wird gezaehlt. Siehe Modulkopf.
#
# Diese beiden Zahlen sind das ganze Nadeloehr: 3 mal 2 sind sechs
# Meldungen, also drei bis vier gesprochene Saetze. Beim ersten Bau
# standen sie nicht da, und die A7 kam mit siebzehn Richtungen und
# zweiundzwanzig Ortsnamen zurueck -- unhoerbar.
MAX_RICHTUNGEN = 3
JE_RICHTUNG = 2


def schluessel():
    """Der Tankerkoenig-Schluessel aus der .env, oder None."""
    return config._env_werte().get(TANKER_SCHLUESSEL_NAME)


def bereit() -> bool:
    """Ob die Tank-Werkzeuge gebaut werden koennen.

    Die Autobahn-Werkzeuge haengen NICHT daran -- die brauchen keinen
    Zugang und werden immer gebaut.
    """
    return bool(schluessel())


# --- Abrufen --------------------------------------------------------------

def _holen(url: str, params: dict | None = None,
           kopf: dict | None = None) -> tuple[int, dict]:
    """Ein GET. (status, inhalt) -- inhalt notfalls leer.

    Kein Aufruf hier darf ein Gespraech anhalten: Jeder Fehlschlag, vom
    Namensaufloeser bis zum kaputten JSON, kommt als (0, {}) zurueck und
    wird oben zu einem Satz. Ein haengender Verkehrsserver ist kein
    Grund, Sarvis mitten im Reden zu blockieren.
    """
    try:
        with httpx.Client(timeout=ZEITGRENZE, follow_redirects=True) as c:
            a = c.get(url, params=params, headers=kopf or {})
        if not a.content:
            return a.status_code, {}
        return a.status_code, a.json()
    except (httpx.HTTPError, ValueError):
        return 0, {}


# --- Autobahnnamen --------------------------------------------------------

_strassen_liste: list[str] = []


def _strassen() -> list[str]:
    """Alle Autobahnen, die die API kennt. Einmal geholt, dann gemerkt.

    Dient nur der Fehlermeldung: Ohne die Liste antwortet die API auf
    eine erfundene Autobahn mit einer leeren Menge, und Sarvis sagt
    froehlich "auf der A4711 ist alles frei". Mit der Liste sagt er, dass
    es die Autobahn nicht gibt.
    """
    global _strassen_liste
    if not _strassen_liste:
        stand, d = _holen(f"{AUTOBAHN}/")
        if stand == 200:
            _strassen_liste = [s.strip() for s in (d.get("roads") or [])]
    return _strassen_liste


def _strasse(text: str) -> str | None:
    """"die A 2", "Autobahn 2", "a2" -> "A2". Sonst None.

    Gesprochen kommt so gut wie nie ein sauberes "A2" an. Der Buchstabe
    hinten ist echt: Die API kennt A99a und A64a.
    """
    treffer = re.search(r"(\d{1,3})\s*([a-zA-Z])?", text or "")
    if not treffer:
        return None
    name = "A" + treffer.group(1) + (treffer.group(2) or "").lower()
    liste = _strassen()
    if liste and name not in liste:
        return None
    return name


# --- Meldungen zurechtlegen ----------------------------------------------

def _echte_richtung(eintrag: dict) -> bool:
    """Ob `subtitle` eine Fahrtrichtung ist -- und keine Rampe.

    Die API benutzt dasselbe Feld fuer zweierlei: "Magdeburg ->
    Braunschweig" ist eine Fahrtrichtung, "AS Bornstedt (aus Richtung
    Börde)" ist eine einzelne Auf- oder Abfahrt. Der Pfeil trennt beides
    zuverlaessig.

    Der Unterschied ist nicht kosmetisch: Ohne ihn bekommt jede gesperrte
    Rampe ihre eigene "Richtung", und die A7 antwortete mit siebzehn
    davon. Rampen werden deshalb nur noch gezaehlt -- wer eine bestimmte
    Abfahrt braucht, fragt gezielt nach dem Abschnitt.
    """
    return "->" in (eintrag.get("subtitle") or "")


def _richtung(eintrag: dict) -> str:
    """" Magdeburg -> Braunschweig" -> "Magdeburg Richtung Braunschweig".

    Der Pfeil ist ungesprochen. Und das fuehrende Leerzeichen kommt so
    aus der API -- bei jedem Eintrag.
    """
    roh = (eintrag.get("subtitle") or "").strip()
    if not roh:
        return "ohne Richtungsangabe"
    return " ".join(roh.replace("->", "Richtung").split())


def _kurz(text: str, laenge: int = 45) -> str:
    """Baustellennamen auf Hoerlaenge stutzen.

    Die Autobahnmeisterei schreibt in den Titel, was sie fuer ihre Akte
    braucht: "A2, Fahrbahnerhaltung zw. AS Brandenburg und LG BB ST (km
    18,390-44,200), beide FR". Ein Abschnitt davon reicht fuers Ohr;
    Kilometrierung und Massnahmennummer helfen niemandem am Steuer.

    Klammern fliegen zuerst raus, und zwar vor dem Zerlegen: In ihnen
    steckt die Kilometrierung, und die enthaelt selbst Kommata ("(km
    18,390-44,200)"). Wer erst zerlegt, schneidet mitten in der Klammer
    ab.

    Und der erste Abschnitt ist oft nur die Autobahn selbst -- in einer
    Antwort ueber die A2 die nutzloseste aller Ortsangaben. Dann zaehlt
    der naechste.
    """
    ohne_klammern = re.sub(r"\s*\([^)]*\)", "", text)
    stuecke = [s.strip() for s in ohne_klammern.split(",") if s.strip()]
    vorn = next((s for s in stuecke
                 if not re.fullmatch(r"A\s?\d{1,3}[a-zA-Z]?", s)), "")
    if not vorn:
        vorn = stuecke[0] if stuecke else text.strip()
    if len(vorn) > laenge:
        vorn = vorn[:laenge].rsplit(" ", 1)[0]
    return vorn


def _ort(eintrag: dict) -> str:
    """"A2 | Bornstedt - Lorkberg" -> "zwischen Bornstedt und Lorkberg".

    Manche Eintraege heissen nur "A2 | Verkehrsmeldung" -- da steht kein
    Ort drin, und dann ist Schweigen besser als das Wort.
    """
    roh = (eintrag.get("title") or "")
    teil = roh.split("|", 1)[1].strip() if "|" in roh else roh.strip()
    if not teil or teil.lower() in ("verkehrsmeldung", "undefined"):
        return ""
    if " - " in teil:
        von, bis = _kurz(teil.split(" - ", 1)[0]), _kurz(
            teil.split(" - ", 1)[1])
        # Die API nennt gelegentlich zweimal denselben Anschluss --
        # "zwischen Bad Reichenhall und Bad Reichenhall" klingt kaputt.
        return f"bei {von}" if von == bis else f"zwischen {von} und {bis}"
    return f"bei {_kurz(teil, 60)}"


# Die Ereignisworte, die die API in den Aufzaehlungspunkten benutzt.
EREIGNISSE = {
    "im stillstand": "Stillstand",
    "stockender verkehr": "stockender Verkehr",
    "zähfließender verkehr": "zäher Verkehr",
    "unfall": "Unfall",
    "gefahr": "Gefahrenstelle",
}


def _art(eintrag: dict) -> str:
    """Die Art der Meldung, wie ein Mensch sie sagen wuerde.

    Zwei Stellen im Datensatz taugen dafuer. Die eine ist die Zeile
    "Unfall, seit 30.08.2026, 16:31" -- brauchbar, ausser sie sagt
    "Angespannte Verkehrslage": Das ist die Sammelvokabel der API und
    steht ueber Stillstand genauso wie ueber leichtem Zaehfliessen. Dann
    zaehlt die zweite Stelle, die Aufzaehlung unter "Ereignismeldung:",
    wo "- Im Stillstand" oder "- Stockender Verkehr" steht.

    Die Maschinencodes daneben (`UNSPECIFIED_ABNORMAL_TRAFFIC`) bleiben
    der letzte Rueckfall -- sie sind grober als beide Texte.

    Die Zeitangaben aus dem Text werden NICHT uebernommen. Dieselbe
    Meldung nennt in `description` "Beginn: 19:07 Uhr" und zwei Zeilen
    tiefer "seit 17:07" -- die API widerspricht sich in sich selbst. Was
    stimmt, ist nicht entscheidbar, also wird es weggelassen; der
    Zeitverlust in Minuten sagt ohnehin mehr.
    """
    if (eintrag.get("display_type") or "") == "CLOSURE":
        return "gesperrt"

    zeilen = [(z or "").strip() for z in (eintrag.get("description") or [])]
    for zeile in zeilen:
        if zeile.startswith("- "):
            wort = EREIGNISSE.get(zeile[2:].strip().lower())
            if wort:
                return wort
    for zeile in zeilen[:5]:
        if "," in zeile and " seit " in zeile.lower():
            wort = zeile.split(",")[0].strip()
            if wort and not wort.lower().startswith("angespannte"):
                return wort
    grob = {
        "STATIONARY_TRAFFIC": "Stillstand",
        "QUEUING_TRAFFIC": "stockender Verkehr",
        "SLOW_TRAFFIC": "zäher Verkehr",
    }
    return grob.get(eintrag.get("abnormalTrafficType") or "",
                    "angespannte Lage")


def _verlust(eintrag: dict) -> int:
    try:
        return int(eintrag.get("delayTimeValue") or 0)
    except (TypeError, ValueError):
        return 0


def _gesperrt(eintrag: dict) -> bool:
    """Ob wirklich zu ist.

    `isBlocked` kommt als Zeichenkette "false", nicht als Wahrheitswert
    -- ein blosses `if eintrag["isBlocked"]` waere immer wahr. Der
    display_type CLOSURE zaehlt mit, weil Sperrungen dort das Feld
    haeufig auf "false" stehen lassen.
    """
    if str(eintrag.get("isBlocked", "")).lower() == "true":
        return True
    return (eintrag.get("display_type") or "") == "CLOSURE"


def _schwere(eintrag: dict) -> tuple:
    """Sortierschluessel: gesperrt zuerst, dann nach Zeitverlust."""
    stillstand = (eintrag.get("abnormalTrafficType") or "") in (
        "STATIONARY_TRAFFIC", "QUEUING_TRAFFIC")
    return (_gesperrt(eintrag), stillstand, _verlust(eintrag))


def _passt(eintrag: dict, suche: str) -> bool:
    """Ob eine Meldung zu einem genannten Abschnitt gehoert.

    Grob mit Absicht: "bei Hannover" soll auch das Kreuz Hannover-Ost und
    die Richtungsangabe treffen. Zu streng waere hier schlimmer als zu
    weit -- eine Meldung zu viel kostet einen Halbsatz, eine fehlende
    kostet eine Stunde im Stau.
    """
    if not suche:
        return True
    heuhaufen = " ".join([
        eintrag.get("title") or "",
        eintrag.get("subtitle") or "",
        " ".join(eintrag.get("description") or []),
    ]).lower()
    return all(w in heuhaufen for w in suche.lower().split())


def _entdoppeln(eintraege: list[dict]) -> list[dict]:
    """Dieselbe Stelle kommt mehrfach.

    Die API zerlegt eine Massnahme in Bauphasen und liefert jede als
    eigenen Eintrag -- mit identischem Titel und identischer Richtung.
    Vorgelesen klingt das wie ein Aussetzer ("zwischen Braunschweig-Hafen
    und Peine-Ost; zwischen Braunschweig-Hafen und Peine-Ost").

    Die Art der Meldung gehoert bewusst NICHT zum Merkmal: Dieselbe
    Stelle steht oft einmal als ROADWORKS und einmal als
    SHORT_TERM_ROADWORKS drin, und in der Verkehrslage einmal als
    Sperrung und einmal als Stau. Der Aufrufer sortiert die schwerere
    Sicht nach vorn; die gewinnt dann.
    """
    gesehen = set()
    raus = []
    for e in eintraege:
        merkmal = (e.get("title"), e.get("subtitle"))
        if merkmal in gesehen:
            continue
        gesehen.add(merkmal)
        raus.append(e)
    return raus


def _aufteilen(eintraege: list[dict]) -> tuple[list[dict], int]:
    """(Meldungen auf der Strecke, Anzahl an Auf- und Abfahrten).

    Siehe _echte_richtung: Rampen kommen nur noch als Zahl vor.
    """
    sauber = _entdoppeln(eintraege)
    strecke = [e for e in sauber if _echte_richtung(e)]
    return strecke, len(sauber) - len(strecke)


def _gruppieren(eintraege: list[dict], rang) -> list[tuple[str, list[dict]]]:
    """Nach Richtung, die schwerste Richtung zuerst.

    `rang` entscheidet, was schwer heisst -- bei Staus der Zeitverlust,
    bei Baustellen die weggenommene Spur. Deshalb wird es hereingereicht
    und steht nicht fest.
    """
    nach_richtung: dict[str, list[dict]] = {}
    for e in eintraege:
        nach_richtung.setdefault(_richtung(e), []).append(e)
    for liste in nach_richtung.values():
        liste.sort(key=rang, reverse=True)
    return sorted(nach_richtung.items(),
                  key=lambda p: rang(p[1][0]), reverse=True)


def _satz(eintrag: dict) -> str:
    """Eine Meldung als ein sprechbarer Halbsatz."""
    teile = [_art(eintrag)]
    wo = _ort(eintrag)
    if wo:
        teile.append(wo)
    minuten = _verlust(eintrag)
    if minuten >= 5:
        teile.append(f"{minuten} Minuten Zeitverlust")
    return ", ".join(teile)


def _bauen(gruppen, beschreiben, wort_eins: str, wort_viele: str) -> str:
    """Der ganze Zweck dieses Moduls in einer Funktion.

    Aus einer beliebig langen Meldungsliste werden drei bis vier Saetze:
    hoechstens drei Richtungen, darin je hoechstens zwei Meldungen im
    Klartext, alles Weitere als Zahl. Siehe Modulkopf, Abschnitt "Es wird
    im Auto gehoert".
    """
    stuecke = []
    for richtung, liste in gruppen[:MAX_RICHTUNGEN]:
        # Ein zweites Mal entdoppeln, jetzt am fertigen Halbsatz: Zwei
        # Bauphasen mit verschieden nummerierten Titeln ueberleben die
        # erste Runde, ergeben aber denselben gesprochenen Satz. Zweimal
        # dasselbe zu hoeren klingt nach Aussetzer, nicht nach zwei
        # Baustellen.
        saetze = []
        for e in liste:
            satz = beschreiben(e)
            if satz not in saetze:
                saetze.append(satz)
        vorn = saetze[:JE_RICHTUNG]
        rest = len(saetze) - len(vorn)
        if rest == 1:
            vorn.append(f"dazu {wort_eins}")
        elif rest > 1:
            vorn.append(f"dazu {rest} {wort_viele}")
        stuecke.append(f"{richtung}: " + "; ".join(vorn))

    uebrig = gruppen[MAX_RICHTUNGEN:]
    if uebrig:
        weitere = sum(len(l) for _, l in uebrig)
        stuecke.append(f"In {len(uebrig)} weiteren Fahrtrichtungen "
                       f"{weitere} {wort_viele}")
    return ". ".join(stuecke)


def _laenge(eintrag: dict) -> float:
    """Die Baustellenlaenge in km aus dem Beschreibungstext.

    Steht nur als Fliesstext da ("Länge: 2.17 km"), es gibt kein Feld
    dafuer. Manchmal steht dort auch "konnte nicht ermittelt werden" --
    dann ist es null und die Baustelle rutscht nach hinten, was richtig
    ist: Wer keine Laenge kennt, hat meist auch keine grosse.
    """
    for zeile in (eintrag.get("description") or []):
        treffer = re.search(r"Länge:\s*([\d.,]+)\s*km", zeile or "")
        if treffer:
            try:
                return float(treffer.group(1).replace(",", "."))
            except ValueError:
                return 0.0
    return 0.0


def _spur_zu(eintrag: dict) -> bool:
    """Ob die Baustelle wirklich eine Spur wegnimmt.

    Das entscheidet, ob es stockt. Die API sagt es nur ueber die
    Symbolkette, mit der sie das Fahrstreifenbild zeichnet.
    """
    symbole = ((eintrag.get("impact") or {}).get("symbols") or [])
    return "CLOSED" in symbole


# --- Tankerkoenig: Sperre und Zwischenspeicher ----------------------------

_letzte_anfrage = 0.0
_gemerkt: dict[str, tuple[float, dict]] = {}


def _tanker(weg: str, params: dict) -> tuple[dict | None, str]:
    """Eine Tankerkoenig-Anfrage -- oder eben keine. (daten, hinweis)

    Hier steckt die Minutensperre. Drei Faelle, in dieser Reihenfolge:

    1. Dieselbe Frage kam innerhalb der Minute schon: Die gespeicherte
       Antwort geht zurueck. Spritpreise aendern sich nicht im
       Sekundentakt, und "frag in 40 Sekunden nochmal" waere hier eine
       Frechheit gegenueber jemandem, der nur nachgehakt hat.
    2. Eine ANDERE Frage innerhalb der Minute: abgelehnt, mit Restzeit.
       Lieber ein ehrliches Nein als ein verlorener Schluessel.
    3. Sonst: raus damit.

    Die Uhr wird VOR dem Absenden gestellt, nicht danach. Sonst zaehlt
    die Sperre erst ab dem Ende einer langsamen Antwort, und zwei rasch
    aufeinander folgende Fragen sind beide schon unterwegs.
    """
    global _letzte_anfrage
    kennung = schluessel()
    if not kennung:
        return None, "Für Tankerkönig fehlt der Schlüssel."

    signatur = weg + repr(sorted(params.items()))
    jetzt = time.monotonic()

    alt = _gemerkt.get(signatur)
    if alt and jetzt - alt[0] < TANKER_ABSTAND:
        return alt[1], ""

    rest = TANKER_ABSTAND - (jetzt - _letzte_anfrage)
    if rest > 0:
        return None, ("Tankerkönig erlaubt nur eine Abfrage pro Minute, und "
                      f"die ist gerade verbraucht. In {int(rest) + 1} "
                      "Sekunden geht es wieder.")

    _letzte_anfrage = jetzt
    stand, d = _holen(f"{TANKER}/{weg}", params={**params, "apikey": kennung})
    if stand == 401 or (isinstance(d, dict) and not d.get("ok")
                        and "key" in str(d.get("message", "")).lower()):
        return None, "Tankerkönig weist den Schlüssel zurück."
    if stand != 200 or not isinstance(d, dict) or not d.get("ok"):
        return None, "Tankerkönig antwortet gerade nicht."

    _gemerkt[signatur] = (jetzt, d)
    # Der Speicher darf nicht ueber die Laufzeit wachsen; alles aelter als
    # die Sperrzeit ist ohnehin wertlos.
    for k, (wann, _) in list(_gemerkt.items()):
        if jetzt - wann > TANKER_ABSTAND:
            _gemerkt.pop(k, None)
    return d, ""


# --- Ortsnamen zu Koordinaten --------------------------------------------

_orte: dict[str, tuple[float, float]] = {}


def _koordinaten(ort: str) -> tuple[float, float] | None:
    """"Sarstedt" -> (52.234, 9.853). Einmal nachgeschlagen, dann gemerkt.

    Auf Deutschland eingegrenzt: "Hannover" gibt es auch in Pennsylvania,
    und die dortigen Spritpreise helfen niemandem.
    """
    reiner = (ort or "").strip()
    if not reiner:
        return None
    haken = reiner.lower()
    if haken in _orte:
        return _orte[haken]
    stand, d = _holen(NOMINATIM,
                      params={"q": reiner, "format": "json", "limit": 1,
                              "countrycodes": "de"},
                      kopf={"User-Agent": NOMINATIM_KENNUNG})
    if stand != 200 or not isinstance(d, list) or not d:
        return None
    try:
        paar = (float(d[0]["lat"]), float(d[0]["lon"]))
    except (KeyError, TypeError, ValueError):
        return None
    _orte[haken] = paar
    return paar


def _preis(wert) -> str:
    """1.659 -> "1,659 Euro". Komma, weil es vorgelesen wird."""
    try:
        return f"{float(wert):.3f}".replace(".", ",") + " Euro"
    except (TypeError, ValueError):
        return "kein Preis"


def _entfernung(wert) -> str:
    try:
        return f"{float(wert):.1f}".replace(".", ",") + " Kilometer"
    except (TypeError, ValueError):
        return ""


def _lesbar(text: str) -> str:
    """"HILDESHEIMER STR." -> "Hildesheimer Str."

    Die Markttransparenzstelle bekommt ihre Daten von den Betreibern, und
    ein Teil davon liefert alles in Grossbuchstaben. Vorgelesen faellt es
    nicht auf, auf der Kachel schon.
    """
    reiner = (text or "").strip()
    return reiner.title() if reiner.isupper() else reiner


def _tankstelle(s: dict) -> str:
    """Marke und Ort -- nicht die volle Anschrift.

    "Aral, Bruchstraße 12, 31157 Sarstedt" ist eine Zeile fuer die
    Rechnung, kein Satz fuers Ohr. Die Strasse steht drin, weil es in
    einem Ort mehrere derselben Marke gibt.
    """
    marke = _lesbar(s.get("brand") or s.get("name") or "Tankstelle")
    strasse = _lesbar(s.get("street") or "")
    stadt = _lesbar(s.get("place") or "")
    hinten = ", ".join(t for t in (strasse, stadt) if t)
    return f"{marke} in {hinten}" if hinten else marke


SORTEN = {"diesel": "diesel", "e5": "e5", "e10": "e10",
          "super": "e5", "benzin": "e10"}


def werkzeuge(protokoll, leuchten=None):
    """Die Werkzeuge dieses Moduls.

    `protokoll` wird entgegengenommen und nicht benutzt -- absichtlich.
    Dort hinein gehoert nur, was bleibende Wirkung hat, damit ein
    Abbruch mitten in der Antwort nichts Halbfertiges hinterlaesst (siehe
    __init__.Protokoll). Hier fragt alles nur nach; ein abgebrochener
    Blick auf die A2 hat nichts hinterlassen, das nachzutragen waere.

    Der Parameter bleibt trotzdem stehen, damit alle Module gleich
    aufgerufen werden.
    """

    def leuchte() -> None:
        if leuchten:
            leuchten("Unterwegs")

    # --- Verkehrslage ---------------------------------------------------

    @tool(
        "autobahn_lage",
        "Was gerade auf einer Autobahn los ist: Staus, Unfälle, "
        "Verkehrsmeldungen und aktive Sperrungen — zusammengefasst nach "
        "Fahrtrichtung, das Schlimmste zuerst. Für Fragen wie 'Was ist auf "
        "der A2 los?' oder 'Steht was auf der A7 bei Hannover?'. Quelle: "
        "Autobahn GmbH des Bundes.",
        {
            "type": "object",
            "properties": {
                "autobahn": {"type": "string",
                             "description": "z.B. 'A2', 'A7', 'A99'"},
                "abschnitt": {"type": "string",
                              "description": "Optional: nur Meldungen, die "
                                             "dazu passen, z.B. 'Hannover' "
                                             "oder 'Braunschweig'"},
            },
            "required": ["autobahn"],
        },
    )
    async def autobahn_lage(args):
        leuchte()
        name = _strasse(args.get("autobahn") or "")
        if not name:
            return {"content": [{"type": "text", "text":
                    f"Eine Autobahn {args.get('autobahn')} kenne ich nicht."}],
                    "is_error": True}

        stand_w, dw = _holen(f"{AUTOBAHN}/{name}/services/warning")
        stand_s, ds = _holen(f"{AUTOBAHN}/{name}/services/closure")
        if stand_w != 200 and stand_s != 200:
            return {"content": [{"type": "text", "text":
                    "Der Verkehrsdienst des Bundes antwortet gerade nicht."}],
                    "is_error": True}

        suche = (args.get("abschnitt") or "").strip()
        meldungen = [e for e in (dw.get("warning") or []) if _passt(e, suche)]
        # Sperrungen, die erst kuenftig gelten, gehoeren nicht in eine
        # Frage nach dem Jetzt -- sonst meldet die A8 eine Vollsperrung,
        # die naechste Woche Freitag beginnt.
        sperren = [e for e in (ds.get("closure") or [])
                   if not e.get("future") and _passt(e, suche)]

        wo = f" bei {suche}" if suche else ""
        strecke, rampen = _aufteilen(sperren + meldungen)

        if not strecke and not rampen:
            return {"content": [{"type": "text", "text":
                    f"Auf der {name}{wo} ist gerade nichts gemeldet — keine "
                    "Staus, keine Sperrungen."}]}

        if strecke:
            text = (f"{name}{wo} — "
                    + _bauen(_gruppieren(strecke, _schwere), _satz,
                             "eine weitere Meldung", "weitere Meldungen")
                    + ".")
        else:
            text = f"Auf der Strecke der {name}{wo} ist nichts gemeldet."
        if rampen:
            text += (f" Dazu {rampen} gesperrte Auf- und Abfahrten."
                     if rampen > 1 else
                     " Dazu eine gesperrte Auf- oder Abfahrt.")
        return {"content": [{"type": "text", "text": text}]}

    # --- Baustellen -----------------------------------------------------

    @tool(
        "autobahn_baustellen",
        "Die Baustellen auf einer Autobahn, nach Fahrtrichtung "
        "zusammengefasst — zuerst die, die eine Spur wegnehmen. Zählt nur "
        "die, die gerade wirklich stehen; kurzfristige Baustellen, die erst "
        "später beginnen, werden nur erwähnt. Quelle: Autobahn GmbH des "
        "Bundes.",
        {
            "type": "object",
            "properties": {
                "autobahn": {"type": "string",
                             "description": "z.B. 'A2', 'A7', 'A99'"},
                "abschnitt": {"type": "string",
                              "description": "Optional: nur Baustellen, die "
                                             "dazu passen, z.B. 'Hannover'"},
            },
            "required": ["autobahn"],
        },
    )
    async def autobahn_baustellen(args):
        leuchte()
        name = _strasse(args.get("autobahn") or "")
        if not name:
            return {"content": [{"type": "text", "text":
                    f"Eine Autobahn {args.get('autobahn')} kenne ich nicht."}],
                    "is_error": True}

        stand, d = _holen(f"{AUTOBAHN}/{name}/services/roadworks")
        if stand != 200:
            return {"content": [{"type": "text", "text":
                    "Der Verkehrsdienst des Bundes antwortet gerade nicht."}],
                    "is_error": True}

        suche = (args.get("abschnitt") or "").strip()
        alle = [e for e in (d.get("roadworks") or []) if _passt(e, suche)]
        jetzt = [e for e in alle if not e.get("future")]
        spaeter = len(alle) - len(jetzt)
        strecke, rampen = _aufteilen(jetzt)

        # Andere Rangfolge als bei der Verkehrslage: Eine Baustelle hat
        # keinen Zeitverlust im Datensatz. Was zaehlt, ist die weggenommene
        # Spur und danach die Laenge.
        def rang(e):
            return (_spur_zu(e), _laenge(e))

        def beschreiben(e):
            stelle = _ort(e) or "ohne Ortsangabe"
            zusatz = []
            if _spur_zu(e):
                zusatz.append("Spur gesperrt")
            km = _laenge(e)
            if km >= 1:
                zusatz.append(f"{km:.0f} Kilometer")
            return stelle + (f" ({', '.join(zusatz)})" if zusatz else "")

        wo = f" bei {suche}" if suche else ""
        if strecke:
            text = (f"{name}{wo} — {len(strecke)} Baustellen auf der "
                    "Strecke. "
                    + _bauen(_gruppieren(strecke, rang), beschreiben,
                             "eine weitere", "weitere")
                    + ".")
        elif rampen:
            text = f"Auf der Strecke der {name}{wo} steht keine Baustelle."
        else:
            text = f"Auf der {name}{wo} steht gerade keine Baustelle."
        if rampen:
            text += (f" Dazu {rampen} an Auf- und Abfahrten."
                     if rampen > 1 else " Dazu eine an einer Auffahrt.")
        if spaeter:
            text += (f" Und {spaeter} kurzfristige, die erst später "
                     "beginnen." if spaeter > 1 else
                     " Und eine kurzfristige, die erst später beginnt.")
        return {"content": [{"type": "text", "text": text}]}

    gebaut = [autobahn_lage, autobahn_baustellen]

    if not bereit():
        # Ohne Schluessel gar nicht erst bauen -- lieber zwei Werkzeuge
        # als vier, von denen zwei nur "kein Zugang" sagen koennen.
        # Dieselbe Entscheidung wie bei Musik, Finanzen und Google.
        return gebaut

    # --- Spritpreise ----------------------------------------------------

    @tool(
        "tanken_guenstig",
        "Die günstigsten Tankstellen im Umkreis eines Ortes, mit Preis und "
        "Entfernung. Sorte wählbar: Diesel, E5 oder E10. Höchstens 25 "
        "Kilometer Umkreis und nur eine Abfrage pro Minute — das sind die "
        "Auflagen der Quelle. Preise von Tankerkönig aus der "
        "Markttransparenzstelle für Kraftstoffe des Bundeskartellamts.",
        {
            "type": "object",
            "properties": {
                "ort": {"type": "string",
                        "description": "Ort oder Postleitzahl, z.B. "
                                       "'Sarstedt' oder '31157'"},
                "sorte": {"type": "string",
                          "enum": ["diesel", "e5", "e10"],
                          "description": "Ohne Angabe: Diesel."},
                "umkreis": {"type": "integer",
                            "description": "Kilometer, höchstens 25, "
                                           "Vorgabe 10"},
                "anzahl": {"type": "integer",
                           "description": "Wie viele genannt werden, "
                                          "höchstens 5, Vorgabe 3"},
            },
            "required": ["ort"],
        },
    )
    async def tanken_guenstig(args):
        leuchte()
        ort = (args.get("ort") or "").strip()
        punkt = _koordinaten(ort)
        if not punkt:
            return {"content": [{"type": "text", "text":
                    f"Einen Ort namens {ort} finde ich nicht."}],
                    "is_error": True}

        sorte = SORTEN.get((args.get("sorte") or "diesel").lower(), "diesel")
        radius = min(TANKER_RADIUS_MAX, max(1.0,
                     float(args.get("umkreis") or 10)))
        wie_viele = max(1, min(5, int(args.get("anzahl") or 3)))

        d, hinweis = _tanker("list.php", {
            "lat": round(punkt[0], 5), "lng": round(punkt[1], 5),
            "rad": radius, "sort": "price", "type": sorte})
        if d is None:
            return {"content": [{"type": "text", "text": hinweis}],
                    "is_error": True}

        offen = [s for s in (d.get("stations") or [])
                 if s.get("isOpen") and s.get("price")]
        if not offen:
            return {"content": [{"type": "text", "text":
                    f"Im Umkreis von {int(radius)} Kilometern um {ort} hat "
                    "gerade keine Tankstelle offen."}]}

        namen = {"diesel": "Diesel", "e5": "E5", "e10": "E10"}[sorte]
        zeilen = []
        for s in offen[:wie_viele]:
            weg = _entfernung(s.get("dist"))
            zeilen.append(f"{_tankstelle(s)} für {_preis(s.get('price'))}"
                          + (f", {weg} weg" if weg else ""))
        return {"content": [{"type": "text", "text":
                f"{namen} um {ort}, am günstigsten: " + ". ".join(zeilen)
                + ". Preise von Tankerkönig."}]}

    @tool(
        "tanken_preis",
        "Was eine bestimmte Tankstelle gerade verlangt — alle drei Sorten "
        "auf einmal, dazu ob sie offen hat. Sag die Marke und den Ort, zum "
        "Beispiel 'Aral in Sarstedt'. Nur eine Abfrage pro Minute, das ist "
        "die Auflage der Quelle. Preise von Tankerkönig aus der "
        "Markttransparenzstelle für Kraftstoffe des Bundeskartellamts.",
        {
            "type": "object",
            "properties": {
                "name": {"type": "string",
                         "description": "Marke oder Name, z.B. 'Aral', "
                                        "'Jet', 'Raiffeisen'"},
                "ort": {"type": "string",
                        "description": "Ort oder Postleitzahl, in dem sie "
                                       "steht"},
            },
            "required": ["name", "ort"],
        },
    )
    async def tanken_preis(args):
        leuchte()
        ort = (args.get("ort") or "").strip()
        gesucht = (args.get("name") or "").strip().lower()
        punkt = _koordinaten(ort)
        if not punkt:
            return {"content": [{"type": "text", "text":
                    f"Einen Ort namens {ort} finde ich nicht."}],
                    "is_error": True}

        # Nach Entfernung sortiert, nicht nach Preis: Tankerkoenig erlaubt
        # sort=price nur mit EINER Sorte, hier sollen aber alle drei
        # Preise kommen -- und type=all geht nur mit sort=dist.
        d, hinweis = _tanker("list.php", {
            "lat": round(punkt[0], 5), "lng": round(punkt[1], 5),
            "rad": 10, "sort": "dist", "type": "all"})
        if d is None:
            return {"content": [{"type": "text", "text": hinweis}],
                    "is_error": True}

        treffer = [s for s in (d.get("stations") or [])
                   if gesucht in ((s.get("brand") or "") + " "
                                  + (s.get("name") or "")).lower()]
        if not treffer:
            marken = sorted({(s.get("brand") or s.get("name") or "").strip()
                             for s in (d.get("stations") or [])} - {""})
            return {"content": [{"type": "text", "text":
                    f"Eine {args.get('name')} finde ich in {ort} nicht."
                    + (" Da sind: " + ", ".join(marken[:8]) + "."
                       if marken else "")}], "is_error": True}

        s = treffer[0]
        preise = [f"{n} {_preis(s[k])}"
                  for n, k in (("Diesel", "diesel"), ("E5", "e5"),
                               ("E10", "e10"))
                  if s.get(k)]
        if not preise:
            return {"content": [{"type": "text", "text":
                    f"{_tankstelle(s)} meldet gerade keine Preise."}]}
        zustand = "" if s.get("isOpen") else " Sie hat gerade zu."
        weiter = (f" Und {len(treffer) - 1} weitere derselben Marke in der "
                  "Nähe.") if len(treffer) > 1 else ""
        return {"content": [{"type": "text", "text":
                f"{_tankstelle(s)}: " + ", ".join(preise) + "."
                + zustand + weiter + " Preise von Tankerkönig."}]}

    return gebaut + [tanken_guenstig, tanken_preis]
