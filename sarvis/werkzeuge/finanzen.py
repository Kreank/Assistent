# -*- coding: utf-8 -*-
"""Das Finanzdashboard auf finanz.tech-artist.de.

Der Assistent spricht dieselbe Schnittstelle wie die Weboberflaeche und
darf grundsaetzlich dasselbe. Der Unterschied ist nur der Nachweis: die
Oberflaeche ein Sitzungs-Cookie, Sarvis eine Kopfzeile mit dem
Schluessel.

Zwei Dinge bestimmen den Zuschnitt hier:

**Es wird vorgelesen.** Deshalb gibt keins dieser Werkzeuge JSON zurueck,
sondern fertige deutsche Saetze mit Komma-Betraegen. "1098,00 Euro" ist
sprechbar, {"summe": "1098.00"} nicht -- und ein Modell, das aus rohen
Zahlen erst formulieren muss, verplappert sich dabei.

**Lesen ist harmlos, Schreiben nicht.** Alle Abfragen laufen still durch;
eine Buchung oder Umbuchung anzulegen fragt nach. Geloescht wird ueber Sarvis gar
nicht: Eine verlorene Buchung faellt erst beim Kontoabgleich auf, und
dann weiss niemand mehr, was da stand. Das gehoert an den Bildschirm.

Der Schluessel steht in .env unter FD_API_SCHLUESSEL und niemals im
Quelltext -- so steht es auch in der Referenz des Dashboards selbst.
"""
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

import httpx
from claude_agent_sdk import tool

from .. import config


def _betrag(wert) -> str:
    """"-1098.00" -> "1098,00 Euro". Vorzeichen traegt der Satz, nicht die Zahl.

    Betraege kommen als Zeichenketten, nicht als Fliesskommazahlen -- das
    ist Absicht des Dashboards, weil Geld als float rundet. Deshalb hier
    Decimal und keine Umwandlung nach float.
    """
    try:
        d = Decimal(str(wert))
    except (InvalidOperation, TypeError, ValueError):
        return str(wert)
    # Kein Tausenderpunkt: "1.098,00" liest Piper als zwei Zahlen.
    return f"{abs(d):.2f}".replace(".", ",") + " Euro"


def _datum(iso: str) -> str:
    """2026-08-20 -> 20.08.2026 -- vorgelesen wird deutsch."""
    try:
        return f"{datetime.strptime(str(iso)[:10], '%Y-%m-%d'):%d.%m.%Y}"
    except (TypeError, ValueError):
        return str(iso)


def _monat(iso: str) -> str:
    """2026-07 -> Juli 2026."""
    namen = ("Januar", "Februar", "März", "April", "Mai", "Juni", "Juli",
             "August", "September", "Oktober", "November", "Dezember")
    try:
        jahr, monat = str(iso).split("-")[:2]
        return f"{namen[int(monat) - 1]} {jahr}"
    except (IndexError, ValueError):
        return str(iso)


async def _holen(weg: str, **parameter):
    """Eine Abfrage. Gibt (Daten, Fehlertext) zurueck -- nie eine Ausnahme.

    Ein Netzfehler darf Sarvis nicht abwuergen; er soll sagen koennen,
    dass er das Dashboard gerade nicht erreicht.
    """
    schluessel = config.finanz_schluessel()
    if not schluessel:
        return None, ("Für das Finanzdashboard ist kein Schlüssel "
                      "hinterlegt. Er gehört in die Punkt-env-Datei unter "
                      "F D unterstrich A P I unterstrich Schluessel.")
    sauber = {k: v for k, v in parameter.items() if v not in (None, "")}
    try:
        async with httpx.AsyncClient(
                timeout=config.FINANZ_ZEITGRENZE,
                headers={"X-Api-Key": schluessel}) as klient:
            antwort = await klient.get(config.FINANZ_BASIS + weg, params=sauber)
    except httpx.HTTPError as e:
        return None, f"Ich erreiche das Finanzdashboard nicht: {type(e).__name__}."

    if antwort.status_code == 401:
        return None, "Das Dashboard hat den Schlüssel abgelehnt."
    if antwort.status_code == 503:
        return None, "Auf dem Server ist noch kein Passwort hinterlegt."
    if antwort.status_code >= 400:
        return None, f"Das Dashboard antwortet mit Fehler {antwort.status_code}."
    try:
        return antwort.json(), ""
    except ValueError:
        return None, "Das Dashboard hat etwas Unlesbares geschickt."


