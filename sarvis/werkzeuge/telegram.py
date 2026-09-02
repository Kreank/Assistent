"""Telegram über das eigene Konto (MTProto).

Sarvis handelt hier als du, nicht als Bot. Das ist der einzige Weg, der
beliebige Kontakte anschreiben und Chats lesen kann -- ein Bot darf
beides nicht.

Die wichtigste Entscheidung steckt in _finden(): Bei Mehrdeutigkeit wird
NICHT geraten. Eine Nachricht an den falschen Menschen ist der einzige
Fehler in diesem Modul, den niemand zurücknehmen kann. Lieber fragt
Sarvis nach, welcher Alex gemeint ist.
"""
import asyncio
import re
from pathlib import Path

from claude_agent_sdk import tool

from .. import config
from . import eingang

_klient = None
_schloss = asyncio.Lock()
# In welcher Ereignisschleife der Klient lebt. Telethon bindet ihn beim
# Verbinden an genau eine und beschwert sich, wenn spaeter eine andere
# kommt. Gebraucht wird das beim Beenden: schliessen() laeuft in einem
# fremden Thread und muss das Trennen dorthin zurueckgeben, wo der
# Klient zu Hause ist. client.loop taugt dafuer NICHT -- die
# Eigenschaft liefert die gerade laufende Schleife, nicht die eigene.
_schleife = None


async def _trennen(k) -> None:
    """Eine Verbindung zumachen, ohne dass ein Fehler den Aufrufer stoert.

    Beim Trennen ist jeder Fehler schon egal: Was hier schiefgeht,
    aendert nichts mehr daran, dass die Verbindung weg soll.
    """
    try:
        await k.disconnect()
    except Exception:
        pass


async def klient():
    """Verbindung herstellen und offen halten.

    Erst beim ersten Gebrauch, nicht beim Start: Wer Telegram nie
    benutzt, soll dafuer keine Sekunde Startzeit zahlen.
    """
    global _klient, _schleife
    async with _schloss:
        if _klient is not None:
            if _klient.is_connected():
                return _klient
            # Der alte Klient wurde frueher einfach ueberschrieben und hielt
            # seine Netzwerk-Tasks weiter offen.
            await _trennen(_klient)
            _klient = None
        zugang = config.telegram_zugang()
        if not zugang or not config.TELEGRAM_SITZUNG.exists():
            return None
        from telethon import TelegramClient

        api_id, api_hash = zugang
        _klient = TelegramClient(str(config.TELEGRAM_SITZUNG), api_id, api_hash)
        _schleife = asyncio.get_running_loop()
        await _klient.connect()
        if not await _klient.is_user_authorized():
            # Ist die Sitzung am Telefon widerrufen, laeuft jeder Aufruf
            # hier durch; ohne disconnect bliebe jedes Mal eine Verbindung
            # stehen.
            await _trennen(_klient)
            _klient = None
        return _klient


def schliessen() -> None:
    """Die Verbindung beim Beenden zumachen. Bewusst SYNCHRON.

    Der Fund von vorhin hatte eine zweite Haelfte. Gerufen wird diese
    Funktion genau einmal, aus main.py, und zwar als
    "asyncio.to_thread(telegram.schliessen)". Solange sie eine
    Koroutine war, kam dabei nur das Koroutinen-Objekt aus dem Thread
    zurueck -- erwartet hat es nie jemand, disconnect lief nie, und die
    Verbindung blieb beim Beenden trotzdem offen. Ein disconnect, das
    niemand ausfuehrt, ist keines.

    Das Trennen selbst gehoert in die Schleife, in der der Klient lebt.
    Deshalb der Umweg ueber run_coroutine_threadsafe statt eines
    eigenen asyncio.run() -- letzteres wuerde eine zweite Schleife
    aufmachen, und Telethon haelt seine Netzwerk-Tasks in der ersten.
    """
    global _klient, _schleife
    k, schleife = _klient, _schleife
    _klient, _schleife = None, None
    if k is None:
        return

    try:
        hier = asyncio.get_running_loop()
    except RuntimeError:
        hier = None

    if hier is not None and hier is schleife:
        # Direkt aus der Schleife gerufen: Warten wuerde genau die
        # Schleife anhalten, die das Trennen erledigen soll.
        hier.create_task(_trennen(k))
        return
    if schleife is not None and not schleife.is_closed():
        try:
            asyncio.run_coroutine_threadsafe(_trennen(k), schleife).result(10)
        except Exception:
            pass
        return
    # Keine Schleife mehr da, in der der Klient lebt -- dann bleibt nur
    # eine eigene. Beim Beenden ist das der letzte Versuch, nicht der
    # Regelfall.
    try:
        asyncio.run(_trennen(k))
    except Exception:
        pass


