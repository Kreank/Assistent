"""Wetter und amtliche Warnungen vom Deutschen Wetterdienst.

WARUM BRIGHT SKY UND NICHT EIN WETTERDIENST

Sascha steht auf Baustellen, nicht auf einer Terrasse. Was ihn
interessiert, ist nicht "gefuehlt 21 Grad", sondern ob heute Nacht die
Aussenleitung einfriert und ob morgen frueh das Geruest steht. Genau
das liefert nur der DWD -- er ist die amtliche Stelle, seine Warnungen
sind die, nach denen sich Feuerwehr und Bauleitung richten, und er
kostet nichts.

Der DWD selbst gibt seine Daten aber als FTP-Verzeichnis mit
Festbreitendateien und als CAP-XML heraus. Bright Sky
(api.brightsky.dev) ist der offizielle, vom DWD selbst empfohlene
JSON-Aufsatz darauf: dieselben Zahlen, dieselben Warnungen, nur ohne
Parser. Kein Schluessel, keine Registrierung, kein Kontingent -- und
damit nichts, was in einem halben Jahr stillschweigend ablaeuft.

Der Pollenflug-Index kommt direkt von opendata.dwd.de, weil Bright Sky
ihn nicht mitfuehrt. Dieselbe Quelle, nur eine Tuer weiter.

WARUM DIE ANTWORTEN SAETZE SIND UND KEINE TABELLEN

Sarvis wird gehoert, nicht gelesen. Eine Vorhersage als Stundenraster
ist am Bildschirm gut und am Ohr wertlos -- niemand behaelt zwoelf
Zeilen. Deshalb fassen diese Werkzeuge zusammen, was ein Mensch
weitersagen wuerde: Spanne statt Reihe, "am Nachmittag" statt "14:00".

Am deutlichsten beim Regenradar. Das DWD-Produkt RV ist ein Bild --
ueber Sprache voellig nutzlos. Hier wird es deshalb nicht gezeigt,
sondern ausgerechnet: eine Zelle von einem Kilometer ueber dem
gefragten Ort, 25 Aufnahmen im Fuenfminutentakt, daraus die zwei
Zahlen, die zaehlen -- wann faengt es an und wie lange haelt es an.

WAS BEIM AUSWERTEN DES RADARS ZU BEACHTEN WAR

Das Radar zaehlt in Hundertsteln Millimeter je fuenf Minuten. Einzelne
Einsen stehen ueberall im Bild, auch bei trockener Luft; das ist
Rauschen, kein Regen. Deshalb die Schwelle: Erst ab REGEN_SCHWELLE
gilt eine Zelle als nass. Und eine einzelne trockene Aufnahme mitten
im Schauer beendet ihn nicht -- ein Schauer, den man in zwei Haelften
ansagt, klingt wie zwei Schauer.

WAS AN ZUGAENGEN NOETIG IST

Nichts. Deshalb werden diese Werkzeuge auch immer gebaut und nicht wie
Musik oder Google an einen Schluessel gehaengt.
"""
import json
from datetime import datetime, timedelta, timezone

import httpx
from claude_agent_sdk import tool

BRIGHTSKY = "https://api.brightsky.dev"
POLLEN_URL = ("https://opendata.dwd.de/climate_environment/health/"
              "alerts/s31fg.json")
# Bright Sky kennt keine Ortsnamen, nur Koordinaten. Der Umweg ueber
# diesen Geokoder ist die einzige Stelle, an der Daten nicht vom DWD
# kommen -- und er liefert auch nur zwei Zahlen, keine Wetterwerte.
GEOKODER = "https://geocoding-api.open-meteo.com/v1/search"

ZEITGRENZE = 20.0
ZEITZONE = "Europe/Berlin"   # DWD-Daten enden an der Grenze, die Zone auch

# ---------------------------------------------------------------------------
# HEIMATORT -- von Sascha bestaetigt am 30.08.2026: 12249 Berlin-Lankwitz.
#
# Die Koordinaten stammen aus der Aufloesung der Postleitzahl, nicht aus
# einer Schaetzung. Sie entscheiden mehr, als es aussieht: Warnungen des
# Wetterdienstes gelten je Kreis, und Berlin grenzt an Brandenburg --
# eine Frostwarnung fuer Teltow-Flaeming ist keine fuer Steglitz.
#
# Aendert sich der Wohnort, aendern sich hier drei Zeilen, sonst nichts.
# ---------------------------------------------------------------------------
HEIMAT_NAME = "Berlin"
HEIMAT_LAT = 52.4263
HEIMAT_LON = 13.3517

# Hundertstel Millimeter je fuenf Minuten. Ab hier ist es Regen und
# nicht Rauschen: 5 sind 0,6 mm in der Stunde, also der Punkt, an dem
# eine Windschutzscheibe nass wird.
REGEN_SCHWELLE = 5
# So viele trockene Aufnahmen darf ein Schauer haben, ohne dass er als
# beendet gilt. Eine sind fuenf Minuten.
REGEN_LUECKE = 1

# Warnereignisse, die fuer Sascha etwas kosten: offene Baustelle,
# Aussenleitung, Geruest, Material auf dem Anhaenger. Gepruefte wird der
# Klartext event_de, weil die DWD-Ereignisnummern zwischen
# Warnstufen wechseln, der Wortstamm aber nicht.
WICHTIG = ("FROST", "GLÄTTE", "GLATT", "STURM", "ORKAN", "WIND",
           "REGEN", "GEWITTER", "HAGEL", "SCHNEE", "TAUWETTER")

