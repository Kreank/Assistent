"""Gedaechtnis schreiben und lesen.

ZWEI SCHICHTEN, und die Trennung entscheidet, ob das Ding auf Dauer
taugt:

  Schicht 1, immer geladen -- haengt an jedem Zuruf mit dran:
    kern.md         Wenige dauerhafte Fakten (siehe gedaechtnis.py).
    gemerkt.md      Was du ausdruecklich gesagt hast. Gilt als Tatsache.
    beobachtet.md   Was Sarvis geschlossen hat. Gilt als Vermutung.

  Schicht 2, nur auf Nachfrage -- kostet einen Werkzeugaufruf:
    personen/<name>.md        alles ueber einen Menschen
    notizen/JJJJ-MM-TT-*.md   Episodisches, datiert

Schicht 1 ist teuer und deshalb begrenzt (config.GEDAECHTNIS_MAX_
EINTRAEGE). Schicht 2 darf beliebig wachsen -- sie wird nur gelesen,
wenn jemand danach fragt. Ohne Schicht 2 gaebe es fuer alles nur den
teuren Platz, und genau daran kippen Gedaechtnisse: Nicht weil sie zu
viel wissen, sondern weil alles gleich laut ist.

Quer dazu liegt die Trennung nach SICHERHEIT, und die bleibt in
Schicht 1 wie sie war: gemerkt gegen beobachtet. Sie ist nicht
Ordnungsliebe. Eine Vermutung zu speichern ist
harmlos; sie spaeter als Tatsache zu behandeln ist es nicht. Getrennte
Dateien machen den Unterschied nachlesbar -- fuer Sarvis und fuer dich.

Fuer Handlungen nach aussen zaehlt ohnehin keins von beidem: Mail,
Telegram und Termine gehen nur auf ausdruecklichen Zuruf und mit
Rueckfrage.
"""
import re
from datetime import date, datetime

from claude_agent_sdk import tool

from .. import config

GESAGT = "gemerkt.md"
BEMERKT = "beobachtet.md"

KOPF = {
    GESAGT: "# Gemerkt\n\nWas du mir ausdrücklich gesagt hast.\n",
    BEMERKT: ("# Beobachtet\n\nWas mir von selbst aufgefallen ist — "
              "**Vermutungen, keine Tatsachen.**\nHier darf falsch stehen, "
              "was ich falsch verstanden habe. Durchsehen und korrigieren\n"
              "ist ausdrücklich vorgesehen.\n"),
}

_ABLAUF = re.compile(r"\(gilt bis (\d{1,2})\.(\d{1,2})\.(\d{4})\)")


def _datei(art: str):
    return config.GEDAECHTNIS / (BEMERKT if art == "bemerkt" else GESAGT)


def _sauberer_name(text: str, laenge: int = 40) -> str:
    """Aus einem gesprochenen Namen einen Dateinamen machen.

    Gesprochen kommt "Thomas Müller" oder "das Finanzdashboard" -- daraus
    muss ein Name werden, den man auf jedem Dateisystem anlegen kann und
    unter dem man ihn spaeter wiederfindet.
    """
    t = " ".join(str(text or "").split()).lower()
    for alt, neu in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        t = t.replace(alt, neu)
    t = re.sub(r"[^a-z0-9]+", "-", t).strip("-")
    return t[:laenge] or "ohne-namen"


def _falten(text: str) -> str:
    """Umlaute auf beiden Seiten gleich schreiben.

    Dateinamen sind umlautfrei (_sauberer_name), gesprochene Namen nicht.
    Ohne diese Faltung fand "Müller" die Zeile "Müller", aber nie die
    Akte mueller.md -- und "Mueller" umgekehrt nichts von beidem.
    """
    t = str(text or "").lower()
    for alt, neu in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        t = t.replace(alt, neu)
    return t


def _personenordner():
    p = config.GEDAECHTNIS / "personen"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _notizenordner():
    p = config.GEDAECHTNIS / "notizen"
    p.mkdir(parents=True, exist_ok=True)
    return p


def notiz_anlegen(titel: str, inhalt: str) -> str:
    """Eine datierte Notiz in Schicht 2. Gibt den Dateinamen zurueck."""
    ordner = _notizenordner()
    stamm = f"{datetime.now():%Y-%m-%d}-{_sauberer_name(titel)}"
    pfad = ordner / f"{stamm}.md"
    zaehler = 2
    while pfad.exists():          # zwei Notizen am selben Tag, gleicher Titel
        pfad = ordner / f"{stamm}-{zaehler}.md"
        zaehler += 1
    pfad.write_text(
        f"# {' '.join(str(titel).split())}\n\n"
        f"_{datetime.now():%d.%m.%Y %H:%M}_\n\n{inhalt.strip()}\n",
        encoding="utf-8")
    return pfad.name


