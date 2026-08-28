"""Etwas neben der Engine einblenden -- der Hahn zu den Kacheln.

Die Kacheln gab es vor dieser Datei schon vollstaendig: Sender, Empfaenger,
Platzierung neben der Engine, Balken, Hervorheben einer Zeile. Nur konnte
Sarvis sie nicht erreichen -- es gab kein Werkzeug dafuer. Gemessen im
Betrieb, und es sah genau so aus, wie man es erwarten wuerde:

    Nutzer: "Kannst du mir das nicht visuell zeigen?"
    Sarvis: oeffnet den Browser mit Telegram Web
    Nutzer: "ohne dass ich mich einloggen muss"
    Sarvis: "Soll ich chat-niko.html anlegen?"

Er hatte die Nachrichten bereits gelesen. Ihm fehlte nur der Weg, sie
hinzustellen -- also nahm er die Wege, die er kannte: fremde Seite,
selbstgebaute Datei. Beides schlechter als die Kachel, die daneben
ungenutzt lag.

DIE ABGRENZUNG, die in den Beschreibungen steht und hier begruendet:

    kachel_zeigen   Du HAST die Daten -- aus einem Werkzeug oder aus dem
                    Gespraech. Sie gehoeren neben die Engine.
    web_zeigen      Der Nutzer will eine WEBSEITE. Nicht fuer Daten, die
                    du schon hast: Ihn erst anmelden zu lassen, um etwas
                    zu sehen, das du bereits vorgelesen hast, ist die
                    schlechteste aller Antworten.

Datenpunkte statt fertiger Zeilen: Aus "zahl" wird die Laenge des
Balkens, und daran erkennt die Kachel spaeter, welchen Posten Sarvis
gerade nennt. Wer Text schickt, kann weder zeichnen noch hervorheben.
"""
from claude_agent_sdk import tool

from .. import config
from ..anzeige import Anzeige

# Zwei feste Namen. Der Name ist die Identitaet einer Kachel: Zweimal
# derselbe heisst dieselbe Kachel mit neuem Inhalt, nicht zwei
# uebereinander. Mehr als zwei gleichzeitig waeren Werbung um den Ring
# herum -- eine Antwort und ein laufender Zustand reichen.
ANTWORT = "antwort"
ZUSTAND = "zustand"


