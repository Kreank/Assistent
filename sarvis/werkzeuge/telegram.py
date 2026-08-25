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

from claude_agent_sdk import tool

from .. import config

_klient = None
_schloss = asyncio.Lock()


async def klient():
    """Verbindung herstellen und offen halten.

    Erst beim ersten Gebrauch, nicht beim Start: Wer Telegram nie
    benutzt, soll dafuer keine Sekunde Startzeit zahlen.
    """
    global _klient
    async with _schloss:
        if _klient is not None and _klient.is_connected():
            return _klient
        zugang = config.telegram_zugang()
        if not zugang or not config.TELEGRAM_SITZUNG.exists():
            return None
        from telethon import TelegramClient

        api_id, api_hash = zugang
        _klient = TelegramClient(str(config.TELEGRAM_SITZUNG), api_id, api_hash)
        await _klient.connect()
        if not await _klient.is_user_authorized():
            _klient = None
        return _klient


async def schliessen():
    global _klient
    if _klient is not None:
        try:
            await _klient.disconnect()
        except Exception:
            pass
        _klient = None


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
        "passenden Chats wird nichts gesendet, sondern nachgefragt.",
        {
            "type": "object",
            "properties": {
                "an": {"type": "string",
                       "description": "Exakter Chatname aus telegram_kontakte."},
                "text": {"type": "string",
                         "description": "Der Nachrichtentext, fertig "
                                        "formuliert."},
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

        treffer = await _finden(k, an)
        if not treffer:
            return {"content": [{"type": "text", "text":
                    f"Keinen Chat namens {an!r} gefunden. Nichts gesendet."}],
                    "is_error": True}

        # Mehrdeutigkeit ist hier kein Randfall, sondern der gefaehrlichste:
        # Eine Nachricht an den Falschen laesst sich nicht zurueckholen.
        beste = treffer[0][0]
        gleichauf = [d for g, d in treffer if g == beste]
        if len(gleichauf) > 1:
            namen = ", ".join(d.name for d in gleichauf[:5])
            return {"content": [{"type": "text", "text":
                    f"Mehrdeutig — es passen: {namen}. Nichts gesendet, "
                    "frag nach, wer gemeint ist."}], "is_error": True}

        ziel = gleichauf[0]
        await k.send_message(ziel.entity, text)
        blinken()
        vermerken(f"telegram_senden: Nachricht an {ziel.name} ist raus — "
                  f"„{text[:60]}“")
        return {"content": [{"type": "text", "text":
                f"Gesendet an {ziel.name}."}]}

    @tool(
        "telegram_lesen",
        "Liest die letzten Nachrichten eines Chats. Für 'was hat Anna "
        "geschrieben' oder 'lies mir das vor'.",
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
            if not n.text:
                continue
            wer = "Du" if n.out else ziel.name
            zeilen.append(f"[{n.date.astimezone():%d.%m. %H:%M}] {wer}: {n.text}")
        blinken()
        if not zeilen:
            return {"content": [{"type": "text", "text":
                    f"In {ziel.name} steht nichts Lesbares."}]}
        return {"content": [{"type": "text", "text":
                f"Chat mit {ziel.name}, neueste zuerst:\n"
                + "\n".join(reversed(zeilen))}]}

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

    return [telegram_kontakte, telegram_senden, telegram_lesen, telegram_suchen]
