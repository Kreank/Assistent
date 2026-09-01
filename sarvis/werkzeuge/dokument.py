"""Blaetter und Dateien -- was man liest statt hoert.

Sarvis ist ein Sprachassistent, und das bleibt der Kern: Die Antwort
wird gesprochen. Es gibt aber Antworten, die gesprochen nichts wert
sind -- eine Aufstellung mit acht Posten, eine Anleitung in Schritten,
ein Angebot, das jemand behalten soll. Dafuer sind diese drei Werkzeuge.

DIE ABGRENZUNG, dieselbe Linie wie in kacheln.py und bericht.py, um
zwei Faelle erweitert:

    kachel_zeigen       Ein paar Zeilen neben der Engine, im
                        Vorbeigehen. Zwoelf Datenpunkte, keine Struktur.
    blatt_zeigen        Eine formatierte Antwort im Gespraech:
                        Ueberschriften, Listen, eine kleine Tabelle.
                        Bleibt Text, wird nichts, was auf der Platte
                        liegt. HIER ANFANGEN, wenn unklar ist, welches.
    seite_zeigen        Eine ganze Auswertung mit Diagrammen, zum
                        Hinsetzen (werkzeuge/bericht.py).
    dokument_erstellen  Etwas zum BEHALTEN oder WEITERGEBEN: PDF zum
                        Ausdrucken und Verschicken, Word zum
                        Weiterschreiben.

Der Unterschied zwischen den letzten beiden ist nicht die Groesse,
sondern was danach damit geschieht. Eine Seite liest man und schliesst
sie. Ein Dokument geht an jemanden.

WARUM DAS PDF EIN EIGENER CHROME-AUFRUF IST

Im Container laeuft bereits ein Chrome -- Sarvis' eigener Browser
(netz/browser_kopf.py). Dort zu drucken waere schneller (er steht
schon), und genau das ist der Grund, es NICHT zu tun: In dem Browser
steht die Seite, die Sarvis gerade liest. Ein Druckauftrag muesste sie
wegnavigieren, das PDF holen und zurueckkehren -- mitten in einer
Recherche, deren Zwischenstand danach weg waere. Ein Fehler, der sich
als "der Assistent hat vergessen, was auf der Seite stand" zeigt und
nicht als Absturz.

Ein eigener Prozess kostet gemessen 4,4 Sekunden und stoert nichts.
Ein Dokument wird einmal erzeugt, nicht achtmal je Sekunde.

WARUM ES KEIN WEASYPRINT UND KEIN python-docx GIBT

Beides waere eine Zeile in requirements.txt und danach ein Neubau des
Images samt der 1,5 GB CUDA-Raeder, die an derselben pip-Schicht
haengen. Das PDF macht der Chrome, der ohnehin im Image liegt; die
Word-Datei macht docx_bauen.py mit zipfile aus der Standardbibliothek.
Dieselbe Rechnung wie bei Playwright und ffmpeg, siehe Dockerfile.
"""
import asyncio
import logging
import shutil

from claude_agent_sdk import tool

from .. import anzeige as anzeige_modul
from .. import config
from . import bericht, docx_bauen, markdown_lesen, xlsx_bauen

log = logging.getLogger("sarvis.dokument")

# Wie lange ein Markdown-Blatt stehen bleibt. Laenger als eine Kachel:
# Es wird gelesen, nicht ueberflogen. Null hiesse "bis es weggeklickt
# wird" -- das waere hier falsch, weil dann jede formatierte Antwort
# eine Handlung erfordert.
BLATT_SEKUNDEN = 900.0

# Obergrenze fuer den Inhalt. Der Draht traegt 4 MB, anzeige.blatt kappt
# schon bei 40.000 Zeichen -- diese Grenze steht davor, damit die
# Antwort des Werkzeugs "zu lang" sagen kann, statt dass stumm gekuerzt
# wird und Sarvis den Rest fuer zugestellt haelt.
INHALT_MAX = 40_000