def _passt(name: str, gesucht: str) -> int:
    """Wie gut ein Chatname zur Suche passt. 0 = gar nicht."""
    n, g = (name or "").lower().strip(), (gesucht or "").lower().strip()
    if not n or not g:
        return 0
    if n == g:
        return 100
    if n.startswith(g):
        return 80
    # Vorname trifft: "Alex" findet "Alex Frank"
    if any(teil == g for teil in n.split()):
        return 70
    if any(teil.startswith(g) for teil in n.split()):
        return 50
    if g in n:
        return 30
    return 0


def _marke(n) -> str:
    """Wofuer eine Nachricht ohne Text steht.

    Die Anzahlgrenze wirkt beim Holen, der Textfilter erst danach: "lies
    die letzten acht" ergab drei Zeilen, wenn fuenf davon Fotos waren --
    ohne dass die Luecke sichtbar wurde. Vorlesen kann Sarvis ein Foto
    nicht, aber sagen, dass eins da war.
    """
    # Reihenfolge zaehlt: Ein bewegter Sticker traegt auch das Merkmal
    # Video, eine Sprachnachricht auch das Merkmal Dokument.
    for merkmal, marke in (("sticker", "[Sticker]"),
                           ("photo", "[Foto]"),
                           ("voice", "[Sprachnachricht]"),
                           ("video", "[Video]"),
                           ("audio", "[Audio]"),
                           ("geo", "[Standort]"),
                           ("contact", "[Kontakt]"),
                           ("poll", "[Umfrage]"),
                           ("document", "[Datei]")):
        if getattr(n, merkmal, None):
            return marke
    if getattr(n, "media", None):
        return "[Anhang]"
    if getattr(n, "action", None):
        return "[Systemnachricht]"
    return "[ohne Text]"


# Der Artikel zur Marke, fuer den Antwortsatz nach dem Download.
# "Datei aus dem Chat mit Niko liegt jetzt..." ist kein deutscher Satz,
# und vorgelesen faellt genau das auf.
_ARTIKEL = {
    "Foto": "Das Foto", "Video": "Das Video", "Audio": "Das Audio",
    "Sticker": "Der Sticker", "Sprachnachricht": "Die Sprachnachricht",
    "Datei": "Die Datei",
}


def _ladbar(n) -> bool:
    """Haengt an der Nachricht eine Datei, die man wirklich holen kann?

    Nicht jedes Medium ist eine Datei: Standort, Kontakt, Umfrage und
    die Vorschau eines Links sind Medien ohne etwas zum Speichern --
    download_media gibt dafuer None zurueck. Wer sie beim Lesen als
    holbar ausweist, verspricht etwas, das nicht kommt.

    Alles Ladbare ist am Ende Foto oder Dokument; Video,
    Sprachnachricht, Sticker und Audio sind Dokumente.
    """
    if not getattr(n, "media", None):
        return False
    return bool(getattr(n, "photo", None) or getattr(n, "document", None))


# Wie eine Nachricht in der Leseansicht ihre Nummer traegt.
#
# Die IDs muessen mit, sonst kann man auf nichts gezielt antworten und
# kein Medium gezielt holen -- aber die Antwort wird VORGELESEN, und
# eine Zahl mitten im Satz liest das Modell mit vor: "Anna, viertausend
# siebenhunderteins, hallo". Deshalb drei Entscheidungen:
#
#   1. Die Nummer steht am ZEILENENDE, hinter dem Inhalt. Was am Ende
#      steht, laesst sich beim Zusammenfassen weglassen, ohne dass der
#      Satz zerfaellt.
#   2. Sie traegt ein "#" davor. Das Zeichen hat keine Aussprache --
#      es ist damit sichtbar keine Sprache, sondern eine Angabe fuer
#      Werkzeuge.
#   3. Der Kopf sagt es ausdruecklich dazu. Ein Modell, das nicht
#      weiss, wofuer eine Zahl da ist, liest sie im Zweifel vor.
_KOPF_ERKLAERUNG = (
    "Am Zeilenende steht je Nachricht ihre Nummer als #Zahl, "
    "\"+Medium\" heißt: da hängt eine Datei dran. Beides ist für "
    "Werkzeuge gedacht — telegram_senden (antwort_auf) und "
    "telegram_medium_holen (nachricht_id) — und wird nicht vorgelesen."
)


