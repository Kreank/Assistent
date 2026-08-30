"""Telegram als Bedienung -- eine Oberflaeche wie jede andere.

Sarvis kennt keinen Telegram-Sonderfall. Dieser Dienst haengt sich als
gewoehnliche Oberflaeche an den Draht, genau wie ein Browser oder eine
native App: Er meldet sich mit einem Geraeteschluessel an, schickt
`zuruf` und `sprache` hinein und macht aus dem, was zurueckkommt,
Telegram-Nachrichten.

Das ist der Grund, warum es ihn ueberhaupt geben kann, ohne dass im Kern
eine Zeile dafuer steht. Wer eine weitere Bedienung will -- Discord, eine
Uhr, ein Knopf an der Wand -- baut dasselbe noch einmal.

WOZU, WENN ES DIE OBERFLAECHE GIBT

Als Ausweichweg. Telegram laeuft ueberall, hat seine eigene
Push-Infrastruktur und funktioniert auch dann noch, wenn die Weboberflaeche
kaputt, das Zertifikat abgelaufen oder das Handy neu ist. Es kostet
nichts, es liegen zu lassen, und es ist der einzige Kanal, der einen
erreicht, ohne dass man ihn vorher geoeffnet hat.

Und solange es keine native Android-App gibt, ist es der bequemste Weg,
Sarvis unterwegs eine Sprachnachricht zu schicken.

WAS ES NICHT IST

Kein Ersatz fuer das Gespraech. Telegram ist rundenbasiert -- eine
Nachricht, eine Antwort. Der Ring schlaegt nicht aus, es gibt kein
Reinreden, kein Weckwort, keine Kacheln. Wer den Assistenten wirklich
BENUTZT, tut das ueber die Oberflaeche; hier fragt man etwas, wenn man
gerade nicht anders kann.

Deshalb faellt hier auch alles weg, was Zustand ist: `pegel`,
`nachhoeren`, `freigabe`, `werkzeug`. Was ankommt, sind Saetze.
"""
import asyncio
import base64
import json
import logging
import os
import subprocess
import tempfile
import time
from pathlib import Path

import aiohttp

log = logging.getLogger("sarvis.telegram")

API = "https://api.telegram.org/bot{token}/{methode}"

# Wie lange die Telegram-Abfrage offen bleibt. Long Polling: Der Server
# antwortet erst, wenn etwas da ist oder die Zeit um ist -- das spart
# Anfragen und ist trotzdem sofort da.
WARTEN = 50

# Ab wie vielen Zeichen die Antwort geteilt wird. Telegram nimmt 4096;
# etwas Luft, weil Markdown-Reste die Laenge veraendern koennen.
NACHRICHT_MAX = 3800

# Wie lange auf Sarvis' Antwort gewartet wird, bevor der Kanal aufgibt
# und das sagt. Er ist rundenbasiert -- ohne Frist wartet er ewig auf
# eine Antwort, die vielleicht nie kommt.
ANTWORT_FRIST = 180.0


def _opus_zu_pcm(datei: Path) -> bytes | None:
    """Eine Telegram-Sprachnachricht in das Format, das Whisper will.

    Telegram schickt Opus in einem OGG-Behaelter. Whisper braucht
    16 kHz, mono, int16 -- also genau das, was auch die Weboberflaeche
    schickt. ffmpeg macht beides in einem Durchgang, samt Tiefpass beim
    Umtasten; von Hand jeden dritten Wert zu nehmen waere billiger und
    haette hoerbares Aliasing.
    """
    try:
        fertig = subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error",
             "-i", str(datei), "-f", "s16le", "-acodec", "pcm_s16le",
             "-ac", "1", "-ar", "16000", "-"],
            capture_output=True, timeout=120,
        )
        if fertig.returncode != 0:
            log.warning("ffmpeg: %s", fertig.stderr.decode()[:200])
            return None
        return fertig.stdout or None
    except (OSError, subprocess.SubprocessError) as e:
        log.warning("Umwandeln ging nicht: %s", e)
        return None