# Wie lange auf Chrome gewartet wird. Gemessen 4,4 s im Container, kalt.
# Dreissig lassen Luft fuer eine grosse Seite und brechen trotzdem ab,
# bevor der Nutzer glaubt, Sarvis haenge.
DRUCK_ZEITLIMIT = 30.0

# Was erzeugt werden kann: Endung und wie es beim Nutzer heisst.
# Die Reihenfolge ist die, in der sie im Werkzeug angeboten werden --
# vom Fertigen zum Rohen.
SORTEN = {
    "pdf":   (".pdf",  "PDF"),
    "word":  (".docx", "Word-Datei"),
    "excel": (".xlsx", "Excel-Tabelle"),
    "csv":   (".csv",  "CSV-Datei"),
    "text":  (".md",   "Textdatei"),
}


def _chrome() -> str:
    """Wo Chrome liegt -- oder "", wenn es ihn hier nicht gibt.

    Ueber browser_kopf gefragt und nicht selbst gesucht: Dort steht die
    Liste der Orte schon, und zwei Listen liefen auseinander.
    """
    try:
        from ..netz.browser_kopf import chrome_finden
        return chrome_finden() or ""
    except Exception:
        return shutil.which("google-chrome") or shutil.which("chromium") or ""


async def _drucken(quelle, ziel) -> str:
    """HTML-Datei zu PDF. Gibt "" zurueck, wenn es geklappt hat."""
    binaer = _chrome()
    if not binaer:
        return "Auf diesem Rechner ist kein Chrome installiert."
    # --no-sandbox: Der Container laeuft schon ohne Rechte als uid 1000,
    # und Chromes eigene Sandbox braucht dafuer user namespaces, die
    # hier nicht offen sind. Dieselbe Zeile steht aus demselben Grund in
    # browser_kopf.py.
    prozess = await asyncio.create_subprocess_exec(
        binaer, "--headless", "--disable-gpu", "--no-sandbox",
        "--no-pdf-header-footer", "--disable-dev-shm-usage",
        f"--print-to-pdf={ziel}", quelle.as_uri(),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE)
    try:
        _, fehler = await asyncio.wait_for(prozess.communicate(),
                                           DRUCK_ZEITLIMIT)
    except asyncio.TimeoutError:
        prozess.kill()
        return "Chrome hat zu lange gebraucht."
    if not ziel.is_file() or ziel.stat().st_size < 500:
        # Chrome meldet den Fehler auf stderr zwischen Dutzenden
        # dbus-Warnungen, die hier immer kommen und nichts bedeuten.
        # Deshalb entscheidet die DATEI, nicht der Rueckgabewert.
        letzte = (fehler or b"").decode("utf-8", "replace").strip()
        letzte = letzte.splitlines()[-1] if letzte else "kein Grund genannt"
        return f"Chrome hat kein PDF geschrieben ({letzte})."
    return ""