def _nummer(n) -> str:
    """Der technische Anhang einer Leseansicht-Zeile."""
    return f"  #{n.id}" + (" +Medium" if _ladbar(n) else "")


async def _finden(k, gesucht: str, grenze: int = 200):
    """Alle Chats, die passen -- absteigend nach Güte.

    Gibt bewusst eine Liste zurueck und nicht den besten Treffer: Ueber
    Mehrdeutigkeit entscheidet nicht dieses Modul, sondern der Nutzer.
    """
    treffer = []
    async for d in k.iter_dialogs(limit=grenze):
        g = _passt(d.name, gesucht)
        if g:
            treffer.append((g, d))
    treffer.sort(key=lambda p: -p[0])
    return treffer


# --- Medien auf die Platte ------------------------------------------------
# Ein fester Unterordner unter Sarvis selbst, kein frei waehlbarer Pfad:
# Was aus einem fremden Chat kommt, landet an EINER Stelle, die man
# kennt und jederzeit leerraeumen kann. Ein Werkzeug, dem man den
# Zielordner nennen darf, waere ein Schreibzugriff auf die ganze Platte
# mit Telegram als Zulieferer.
MEDIEN_ORDNER = "telegram"

# Wie gross eine Datei hoechstens sein darf. Gehoert eigentlich nach
# config.py zu den anderen Stellschrauben; hier, weil diese Datei die
# einzige war, die geaendert werden durfte.
#
# Die Grenze ist keine Sicherheitsfrage, sondern eine Gespraechsfrage:
# Ein Video von zwei Gigabyte laedt minutenlang, und solange steht das
# Gespraech. Wer es trotzdem braucht, holt es am Telefon.
MEDIUM_HOECHSTENS_BYTES = 50 * 1024 * 1024

# Erlaubt bleibt, was einen Dateinamen ausmacht -- alles andere fliegt
# raus. Bewusst eine Erlaubnisliste: Eine Sperrliste muesste jedes
# Zeichen kennen, das Windows, eine Shell oder ein Pfad besonders
# behandelt, und uebersieht das erste, an das niemand gedacht hat.
_NAME_ERLAUBT = re.compile(r"[^A-Za-z0-9äöüÄÖÜß._ -]")


def _sauberer_name(roh: str) -> str:
    """Einen Dateinamen aus fremder Hand entschaerfen.

    Der Name steht so im Dokument, wie der ABSENDER ihn gesetzt hat --
    er ist eine Eingabe von aussen, kein Fund auf der eigenen Platte.
    "..\\..\\sarvis\\config.py" ist ein gueltiger Telegram-Dateiname;
    ungeprueft an download_media weitergereicht, schriebe der Download
    dorthin, wohin der Absender zeigt, statt in den Medienordner.

    Deshalb: nur der letzte Namensteil, keine Pfadtrenner, keine Punkte
    und Leerzeichen am Rand (damit weder ".." noch eine versteckte
    Datei uebrig bleibt), nur erlaubte Zeichen, begrenzte Laenge.
    Bleibt nichts uebrig, kommt ein leerer Name zurueck -- der Aufrufer
    setzt dann seinen eigenen ein.
    """
    letzter = re.split(r"[\\/]", str(roh or ""))[-1]
    sauber = _NAME_ERLAUBT.sub("_", letzter)
    sauber = re.sub(r"_{2,}", "_", sauber).strip(" ._")
    return sauber[:60]


def _endung(roh: str) -> str:
    """Die Dateiendung, ebenfalls entschaerft.

    Telethon leitet sie aus dem MIME-Typ ab, und der kommt genauso von
    aussen wie der Name. Punkt plus Buchstaben und Ziffern, mehr nicht.
    """
    rest = re.sub(r"[^A-Za-z0-9]", "", str(roh or ""))[:8]
    return f".{rest.lower()}" if rest else ""


def _medienordner() -> Path:
    """Der Zielordner -- angelegt, falls es ihn noch nicht gibt."""
    ordner = config.WURZEL / MEDIEN_ORDNER
    ordner.mkdir(parents=True, exist_ok=True)
    return ordner


