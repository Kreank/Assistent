# -*- coding: utf-8 -*-
"""Einmalige Telegram-Anmeldung.

Läuft genau einmal. Danach liegt `sarvis.session` im Projektordner und
Sarvis meldet sich damit selbst an — ohne Code, ohne Passwort.

    .venv\\Scripts\\python.exe telegram_anmelden.py

WICHTIG zu `sarvis.session`: Diese Datei ist so viel wert wie dein
Telegram-Konto. Wer sie hat, ist als du angemeldet. Sie steht in der
.gitignore und gehört weder in ein Repository noch in eine Sicherung,
die andere lesen können. Verloren gegangen? In Telegram unter
Einstellungen → Geräte die Sitzung beenden, dann hier neu anmelden.
"""
import asyncio
import sys

from telethon import TelegramClient

from sarvis import config


async def main() -> int:
    zugang = config.telegram_zugang()
    if not zugang:
        print("\n  In der .env fehlen TELEGRAM_API_ID / TELEGRAM_API_HASH.")
        print("  Zu holen bei my.telegram.org → API development tools.\n")
        return 1

    api_id, api_hash = zugang
    print("\n  Telegram-Anmeldung für Sarvis")
    print("  " + "-" * 44)
    print(f"  Sitzungsdatei: {config.TELEGRAM_SITZUNG}")
    print("  Du brauchst gleich deine Telefonnummer (mit +49...) und den")
    print("  Code, den Telegram dir in die App schickt.\n")

    klient = TelegramClient(str(config.TELEGRAM_SITZUNG), api_id, api_hash)
    await klient.start()   # fragt selbst nach Nummer, Code und ggf. Passwort

    ich = await klient.get_me()
    name = " ".join(filter(None, [ich.first_name, ich.last_name]))
    print(f"\n  Angemeldet als: {name}"
          + (f" (@{ich.username})" if ich.username else ""))

    # Ein paar Kontakte zeigen, damit du gleich weisst, welche Namen
    # Sarvis spaeter treffen kann.
    print("\n  Deine letzten Chats (so heissen sie fuer Sarvis):")
    async for dialog in klient.iter_dialogs(limit=12):
        art = "Gruppe" if dialog.is_group else ("Kanal" if dialog.is_channel
                                                else "Person")
        print(f"    {art:7s}  {dialog.name}")

    await klient.disconnect()
    print("\n  Fertig. Die Sitzungsdatei bleibt liegen — nicht weitergeben.\n")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