# Bundesland -> Pollenregion des DWD. Die Kuerzel kommen aus der
# Ortsangabe der Warnabfrage, die ohnehin schon geholt wird -- damit
# braucht es keine zweite Ortsbestimmung und keine Landkreisliste.
POLLEN_REGION = {
    "SH": 10, "HH": 10, "MV": 20, "NI": 30, "HB": 30, "NW": 40,
    "BB": 50, "BE": 50, "ST": 60, "TH": 70, "SN": 80, "HE": 90,
    "RP": 100, "SL": 100, "BW": 110, "BY": 120,
}

# Wenn nur Koordinaten hereinkommen, gibt es keinen Namen zum Sagen.
# Statt Zahlen vorzulesen ("in 53 Komma 6 Grad Nord") tritt diese Marke
# an die Stelle des Namens; _wo und _wofuer setzen dafuer eine
# Umschreibung im richtigen Fall ein.
KOORDINATEN = "\x00koordinaten"

# Gemerkte Ortsnamen. Ein Ort wandert nicht, und Sascha fragt tagelang
# nach denselben drei. Kein Ablauf noetig.
_orte: dict[str, tuple[float, float, str]] = {}


# --- holen -----------------------------------------------------------------

def _holen(url: str, params: dict | None = None) -> tuple[int, dict]:
    """Ein Aufruf. (status, inhalt) -- inhalt notfalls leer.

    Netzfehler werden hier zu Status 0 und nicht zu einer Ausnahme:
    Ein Werkzeug, das eine Ausnahme wirft, reisst den Zug ab; eines, das
    "der DWD antwortet gerade nicht" sagt, laesst das Gespraech
    weiterlaufen.
    """
    try:
        with httpx.Client(timeout=ZEITGRENZE) as c:
            # Accept-Encoding ausdruecklich: Das Radar antwortet mit 400
            # "must accept br, zstd, or gzip encoding", wenn es fehlt.
            # httpx setzt es von sich aus, aber nicht in jeder Fassung --
            # und der Fehler sieht dann aus wie ein Serverfehler.
            a = c.get(url, params=params,
                      headers={"Accept-Encoding": "gzip, deflate"})
        if not a.content:
            return a.status_code, {}
        return a.status_code, a.json()
    except (httpx.HTTPError, ValueError, json.JSONDecodeError):
        return 0, {}


def _koordinaten(ort: str) -> tuple[float, float, str] | None:
    """Ortsname -> (lat, lon, sauberer Name), oder None.

    Auf Deutschland eingegrenzt, und zwar nicht aus Bequemlichkeit:
    Der DWD misst nur hier. Ein Treffer in Suriname -- den der Geokoder
    fuer "Hannover" tatsaechlich als zweites liefert -- wuerde zu einer
    Wetterabfrage fuehren, die leer zurueckkommt, und niemand wuesste
    warum.
    """
    schluessel = ort.strip().lower()
    if schluessel in _orte:
        return _orte[schluessel]
    stand, d = _holen(GEOKODER, {"name": ort.strip(), "count": 5,
                                 "language": "de", "countryCode": "DE",
                                 "format": "json"})
    if stand != 200:
        return None
    for t in (d.get("results") or []):
        if t.get("country_code") != "DE":
            continue
        gefunden = (float(t["latitude"]), float(t["longitude"]),
                    t.get("name") or ort.strip())
        _orte[schluessel] = gefunden
        return gefunden
    return None


def _ort(args: dict) -> tuple[float, float, str, dict | None]:
    """Der gefragte Ort aus den Werkzeugargumenten.

    Drei Wege in dieser Reihenfolge: ausdrueckliche Koordinaten, dann
    ein Ortsname, dann der Heimatort. Der vierte Rueckgabewert ist eine
    fertige Fehlerantwort, falls der Name nicht aufloesbar war -- so
    muss jedes Werkzeug nur eine Zeile pruefen statt drei Faelle.
    """
    lat, lon = args.get("lat"), args.get("lon")
    if lat is not None and lon is not None:
        try:
            return float(lat), float(lon), KOORDINATEN, None
        except (TypeError, ValueError):
            pass

    name = (args.get("ort") or "").strip()
    if not name:
        return HEIMAT_LAT, HEIMAT_LON, HEIMAT_NAME, None

    gefunden = _koordinaten(name)
    if gefunden is None:
        return 0.0, 0.0, name, {"content": [{"type": "text", "text":
                f"Einen Ort namens {name} finde ich in Deutschland nicht. "
                f"Der Wetterdienst misst nur hier — für weiter weg habe "
                f"ich keine Daten."}], "is_error": True}
    return gefunden[0], gefunden[1], gefunden[2], None


def _gross(text: str) -> str:
    """Nur den ersten Buchstaben gross.

    Nicht str.capitalize(): das schreibt den Rest KLEIN und macht aus
    "in Hannover" ein "In hannover".
    """
    return text[:1].upper() + text[1:]


