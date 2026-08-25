"""Gedaechtnis schreiben und lesen.

Zwei Ablagen, streng getrennt -- das ist der ganze Trick:

  gemerkt.md      Was du ausdruecklich gesagt hast. Gilt als Tatsache.
  beobachtet.md   Was Sarvis von selbst geschlossen hat. Gilt als Vermutung.

Die Trennung ist nicht Ordnungsliebe. Eine Vermutung zu speichern ist
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


def _schreiben(pfad, zeilen: list[str]) -> None:
    kopf = KOPF.get(pfad.name, "")
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(kopf + "\n" + "\n".join(zeilen) + "\n", encoding="utf-8")


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
        # Eintraege sind schlimmer als keiner.
        kern = inhalt.lower()[:40]
        zeilen = [z for z in zeilen if kern not in z.lower()]
        zeilen.append(eintrag)
        _schreiben(pfad, zeilen)

        blinken()
        vermerken(f"merken ({art}): {inhalt}")
        return {"content": [{"type": "text", "text":
                f"Gemerkt ({'Beobachtung' if art == 'bemerkt' else 'gesagt'})."}]}

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

    return [merken, gedaechtnis_zeigen, vergessen]