def werkzeuge(protokoll=None, leuchten=None) -> list:
    def vermerken(text: str):
        if protokoll is not None:
            protokoll.merken(text)

    # Die gemeinsame Anzeige, nicht eine eigene -- siehe
    # anzeige.aktuelle(). Ein eigener UDP-Socket schickte im
    # Netzbetrieb an ein Fenster, das es nicht gibt.
    sicht = anzeige_modul.aktuelle()

    @tool("blatt_zeigen",
          "Zeigt eine formatierte Antwort als Blatt: Überschriften, "
          "Listen, kleine Tabellen, Links. Für alles, was gesprochen "
          "unübersichtlich wäre — eine Aufstellung, eine Anleitung in "
          "Schritten, ein Vergleich. Sag den Kern trotzdem laut; das "
          "Blatt ersetzt deine Antwort nicht, es ergänzt sie.",
          {
              "type": "object",
              "properties": {
                  "titel": {"type": "string",
                            "description": "Überschrift des Blattes, kurz."},
                  "inhalt": {
                      "type": "string",
                      "description":
                          "Markdown. Unterstützt: # Überschriften, **fett**, *kursiv*, ~~durchgestrichen~~, `code`, - Listen (auch eingerückte Unterpunkte), 1. Nummerierung, - [ ] und - [x] für Haken, > Zitat, ```Codeblöcke```, | Tabellen | (die |---|-Zeile ist Pflicht), --- Trennlinie, [Text](https://ziel). "
                          "Kein HTML — das wird als Text angezeigt, "
                          "nicht ausgeführt. Bilder werden nur benannt, "
                          "nicht geladen."},
                  "kennung": {
                      "type": "string",
                      "description":
                          "Nur angeben, um ein bestehendes Blatt zu "
                          "ERSETZEN — gleiche Kennung heißt gleiches "
                          "Blatt mit neuem Inhalt."},
              },
              "required": ["titel", "inhalt"],
          })
    async def blatt_zeigen(args):
        titel = str(args.get("titel") or "").strip()
        inhalt = str(args.get("inhalt") or "").strip()
        if not titel or not inhalt:
            return {"content": [{"type": "text", "text":
                    "Ohne Titel und Inhalt kann ich kein Blatt zeigen."}],
                    "is_error": True}
        if len(inhalt) > INHALT_MAX:
            return {"content": [{"type": "text", "text":
                    f"Der Inhalt ist {len(inhalt)} Zeichen lang. Auf ein "
                    "Blatt passen 40.000 — nimm seite_zeigen für einen "
                    "richtigen Bericht."}], "is_error": True}

        kennung = str(args.get("kennung") or "").strip() or "antwort"
        sicht.blatt(kennung, sorte="markdown", titel=titel, inhalt=inhalt,
                    sekunden=BLATT_SEKUNDEN)
        # HIER LEUCHTET NICHTS, und das ist Absicht: Der Kranz kennt
        # siebzehn feste Namen (WERKZEUGE in web/sarvis.js, dieselbe
        # Reihe in hud.py), und "Blatt" ist keiner davon. Einen achtzehnten
        # aufzunehmen hiesse, die Geometrie in beiden Anzeigen zu
        # verschieben -- fuer ein Werkzeug, dessen Wirkung ohnehin gross
        # und sichtbar in der Mitte steht. Ein falsches Symbol waere
        # schlechter als keines.

        draht = sicht.draht()
        # Ueber UDP weiss niemand, ob hingesehen wird; ueber Netz schon.
        # Nur im zweiten Fall wird die Aussage gemacht.
        if sicht.ueber_netz() and draht and not draht.wie_viele():
            return {"content": [{"type": "text", "text":
                    f"»{titel}« ist gesetzt, aber gerade ist keine "
                    "Oberfläche verbunden — es sieht es also niemand. "
                    "Sag den Inhalt."}]}
        return {"content": [{"type": "text", "text":
                f"»{titel}« liegt als Blatt vor dem Nutzer. Sag den Kern "
                "trotzdem — das Blatt ersetzt deine Antwort nicht."}]}

    @tool("blatt_weg",
          "Nimmt ein Blatt wieder weg. Nur nötig, wenn es ein Blatt mit "
          "eigener Kennung war und es nicht von selbst verschwinden soll.",
          {
              "type": "object",
              "properties": {
                  "kennung": {"type": "string",
                              "description": "Die Kennung des Blattes."},
              },
              "required": ["kennung"],
          })
    async def blatt_weg(args):
        kennung = str(args.get("kennung") or "").strip()
        if not kennung:
            return {"content": [{"type": "text", "text":
                    "Ohne Kennung weiß ich nicht, welches."}],
                    "is_error": True}
        sicht.blatt_weg(kennung)
        return {"content": [{"type": "text", "text": "Weg."}]}

    @tool("dokument_erstellen",
          "Erstellt eine Datei zum Behalten oder Weitergeben und gibt "
          "dem Nutzer einen Knopf zum Herunterladen. 'pdf' zum "
          "Ausdrucken und Verschicken, 'word' zum Weiterschreiben. "
          "NICHT für etwas, das nur angesehen werden soll — dafür sind "
          "blatt_zeigen und seite_zeigen da.",
          {
              "type": "object",
              "properties": {
                  "titel": {"type": "string",
                            "description":
                                "Titel des Dokuments. Wird auch der "
                                "Dateiname."},
                  "inhalt": {
                      "type": "string",
                      "description":
                          "Markdown, dieselbe Teilmenge wie bei "
                          "blatt_zeigen. Bei 'excel' zählt vor allem "
                          "die Tabelle: Zahlen dort ohne Einheit "
                          "schreiben ('12.400,00', nicht '12.400 €'), "
                          "sonst landen sie als Text und man kann "
                          "nicht damit rechnen."},
                  "sorte": {
                      "type": "string",
                      "enum": ["pdf", "word", "excel", "csv", "text"],
                      "description":
                          "'pdf' = fertig, sieht überall gleich aus, zum "
                          "Ausdrucken und Verschicken. 'word' = zum "
                          "Weiterschreiben. 'excel' = wenn gerechnet, "
                          "sortiert oder gefiltert werden soll — Zahlen "
                          "kommen dort als Zahlen an. 'csv' = zum Import "
                          "in ein anderes Programm. 'text' = das rohe "
                          "Markdown zum Weiterverwenden."},
                  "untertitel": {"type": "string",
                                 "description": "Eine Zeile unter dem "
                                                "Titel. Optional."},
                  "stand": {"type": "string",
                            "description":
                                "Statt 'Stand <heute>' — etwa 'Angebot "
                                "vom 12.03.'. Optional."},
              },
              "required": ["titel", "inhalt", "sorte"],
          })
    async def dokument_erstellen(args):
        titel = str(args.get("titel") or "").strip()
        inhalt = str(args.get("inhalt") or "").strip()
        sorte = str(args.get("sorte") or "").strip().lower()
        if not titel or not inhalt:
            return {"content": [{"type": "text", "text":
                    "Ohne Titel und Inhalt kann ich kein Dokument bauen."}],
                    "is_error": True}
        if sorte not in SORTEN:
            moeglich = ", ".join(f"'{s}'" for s in SORTEN)
            return {"content": [{"type": "text", "text":
                    f"»{sorte}« kenne ich nicht — {moeglich}."}],
                    "is_error": True}
        if len(inhalt) > bericht.INHALT_MAX:
            return {"content": [{"type": "text", "text":
                    f"Der Inhalt ist {len(inhalt)} Zeichen lang und damit "
                    "zu groß für ein Dokument."}], "is_error": True}

        bloecke = markdown_lesen.lesen(inhalt)
        if not bloecke:
            return {"content": [{"type": "text", "text":
                    "Aus dem Inhalt wurde nichts — steht wirklich etwas "
                    "darin?"}], "is_error": True}

        endung, wie = SORTEN[sorte]
        stamm = bericht._stamm_saeubern(titel)
        ziel = bericht._ziel(stamm, endung)
        if ziel is None:
            return {"content": [{"type": "text", "text":
                    f"Der Titel {titel!r} führt aus der Ablage heraus. "
                    "Nichts geschrieben."}], "is_error": True}

        untertitel = str(args.get("untertitel") or "")
        stand = str(args.get("stand") or "")

        if sorte in ("word", "excel"):
            bauen = (docx_bauen if sorte == "word" else xlsx_bauen).schreiben
            try:
                await asyncio.to_thread(bauen, ziel, titel, bloecke,
                                        untertitel, stand)
            except OSError as e:
                return {"content": [{"type": "text", "text":
                        f"Konnte die Datei nicht schreiben: {e}"}],
                        "is_error": True}
        elif sorte in ("csv", "text"):
            # Beide sind einfach Text auf der Platte. Getrennt behandelt,
            # weil CSV die Tabellen herausloest und die Textdatei den
            # Inhalt so laesst, wie er geschrieben wurde -- wer "das
            # Rohe" will, will keine umgebaute Fassung davon.
            inhalt_datei = (markdown_lesen.als_csv(bloecke) if sorte == "csv"
                            else inhalt + "\n")
            try:
                await asyncio.to_thread(ziel.write_text, inhalt_datei,
                                        encoding="utf-8")
            except OSError as e:
                return {"content": [{"type": "text", "text":
                        f"Konnte die Datei nicht schreiben: {e}"}],
                        "is_error": True}
        else:
            # Ueber dieselbe Seite wie ein Bericht -- damit sieht ein PDF
            # aus wie Sarvis und nicht wie ein zweites Programm. Hell
            # wird es durch den @media-print-Block in bericht._STIL, den
            # Chrome beim Drucken heranzieht.
            seite = bericht.seite_bauen(titel,
                                        markdown_lesen.als_html(bloecke, titel),
                                        untertitel=untertitel, stand=stand)
            zwischen = ziel.with_suffix(".druck.html")
            try:
                await asyncio.to_thread(zwischen.write_text, seite,
                                        encoding="utf-8")
                fehler = await _drucken(zwischen, ziel)
            except OSError as e:
                return {"content": [{"type": "text", "text":
                        f"Konnte nicht drucken: {e}"}], "is_error": True}
            finally:
                # Die Zwischendatei traegt nicht das Namensmuster und
                # wuerde von _aufraeumen nie angefasst. Sie geht hier
                # weg, auch wenn das Drucken schiefging.
                try:
                    zwischen.unlink(missing_ok=True)
                except OSError:
                    pass
            if fehler:
                return {"content": [{"type": "text",
                                     "text": fehler}], "is_error": True}

        await asyncio.to_thread(bericht._aufraeumen)

        if not sicht.ueber_netz():
            # Auf dem Dev-PC gibt es keinen Weg, eine Datei anzubieten --
            # sie liegt ja schon auf demselben Rechner. Den Pfad nennen
            # ist dort die richtige Antwort.
            vermerken(f"dokument_erstellen: {titel} -> {ziel.name}")
            return {"content": [{"type": "text", "text":
                    f"»{titel}« liegt als {wie} unter {ziel}."}]}

        from ..netz import blaetter
        try:
            # Die Sortennamen sind absichtlich dieselben in beiden
            # Tabellen -- blaetter.TYPEN kennt genau diese fuenf.
            kennung = await asyncio.to_thread(
                blaetter.hinlegen, ziel, sorte, titel, f"{stamm}{endung}")
        except (OSError, ValueError) as e:
            return {"content": [{"type": "text", "text":
                    f"Die Datei ist da, aber ich konnte sie nicht "
                    f"bereitstellen: {e}"}], "is_error": True}

        groesse = ziel.stat().st_size
        sicht.blatt(kennung, sorte="datei", titel=titel,
                    adresse=blaetter.adresse(kennung),
                    datei=f"{stamm}{endung}", bytes_=groesse)
        if leuchten:
            # "Dateien" und nicht "Websuche" wie bei der Seite: Hier
            # entsteht wirklich eine Datei, die danach liegen bleibt.
            leuchten("Dateien")
        vermerken(f"dokument_erstellen: {titel} -> {ziel.name}")

        draht = sicht.draht()
        if draht and not draht.wie_viele():
            return {"content": [{"type": "text", "text":
                    f"»{titel}« ist als {wie} fertig, aber gerade ist "
                    "keine Oberfläche verbunden — der Knopf zum "
                    "Herunterladen ist da, sobald wieder eine offen ist."}]}
        return {"content": [{"type": "text", "text":
                f"»{titel}« ist als {wie} fertig "
                f"({groesse // 1024 or 1} KB). Der Nutzer hat jetzt einen "
                "Knopf zum Herunterladen."}]}

    return [blatt_zeigen, blatt_weg, dokument_erstellen]