async def _schicken(weg: str, koerper: dict, was: str):
    """Ein Schreibvorgang. Gibt (Daten, Fehlertext) zurueck -- wie _holen.

    `was` steht im Ablehnungssatz ("lehnt die Buchung ab"), damit der
    Vorgelesene benennt, was nicht geklappt hat.
    """
    schluessel = config.finanz_schluessel()
    if not schluessel:
        return None, "Für das Finanzdashboard ist kein Schlüssel hinterlegt."
    try:
        async with httpx.AsyncClient(
                timeout=config.FINANZ_ZEITGRENZE,
                headers={"X-Api-Key": schluessel}) as klient:
            antwort = await klient.post(config.FINANZ_BASIS + weg, json=koerper)
    except httpx.HTTPError as e:
        return None, f"Ich erreiche das Dashboard nicht: {type(e).__name__}."
    if antwort.status_code >= 400:
        return None, f"Das Dashboard lehnt {was} ab (Fehler {antwort.status_code})."
    try:
        return antwort.json(), ""
    except ValueError:
        # Angelegt ist angelegt -- nur die Antwort war nicht lesbar.
        return {}, ""


def _vergleichsform(text) -> str:
    """Kategorienamen vergleichbar machen: klein, ohne Umlaute, ohne Rand.

    Gesprochenes kommt durch die Erkennung mal als "Lebensmittel", mal als
    "lebensmittel"; ein Modell schreibt "Buero" statt "Büro". Verglichen
    wird deshalb nicht der Name, sondern diese Form davon.
    """
    kleines = str(text or "").strip().lower()
    for um, ersatz in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        kleines = kleines.replace(um, ersatz)
    return kleines


async def _kategorie_treffen(gesucht: str):
    """Gesprochener Kategoriename -> (id, Name, Fehlertext).

    Der Fehlertext ist ein fertiger Satz und nennt bei Fehlschlag, was es
    stattdessen gibt -- sonst raet das Modell die naechste ID.
    """
    daten, fehler = await _holen("/kategorien")
    if fehler:
        return None, "", fehler
    if not daten:
        return None, "", "Es ist noch keine Kategorie angelegt."

    wort = _vergleichsform(gesucht)
    genau = [k for k in daten if _vergleichsform(k.get("name")) == wort]
    # Erst genau, dann ungefaehr: "Lebensmittel" darf nicht an
    # "Lebensmittel und Drogerie" scheitern, aber wo es exakt passt,
    # gewinnt das Exakte.
    treffer = genau or [k for k in daten
                        if wort and (wort in _vergleichsform(k.get("name"))
                                     or _vergleichsform(k.get("name")) in wort)]
    if len(treffer) == 1:
        return treffer[0].get("id"), treffer[0].get("name"), ""
    if len(treffer) > 1:
        namen = ", ".join(str(k.get("name")) for k in treffer)
        return None, "", (f"Auf {gesucht} passen mehrere Kategorien: "
                          f"{namen}. Welche davon?")
    oben = [str(k.get("name")) for k in daten[:config.FINANZ_HOECHSTENS]]
    satz = f"Eine Kategorie {gesucht} kenne ich nicht. Es gibt " + \
           ", ".join(oben)
    rest = len(daten) - len(oben)
    if rest > 0:
        satz += f" und {rest} weitere"
    return None, "", satz + "."