def _zielpfad(n, ordner: Path) -> Path | None:
    """Wohin das Medium dieser Nachricht gespeichert wird.

    Vorn steht IMMER die Nachrichtennummer. Das hat drei Wirkungen auf
    einmal: Die Datei ist ihrer Nachricht zuzuordnen, ein Name kann
    nicht leer bleiben, und Windows' Geraetenamen (CON, NUL, LPT1) sind
    aus dem Weg -- "4711_CON.txt" ist eine gewoehnliche Datei.

    None heisst: Der Name fuehrt aus dem Ordner heraus. Das kann nach
    dem Saeubern nicht mehr passieren; die Pruefung bleibt trotzdem
    stehen, weil sie das Versprechen ist, auf das der Rest sich stuetzt.
    """
    datei = getattr(n, "file", None)
    name = _sauberer_name(getattr(datei, "name", None) or "")
    if not name:
        # Kein eigener Name (Fotos und Sprachnachrichten haben keinen).
        # Dann sagt die Marke, worum es geht: "[Foto]" wird "foto".
        name = _sauberer_name(_marke(n).strip("[]").lower()) or "medium"
    endung = _endung(getattr(datei, "ext", None) or "")
    if endung and not name.lower().endswith(endung):
        name += endung

    ziel = ordner / f"{n.id}_{name}"
    try:
        if ziel.resolve().parent != ordner.resolve():
            return None
    except (OSError, ValueError):
        return None
    return ziel