def _datum_von(zeile: str) -> str:
    """Das fuehrende Datum eines Eintrags -- zum Sortieren nach Alter."""
    t = re.match(r"- (\d{4}-\d{2}-\d{2})", zeile.strip())
    return t.group(1) if t else "0000-00-00"


def _ablegen(art: str, zeilen: list[str]) -> None:
    """Eintraege eine Schicht tiefer legen, statt sie wegzuwerfen.

    EINE Sammeldatei je Monat, nicht eine je Auslagerung. Sonst entstehen
    im Lauf eines Jahres Dutzende Schnipsel mit je zwei Zeilen -- und die
    zu durchsuchen ist muehsamer, als sie wert sind.
    """
    if not zeilen:
        return
    ablage = _notizenordner() / f"{datetime.now():%Y-%m}-ausgelagert-{art}.md"
    if not ablage.exists():
        ablage.write_text(
            f"# Ausgelagert aus {art}\n\n"
            "Diese Einträge standen im immer geladenen Gedächtnis und sind "
            "dort verschwunden — weil zu viele dazukamen oder weil eine "
            "neuere Angabe sie ersetzt hat.\n**Gelöscht ist nichts**, über "
            "gedaechtnis_nachschlagen sind sie weiter zu finden.\n\n",
            encoding="utf-8")
    with open(ablage, "a", encoding="utf-8") as f:
        f.write("\n".join(zeilen) + "\n")


def umschichten(art: str) -> int:
    """Was ueber die Grenze hinausgeht, wandert eine Schicht tiefer.

    Bewusst NICHT loeschen. Was der Nutzer ausdruecklich gesagt hat, darf
    nicht verschwinden, nur weil viel dazugekommen ist -- es steht danach
    in einer datierten Notiz und bleibt ueber gedaechtnis_nachschlagen
    auffindbar. Es haengt nur nicht mehr an jedem einzelnen Zuruf mit
    dran.

    Das Aelteste zuerst: Was lange niemand bestaetigt hat, ist eher eine
    Erinnerung als eine Tatsache.
    """
    pfad = _datei(art)
    zeilen = _zeilen(pfad)
    ueber = len(zeilen) - config.GEDAECHTNIS_MAX_EINTRAEGE
    if ueber <= 0:
        return 0
    zeilen.sort(key=_datum_von)
    raus, bleiben = zeilen[:ueber], zeilen[ueber:]
    _ablegen(art, raus)
    _schreiben(pfad, bleiben)
    print(f"  (Gedächtnis: {len(raus)} alte Einträge in eine Notiz ausgelagert)")
    return len(raus)


def nachschlagen(stichwort: str, hoechstens: int = 6) -> list:
    """Schicht 2 durchsuchen: Personen und Notizen.

    Rueckgabe: Liste von (Datei, passende Zeilen). Bewusst zeilenweise --
    eine ganze Notiz vorzulesen ist unzumutbar, die passende Zeile
    beantwortet die Frage.
    """
    suche = " ".join(str(stichwort or "").lower().split())
    if not suche:
        return []
    # Beim Anlegen wird der Name zum Dateinamen gefaltet ("Thomas Müller"
    # -> thomas-mueller), beim Suchen war er es nicht. "thomas müller" in
    # "thomas-mueller" ist False -- die Akte galt dann nur ueber ihre
    # Ueberschriftzeile als Treffer, und geliefert wurde auch nur die.
    # Sarvis sah eine leere Akte und sagte, er wisse nichts, obwohl alles
    # dastand. Deshalb wird jetzt genauso gefaltet wie beim Schreiben.
    schluessel = _sauberer_name(suche, 80)
    if schluessel == "ohne-namen":
        schluessel = ""       # der Rueckfall von _sauberer_name, kein Treffer
    gefaltet = _falten(suche)
    treffer = []
    for ordner in (_personenordner(), _notizenordner()):
        for datei in sorted(ordner.glob("*.md"), reverse=True):
            if datei.stem == "BEISPIEL":
                continue
            try:
                text = datei.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            stamm = datei.stem.lower()
            passt = gefaltet in stamm or (schluessel and schluessel in stamm)
            zeilen = [z.strip() for z in text.splitlines()
                      if z.strip() and (passt or gefaltet in _falten(z))]
            if zeilen:
                treffer.append((datei.name, zeilen[:8]))
            if len(treffer) >= hoechstens:
                return treffer
    return treffer