def _wo(name: str) -> str:
    """'in Hannover' -- Ortsangabe im Dativ.

    Es gibt zwei Helfer und nicht einen, weil Deutsch zwei Faelle
    braucht: "in Hannover", aber "fuer Hannover". Ohne Namen muss die
    Umschreibung mitgebeugt werden, sonst kommt "fuer dem angegebenen
    Ort" heraus -- und genau das stand vor dieser Zeile in der Ausgabe.
    """
    return "am angegebenen Ort" if name == KOORDINATEN else f"in {name}"


def _wofuer(name: str) -> str:
    """'fuer Hannover' -- dasselbe im Akkusativ."""
    return ("für den angegebenen Ort" if name == KOORDINATEN
            else f"für {name}")


def _dwd_ausfall() -> dict:
    """Der einzige Fehlschlag, den es hier gibt, als Satz statt als Zahl."""
    return {"content": [{"type": "text", "text":
            "Der Wetterdienst antwortet gerade nicht. Das legt sich "
            "meistens von selbst — frag es gleich noch mal."}],
            "is_error": True}


# --- in Sprache uebersetzen ------------------------------------------------

def _zahl(wert, stellen: int = 0) -> str:
    """Zahl mit Komma statt Punkt -- sonst liest die Stimme 'zwanzig Punkt
    vier' vor."""
    try:
        text = f"{float(wert):.{stellen}f}"
    except (TypeError, ValueError):
        return "?"
    return text.replace(".", ",")