class TelegramKanal:
    """Bindeglied zwischen Telegram und dem Draht."""

    def __init__(self, token: str, schluessel: str, erlaubt: set[int],
                 draht: str = "ws://127.0.0.1:8900/draht"):
        self.token = token
        self.schluessel = schluessel
        # Wer schreiben darf. Ein Bot-Name ist oeffentlich, und ein
        # Assistent, der Mails senden und Geld buchen kann, gehoert nicht
        # jedem, der ihn findet.
        self.erlaubt = erlaubt
        self.draht = draht
        self.sitzung: aiohttp.ClientSession | None = None
        self.ws = None
        self.letzte = 0
        # Wer gerade auf Antwort wartet. Telegram ist rundenbasiert:
        # Was Sarvis sagt, geht an den, der zuletzt gefragt hat.
        self.wartet_auf: int | None = None
        self.gesammelt: list[str] = []
        self.zuletzt_gesagt = 0.0

    # --- Telegram --------------------------------------------------------

    async def _tg(self, methode: str, **felder):
        url = API.format(token=self.token, methode=methode)
        async with self.sitzung.post(url, json=felder) as a:
            return await a.json()

    async def schreiben(self, chat: int, text: str) -> None:
        """Text hinaus -- notfalls in mehreren Stuecken.

        Geteilt wird an Zeilenumbruechen, nicht mitten im Wort: Eine
        Antwort, die im Satz abbricht und im naechsten Kasten weitergeht,
        liest sich wie ein Fehler.
        """
        for stueck in self._teilen(text):
            try:
                await self._tg("sendMessage", chat_id=chat, text=stueck)
            except Exception as e:
                log.warning("Senden ging nicht: %s", e)

    @staticmethod
    def _teilen(text: str) -> list[str]:
        text = (text or "").strip()
        if len(text) <= NACHRICHT_MAX:
            return [text] if text else []
        stuecke, rest = [], text
        while len(rest) > NACHRICHT_MAX:
            schnitt = rest.rfind("\n", 0, NACHRICHT_MAX)
            if schnitt < NACHRICHT_MAX // 2:
                schnitt = rest.rfind(" ", 0, NACHRICHT_MAX)
            if schnitt <= 0:
                schnitt = NACHRICHT_MAX
            stuecke.append(rest[:schnitt].strip())
            rest = rest[schnitt:].lstrip()
        if rest:
            stuecke.append(rest)
        return stuecke

    async def _datei_holen(self, datei_id: str) -> Path | None:
        d = await self._tg("getFile", file_id=datei_id)
        pfad = (d.get("result") or {}).get("file_path")
        if not pfad:
            return None
        url = f"https://api.telegram.org/file/bot{self.token}/{pfad}"
        ziel = Path(tempfile.gettempdir()) / f"sarvis-{int(time.time()*1000)}.oga"
        async with self.sitzung.get(url) as a:
            if a.status != 200:
                return None
            ziel.write_bytes(await a.read())
        return ziel

    # --- Der Draht -------------------------------------------------------

    async def _anmelden(self) -> bool:
        self.ws = await self.sitzung.ws_connect(self.draht, heartbeat=30)
        await self.ws.send_str(json.dumps({
            "schluessel": self.schluessel,
            # Telegram hat keinen Bildschirm, auf dem man eine Seite
            # bedienen koennte. Die Frage geht woandershin.
            "kann_browser": False,
        }))
        erste = await asyncio.wait_for(self.ws.receive(), 15)
        if erste.type is not aiohttp.WSMsgType.TEXT:
            return False
        m = json.loads(erste.data)
        if m.get("art") != "willkommen":
            return False
        log.info("Am Draht als '%s'", m.get("geraet"))
        return True

    async def _vom_draht(self) -> None:
        """Was Sarvis sagt, nach Telegram tragen.

        Gesammelt wird bis zur Ruhe: Sarvis spricht satzweise, und jeden
        Satz einzeln zu schicken ergaebe fuenf Benachrichtigungen fuer
        eine Antwort.
        """
        async for nachricht in self.ws:
            if nachricht.type is not aiohttp.WSMsgType.TEXT:
                continue
            try:
                m = json.loads(nachricht.data)
            except ValueError:
                continue
            art = m.get("art")

            if art == "untertitel" and m.get("wer") == "sarvis" and not m.get("strom"):
                text = (m.get("text") or "").strip()
                # Der Untertitel waechst mit jedem Satz -- er traegt
                # immer die ganze bisherige Antwort. Also ersetzen,
                # nicht anhaengen.
                if text:
                    self.gesammelt = [text]
                    self.zuletzt_gesagt = time.monotonic()

            elif art == "zustand" and not m.get("strom"):
                # Zurueck auf ruhig heisst: Er ist fertig.
                if m.get("zustand") == "ruhig" and self.gesammelt:
                    await self._abliefern()

    async def _abliefern(self) -> None:
        text = "\n".join(self.gesammelt).strip()
        self.gesammelt = []
        ziel = self.wartet_auf
        self.wartet_auf = None
        if text and ziel:
            await self.schreiben(ziel, text)

    # --- Zusammenbinden --------------------------------------------------

    async def _eine_nachricht(self, m: dict) -> None:
        chat = (m.get("chat") or {}).get("id")
        if chat is None:
            return
        if self.erlaubt and chat not in self.erlaubt:
            log.warning("Abgewiesen: %s", chat)
            return

        self.wartet_auf = chat

        if m.get("voice") or m.get("audio"):
            teil = m.get("voice") or m.get("audio")
            await self._tg("sendChatAction", chat_id=chat, action="typing")
            datei = await self._datei_holen(teil.get("file_id"))
            if datei is None:
                await self.schreiben(chat, "Die Sprachnachricht kam nicht an.")
                return
            try:
                pcm = await asyncio.to_thread(_opus_zu_pcm, datei)
            finally:
                datei.unlink(missing_ok=True)
            if not pcm:
                await self.schreiben(
                    chat, "Ich konnte die Aufnahme nicht umwandeln.")
                return
            await self.ws.send_str(json.dumps({
                "art": "sprache", "rate": 16000,
                "daten": base64.b64encode(pcm).decode("ascii"),
            }))
            return

        text = (m.get("text") or "").strip()
        if not text:
            return
        await self._tg("sendChatAction", chat_id=chat, action="typing")
        await self.ws.send_str(json.dumps({"art": "zuruf", "text": text}))

    async def _abholen(self) -> None:
        while True:
            try:
                d = await self._tg("getUpdates", offset=self.letzte + 1,
                                   timeout=WARTEN,
                                   allowed_updates=["message"])
            except Exception as e:
                log.warning("getUpdates: %s", e)
                await asyncio.sleep(3)
                continue
            for u in d.get("result", []):
                self.letzte = max(self.letzte, u.get("update_id", 0))
                m = u.get("message")
                if m:
                    try:
                        await self._eine_nachricht(m)
                    except Exception as e:
                        log.warning("Nachricht ging schief: %s", e)

    async def _wache(self) -> None:
        """Aufgeben, wenn keine Antwort kommt.

        Ohne das wartet jemand, der etwas gefragt hat, bis zum
        Sanktnimmerleinstag auf eine Antwort -- und weiss nicht, ob
        Sarvis noch denkt oder laengst gestorben ist.
        """
        while True:
            await asyncio.sleep(5)
            if (self.wartet_auf and self.zuletzt_gesagt
                    and time.monotonic() - self.zuletzt_gesagt > ANTWORT_FRIST):
                ziel = self.wartet_auf
                self.wartet_auf = None
                self.gesammelt = []
                await self.schreiben(
                    ziel, "Ich habe zu lange gebraucht und höre hier auf. "
                          "Frag noch einmal, wenn du magst.")

    async def laufen(self) -> None:
        async with aiohttp.ClientSession() as s:
            self.sitzung = s
            warte = 1.0
            while True:
                try:
                    if not await self._anmelden():
                        log.error("Der Draht nimmt den Schlüssel nicht an.")
                        await asyncio.sleep(30)
                        continue
                    warte = 1.0
                    await asyncio.gather(self._vom_draht(), self._abholen(),
                                         self._wache())
                except Exception as e:
                    log.warning("Verbindung weg (%s) -- neu in %.0fs", e, warte)
                    await asyncio.sleep(warte)
                    warte = min(warte * 1.6, 20.0)


def main() -> int:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    token = os.environ.get("SARVIS_TG_TOKEN", "").strip()
    schluessel = os.environ.get("SARVIS_TG_SCHLUESSEL", "").strip()
    erlaubt = {int(x) for x in os.environ.get("SARVIS_TG_ERLAUBT", "").split(",")
               if x.strip().lstrip("-").isdigit()}
    if not token or not schluessel:
        print("SARVIS_TG_TOKEN und SARVIS_TG_SCHLUESSEL setzen.")
        return 1
    if not erlaubt:
        # Bewusst ein Abbruch und keine Warnung: Ein Bot-Name ist
        # oeffentlich. Ohne Liste koennte jeder, der ihn findet, Mails
        # in Saschas Namen schicken.
        print("SARVIS_TG_ERLAUBT setzen -- ohne Liste darf niemand.")
        return 1
    draht = os.environ.get("SARVIS_DRAHT", "ws://127.0.0.1:8900/draht")
    asyncio.run(TelegramKanal(token, schluessel, erlaubt, draht).laufen())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