def _zeilen(pfad) -> list[str]:
    if not pfad.exists():
        return []
    return [z for z in pfad.read_text(encoding="utf-8").splitlines()
            if z.strip().startswith("- ")]


def _abgelaufen(zeile: str, heute: date) -> bool:
    t = _ABLAUF.search(zeile)
    if not t:
        return False
    try:
        return date(int(t.group(3)), int(t.group(2)), int(t.group(1))) < heute
    except ValueError:
        return False


def aufraeumen(art: str) -> int:
    """Abgelaufene Eintraege entfernen. Gibt zurueck, wie viele.

    Das ist die Stelle, an der die meisten Gedaechtnisse scheitern: Sie
    sammeln, aber vergessen nie. "Ich bin naechste Woche in Hamburg" ist
    in drei Wochen schlicht falsch.
    """
    pfad = _datei(art)
    zeilen = _zeilen(pfad)
    if not zeilen:
        return 0
    heute = date.today()
    bleiben = [z for z in zeilen if not _abgelaufen(z, heute)]
    weg = len(zeilen) - len(bleiben)
    if weg:
        _schreiben(pfad, bleiben)
    return weg


def _fremdtext(pfad) -> list[str]:
    """Zeilen, die weder Eintrag noch Kopf sind -- also von Hand geschrieben.

    Der Kopf von beobachtet.md fordert ausdruecklich zum Korrigieren auf.
    Wer daraufhin einen Satz ohne fuehrenden Strich dazuschreibt, war ihn
    beim naechsten Schreibvorgang los: _zeilen() liest nur '- '-Zeilen,
    und _schreiben() baute die Datei genau daraus neu auf.
    """
    if not pfad.exists():
        return []
    kopf = {z for z in KOPF.get(pfad.name, "").splitlines() if z.strip()}
    return [z for z in pfad.read_text(encoding="utf-8").splitlines()
            if z.strip() and not z.strip().startswith("- ") and z not in kopf]


def _schreiben(pfad, zeilen: list[str]) -> None:
    kopf = KOPF.get(pfad.name, "")
    fremd = _fremdtext(pfad)
    pfad.parent.mkdir(parents=True, exist_ok=True)
    text = kopf + "\n"
    if fremd:
        # Vor den Eintraegen, nicht dazwischen: Die urspruengliche Stelle
        # laesst sich nicht sicher wiederfinden, der Satz selbst schon.
        text += "\n".join(fremd) + "\n\n"
    pfad.write_text(text + "\n".join(zeilen) + "\n", encoding="utf-8")


def lesen(art: str) -> list[str]:
    aufraeumen(art)
    return _zeilen(_datei(art))