def _himmelsrichtung(grad) -> str:
    try:
        g = float(grad) % 360
    except (TypeError, ValueError):
        return ""
    namen = ("Norden", "Nordosten", "Osten", "Südosten", "Süden",
             "Südwesten", "Westen", "Nordwesten")
    return namen[int((g + 22.5) // 45) % 8]


def _windstaerke(kmh) -> str:
    """Windgeschwindigkeit als Wort.

    Die Grenzen sind die der Beaufortskala, nicht selbst gewaehlt: Ab
    39 km/h spricht der DWD von Windboeen, ab 62 von Sturmboeen. Damit
    heisst hier dasselbe wie in der Warnung, die Sarvis gleich danach
    vorliest.
    """
    try:
        v = float(kmh)
    except (TypeError, ValueError):
        return ""
    if v < 6:
        return "windstill"
    if v < 20:
        return "leichter Wind"
    if v < 39:
        return "frischer Wind"
    if v < 62:
        return "stürmisch"
    return "Sturm"


def _bewoelkung(prozent) -> str:
    try:
        p = float(prozent)
    except (TypeError, ValueError):
        return ""
    if p <= 12:
        return "klar"
    if p <= 37:
        return "gering bewölkt"
    if p <= 75:
        return "wolkig"
    if p <= 95:
        return "stark bewölkt"
    return "bedeckt"


ZUSTAND = {
    "dry": "trocken", "fog": "Nebel", "rain": "Regen", "sleet": "Schneeregen",
    "snow": "Schnee", "hail": "Hagel", "thunderstorm": "Gewitter",
}


# Runde Dauern als Wort. Links die Grundform ("rund eine halbe
# Stunde"), rechts der Dativ ("in einer halben Stunde") -- ohne die
# zweite Spalte sagt Sarvis "in etwa eine Viertelstunde".
#
# Kein "etwa" und kein "rund" in der Tabelle selbst: Die Absicherung
# setzt der Satz, und zweimal hintereinander ergab "rund etwa zwanzig
# Minuten".
DAUERN = {
    5:   ("fünf Minuten", "fünf Minuten"),
    10:  ("zehn Minuten", "zehn Minuten"),
    15:  ("eine Viertelstunde", "einer Viertelstunde"),
    20:  ("zwanzig Minuten", "zwanzig Minuten"),
    30:  ("eine halbe Stunde", "einer halben Stunde"),
    45:  ("eine Dreiviertelstunde", "einer Dreiviertelstunde"),
    60:  ("eine Stunde", "einer Stunde"),
    75:  ("eine gute Stunde", "einer guten Stunde"),
    90:  ("anderthalb Stunden", "anderthalb Stunden"),
    120: ("zwei Stunden", "zwei Stunden"),
}


def _dauer_grob(minuten: int, dativ: bool = False) -> str:
    """Minuten so sagen, wie ein Mensch sie sagt.

    Eine Radarvorhersage auf die Minute genau anzusagen taeuscht eine
    Genauigkeit vor, die das Produkt nicht hat -- es rechnet selbst in
    Fuenfminutenschritten und verschiebt sich mit jedem Lauf. "Rund eine
    halbe Stunde" ist ehrlicher als "32 Minuten" und leichter zu
    behalten.
    """
    m = max(5, int(round(minuten / 5.0)) * 5)
    if m in DAUERN:
        return DAUERN[m][1 if dativ else 0]
    return f"{m} Minuten"


def _staerke(hundertstel: int) -> str:
    """Radarwert -> Wort. Umgerechnet in Millimeter je Stunde.

    Der Wert ist 0,01 mm je fuenf Minuten; mal zwoelf ergibt mm/h. Die
    Grenzen 2,5 und 10 mm/h sind die uebliche Einteilung leicht /
    maessig / stark.
    """
    mmh = hundertstel * 0.12
    if mmh < 2.5:
        return "leicht"
    if mmh < 10:
        return "mäßig"
    return "kräftig"


# Woerter, die der DWD in seinen Ereignisnamen kleinschreibt. Ohne die
# Ausnahme macht .title() aus "GEWITTER MIT STARKREGEN" ein "Gewitter
# Mit Starkregen".
KLEIN = {"mit", "und", "oder", "in", "im", "bei", "vor", "ab", "an",
         "der", "die", "das", "des", "dem", "den", "zu", "von"}


def _ereignis_name(roh: str) -> str:
    """Den Ereignisnamen des DWD lesbar machen.

    Er kommt durchgehend gross herein -- aus "WINDBÖEN" wird hier
    "Windböen", aus "GEWITTER MIT STARKREGEN" ein "Gewitter mit
    Starkregen". Vorgelesen macht das keinen Unterschied, gelesen
    schon, und dieselbe Warnung geht auch als Text an die App.
    """
    worte = []
    for i, wort in enumerate(roh.split()):
        klein = wort.lower()
        worte.append(klein if i and klein in KLEIN
                     else klein[:1].upper() + klein[1:])
    return " ".join(worte) or "Warnung"


def _uhr(iso: str) -> str:
    """Volle Stunde ohne fuehrende Null.

    "%H" liefert "09", und die Stimme liest daraus "null neun Uhr".
    """
    try:
        return f"{datetime.fromisoformat(iso).hour} Uhr"
    except (TypeError, ValueError):
        return ""


def _tageszeit(stunde: int) -> str:
    if stunde < 6:
        return "in der Nacht"
    if stunde < 11:
        return "am Vormittag"
    if stunde < 14:
        return "um die Mittagszeit"
    if stunde < 18:
        return "am Nachmittag"
    if stunde < 22:
        return "am Abend"
    return "in der Nacht"


# --- Vorhersagestunden zusammenfassen --------------------------------------

def _stunden_holen(lat: float, lon: float, von: datetime,
                   bis: datetime) -> list[dict] | None:
    stand, d = _holen(f"{BRIGHTSKY}/weather", {
        "lat": lat, "lon": lon, "tz": ZEITZONE,
        "date": von.strftime("%Y-%m-%dT%H:%M"),
        "last_date": bis.strftime("%Y-%m-%dT%H:%M"),
    })
    if stand != 200:
        return None
    return d.get("weather") or []


def _satz_ueber(stunden: list[dict]) -> str:
    """Eine Reihe Stundenwerte als ein bis zwei gesprochene Saetze.

    Was hier NICHT vorkommt, ist Absicht: kein Luftdruck, keine
    Luftfeuchte, keine Sichtweite. Wer nach dem Wetter fragt, will
    wissen, wie er sich anzieht und ob er das Material abdeckt. Alles
    Weitere macht den Satz laenger, ohne ihn nuetzlicher zu machen.
    """
    if not stunden:
        return ""
    temps = [h["temperature"] for h in stunden if h.get("temperature") is not None]
    teile = []
    if temps:
        tief, hoch = min(temps), max(temps)
        if hoch - tief < 2:
            teile.append(f"um die {_zahl(hoch)} Grad")
        else:
            teile.append(f"{_zahl(tief)} bis {_zahl(hoch)} Grad")

    himmel = [h.get("cloud_cover") for h in stunden
              if h.get("cloud_cover") is not None]
    if himmel:
        teile.append(_bewoelkung(sum(himmel) / len(himmel)))

    nass = [h for h in stunden if (h.get("precipitation") or 0) > 0.05]
    if nass:
        menge = sum(h.get("precipitation") or 0 for h in nass)
        # dict.fromkeys statt sorted(set(...)): Eine Menge kommt
        # alphabetisch heraus, und dann sagt Sarvis "Regen am Abend und
        # am Nachmittag" -- in der falschen Reihenfolge.
        wann = list(dict.fromkeys(
            _tageszeit(datetime.fromisoformat(h["timestamp"]).hour)
            for h in nass))
        teile.append(f"Regen {' und '.join(wann)}, zusammen etwa "
                     f"{_zahl(menge, 1)} Millimeter")
    else:
        # Die Wahrscheinlichkeit nur nennen, wenn sie etwas aussagt.
        # "10 Prozent Regenwahrscheinlichkeit" ist kein Wetter, das ist
        # eine Zahl.
        risiko = [h.get("precipitation_probability") or 0 for h in stunden]
        if risiko and max(risiko) >= 30:
            teile.append(f"Regen möglich, bis zu {max(risiko)} Prozent")
        else:
            teile.append("trocken")

    boeen = [h.get("wind_gust_speed") or 0 for h in stunden]
    if boeen and max(boeen) >= 39:
        teile.append(f"Böen bis {_zahl(max(boeen))} Stundenkilometer")
    else:
        wind = [h.get("wind_speed") or 0 for h in stunden]
        if wind:
            teile.append(_windstaerke(sum(wind) / len(wind)))
    return ", ".join(t for t in teile if t)


# --- Pollen ----------------------------------------------------------------

def _pollen_zahl(stufe: str) -> float:
    """Die DWD-Stufe als Zahl, zum Sortieren.

    Der DWD schreibt Zwischenstufen als "0-1" oder "2-3". Das ist keine
    Spanne, sondern eine eigene Stufe -- deshalb die Mitte und nicht die
    Obergrenze, sonst waere "0-1" so schlimm wie "1".
    """
    try:
        teile = [float(x) for x in str(stufe).split("-")]
        return sum(teile) / len(teile)
    except (TypeError, ValueError):
        return -1.0


def _pollen_name(art: str) -> str:
    """Die Schreibweise des DWD ins Gesprochene."""
    return {"Graeser": "Gräser", "Beifuss": "Beifuß"}.get(art, art)


# ---------------------------------------------------------------------------

def werkzeuge(protokoll, leuchten=None):
    """Die fuenf Wetterwerkzeuge.

    Alle lesen nur. Deshalb ruft keines protokoll.merken() -- der
    Nachtrag nach einem Abbruch soll das aufzaehlen, was weiterwirkt,
    und eine Wetterabfrage wirkt nicht weiter. Der Parameter bleibt
    trotzdem in der Signatur, damit __init__.py alle Module gleich
    aufruft.
    """

    def leuchte() -> None:
        if leuchten:
            leuchten("Wetter")

    def sagen(text: str) -> dict:
        return {"content": [{"type": "text", "text": text}]}

    ORT_FELDER = {
        "ort": {"type": "string",
                "description": "Ortsname in Deutschland, z.B. 'Bad "
                               "Nenndorf'. Ohne Angabe gilt der "
                               f"Heimatort ({HEIMAT_NAME})."},
        "lat": {"type": "number",
                "description": "Breitengrad, falls statt eines Namens "
                               "Koordinaten vorliegen."},
        "lon": {"type": "number", "description": "Längengrad."},
    }

    # --- Jetzt ----------------------------------------------------------

    @tool(
        "wetter_jetzt",
        "Das Wetter in diesem Moment: Temperatur, Niederschlag, Wind und "
        "Bewölkung, gemessen an der nächsten Station des Deutschen "
        "Wetterdienstes. Für 'wie ist das Wetter', 'wie warm ist es', "
        "'regnet es gerade'.",
        {"type": "object", "properties": dict(ORT_FELDER)},
    )
    async def wetter_jetzt(args):
        lat, lon, name, fehler = _ort(args)
        leuchte()
        if fehler:
            return fehler
        stand, d = _holen(f"{BRIGHTSKY}/current_weather",
                          {"lat": lat, "lon": lon, "tz": ZEITZONE})
        if stand != 200 or not d.get("weather"):
            return _dwd_ausfall()
        w = d["weather"]

        teile = [f"{_gross(_wo(name))} sind es "
                 f"{_zahl(w.get('temperature'), 1)} Grad"]
        himmel = _bewoelkung(w.get("cloud_cover"))
        zustand = ZUSTAND.get(w.get("condition") or "", "")
        if zustand and zustand != "trocken":
            teile.append(zustand.lower() if zustand[0].islower() else zustand)
        elif himmel:
            teile.append(himmel)

        # Der Zehnminutenwert ist der aktuellere; faellt er aus, taugt
        # die letzte Stunde immer noch als Aussage.
        regen10 = w.get("precipitation_10")
        regen60 = w.get("precipitation_60")
        if regen10:
            teile.append(f"es regnet, {_zahl(regen10, 1)} Millimeter in den "
                         f"letzten zehn Minuten")
        elif regen60:
            teile.append(f"in der letzten Stunde {_zahl(regen60, 1)} "
                         f"Millimeter Regen")

        wind = w.get("wind_speed_10")
        if wind is None:
            wind = w.get("wind_speed_60")
        richtung = _himmelsrichtung(w.get("wind_direction_10")
                                    or w.get("wind_direction_60"))
        if wind is not None:
            satz = f"{_windstaerke(wind)} mit {_zahl(wind)} Stundenkilometern"
            if richtung:
                satz += f" aus {richtung}"
            teile.append(satz)
        boe = w.get("wind_gust_speed_10") or w.get("wind_gust_speed_60")
        if boe and float(boe) >= 39:
            teile.append(f"Böen bis {_zahl(boe)}")

        quelle = (d.get("sources") or [{}])[0]
        station = quelle.get("station_name")
        entfernung = quelle.get("distance")
        nachsatz = ""
        if station and entfernung is not None:
            # Die Stationsangabe ist kein Beiwerk: Bright Sky greift
            # stillschweigend auf entferntere Stationen zurueck, wenn die
            # naechste einen Wert nicht meldet. Steht die Entfernung da,
            # merkt man, wenn die Zahl von 40 km weiter kommt.
            nachsatz = (f" (gemessen in {station}, "
                        f"{_zahl(float(entfernung) / 1000, 1)} km entfernt)")
        return sagen(", ".join(teile) + "." + nachsatz)

    # --- Vorhersage -----------------------------------------------------

    @tool(
        "wetter_vorhersage",
        "Die Wettervorhersage als kurzer gesprochener Überblick — für die "
        "nächsten Stunden, für heute oder für morgen. Antwortet in ein "
        "bis zwei Sätzen, nicht als Stundenliste.",
        {
            "type": "object",
            "properties": dict(
                ORT_FELDER,
                wann={"type": "string",
                      "enum": ["stunden", "heute", "morgen", "uebermorgen"],
                      "description": "'stunden' sind die nächsten acht "
                                     "Stunden. Ohne Angabe: stunden."},
            ),
        },
    )
    async def wetter_vorhersage(args):
        lat, lon, name, fehler = _ort(args)
        leuchte()
        if fehler:
            return fehler
        wann = args.get("wann") or "stunden"
        jetzt = datetime.now()

        if wann == "stunden":
            von = jetzt
            bis = jetzt.replace(minute=0) + timedelta(hours=8)
            vorspann = f"Die nächsten Stunden {_wo(name)}"
        else:
            tage = {"heute": 0, "morgen": 1, "uebermorgen": 2}[wann]
            tag = (jetzt + timedelta(days=tage)).replace(
                hour=0, minute=0, second=0, microsecond=0)
            # Bei "heute" nur noch das, was kommt -- eine Vorhersage fuer
            # heute Morgen um sieben ist um vier Uhr nachmittags keine
            # Vorhersage mehr, sondern eine Gedaechtnisstuetze.
            von = max(tag, jetzt) if tage == 0 else tag
            bis = tag + timedelta(hours=23)
            benennung = {"heute": "Heute", "morgen": "Morgen",
                         "uebermorgen": "Übermorgen"}[wann]
            vorspann = f"{benennung} {_wo(name)}"

        stunden = _stunden_holen(lat, lon, von, bis)
        if stunden is None:
            return _dwd_ausfall()
        satz = _satz_ueber(stunden)
        if not satz:
            return sagen(f"{_gross(_wofuer(name))} habe ich für "
                         f"den Zeitraum keine Vorhersage.")
        return sagen(f"{vorspann}: {satz}.")

    # --- Warnungen ------------------------------------------------------

    @tool(
        "wetter_warnungen",
        "Amtliche Unwetterwarnungen des Deutschen Wetterdienstes für einen "
        "Ort: Frost, Sturm, Starkregen, Gewitter, Glätte, Schnee. Nennt "
        "Stufe, Zeitraum und die amtliche Handlungsempfehlung. Immer "
        "benutzen, wenn nach Warnungen, Unwetter, Sturm oder Frost gefragt "
        "wird — und bei Fragen zur Baustelle oder zu Außenleitungen.",
        {"type": "object", "properties": dict(ORT_FELDER)},
    )
    async def wetter_warnungen(args):
        lat, lon, name, fehler = _ort(args)
        leuchte()
        if fehler:
            return fehler
        stand, d = _holen(f"{BRIGHTSKY}/alerts",
                          {"lat": lat, "lon": lon, "tz": ZEITZONE})
        if stand != 200:
            return _dwd_ausfall()

        wo = d.get("location") or {}
        gebiet = wo.get("name") or (
            "den angegebenen Ort" if name == KOORDINATEN else name)
        warnungen = d.get("alerts") or []
        if not warnungen:
            return sagen(f"Für {gebiet} liegt keine Warnung des "
                         f"Wetterdienstes vor.")

        # Nach Schwere sortieren, das Schlimmste zuerst. Sarvis wird
        # unterbrochen; was zuerst kommt, wird gehoert.
        rang = {"extreme": 0, "severe": 1, "moderate": 2, "minor": 3}
        warnungen.sort(key=lambda a: rang.get(a.get("severity"), 9))

        zeilen = []
        for a in warnungen:
            ereignis = _ereignis_name(a.get("event_de") or "")
            stufe = {"extreme": "höchste Stufe", "severe": "Unwetterwarnung",
                     "moderate": "Warnung",
                     "minor": "Wetterwarnung"}.get(a.get("severity"), "")
            zeile = f"{ereignis} ({stufe})" if stufe else ereignis

            von = _uhr(a.get("onset") or "")
            bis = _uhr(a.get("expires") or "")
            try:
                beginn = datetime.fromisoformat(a["onset"])
                tag = beginn.date() - datetime.now(beginn.tzinfo).date()
                wenn = {0: "heute", 1: "morgen"}.get(tag.days, "")
            except (KeyError, TypeError, ValueError):
                wenn = ""
            if von and bis:
                # wenn ist leer, sobald die Warnung weiter weg liegt als
                # morgen. Zusammengesetzt statt eingesetzt, sonst steht
                # dort ein doppeltes Leerzeichen.
                zeile += ", " + " ".join(
                    t for t in (wenn, f"von {von} bis {bis}") if t)

            gross = (a.get("event_de") or "").upper()
            if any(k in gross for k in WICHTIG):
                # Der Grund, warum es dieses Werkzeug ueberhaupt gibt.
                # Frost, Sturm und Starkregen kosten Sascha Geld, nicht
                # Bequemlichkeit -- offene Leitung, unabgedecktes
                # Material, ein Geruest im Wind.
                zeile += " — für die Baustellen relevant"

            hinweis = (a.get("instruction_de") or "").strip()
            if hinweis:
                # Der DWD schreibt die Empfehlung mehrzeilig mit
                # Doppelpunkten. Vorgelesen wird daraus ein Stolpern,
                # also in eine Zeile ziehen.
                hinweis = " ".join(hinweis.split())
                zeile += f". Empfehlung: {hinweis}"
            zeilen.append(zeile)

        kopf = (f"Für {gebiet} liegt eine Warnung vor" if len(zeilen) == 1
                else f"Für {gebiet} liegen {len(zeilen)} Warnungen vor")
        # Punkt und Leerzeichen als Trenner, kein Strich: Der Text
        # wird vorgelesen, und ein Satzende ist die einzige Pause, die
        # eine Sprachausgabe verlaesslich macht.
        return sagen(kopf + ": " + ". ".join(zeilen) + ".")

    # --- Regenradar -----------------------------------------------------

    @tool(
        "regen_bald",
        "Regenradar, ausgewertet als Ansage: wann es anfängt zu regnen, "
        "wie lange und wie stark. Für 'muss ich gleich los', 'hält das "
        "Wetter noch', 'wann hört das auf'. Genauer als die "
        "Stundenvorhersage, reicht aber höchstens zwei Stunden voraus — "
        "meist weniger, je nachdem wie lange der letzte Radarlauf her "
        "ist. Sagt die tatsächliche Reichweite mit.",
        {"type": "object", "properties": dict(ORT_FELDER)},
    )
    async def regen_bald(args):
        lat, lon, name, fehler = _ort(args)
        leuchte()
        if fehler:
            return fehler
        # distance=1000 gibt ein Gitter von drei mal drei Zellen um den
        # Punkt. Weniger geht nicht, mehr braucht es nicht -- und die
        # Antwort bleibt bei vier Kilobyte statt bei Megabyte.
        stand, d = _holen(f"{BRIGHTSKY}/radar", {
            "lat": lat, "lon": lon, "distance": 1000, "format": "plain"})
        if stand != 200 or not d.get("radar"):
            return _dwd_ausfall()

        bilder = d["radar"]
        lage = d.get("latlon_position") or {}
        gitter = bilder[0]["precipitation_5"]
        # latlon_position kommt mit Nachkommastellen -- das ist die
        # genaue Lage des Punktes IN der Zelle, kein Index. Ungerundet
        # wirft es TypeError.
        zeile = max(0, min(len(gitter) - 1, int(round(lage.get("y", 1)))))
        spalte = max(0, min(len(gitter[0]) - 1, int(round(lage.get("x", 1)))))

        jetzt = datetime.now(timezone.utc)
        reihe = []
        for b in bilder:
            try:
                zeitpunkt = datetime.fromisoformat(b["timestamp"])
                wert = b["precipitation_5"][zeile][spalte]
            except (KeyError, IndexError, TypeError, ValueError):
                continue
            reihe.append((zeitpunkt, int(wert)))
        if not reihe:
            return _dwd_ausfall()

        kommend = [(t, v) for t, v in reihe if t >= jetzt]
        vergangen = [(t, v) for t, v in reihe if t < jetzt]
        weite = int((reihe[-1][0] - jetzt).total_seconds() // 60)
        regnet_jetzt = bool(vergangen and vergangen[-1][1] >= REGEN_SCHWELLE)
        if not kommend:
            # Das Radarprodukt RV wird alle fuenf Minuten neu gerechnet.
            # Bleibt ein Lauf aus, liegt der letzte Zeitpunkt in der
            # Vergangenheit -- dann ist die ehrliche Antwort, dass es
            # gerade keine Vorschau gibt, und nicht "kein Regen".
            return sagen(
                "Das Regenradar hat gerade keine frische Vorschau — der "
                "letzte Lauf des Wetterdienstes liegt schon hinter uns. "
                "Frag es in ein paar Minuten noch mal.")

        def schauer(ab: int) -> tuple[int, int, int] | None:
            """Der naechste Schauer ab Index: (start, ende, hoechstwert).

            Ende ist der Index nach der letzten nassen Aufnahme. Eine
            einzelne trockene Aufnahme mittendrin beendet nichts --
            sonst wird aus einem Schauer zweimal "gleich regnet es".
            """
            i = ab
            while i < len(kommend) and kommend[i][1] < REGEN_SCHWELLE:
                i += 1
            if i >= len(kommend):
                return None
            start, ende, luecke, hoch = i, i, 0, 0
            while i < len(kommend):
                if kommend[i][1] >= REGEN_SCHWELLE:
                    ende, luecke = i, 0
                    hoch = max(hoch, kommend[i][1])
                else:
                    luecke += 1
                    if luecke > REGEN_LUECKE:
                        break
                i += 1
            return start, ende + 1, hoch

        naechster = schauer(0)

        if regnet_jetzt:
            if naechster is None or naechster[0] > 0:
                return sagen(
                    f"{_gross(_wo(name))} regnet es gerade, aber das "
                    f"Radar zeigt es schon aufhören — in den nächsten "
                    f"Minuten müsste es durch sein.")
            dauer = (naechster[1] - naechster[0]) * 5
            if naechster[1] >= len(kommend):
                return sagen(
                    f"{_gross(_wo(name))} regnet es "
                    f"{_staerke(naechster[2])}, und in den nächsten "
                    f"{_dauer_grob(weite)} hört es laut Radar nicht auf.")
            return sagen(
                f"{_gross(_wo(name))} regnet es gerade, "
                f"{_staerke(naechster[2])}. Vorbei ist es in etwa "
                f"{_dauer_grob(dauer, dativ=True)}.")

        if naechster is None:
            return sagen(
                f"Das Regenradar zeigt {_wofuer(name)} in den nächsten "
                f"{_dauer_grob(weite)} keinen Regen.")

        vorlauf = int((kommend[naechster[0]][0] - jetzt).total_seconds() // 60)
        dauer = (naechster[1] - naechster[0]) * 5
        satz = (f"In etwa {_dauer_grob(vorlauf, dativ=True)} kommt es "
                f"{_wo(name)} zu {_staerke(naechster[2])}em Regen")
        if naechster[1] >= len(kommend):
            # Der Schauer laeuft ueber das Ende der Vorhersage hinaus.
            # Das als feste Dauer anzusagen waere gelogen.
            satz += ", und wie lange er anhält, reicht das Radar nicht mehr."
        else:
            satz += f", rund {_dauer_grob(dauer)} lang."
        return sagen(satz)

    # --- Pollen ---------------------------------------------------------

    @tool(
        "pollenflug",
        "Der Pollenflug-Gefahrenindex des Deutschen Wetterdienstes für "
        "heute und morgen: Gräser, Birke, Erle, Hasel, Esche, Roggen, "
        "Beifuß, Ambrosia. Nennt nur die Arten, die überhaupt fliegen.",
        {
            "type": "object",
            "properties": dict(
                ORT_FELDER,
                region_id={"type": "integer",
                           "description": "Regions-ID des DWD (10 "
                                          "Schleswig-Holstein/Hamburg bis "
                                          "120 Bayern). Nur nötig, wenn der "
                                          "Ort nicht reicht."},
            ),
        },
    )
    async def pollenflug(args):
        leuchte()
        region = args.get("region_id")
        gebiet = ""

        if region is None:
            lat, lon, name, fehler = _ort(args)
            if fehler:
                return fehler
            # Das Bundesland kommt aus der Warnabfrage. Das ist kein
            # Umweg, sondern der kuerzeste Weg: Bright Sky loest dort
            # ohnehin die Koordinate auf einen Warnkreis mit Bundesland
            # auf -- eine eigene Landkreisliste waere eine zweite
            # Wahrheit, die veraltet.
            stand, d = _holen(f"{BRIGHTSKY}/alerts", {"lat": lat, "lon": lon})
            if stand != 200:
                return _dwd_ausfall()
            wo = d.get("location") or {}
            region = POLLEN_REGION.get(wo.get("state_short") or "")
            gebiet = wo.get("state") or name
            if region is None:
                return {"content": [{"type": "text", "text":
                        f"Für {name} finde ich keine Pollenregion des "
                        f"Wetterdienstes."}], "is_error": True}

        stand, d = _holen(POLLEN_URL)
        if stand != 200 or not d.get("content"):
            return _dwd_ausfall()

        legende = d.get("legend") or {}
        # Aus der Legende eine Tabelle Stufe -> Klartext bauen, statt die
        # Stufen fest einzutippen: Der DWD hat die Bezeichnungen schon
        # einmal geaendert, die Legende liegt aber in derselben Datei.
        klartext = {}
        for schluessel, wert in legende.items():
            if schluessel.endswith("_desc"):
                continue
            beschreibung = legende.get(schluessel + "_desc")
            if beschreibung:
                klartext[wert] = beschreibung

        teilregionen = [c for c in d["content"]
                        if c.get("region_id") == int(region)]
        if not teilregionen:
            return {"content": [{"type": "text", "text":
                    f"Die Region {region} kennt der Wetterdienst nicht."}],
                    "is_error": True}
        if not gebiet:
            gebiet = teilregionen[0].get("region_name") or f"Region {region}"

        # Ueber die Teilregionen den hoechsten Wert nehmen und, falls sie
        # sich unterscheiden, dazusagen wo. Eine Teilregion zu raten
        # waere bequemer und im Zweifel falsch -- Hannover und die
        # Nordseekueste liegen in derselben Region, aber nicht in
        # derselben Teilregion.
        arten = {}
        for teil in teilregionen:
            for art, werte in (teil.get("Pollen") or {}).items():
                arten.setdefault(art, []).append(
                    (werte.get("today", "0"), werte.get("tomorrow", "0"),
                     teil.get("partregion_name") or ""))
        for art, liste in arten.items():
            liste.sort(key=lambda w: -_pollen_zahl(w[0]))

        aktiv = [(art, liste) for art, liste in arten.items()
                 if _pollen_zahl(liste[0][0]) > 0
                 or _pollen_zahl(liste[0][1]) > 0]
        if not aktiv:
            return sagen(f"In {gebiet} fliegt heute und morgen nichts — "
                         f"alle Arten stehen auf keiner Belastung.")

        aktiv.sort(key=lambda p: -_pollen_zahl(p[1][0][0]))
        zeilen = []
        for art, liste in aktiv:
            heute, morgen, teil = liste[0]
            text = f"{_pollen_name(art)} — {klartext.get(heute, heute)}"
            if morgen != heute:
                text += f", morgen {klartext.get(morgen, morgen)}"
            if len(liste) > 1 and liste[-1][0] != heute and teil:
                # Innerhalb eines Bundeslands weichen die Teilregionen
                # ab -- Kueste und Binnenland fliegen nicht gleich. Die
                # hoehere Zahl zu nennen und zu verschweigen, wo sie
                # gilt, waere die haltlosere Haelfte der Wahrheit.
                text += f" (am stärksten: {teil})"
            zeilen.append(text)
        stand_text = d.get("last_update") or ""
        return sagen(f"Pollenflug in {gebiet}: " + "; ".join(zeilen) + "."
                     + (f" (Stand {stand_text})" if stand_text else ""))

    return [wetter_jetzt, wetter_vorhersage, wetter_warnungen, regen_bald,
            pollenflug]