def werkzeuge(protokoll=None, leuchten=None) -> list:
    def vermerken(text: str):
        if protokoll is not None:
            protokoll.merken(text)

    # Eigener Draht zur Anzeige, wie in programme.py. Anzeige ist ein
    # zustandsloser UDP-Sender, der nie blockiert und ins Nichts sendet,
    # wenn die Anzeige gar nicht laeuft.
    sicht = Anzeige(config.ANZEIGE)

    @tool(
        "kachel_zeigen",
        "Blendet etwas neben der Anzeige ein, damit der Nutzer es SIEHT "
        "statt es nur zu hören. Für 'zeig mir das', 'visuell', 'als "
        "Übersicht', 'kannst du mir das anzeigen', 'stell mir das mal "
        "hin'. Nimm das immer, wenn du die Daten schon hast — aus einem "
        "Werkzeug oder aus dem Gespräch. Schick ihn NICHT auf eine "
        "Webseite und lass ihn sich NICHT anmelden für etwas, das du ihm "
        "gerade vorgelesen hast. Sag den Inhalt trotzdem — die Kachel "
        "ersetzt die Antwort nicht, sie zeigt sie.\n"
        "Wähle die Form nach dem Inhalt: ein Verlauf über Monate als "
        "'balken', Anteile an einem Ganzen als 'torte', Posten mit "
        "Oberbegriffen als 'kategorien', Nachrichten und Mails als "
        "'blasen', zwei Zeiträume nebeneinander als 'vergleich', eine "
        "Zusammenfassung als 'text', alles Übrige als 'liste'.\n"
        "Für eine GROSSE Auswertung — viele Werte, mehrere Diagramme, "
        "etwas zum Durchsehen — nimm stattdessen seite_zeigen.",
        {
            "type": "object",
            "properties": {
                "kopf": {
                    "type": "string",
                    "description": "Kurze Überschrift, zwei bis vier "
                                   "Wörter: 'Ausgaben im August', "
                                   "'Chat mit Niko', 'Termine heute'.",
                },
                "form": {
                    "type": "string",
                    "enum": ["liste", "blasen", "vergleich", "text",
                             "balken", "torte", "kategorien"],
                    "description": "liste: Zeilen mit Wert und Balken "
                                   "(Vorgabe). balken: senkrechte Säulen mit "
                                   "Achse — für einen Verlauf über Monate "
                                   "oder Wochen, Minuswerte gehen nach "
                                   "unten. torte: Kreisdiagramm für Anteile "
                                   "an einem Ganzen, höchstens acht Stücke. "
                                   "kategorien: Posten unter Oberbegriffen, "
                                   "jede Gruppe mit eigener Summe. blasen: "
                                   "ein Gesprächsverlauf, Telegram oder "
                                   "Mail. vergleich: zwei Zeiträume "
                                   "nebeneinander, die Differenz rechnet die "
                                   "Kachel selbst. text: ein Fließtext, "
                                   "Zusammenfassung oder Auszug.",
                },
                "spalten": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Nur bei form=vergleich: die zwei "
                                   "Spaltennamen, z. B. ['August', 'Juli']. "
                                   "Die erste gehört zu wert, die zweite zu "
                                   "wert2.",
                },
                "punkte": {
                    "type": "array",
                    "description": "Die Zeilen. Zwölf bei den meisten "
                                   "Formen, vierundzwanzig bei balken, acht "
                                   "bei torte, dreißig bei kategorien — was "
                                   "darüber liegt, wird abgeschnitten.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "text": {"type": "string",
                                     "description": "Links das Wesentliche — "
                                                    "bei blasen die Nachricht "
                                                    "selbst, bei text ein "
                                                    "Absatz."},
                            "wert": {"type": "string",
                                     "description": "Rechts: Betrag, "
                                                    "Uhrzeit, Datum, Anzahl. "
                                                    "Bei blasen die Zeit."},
                            "zahl": {"type": "number",
                                     "description": "Der rohe Wert, wenn es "
                                                    "einer ist — daraus wird "
                                                    "der Balken oder das "
                                                    "Tortenstück. Bei balken "
                                                    "darf er negativ sein "
                                                    "(Ausgaben und Einnahmen "
                                                    "in einem Bild), bei "
                                                    "torte zählt nur, was "
                                                    "über null liegt."},
                            "gruppe": {"type": "string",
                                       "description": "Nur bei kategorien: "
                                                      "der Oberbegriff, unter "
                                                      "dem die Zeile steht — "
                                                      "'Wohnen', 'Mobilität'. "
                                                      "Gleiche Gruppe heißt "
                                                      "zusammen, in der "
                                                      "Reihenfolge des ersten "
                                                      "Auftretens."},
                            "wert2": {"type": "string",
                                      "description": "Nur bei vergleich: der "
                                                     "Wert der zweiten "
                                                     "Spalte."},
                            "zahl2": {"type": "number",
                                      "description": "Nur bei vergleich: die "
                                                     "rohe Zahl dazu. Fehlt "
                                                     "sie, bleibt die "
                                                     "Differenz leer statt "
                                                     "erfunden."},
                            "von_mir": {"type": "boolean",
                                        "description": "Nur bei blasen: hat "
                                                       "der Nutzer das "
                                                       "geschrieben? Dann "
                                                       "rechts."},
                        },
                        "required": ["text"],
                    },
                },
                "gross": {
                    "type": "string",
                    "description": "Die EINE große Zahl, wenn es eine gibt: "
                                   "'20.000,66 €'. Sonst weglassen.",
                },
                "bleibt": {
                    "type": "boolean",
                    "description": "Steht, bis sie weggenommen wird — für "
                                   "etwas, das LÄUFT (Auftrag, Timer). "
                                   "Vorgabe: nein, dann geht sie nach "
                                   "einer Weile von selbst.",
                },
                "stand": {
                    "type": "string",
                    "description": "Woher die Daten sind: 'Stand 10:42'. "
                                   "Ohne Angabe steht die Uhrzeit da.",
                },
            },
            "required": ["kopf", "punkte"],
        },
    )
    async def kachel_zeigen(args):
        from datetime import datetime

        kopf = str(args.get("kopf") or "").strip()
        punkte = list(args.get("punkte") or [])
        if not kopf or not punkte:
            return {"content": [{"type": "text", "text":
                    "Ohne Überschrift und Zeilen kann ich nichts "
                    "hinstellen."}], "is_error": True}

        bleibt = bool(args.get("bleibt"))
        # Ein Zeitstempel steht IMMER da, auch wenn keiner mitkommt. Eine
        # Kachel ohne ihn veraltet stillschweigend -- man sieht Zahlen und
        # weiss nicht, ob sie von jetzt sind oder von vorgestern.
        stand = str(args.get("stand") or "").strip()
        if not stand:
            stand = f"Stand {datetime.now():%H:%M}"

        sicht.kachel(
            ZUSTAND if bleibt else ANTWORT,
            kopf, punkte,
            sorte=ZUSTAND if bleibt else ANTWORT,
            gross=str(args.get("gross") or ""),
            stand=stand,
            form=str(args.get("form") or "liste"),
            spalten=args.get("spalten") or (),
        )
        if leuchten:
            leuchten("Gedächtnis")
        vermerken(f"kachel_zeigen: {kopf} ({len(punkte)} Zeilen)")

        # Der Hinweis ist fuer SARVIS, nicht fuer den Nutzer: Ohne ihn
        # denkt er, mit der Kachel sei die Frage beantwortet, und
        # schweigt. Der Nutzer sieht dann etwas, aber hoert nichts.
        return {"content": [{"type": "text", "text":
                f"{kopf} steht jetzt neben der Anzeige. Sag den Inhalt "
                "trotzdem — die Kachel ersetzt deine Antwort nicht."}]}

    @tool(
        "kachel_weg",
        "Nimmt eine eingeblendete Kachel wieder weg. Für 'weg damit', "
        "'blende das aus', 'brauch ich nicht mehr'.",
        {
            "type": "object",
            "properties": {
                "welche": {
                    "type": "string",
                    "enum": ["antwort", "zustand", "alle"],
                    "description": "Vorgabe: alle.",
                },
            },
        },
    )
    async def kachel_weg(args):
        welche = str(args.get("welche") or "alle")
        for name in ((ANTWORT, ZUSTAND) if welche == "alle" else (welche,)):
            sicht.kachel_weg(name)
        return {"content": [{"type": "text", "text": "Weg."}]}

    return [kachel_zeigen, kachel_weg]