def werkzeuge(protokoll=None, leuchten=None) -> list:
    def vermerken(text: str):
        if protokoll is not None:
            protokoll.merken(text)

    def blinken():
        if leuchten:
            leuchten("Finanzen")

    def _zeitraum(args) -> dict:
        return {"von": args.get("von"), "bis": args.get("bis"),
                "konto_id": args.get("konto_id")}

    def _antwort(text: str, fehler: str = ""):
        return {"content": [{"type": "text", "text": fehler or text}],
                **({"is_error": True} if fehler else {})}

    def _deckelhinweis(gewuenscht: int) -> str:
        """Der Nachsatz, wenn mehr gewuenscht war als vorgelesen wird.

        Der Deckel ist Absicht (config.FINANZ_HOECHSTENS). Gefehlt hat nur
        der Hinweis: Wer "die letzten fuenfzehn Buchungen" verlangte, bekam
        sechs vorgelesen und musste sie fuer alle halten.
        """
        if gewuenscht > config.FINANZ_HOECHSTENS:
            return " Mehr lese ich nicht am Stück vor."
        return ""

    GEDECKELT = {"type": "integer",
                 "description": "Wie viele. Vorgabe 5, höchstens "
                                f"{config.FINANZ_HOECHSTENS} — mehr wird "
                                "nicht am Stück vorgelesen."}

    ZEITRAUM = {
        "von": {"type": "string",
                "description": "Anfang, ISO wie 2026-07-01. Weglassen = alles.",
                "pattern": r"^\d{4}-\d{2}-\d{2}$"},
        "bis": {"type": "string",
                "description": "Ende, ISO wie 2026-07-31.",
                "pattern": r"^\d{4}-\d{2}-\d{2}$"},
        "konto_id": {"type": "integer",
                     "description": "Nur dieses Konto. Weglassen = alle."},
    }

    # Beim Kontostand ist "von" die gefaehrliche Angabe: der Endpunkt
    # summiert nur, was im Zeitraum liegt. Wer nach dem Stand Ende Juli
    # fragt, will alles bis dahin -- also nur "bis". Mit "von" bekaeme er
    # den Zuwachs des Zeitraums vorgelesen und hielte ihn fuer den Saldo.
    STICHTAG = dict(
        ZEITRAUM,
        von={**ZEITRAUM["von"],
             "description": "Nur wenn ausdrücklich AB einem Tag gerechnet "
                            "werden soll. Für einen Stichtag weglassen."},
        bis={**ZEITRAUM["bis"],
             "description": "Stichtag, ISO wie 2026-07-31. Weglassen = heute."},
    )

    @tool(
        "finanzen_kontostand",
        "Sagt den Kontostand — heute oder zu einem Stichtag. Für 'wie viel "
        "habe ich noch', 'wie stand mein Konto Ende Juli'. Ohne konto_id über "
        "alle Konten zusammen. Für einen Stichtag NUR bis setzen, von "
        "weglassen. Rechne das Datum selbst aus — heute steht in deinem "
        "Vorspann.",
        {"type": "object", "properties": dict(STICHTAG)},
    )
    async def finanzen_kontostand(args):
        blinken()
        daten, fehler = await _holen("/auswertungen/kontostand",
                                     **_zeitraum(args))
        if fehler:
            return _antwort("", fehler)
        if not daten:
            # Ohne konto_id waere "zu dem Konto" gelogen, mit Stichtag heisst
            # leer ausserdem "bis dahin nichts" und nicht "gar nichts".
            return _antwort("Dazu finde ich keinen Kontostand — bis dahin ist "
                            "keine Buchung verbucht.")
        # Der letzte Punkt traegt den Saldo am Ende des abgefragten
        # Zeitraums. Sein Datum aber nicht: gemessen am 28.08.2026 gibt der
        # Endpunkt auch mit bis=2026-01-31 einen Punkt von heute zurueck.
        # Vorgelesen wird darum der erfragte Stichtag -- sonst behauptet der
        # Satz einen Stand von heute, den er gar nicht gerechnet hat.
        letzter = daten[-1]
        stand = (_datum(args["bis"]) if args.get("bis")
                 else _datum(letzter.get("datum")))
        return _antwort(
            f"Der Kontostand liegt bei {_betrag(letzter.get('saldo'))}, "
            f"Stand {stand}.")

    @tool(
        "finanzen_ausgaben",
        "Wofür das Geld draufgeht: Ausgaben nach Kategorie in einem Zeitraum. "
        "Für 'was habe ich im Juli ausgegeben', 'wofür geht mein Geld drauf'. "
        "Rechne den Zeitraum selbst aus — das heutige Datum steht in deinem "
        "Vorspann.",
        {"type": "object", "properties": dict(ZEITRAUM)},
    )
    async def finanzen_ausgaben(args):
        blinken()
        daten, fehler = await _holen("/auswertungen/kategorien",
                                     nur_ausgaben=True, **_zeitraum(args))
        if fehler:
            return _antwort("", fehler)
        if not daten:
            return _antwort("In dem Zeitraum sind keine Ausgaben verbucht.")
        gesamt = sum(Decimal(str(e.get("summe", "0"))) for e in daten)
        # Nur die groessten: Eine Aufzaehlung von zwanzig Kategorien ist
        # gesprochen nicht auszuhalten.
        oben = daten[:config.FINANZ_HOECHSTENS]
        teile = [f"{e.get('kategorie') or 'ohne Kategorie'} "
                 f"{_betrag(e.get('summe'))}" for e in oben]
        rest = len(daten) - len(oben)
        satz = (f"Insgesamt {_betrag(gesamt)}. Die größten Posten: "
                + ", ".join(teile))
        if rest > 0:
            satz += f", dazu {rest} kleinere Kategorien"
        return _antwort(satz + ".")

    @tool(
        "finanzen_monate",
        "Einnahmen, Ausgaben und was übrig blieb — je Monat. Für 'wie war "
        "der letzte Monat', 'komme ich hin', 'wie viel spare ich'.",
        {"type": "object", "properties": dict(ZEITRAUM)},
    )
    async def finanzen_monate(args):
        blinken()
        daten, fehler = await _holen("/auswertungen/monate", **_zeitraum(args))
        if fehler:
            return _antwort("", fehler)
        if not daten:
            return _antwort("Dazu sind noch keine Monate ausgewertet.")
        # Die jüngsten zuerst -- danach wird gefragt, nicht nach dem Anfang.
        letzte = daten[-config.FINANZ_HOECHSTENS:][::-1]
        teile = [f"{_monat(m.get('monat'))}: {_betrag(m.get('einnahmen'))} "
                 f"rein, {_betrag(m.get('ausgaben'))} raus, "
                 f"{'plus' if Decimal(str(m.get('saldo', '0'))) >= 0 else 'minus'} "
                 f"{_betrag(m.get('saldo'))}" for m in letzte]
        return _antwort(". ".join(teile) + ".")

    @tool(
        "finanzen_empfaenger",
        "An wen das Geld geht: die größten Gegenparteien in einem Zeitraum. "
        "Für 'wo gebe ich am meisten aus', 'wie viel zahle ich an X'.",
        {"type": "object",
         "properties": dict(ZEITRAUM, limit=GEDECKELT)},
    )
    async def finanzen_empfaenger(args):
        blinken()
        gewuenscht = int(args.get("limit") or 5)
        wie_viele = min(gewuenscht, config.FINANZ_HOECHSTENS)
        daten, fehler = await _holen("/auswertungen/gegenparteien",
                                     nur_ausgaben=True, limit=wie_viele,
                                     **_zeitraum(args))
        if fehler:
            return _antwort("", fehler)
        if not daten:
            return _antwort("Dazu finde ich keine Empfänger.")
        teile = []
        for e in daten:
            anzahl = e.get("anzahl") or 0
            # "in 1 Buchungen" faellt beim Zuhoeren sofort auf.
            wort = "Buchung" if anzahl == 1 else "Buchungen"
            teile.append(f"{e.get('gegenpartei')} {_betrag(e.get('summe'))} "
                         f"in {anzahl} {wort}")
        return _antwort("; ".join(teile) + "." + _deckelhinweis(gewuenscht))

    @tool(
        "finanzen_buchungen",
        "Sucht einzelne Buchungen — nach Stichwort, Zeitraum oder Konto. Für "
        "'was habe ich bei REWE ausgegeben', 'zeig mir die letzten Buchungen', "
        "'Buchungen aus Lebensmittel'. Die Kategorie wird als NAME angegeben, "
        "so wie gesprochen — die id musst du nicht kennen. "
        "Für Summen und Übersichten nimm lieber finanzen_ausgaben.",
        {"type": "object",
         "properties": dict(ZEITRAUM,
                            suche={"type": "string",
                                   "description": "Stichwort im "
                                                  "Verwendungszweck."},
                            kategorie={"type": "string",
                                       "description": "Name der Kategorie, so "
                                                      "wie gesagt: "
                                                      "'Lebensmittel'."},
                            kategorie_id={"type": "integer",
                                          "description": "Nur falls die id "
                                                         "schon bekannt ist. "
                                                         "Sonst kategorie "
                                                         "nehmen."},
                            limit=GEDECKELT)},
    )
    async def finanzen_buchungen(args):
        blinken()
        gewuenscht = int(args.get("limit") or 5)
        wie_viele = min(gewuenscht, config.FINANZ_HOECHSTENS)
        # Die Auflösung des Namens gehoert HIERHER und nicht in ein eigenes
        # Werkzeug, das man vorher aufrufen muesste: gesagt wird ein Satz
        # ("Buchungen aus Lebensmittel"), also soll auch ein Werkzeug
        # genuegen. Zwei Aufrufe hintereinander waeren zwei Gelegenheiten,
        # die falsche Nummer zu waehlen -- und im Zweifel erfindet ein
        # Modell die id lieber, als noch einmal nachzuschlagen.
        kategorie_id = args.get("kategorie_id")
        if args.get("kategorie"):
            kategorie_id, _name, fehler = await _kategorie_treffen(
                args["kategorie"])
            if fehler:
                return _antwort("", fehler)
        daten, fehler = await _holen("/transaktionen", suche=args.get("suche"),
                                     kategorie_id=kategorie_id,
                                     limit=wie_viele, **_zeitraum(args))
        if fehler:
            return _antwort("", fehler)
        if not daten:
            return _antwort("Dazu finde ich keine Buchung.")
        teile = []
        for b in daten:
            # Eine Umbuchung als "Ausgabe" vorzulesen waere falsch: das Geld
            # ist nicht weg, es liegt auf dem anderen eigenen Konto.
            if b.get("umbuchung_id"):
                richtung = "Umbuchung"
            else:
                richtung = ("Ausgabe" if Decimal(str(b.get("betrag", "0"))) < 0
                            else "Einnahme")
            teile.append(f"{_datum(b.get('datum'))}: {richtung} "
                         f"{_betrag(b.get('betrag'))}, "
                         f"{b.get('verwendungszweck') or 'ohne Zweck'}")
        return _antwort(". ".join(teile) + "." + _deckelhinweis(gewuenscht))

    @tool(
        "finanzen_konten",
        "Zählt die Konten auf, mit Namen und Bank. Brauchst du, um an eine "
        "konto_id zu kommen.",
        {"type": "object", "properties": {}},
    )
    async def finanzen_konten(args):
        blinken()
        daten, fehler = await _holen("/konten")
        if fehler:
            return _antwort("", fehler)
        if not daten:
            return _antwort("Es ist noch kein Konto angelegt.")
        namen = {k.get("id"): k.get("name") for k in daten}
        teile = []
        for k in daten:
            satz = f"{k.get('id')}: {k.get('name')}"
            if k.get("bank"):
                satz += f" bei der {k.get('bank')}"
            # Konten koennen unter einem anderen haengen. Ohne diesen Zusatz
            # klaenge ein Sparkonto wie ein zweites Girokonto.
            if k.get("eltern_id") in namen:
                satz += f", Unterkonto von {namen[k['eltern_id']]}"
            teile.append(satz)
        return _antwort("; ".join(teile) + ".")

    @tool(
        "finanzen_kategorien",
        "Zählt die Kategorien auf oder sagt, welche Nummer eine bestimmte hat. "
        "Für 'welche Kategorien gibt es'. Um Buchungen einer Kategorie zu "
        "sehen, brauchst du das hier NICHT — finanzen_buchungen nimmt den "
        "Namen selbst entgegen.",
        {"type": "object",
         "properties": {"name": {"type": "string",
                                 "description": "Optional: nur zu dieser "
                                                "Kategorie, so wie gesagt."}}},
    )
    async def finanzen_kategorien(args):
        blinken()
        if args.get("name"):
            kennung, name, fehler = await _kategorie_treffen(args["name"])
            if fehler:
                return _antwort("", fehler)
            return _antwort(f"{name} hat die Nummer {kennung}.")
        daten, fehler = await _holen("/kategorien")
        if fehler:
            return _antwort("", fehler)
        if not daten:
            return _antwort("Es ist noch keine Kategorie angelegt.")
        # Derselbe Deckel wie ueberall: zwanzig Namen am Stueck sind
        # gesprochen nicht zu behalten.
        oben = daten[:config.FINANZ_HOECHSTENS]
        satz = ", ".join(f"{k.get('id')}: {k.get('name')}" for k in oben)
        rest = len(daten) - len(oben)
        if rest > 0:
            satz += f", dazu {rest} weitere"
        return _antwort(satz + ".")

    @tool(
        "finanzen_vergleich",
        "Vergleicht die Ausgaben zweier Zeiträume und sagt, wo der "
        "Unterschied herkommt. Für 'vergleiche Januar mit Dezember', 'gebe "
        "ich mehr aus als im letzten Monat'. von und bis sind der Zeitraum, "
        "über den geredet wird; vergleich_von und vergleich_bis der, mit dem "
        "verglichen wird. Rechne die vier Daten selbst aus — heute steht in "
        "deinem Vorspann.",
        {"type": "object",
         "properties": dict(
             ZEITRAUM,
             # Hier sind von und bis Pflicht -- die geerbte Beschreibung
             # "Weglassen = alles" waere an dieser Stelle eine Einladung
             # zum offenen Zeitraum, und verglichen wird dann nichts.
             von={**ZEITRAUM["von"],
                  "description": "Anfang des ersten Zeitraums, ISO wie "
                                 "2026-01-01."},
             bis={**ZEITRAUM["bis"],
                  "description": "Ende des ersten Zeitraums, ISO wie "
                                 "2026-01-31."},
             vergleich_von={"type": "string",
                            "description": "Anfang des Vergleichszeitraums, "
                                           "ISO wie 2025-12-01.",
                            "pattern": r"^\d{4}-\d{2}-\d{2}$"},
             vergleich_bis={"type": "string",
                            "description": "Ende des Vergleichszeitraums, "
                                           "ISO wie 2025-12-31.",
                            "pattern": r"^\d{4}-\d{2}-\d{2}$"}),
         "required": ["von", "bis", "vergleich_von", "vergleich_bis"]},
    )
    async def finanzen_vergleich(args):
        blinken()
        erster, fehler = await _holen("/auswertungen/kategorien",
                                      nur_ausgaben=True, **_zeitraum(args))
        if fehler:
            return _antwort("", fehler)
        zweiter, fehler = await _holen("/auswertungen/kategorien",
                                       nur_ausgaben=True,
                                       von=args.get("vergleich_von"),
                                       bis=args.get("vergleich_bis"),
                                       konto_id=args.get("konto_id"))
        if fehler:
            return _antwort("", fehler)

        def summen(daten) -> dict:
            """Kategoriename -> Hoehe der Ausgaben, als Decimal.

            abs(): mit nur_ausgaben ist ohnehin alles eine Ausgabe, und ob
            die Schnittstelle sie negativ oder positiv fuehrt, darf die
            Richtung der Differenz nicht drehen. So heisst plus immer "mehr
            ausgegeben".
            """
            werte = {}
            for e in daten or []:
                name = e.get("kategorie") or "ohne Kategorie"
                try:
                    hoehe = abs(Decimal(str(e.get("summe", "0"))))
                except (InvalidOperation, ValueError):
                    continue
                werte[name] = werte.get(name, Decimal("0")) + hoehe
            return werte

        # Gerechnet wird hier, nicht im Sprachmodell: eine subtrahierte Zahl
        # kann nicht halluziniert sein, eine vorgelesene schon.
        jetzt, vorher = summen(erster), summen(zweiter)
        if not jetzt and not vorher:
            return _antwort("In beiden Zeiträumen sind keine Ausgaben "
                            "verbucht.")
        gesamt_jetzt = sum(jetzt.values(), Decimal("0"))
        gesamt_vorher = sum(vorher.values(), Decimal("0"))
        unterschied = gesamt_jetzt - gesamt_vorher

        satz = (f"{_datum(args.get('von'))} bis {_datum(args.get('bis'))}: "
                f"{_betrag(gesamt_jetzt)}. "
                f"{_datum(args.get('vergleich_von'))} bis "
                f"{_datum(args.get('vergleich_bis'))}: "
                f"{_betrag(gesamt_vorher)}. ")
        if unterschied == 0:
            satz += "Genau gleich viel."
        else:
            satz += (f"Das sind {_betrag(unterschied)} "
                     f"{'mehr' if unterschied > 0 else 'weniger'}.")

        abweichungen = [
            (name, jetzt.get(name, Decimal("0")) - vorher.get(name, Decimal("0")))
            for name in set(jetzt) | set(vorher)]
        # Unveraenderte Kategorien sagen nichts aus und kosten nur Zeit im
        # Vorlesen; sortiert wird nach Betrag, egal in welche Richtung.
        abweichungen = sorted((p for p in abweichungen if p[1] != 0),
                              key=lambda p: abs(p[1]), reverse=True)
        if abweichungen:
            oben = abweichungen[:config.FINANZ_HOECHSTENS]
            teile = [f"{name} {_betrag(d)} {'mehr' if d > 0 else 'weniger'}"
                     for name, d in oben]
            satz += " Die größten Abweichungen: " + ", ".join(teile)
            rest = len(abweichungen) - len(oben)
            if rest > 0:
                satz += f", dazu {rest} kleinere"
            satz += "."
        return _antwort(satz)

    @tool(
        "finanzen_buchen",
        "Trägt eine Buchung ein. Für 'trag zwölf Euro fünfzig für Bäcker ein'. "
        "WICHTIG: Ausgaben sind NEGATIV ('-12.50'), Einnahmen positiv. Der "
        "Betrag ist eine Zeichenkette mit Punkt als Dezimaltrenner. Das Datum "
        "ist ISO; ohne Angabe wird heute genommen. Die Stichwort-Regeln des "
        "Dashboards vergeben die Kategorie automatisch.",
        {
            "type": "object",
            "properties": {
                "betrag": {"type": "string",
                           "description": "Zeichenkette, Punkt als Trenner. "
                                          "Ausgabe negativ: '-12.50'.",
                           "pattern": r"^-?\d+(\.\d{1,2})?$"},
                "verwendungszweck": {"type": "string",
                                     "description": "Wofür, in eigenen Worten."},
                "konto_id": {"type": "integer",
                             "description": "Auf welches Konto. Bei nur einem "
                                            "Konto dessen id."},
                "datum": {"type": "string",
                          "description": "ISO. Weglassen = heute.",
                          "pattern": r"^\d{4}-\d{2}-\d{2}$"},
                "gegenpartei": {"type": "string",
                                "description": "Optional: an wen bzw. von wem."},
            },
            "required": ["betrag", "verwendungszweck", "konto_id"],
        },
    )
    async def finanzen_buchen(args):
        koerper = {
            "datum": args.get("datum") or f"{date.today():%Y-%m-%d}",
            "betrag": str(args.get("betrag")),
            "verwendungszweck": " ".join(
                str(args.get("verwendungszweck") or "").split()),
            "konto_id": int(args.get("konto_id")),
        }
        if args.get("gegenpartei"):
            koerper["gegenpartei"] = " ".join(str(args["gegenpartei"]).split())

        _, fehler = await _schicken("/transaktionen", koerper, "die Buchung")
        if fehler:
            return _antwort("", fehler)

        blinken()
        vermerken(f"finanzen_buchen: {koerper['betrag']} für "
                  f"{koerper['verwendungszweck']}")
        richtung = "Ausgabe" if koerper["betrag"].startswith("-") else "Einnahme"
        return _antwort(f"Eingetragen: {richtung} über "
                        f"{_betrag(koerper['betrag'])} für "
                        f"{koerper['verwendungszweck']}.")

    @tool(
        "finanzen_umbuchen",
        "Schiebt Geld von einem eigenen Konto auf ein anderes — Sparen, "
        "Rücklage, Ausgleich. Für 'leg zweihundert Euro aufs Sparkonto'. "
        "Der Betrag ist hier POSITIV ('200.00'); die Richtung sagen "
        "von_konto_id und nach_konto_id. Das Dashboard legt zwei verbundene "
        "Buchungen an, die weder als Einnahme noch als Ausgabe zählen — es "
        "hat ja niemand etwas verdient oder ausgegeben. Für eine "
        "gewöhnliche Ausgabe nimm finanzen_buchen.",
        {
            "type": "object",
            "properties": {
                "betrag": {"type": "string",
                           "description": "Positiv, Punkt als Trenner: "
                                          "'200.00'.",
                           "pattern": r"^\d+(\.\d{1,2})?$"},
                "von_konto_id": {"type": "integer",
                                 "description": "Von welchem Konto das Geld "
                                                "abgeht."},
                "nach_konto_id": {"type": "integer",
                                  "description": "Auf welches Konto es geht."},
                "verwendungszweck": {"type": "string",
                                     "description": "Optional, wofür."},
                "datum": {"type": "string",
                          "description": "ISO. Weglassen = heute.",
                          "pattern": r"^\d{4}-\d{2}-\d{2}$"},
            },
            "required": ["betrag", "von_konto_id", "nach_konto_id"],
        },
    )
    async def finanzen_umbuchen(args):
        von, nach = int(args.get("von_konto_id")), int(args.get("nach_konto_id"))
        if von == nach:
            return _antwort("", "Von und nach demselben Konto — das wäre "
                                "keine Umbuchung.")
        # Das Dashboard verlangt einen Betrag ueber null. Hier abgefangen
        # ergibt das einen Satz statt einer Fehlernummer.
        try:
            if Decimal(str(args.get("betrag"))) <= 0:
                raise InvalidOperation
        except (InvalidOperation, TypeError, ValueError):
            return _antwort("", "Für eine Umbuchung brauche ich einen Betrag "
                                "über null, positiv angegeben.")
        koerper = {
            "datum": args.get("datum") or f"{date.today():%Y-%m-%d}",
            "betrag": str(args.get("betrag")),
            "von_konto_id": von,
            "nach_konto_id": nach,
            "verwendungszweck": " ".join(
                str(args.get("verwendungszweck") or "").split()),
        }
        _, fehler = await _schicken("/transaktionen/umbuchung", koerper,
                                    "die Umbuchung")
        if fehler:
            return _antwort("", fehler)

        blinken()
        vermerken(f"finanzen_umbuchen: {koerper['betrag']} von Konto {von} "
                  f"auf Konto {nach}")
        # Fuer den Satz zaehlen Namen, nicht Nummern. Scheitert der Abruf,
        # bleibt es bei "Konto 3" -- die Umbuchung steht davon unberuehrt.
        konten, _fehler = await _holen("/konten")
        namen = {k.get("id"): k.get("name") for k in (konten or [])}
        satz = (f"Umgebucht: {_betrag(koerper['betrag'])} von "
                f"{namen.get(von) or f'Konto {von}'} auf "
                f"{namen.get(nach) or f'Konto {nach}'}")
        if koerper["verwendungszweck"]:
            satz += f", {koerper['verwendungszweck']}"
        return _antwort(satz + ".")

    return [finanzen_kontostand, finanzen_ausgaben, finanzen_monate,
            finanzen_empfaenger, finanzen_buchungen, finanzen_konten,
            finanzen_kategorien, finanzen_vergleich,
            finanzen_buchen, finanzen_umbuchen]