def werkzeuge(protokoll=None, leuchten=None) -> list:
    def vermerken(text: str):
        if protokoll is not None:
            protokoll.merken(text)

    def blinken():
        if leuchten:
            leuchten("Gedächtnis")

    @tool(
        "merken",
        "Schreibt etwas ins Langzeitgedächtnis. Zwei Arten, und die "
        "Unterscheidung ist wichtig: 'gesagt' für alles, worum der Nutzer "
        "dich ausdrücklich bittet ('merk dir, dass...'). 'bemerkt' für "
        "etwas, das dir von selbst auffällt und dauerhaft nützlich ist — "
        "sparsam benutzen, nur was über den Tag hinaus zählt, niemals "
        "Vergängliches wie laufende Timer. Was nur eine Weile gilt, "
        "bekommt gilt_bis.",
        {
            "type": "object",
            "properties": {
                "inhalt": {
                    "type": "string",
                    "description": "Der Sachverhalt, ein Satz, aus sich "
                                   "heraus verständlich. Nicht 'sie heißt "
                                   "Anna', sondern 'Seine Schwester heißt "
                                   "Anna'.",
                },
                "art": {
                    "type": "string",
                    "enum": ["gesagt", "bemerkt"],
                    "description": "'gesagt' = ausdrücklich gewünscht, "
                                   "'bemerkt' = eigene Beobachtung.",
                },
                "gilt_bis": {
                    "type": "string",
                    "description": "Optional, TT.MM.JJJJ. Für alles "
                                   "Vergängliche. Danach verschwindet der "
                                   "Eintrag von selbst.",
                    "pattern": r"^\d{1,2}\.\d{1,2}\.\d{4}$",
                },
            },
            "required": ["inhalt", "art"],
        },
    )
    async def merken(args):
        inhalt = " ".join(str(args.get("inhalt") or "").split())
        if not inhalt:
            return {"content": [{"type": "text", "text":
                    "Da war kein Inhalt."}], "is_error": True}
        art = args.get("art") or "gesagt"
        pfad = _datei(art)
        zeilen = _zeilen(pfad)

        eintrag = f"- {datetime.now():%Y-%m-%d} — {inhalt}"
        if args.get("gilt_bis"):
            eintrag += f"  (gilt bis {args['gilt_bis']})"

        # Widersprueche ersetzen statt anhaeufen: zwei sich widersprechende
        # Eintraege sind schlimmer als keiner. Aber erst ab einer Laenge,
        # die wirklich denselben Sachverhalt meint -- ein kurzer Kern ist
        # Praefix von allem Moeglichen und frass sonst den genaueren
        # Eintrag ("Ich mag Kaffee" gegen "Ich mag Kaffee schwarz").
        kern = inhalt.lower()[:40]
        ersetzt = [z for z in zeilen if len(kern) >= 20 and kern in z.lower()]
        if ersetzt:
            # Aus Schicht 1 nehmen heisst nicht wegwerfen -- dasselbe
            # Versprechen wie in umschichten().
            _ablegen(art, ersetzt)
            zeilen = [z for z in zeilen if z not in ersetzt]
        zeilen.append(eintrag)
        _schreiben(pfad, zeilen)
        umschichten(art)      # Schicht 1 bleibt klein genug, um zu wirken

        blinken()
        vermerken(f"merken ({art}): {inhalt}"
                  + (f" (ersetzt {len(ersetzt)})" if ersetzt else ""))
        antwort = f"Gemerkt ({'Beobachtung' if art == 'bemerkt' else 'gesagt'})."
        if ersetzt:
            antwort += (f" {len(ersetzt)} früherer Eintrag ersetzt"
                        if len(ersetzt) == 1
                        else f" {len(ersetzt)} frühere Einträge ersetzt")
            antwort += " — nachzulesen in den Notizen."
        return {"content": [{"type": "text", "text": antwort}]}

    @tool(
        "person_merken",
        "Schreibt etwas über einen MENSCHEN in dessen eigene Akte — nicht "
        "ins immer geladene Gedächtnis. Für alles, was einen bestimmten "
        "Menschen betrifft: Vorlieben, Geburtstag, Beruf, was zuletzt war. "
        "Solche Angaben müssen nicht bei jedem Zuruf mitgeschleppt werden, "
        "sie werden nachgeschlagen, wenn es um die Person geht.",
        {
            "type": "object",
            "properties": {
                "name": {"type": "string",
                         "description": "Name des Menschen, wie gesagt."},
                "inhalt": {"type": "string",
                           "description": "Was über ihn gilt, ein Satz."},
            },
            "required": ["name", "inhalt"],
        },
    )
    async def person_merken(args):
        name = " ".join(str(args.get("name") or "").split())
        inhalt = " ".join(str(args.get("inhalt") or "").split())
        if not name or not inhalt:
            return {"content": [{"type": "text", "text":
                    "Dafür brauche ich Name und Inhalt."}], "is_error": True}
        pfad = _personenordner() / f"{_sauberer_name(name)}.md"
        if not pfad.exists():
            pfad.write_text(f"# {name}\n\n", encoding="utf-8")
        with open(pfad, "a", encoding="utf-8") as f:
            f.write(f"- {datetime.now():%Y-%m-%d} — {inhalt}\n")
        blinken()
        vermerken(f"person_merken ({name}): {inhalt}")
        return {"content": [{"type": "text", "text":
                f"In der Akte von {name} vermerkt."}]}

    @tool(
        "notiz_schreiben",
        "Legt eine datierte Notiz an — für Episodisches: was heute besprochen "
        "wurde, wie ein Problem gelöst wurde, was bei einem Projekt der Stand "
        "ist. Das gehört NICHT ins immer geladene Gedächtnis, sondern hierher: "
        "Es ist später nachschlagbar, ohne jeden Zuruf zu belasten. "
        "Faustregel: Dauerhafte Eigenschaften des Nutzers -> merken. "
        "Ereignisse und Zwischenstände -> hierher.",
        {
            "type": "object",
            "properties": {
                "titel": {"type": "string",
                          "description": "Worum es geht, wenige Worte."},
                "inhalt": {"type": "string",
                           "description": "Der Text der Notiz."},
            },
            "required": ["titel", "inhalt"],
        },
    )
    async def notiz_schreiben(args):
        titel = " ".join(str(args.get("titel") or "").split())
        inhalt = str(args.get("inhalt") or "").strip()
        if not titel or not inhalt:
            return {"content": [{"type": "text", "text":
                    "Dafür brauche ich Titel und Inhalt."}], "is_error": True}
        name = notiz_anlegen(titel, inhalt)
        blinken()
        vermerken(f"notiz_schreiben: {titel}")
        return {"content": [{"type": "text", "text":
                f"Notiert unter {name}."}]}

    @tool(
        "gedaechtnis_nachschlagen",
        "Durchsucht die Akten und Notizen — also alles, was NICHT bei jedem "
        "Zuruf mitgeladen wird. Benutze das, wenn nach einem Menschen gefragt "
        "wird ('was weißt du über Thomas?') oder nach etwas Vergangenem ('was "
        "war damals mit dem Dashboard?'). Findest du hier nichts, sag das — "
        "rate nicht.",
        {
            "type": "object",
            "properties": {
                "stichwort": {"type": "string",
                              "description": "Name oder Stichwort."},
            },
            "required": ["stichwort"],
        },
    )
    async def gedaechtnis_nachschlagen(args):
        stichwort = str(args.get("stichwort") or "")
        treffer = nachschlagen(stichwort)
        blinken()
        if not treffer:
            return {"content": [{"type": "text", "text":
                    f"Zu {stichwort} steht nichts in den Akten oder Notizen."}]}
        teile = []
        for datei, zeilen in treffer:
            teile.append(f"{datei}:\n" + "\n".join(f"  {z}" for z in zeilen))
        return {"content": [{"type": "text", "text": "\n\n".join(teile)}]}

    @tool(
        "gedaechtnis_zeigen",
        "Liest vor, was im Gedächtnis steht. Benutze das, wenn gefragt wird, "
        "was du über den Nutzer weißt oder woher du etwas hast.",
        {
            "type": "object",
            "properties": {
                "art": {
                    "type": "string",
                    "enum": ["gesagt", "bemerkt", "alles"],
                    "description": "Welcher Teil. Vorgabe: alles.",
                }
            },
        },
    )
    async def gedaechtnis_zeigen(args):
        art = args.get("art") or "alles"
        teile = []
        for a, ueberschrift in (("gesagt", "Von dir gesagt"),
                                ("bemerkt", "Von mir bemerkt (Vermutungen)")):
            if art in (a, "alles"):
                zeilen = lesen(a)
                teile.append(
                    f"{ueberschrift}:\n" + ("\n".join(zeilen) if zeilen
                                            else "  (nichts)")
                )
        blinken()
        return {"content": [{"type": "text", "text": "\n\n".join(teile)}]}

    @tool(
        "vergessen",
        "Löscht Einträge aus dem Gedächtnis, die ein Stichwort enthalten. "
        "Benutze das, wenn der Nutzer sagt, dass etwas nicht stimmt oder "
        "weg soll.",
        {
            "type": "object",
            "properties": {
                "stichwort": {
                    "type": "string",
                    "description": "Wort oder Wortfolge, die im Eintrag "
                                   "vorkommt.",
                }
            },
            "required": ["stichwort"],
        },
    )
    async def vergessen(args):
        wort = (args.get("stichwort") or "").strip().lower()
        if not wort:
            return {"content": [{"type": "text", "text":
                    "Ohne Stichwort lösche ich nichts."}], "is_error": True}
        geloescht = []
        for art in ("gesagt", "bemerkt"):
            pfad = _datei(art)
            zeilen = _zeilen(pfad)
            bleiben = [z for z in zeilen if wort not in z.lower()]
            if len(bleiben) != len(zeilen):
                geloescht += [z for z in zeilen if wort in z.lower()]
                _schreiben(pfad, bleiben)
        blinken()
        if not geloescht:
            return {"content": [{"type": "text", "text":
                    f"Zu {wort!r} steht nichts im Gedächtnis."}]}
        vermerken(f"vergessen: {len(geloescht)} Eintrag/Einträge zu {wort!r}")
        return {"content": [{"type": "text", "text":
                f"{len(geloescht)} Eintrag/Einträge gelöscht."}]}

    return [merken, gedaechtnis_zeigen, vergessen,
            person_merken, notiz_schreiben, gedaechtnis_nachschlagen]