def werkzeuge(protokoll=None, leuchten=None) -> list:
    def vermerken(text: str):
        if protokoll is not None:
            protokoll.merken(text)

    def blinken():
        if leuchten:
            leuchten("Telegram")

    def _fehlt():
        return {"content": [{"type": "text", "text":
                "Telegram ist nicht angemeldet. Einmalig "
                "telegram_anmelden.py ausführen."}], "is_error": True}

    @tool(
        "telegram_kontakte",
        "Sucht in den Telegram-Chats nach einem Namen und gibt die Treffer "
        "zurück. IMMER zuerst benutzen, bevor du eine Nachricht schickst — "
        "telegram_senden braucht den exakten Chatnamen. Ohne Suchwort "
        "kommen die letzten Chats.",
        {
            "type": "object",
            "properties": {
                "name": {"type": "string",
                         "description": "Teil des Namens, z. B. 'Anna'."},
            },
        },
    )
    async def telegram_kontakte(args):
        k = await klient()
        if k is None:
            return _fehlt()
        blinken()
        gesucht = (args.get("name") or "").strip()
        if not gesucht:
            namen = []
            async for d in k.iter_dialogs(limit=15):
                namen.append(f"{d.name}{' (Gruppe)' if d.is_group else ''}")
            return {"content": [{"type": "text", "text":
                    "Letzte Chats:\n" + "\n".join(namen)}]}

        treffer = await _finden(k, gesucht)
        if not treffer:
            return {"content": [{"type": "text", "text":
                    f"Kein Chat gefunden, der zu {gesucht!r} passt."}]}
        zeilen = [f"{d.name}{' (Gruppe)' if d.is_group else ''}"
                  for _, d in treffer[:8]]
        return {"content": [{"type": "text", "text":
                f"{len(treffer)} Treffer:\n" + "\n".join(zeilen)}]}

    @tool(
        "telegram_senden",
        "Schickt eine Telegram-Nachricht. 'an' muss der exakte Chatname "
        "sein — vorher mit telegram_kontakte nachsehen. Bei mehreren "
        "passenden Chats wird nichts gesendet, sondern nachgefragt. Mit "
        "'antwort_auf' wird daraus eine echte Antwort auf eine bestimmte "
        "Nachricht — die Nummer steht in telegram_lesen hinter dem #.",
        {
            "type": "object",
            "properties": {
                "an": {"type": "string",
                       "description": "Exakter Chatname aus telegram_kontakte."},
                "text": {"type": "string",
                         "description": "Der Nachrichtentext, fertig "
                                        "formuliert."},
                "antwort_auf": {
                    "type": "integer", "minimum": 1,
                    "description": "Optional: Nummer der Nachricht, auf die "
                                   "geantwortet wird (die #Zahl aus "
                                   "telegram_lesen). Ohne Angabe wird eine "
                                   "gewöhnliche Nachricht geschickt.",
                },
                "anhang": {
                    "type": "string",
                    "description": "Eine Datei, die mitgeschickt wird. Der "
                                   "Name reicht und muss nicht genau "
                                   "stimmen — gesucht wird in dem, was du "
                                   "erzeugt hast, und in dem, was Sascha "
                                   "dir geschickt hat.",
                },
            },
            "required": ["an", "text"],
        },
    )
    async def telegram_senden(args):
        k = await klient()
        if k is None:
            return _fehlt()
        an = (args.get("an") or "").strip()
        text = (args.get("text") or "").strip()
        if not (an and text):
            return {"content": [{"type": "text", "text":
                    "Ich brauche Empfänger und Text."}], "is_error": True}

        # Die Nummer wird VOR der Chatsuche geprueft, nicht erst beim
        # Senden. Was hier auffaellt, kostet keine Netzverbindung.
        bezug = args.get("antwort_auf")
        if bezug is not None:
            try:
                bezug = int(bezug)
            except (TypeError, ValueError):
                bezug = 0
            if bezug < 1:
                return {"content": [{"type": "text", "text":
                        "Die Nachrichtennummer ergibt keinen Sinn. Nichts "
                        "gesendet."}], "is_error": True}

        treffer = await _finden(k, an)
        if not treffer:
            return {"content": [{"type": "text", "text":
                    f"Keinen Chat namens {an!r} gefunden. Nichts gesendet."}],
                    "is_error": True}

        # Mehrdeutigkeit ist hier kein Randfall, sondern der gefaehrlichste:
        # Eine Nachricht an den Falschen laesst sich nicht zurueckholen.
        beste = treffer[0][0]
        # Ein einzelner schwacher Treffer galt frueher als eindeutig: "Ben"
        # fand die Gruppe "Kollegen Benedikt" (Guete 50) und die Nachricht
        # ging raus. Die Rueckfrage faengt das nicht auf, sie wird aus dem
        # Rohargument gebaut, bevor hier aufgeloest wird. Ab 70 ist ein
        # ganzes Wort des Chatnamens getroffen -- darunter wird geraten.
        if beste < 70:
            return {"content": [{"type": "text", "text":
                    f"Der beste Treffer zu {an!r} ist "
                    f"{treffer[0][1].name} — das ist geraten. Frag nach, "
                    "wer gemeint ist. Nichts gesendet."}], "is_error": True}
        gleichauf = [d for g, d in treffer if g == beste]
        if len(gleichauf) > 1:
            namen = ", ".join(d.name for d in gleichauf[:5])
            return {"content": [{"type": "text", "text":
                    f"Mehrdeutig — es passen: {namen}. Nichts gesendet, "
                    "frag nach, wer gemeint ist."}], "is_error": True}

        ziel = gleichauf[0]

        # Gibt es die Nachricht ueberhaupt, auf die geantwortet werden
        # soll? Telegram nimmt eine unbekannte Nummer klaglos an und
        # macht daraus eine gewoehnliche Nachricht -- der Bezug faellt
        # still weg. Zugesagt war aber eine ANTWORT auf etwas
        # Bestimmtes; ohne den Bezug ist es nicht dieselbe Handlung.
        # Also lieber nichts senden als etwas anderes.
        if bezug is not None:
            try:
                vorlage = await k.get_messages(ziel.entity, ids=bezug)
            except Exception:
                vorlage = None
            if vorlage is None:
                return {"content": [{"type": "text", "text":
                        f"In {ziel.name} gibt es keine Nachricht mit der "
                        f"Nummer {bezug}. Nichts gesendet."}],
                        "is_error": True}

        anhang = (args.get("anhang") or "").strip()
        pfad = None
        if anhang:
            pfad, fehler = eingang.datei_finden(anhang)
            if pfad is None:
                # Nicht ohne Anhang senden. Eine Nachricht, die "hier ist
                # das Angebot" sagt und nichts mitbringt, ist schlimmer
                # als gar keine -- und niemand merkt es, weil das Senden
                # ja "geklappt" hat.
                return {"content": [{"type": "text", "text":
                        f"{fehler} Ich habe NICHTS gesendet."}],
                        "is_error": True}

        if pfad is None:
            await k.send_message(ziel.entity, text, reply_to=bezug)
        else:
            # force_document: Sonst macht Telegram aus einem PDF-Plan
            # eine Bildvorschau und aus einer .md-Datei einen Textblock.
            # Wer eine Datei schickt, will eine Datei.
            await k.send_file(ziel.entity, str(pfad), caption=text,
                              reply_to=bezug, force_document=True)
        blinken()
        worauf = f" als Antwort auf #{bezug}" if bezug else ""
        dazu = f" mit {pfad.name}" if pfad else ""
        vermerken(f"telegram_senden: Nachricht an {ziel.name}{worauf}{dazu} "
                  f"ist raus — „{text[:60]}“")
        return {"content": [{"type": "text", "text":
                f"Gesendet an {ziel.name}{dazu}"
                + (" — als Antwort auf die genannte Nachricht." if bezug
                   else ".")}]}

    @tool(
        "telegram_lesen",
        "Liest die letzten Nachrichten eines Chats. Für 'was hat Anna "
        "geschrieben' oder 'lies mir das vor'. Am Zeilenende steht je "
        "Nachricht ihre Nummer (#Zahl) und ob eine Datei dranhängt "
        "(+Medium) — damit arbeiten telegram_senden und "
        "telegram_medium_holen. Vorgelesen wird das nicht.",
        {
            "type": "object",
            "properties": {
                "chat": {"type": "string", "description": "Name des Chats."},
                "anzahl": {"type": "integer", "minimum": 1, "maximum": 30,
                           "description": "Wie viele Nachrichten. Vorgabe 8."},
            },
            "required": ["chat"],
        },
    )
    async def telegram_lesen(args):
        k = await klient()
        if k is None:
            return _fehlt()
        treffer = await _finden(k, (args.get("chat") or "").strip())
        if not treffer:
            return {"content": [{"type": "text", "text":
                    "Diesen Chat finde ich nicht."}], "is_error": True}
        ziel = treffer[0][1]
        anzahl = int(args.get("anzahl") or 8)
        zeilen = []
        async for n in k.iter_messages(ziel.entity, limit=anzahl):
            wer = "Du" if n.out else ziel.name
            inhalt = n.text or _marke(n)
            # Ein Foto MIT Bildunterschrift trug bisher nur die
            # Unterschrift: Man las den Text und erfuhr nie, dass ein
            # Bild dranhing. _marke() greift nur, wo gar kein Text ist.
            if n.text and _ladbar(n):
                inhalt = f"{inhalt} {_marke(n)}"
            zeilen.append(f"[{n.date.astimezone():%d.%m. %H:%M}] {wer}: "
                          f"{inhalt}{_nummer(n)}")
        blinken()
        if not zeilen:
            return {"content": [{"type": "text", "text":
                    f"In {ziel.name} steht nichts."}]}
        # reversed() ordnet aufsteigend -- so liest man einen Chat. Der Kopf
        # behauptete dazu das Gegenteil.
        return {"content": [{"type": "text", "text":
                f"Chat mit {ziel.name}, älteste zuerst. {_KOPF_ERKLAERUNG}\n"
                + "\n".join(reversed(zeilen))}]}

    @tool(
        "telegram_medium_holen",
        "Lädt das Foto, die Sprachnachricht oder die Datei einer bestimmten "
        "Telegram-Nachricht auf diesen Rechner und nennt den Pfad. Die "
        "Nachrichtennummer steht in telegram_lesen hinter dem # — dort sind "
        "die Nachrichten mit Datei als +Medium gekennzeichnet.",
        {
            "type": "object",
            "properties": {
                "chat": {"type": "string", "description": "Name des Chats."},
                "nachricht_id": {
                    "type": "integer", "minimum": 1,
                    "description": "Nummer der Nachricht (die #Zahl aus "
                                   "telegram_lesen).",
                },
            },
            "required": ["chat", "nachricht_id"],
        },
    )
    async def telegram_medium_holen(args):
        k = await klient()
        if k is None:
            return _fehlt()
        try:
            nummer = int(args.get("nachricht_id"))
        except (TypeError, ValueError):
            nummer = 0
        if nummer < 1:
            return {"content": [{"type": "text", "text":
                    "Ich brauche die Nummer der Nachricht — die steht beim "
                    "Lesen hinter dem Rautezeichen."}], "is_error": True}

        # Dieselbe milde Chatsuche wie beim Lesen und bewusst nicht die
        # strenge aus telegram_senden: Hier geht nichts hinaus. Wird der
        # falsche Chat getroffen, gibt es die Nummer dort meistens gar
        # nicht -- und wenn doch, hat man eine Datei zu viel geladen,
        # keine Nachricht zu viel verschickt.
        treffer = await _finden(k, (args.get("chat") or "").strip())
        if not treffer:
            return {"content": [{"type": "text", "text":
                    "Diesen Chat finde ich nicht."}], "is_error": True}
        ziel = treffer[0][1]

        try:
            n = await k.get_messages(ziel.entity, ids=nummer)
        except Exception:
            n = None
        if n is None:
            return {"content": [{"type": "text", "text":
                    f"In {ziel.name} gibt es keine Nachricht mit der Nummer "
                    f"{nummer}."}], "is_error": True}
        if not _ladbar(n):
            return {"content": [{"type": "text", "text":
                    f"An der Nachricht {nummer} in {ziel.name} hängt nichts, "
                    "was ich herunterladen könnte."}], "is_error": True}

        groesse = getattr(getattr(n, "file", None), "size", None) or 0
        if groesse > MEDIUM_HOECHSTENS_BYTES:
            return {"content": [{"type": "text", "text":
                    f"Die Datei ist {groesse // (1024 * 1024)} Megabyte groß "
                    "— das lade ich hier nicht, das dauert zu lange."}],
                    "is_error": True}

        ordner = _medienordner()
        ziel_pfad = _zielpfad(n, ordner)
        if ziel_pfad is None:
            return {"content": [{"type": "text", "text":
                    "Der Dateiname aus diesem Chat ist nicht in Ordnung — "
                    "ich lade nichts herunter."}], "is_error": True}

        # Die Nummer steht vorn im Namen, also ueberschreibt ein zweiter
        # Aufruf hoechstens dieselbe Datei mit demselben Inhalt.
        pfad = await k.download_media(n, file=str(ziel_pfad))
        if not pfad:
            return {"content": [{"type": "text", "text":
                    "Telegram hat mir zu dieser Nachricht keine Datei "
                    "gegeben."}], "is_error": True}

        blinken()
        marke = _marke(n).strip("[]")
        name = Path(pfad).name
        vermerken(f"telegram_medium_holen: {marke} aus {ziel.name} "
                  f"(#{nummer}) liegt unter {pfad}")
        return {"content": [{"type": "text", "text":
                f"{_ARTIKEL.get(marke, 'Der Anhang')} aus dem Chat mit "
                f"{ziel.name} liegt jetzt als {name} im Ordner "
                f"{MEDIEN_ORDNER} unter Sarvis. Voller Pfad: {pfad}"}]}

    @tool(
        "telegram_suchen",
        "Durchsucht Telegram-Nachrichten nach einem Stichwort — entweder in "
        "einem bestimmten Chat oder über alle hinweg. Für 'wann hatten wir "
        "über X geschrieben'.",
        {
            "type": "object",
            "properties": {
                "suchwort": {"type": "string", "description": "Wonach suchen."},
                "chat": {"type": "string",
                         "description": "Optional: nur in diesem Chat."},
            },
            "required": ["suchwort"],
        },
    )
    async def telegram_suchen(args):
        k = await klient()
        if k is None:
            return _fehlt()
        wort = (args.get("suchwort") or "").strip()
        if not wort:
            return {"content": [{"type": "text", "text":
                    "Ohne Suchwort geht nichts."}], "is_error": True}

        ziel = None
        if (args.get("chat") or "").strip():
            treffer = await _finden(k, args["chat"].strip())
            if not treffer:
                return {"content": [{"type": "text", "text":
                        "Diesen Chat finde ich nicht."}], "is_error": True}
            ziel = treffer[0][1].entity

        zeilen = []
        async for n in k.iter_messages(ziel, search=wort, limit=12):
            if not n.text:
                continue
            try:
                wer = "Du" if n.out else (
                    getattr(await n.get_chat(), "title", None)
                    or getattr(await n.get_sender(), "first_name", "?")
                )
            except Exception:
                wer = "?"
            zeilen.append(f"[{n.date.astimezone():%d.%m.%Y %H:%M}] {wer}: "
                          f"{n.text[:160]}")
        blinken()
        if not zeilen:
            return {"content": [{"type": "text", "text":
                    f"Nichts zu {wort!r} gefunden."}]}
        return {"content": [{"type": "text", "text":
                f"{len(zeilen)} Fundstellen zu {wort!r}:\n" + "\n".join(zeilen)}]}

    return [telegram_kontakte, telegram_senden, telegram_lesen,
            telegram_medium_holen, telegram_suchen]
