"""Ist Sarvis' Kopf angemeldet? -- und was zu tun ist, wenn nicht.

WARUM ES DAS GIBT

Am 30.08.2026 lief Sarvis vier Stunden lang und antwortete auf jeden
Zuruf mit "Failed to authenticate: OAuth session expired and could not
be refreshed". Auf Englisch, mitten in einem deutschen Gespraech, ohne
einen Hinweis, was zu tun ist. Gemerkt hat es Sascha beim Ausprobieren.

Der Fehler dahinter war meiner: Ich hatte die Anmeldung von Saschas
Claude-Code-Sitzung KOPIERT, statt Sarvis eine eigene zu geben. Das
haelt nicht, und zwar aus einem Grund, der sich nicht wegkonfigurieren
laesst: **Ein Refresh-Token gilt fuer genau eine Einloesung.** Wer
zuerst erneuert, macht die Kopie des anderen ungueltig. Zwei Prozesse
auf einer Anmeldung sind also nicht "riskant", sondern eine Zeitbombe
mit bekannter Zuendzeit.

DER RICHTIGE WEG ist ein eigenes, langlebiges Token:

    docker compose exec sarvis claude setup-token

Das fragt einmal nach einer Anmeldung im Browser und haelt danach.

WAS DIESE DATEI TUT

Sie verhindert den Ausfall nicht -- ein Token kann zurueckgezogen
werden, ein Abo auslaufen, ein Dienst stillstehen. Sie sorgt dafuer,
dass man es SOFORT sieht statt beim naechsten Ausprobieren:

  beim Start        eine deutliche Zeile mit dem Befehl zum Beheben
  im Betrieb        eine deutsche Meldung statt einer englischen
                    Ausnahme -- und in der Anzeige, nicht nur im Log
  nebenher          eine Wache, die von selbst nachsieht und Sascha
                    ANSCHREIBT, sobald der Zugang kippt

Das ist der eigentliche Unterschied im Produktivbetrieb. Nicht dass
nichts kaputtgeht, sondern dass Kaputtes sich meldet.

WARUM ES DIE WACHE BRAUCHT, OBWOHL DER REST SCHON MELDET

Weil alles darueber erst spricht, wenn jemand zuhoert. Der Start ist
einmal, und die Meldung im Gespraech setzt ein Gespraech voraus. Am
31.08.2026 lief Sarvis so vier Stunden ohne Kopf: Er stand da, wirkte
gesund, und gemerkt hat es Sascha erst, als er ihn brauchte -- also im
denkbar schlechtesten Moment.

Ein Token haelt lange, aber nicht ewig. Laeuft es nachts ab, ist das
ohne Wache exakt derselbe Morgen noch einmal. Mit ihr kommt die
Nachricht, bevor er davorsteht.
"""
import asyncio
import json
import os
import subprocess
from datetime import datetime

# Wie lange auf die Auskunft gewartet wird. Sie kostet normalerweise
# Millisekunden; laenger als das heisst, dass etwas anderes klemmt, und
# dann soll der Start nicht daran haengen.
FRIST = 15.0

# Woran ein Anmeldefehler zu erkennen ist. Absichtlich mehrere Muster:
# Die Meldung kommt aus der CLI und kann sich mit ihr aendern, und ein
# Anmeldefehler, den wir nicht erkennen, faellt zurueck in genau das
# Verhalten, gegen das diese Datei gebaut ist.
MUSTER = (
    "failed to authenticate",
    "oauth",
    "session expired",
    "not logged in",
    "unauthorized",
    "401",
    "invalid api key",
    "authentication_error",
)

# Der Befehl allein reicht NICHT, und das hat am 31.08.2026 eine
# Viertelstunde gekostet: `claude setup-token` speichert nichts, es
# ZEIGT das Token nur an. Wer es nicht eintraegt, startet neu und steht
# vor derselben Meldung. Deshalb stehen hier alle drei Schritte.
RAT = (
    "Sarvis' Zugang zu Claude gilt nicht mehr. In /srv/storage/projects/sarvis:\n"
    "      1. docker compose exec sarvis claude setup-token\n"
    "      2. das angezeigte Token (sk-ant-oat01-...) als\n"
    "         CLAUDE_CODE_OAUTH_TOKEN=... in /srv/data/sarvis/claude.env\n"
    "      3. docker compose restart sarvis"
)


def _status_lesen() -> dict:
    """`claude auth status` als Verzeichnis, oder leer."""
    try:
        fertig = subprocess.run(["claude", "auth", "status"],
                                capture_output=True, text=True, timeout=FRIST)
        return json.loads(fertig.stdout or "{}")
    except (OSError, subprocess.SubprocessError, ValueError):
        return {}


async def pruefen() -> tuple[bool, str]:
    """(angemeldet, was man dazu sagen kann).

    Laeuft in einem Faden: Es ist ein Unterprozess, und der gehoert
    nicht in die Ereignisschleife, die gleichzeitig ein Gespraech
    traegt.

    Bei Zweifel WAHR: Wer nicht sicher weiss, dass die Anmeldung fehlt,
    soll den Start nicht mit einer Warnung verstellen, die vielleicht
    falsch ist. Der echte Fehler faellt beim ersten Zuruf ohnehin auf --
    dann aber mit verstaendlichem Text (siehe klingt_nach_anmeldung).
    """
    d = await asyncio.to_thread(_status_lesen)
    if not d:
        return True, "Anmeldung nicht pruefbar (claude auth status)"
    if d.get("loggedIn"):
        art = d.get("authMethod") or "?"
        return True, f"angemeldet ({art})"
    return False, "NICHT ANGEMELDET"


def klingt_nach_anmeldung(fehler) -> bool:
    """Ist dieser Fehler ein Anmeldeproblem?"""
    text = f"{type(fehler).__name__}: {fehler}".lower()
    return any(m in text for m in MUSTER)


def satz() -> str:
    """Was Sarvis dazu SAGT -- gesprochen, nicht als Fehlermeldung.

    Auf Deutsch und ohne Fachwort: Wer gerade mit ihm redet, will
    wissen, was los ist, nicht welche Ausnahme geflogen ist. Der Befehl
    steht im Log, nicht im gesprochenen Satz -- niemand tippt etwas ab,
    das er gehoert hat.
    """
    return ("Mein Zugang zu Claude gilt nicht mehr. Ich kann gerade nicht "
            "denken. Im Protokoll steht, wie du mich wieder anmeldest.")


# --- Die Wache ------------------------------------------------------------
#
# Wie oft nachgesehen wird. Eine halbe Stunde ist reichlich fuer etwas,
# das hoechstens einmal im Jahr passiert -- und die Pruefung kostet
# einen Unterprozess, nicht einen Modellaufruf. Wer schneller Bescheid
# wissen will, dreht hier; wer im Gespraech auf einen Anmeldefehler
# laeuft, weckt die Wache ohnehin sofort (siehe jetzt_nachsehen).
WACHE_ABSTAND_SEK = 1800.0

# Nach einer verschickten Warnung eine Weile Ruhe, auch wenn der Zustand
# schlecht bleibt. Ohne die Sperre wuerde ein abgelaufenes Token alle
# 30 Minuten eine Mail schicken, bis jemand kommt -- aus einer Warnung
# waere ueber Nacht ein Posteingang voll Warnungen geworden, und die
# liest dann niemand mehr.
WACHE_WIEDERHOLUNG_SEK = 12 * 3600.0

# Mit Datum, und das ist kein Schmuck: Gmail buendelt Nachrichten mit
# gleichem Betreff zu einem Gespraechsfaden. Ohne das Datum haette die
# Warnung in einem halben Jahr am Ende eines alten, laengst gelesenen
# Fadens gehangen -- eingeklappt, ungelesen aussehend, uebersehbar.
# Genau bei der Nachricht, die auffallen muss.
def _betreff() -> str:
    return ("Sarvis kann nicht mehr denken "
            f"({datetime.now():%d.%m.%Y %H:%M})")

MELDUNG = (
    "Sarvis laeuft, aber sein Zugang zu Claude gilt nicht mehr. Er nimmt "
    "weiter Zurufe an und kann sie nicht beantworten.\n"
    "\n"
    "So kommt er zurueck -- auf dem Server, im Ordner "
    "/srv/storage/projects/sarvis:\n"
    "\n"
    "1. Ein neues Token holen:\n"
    "\n"
    "       docker compose exec sarvis claude setup-token\n"
    "\n"
    "   Das fragt einmal nach einer Anmeldung im Browser und ZEIGT danach\n"
    "   ein Token an, das mit sk-ant-oat01- beginnt. Gespeichert wird es\n"
    "   nicht -- der Befehl allein reicht also nicht.\n"
    "\n"
    "2. Das Token eintragen, in /srv/data/sarvis/claude.env, als einzige\n"
    "   Zeile ohne Anfuehrungszeichen:\n"
    "\n"
    "       CLAUDE_CODE_OAUTH_TOKEN=sk-ant-oat01-...\n"
    "\n"
    "   Die alte Zeile dabei ersetzen, nicht darunter schreiben.\n"
    "\n"
    "3. Neu starten:\n"
    "\n"
    "       docker compose restart sarvis\n"
    "\n"
    "Danach meldet er beim Start 'Anmeldung : angemeldet'.\n"
)

ENTWARNUNG = ("Sarvis ist wieder angemeldet und denkt. Es ist nichts mehr "
              "zu tun.")

_wecker: asyncio.Event | None = None


def jetzt_nachsehen() -> None:
    """Die Wache aus dem Warten holen.

    Ruft main.py, wenn im Gespraech ein Anmeldefehler geflogen ist. Dann
    steht die Warnung sofort im Postfach statt bis zu einer halben
    Stunde spaeter -- und zwar auch dann, wenn gerade niemand zuhoert,
    der die gesprochene Meldung mitbekommen haette.
    """
    if _wecker is not None:
        _wecker.set()


async def _telegram_hinaus(text: str) -> bool:
    """Ueber den Telegram-Bot melden, falls einer eingerichtet ist.

    Der bevorzugte Weg, denn er klingelt. Nur: Sarvis' Telegram laeuft
    ueber Saschas EIGENEN Account (Telethon, sarvis.session), und der
    kann sich selbst nicht anpiepen -- eine Nachricht an sich selbst
    landet lautlos in den gespeicherten Nachrichten. Dafuer braucht es
    einen Bot, also einen zweiten Absender.

    Der Kanal in netz/telegram_kanal.py bringt einen mit, laeuft hier
    aber nicht. Sobald SARVIS_TG_TOKEN und SARVIS_TG_ERLAUBT gesetzt
    sind, nimmt die Wache ihn von selbst -- bis dahin geht sie den Weg
    darunter.
    """
    token = os.environ.get("SARVIS_TG_TOKEN", "").strip()
    roh = os.environ.get("SARVIS_TG_ERLAUBT", "")
    ziele = [x.strip() for x in roh.split(",") if x.strip()]
    if not token or not ziele:
        return False
    try:
        import aiohttp
        async with aiohttp.ClientSession() as sitzung:
            for chat in ziele:
                await sitzung.post(
                    f"https://api.telegram.org/bot{token}/sendMessage",
                    json={"chat_id": int(chat), "text": text},
                    timeout=aiohttp.ClientTimeout(total=FRIST))
    except Exception:
        return False
    return True


async def _mail_hinaus(betreff: str, text: str) -> bool:
    """Ueber Sarvis' Google-Konto an dieses Konto selbst.

    Die Adresse wird nicht hingeschrieben, sondern erfragt: Wer
    angemeldet ist, ist auch der, den die Warnung angeht. Steht sie im
    Programm, zeigt sie irgendwann ins Leere und niemand merkt es --
    ausgerechnet bei der Nachricht, die man nie testet.
    """
    try:
        from .werkzeuge import google
        an = await google.eigene_adresse()
        if not an:
            return False
        return await google.mail_hinaus(an, betreff, text)
    except Exception:
        return False


async def hinausmelden(betreff: str, text: str) -> str | None:
    """Melden, ueber welchen Weg auch immer. Gibt den Weg zurueck."""
    if await _telegram_hinaus(f"{betreff}\n\n{text}"):
        return "Telegram"
    if await _mail_hinaus(betreff, text):
        return "Mail"
    return None


async def wache(sagen=None) -> None:
    """Nachsehen, ob der Zugang noch gilt -- und anschreiben, wenn nicht.

    Laeuft als eigene Aufgabe neben dem Gespraech und ueberlebt jeden
    Fehler in sich selbst: Eine Wache, die an ihrer eigenen Ausnahme
    stirbt, sieht aus wie eine Wache und ist keine. Deshalb steht der
    ganze Rumpf in einem try.

    Gemeldet wird auf FLANKEN, nicht auf Zustaenden: einmal, wenn der
    Zugang kippt, und einmal, wenn er zurueck ist. Bleibt es schlecht,
    kommt die Erinnerung erst nach WACHE_WIEDERHOLUNG_SEK wieder.

    `sagen` ist der Weg in die Anzeige, falls gerade jemand zuhoert. Er
    ist zusaetzlich, nicht statt: Die Nachricht nach draussen geht
    immer, denn wer zuhoert, hat es schon anders gemerkt.
    """
    global _wecker
    _wecker = asyncio.Event()

    # Beim ersten Durchgang ist noch nichts bekannt. WAHR waere gelogen,
    # FALSCH gaebe bei einem gesunden Start eine Entwarnung fuer eine
    # Warnung, die es nie gab -- also drittes: noch nichts gesehen.
    zuletzt: bool | None = None
    gemeldet_um = 0.0

    while True:
        try:
            angemeldet, wie = await pruefen()

            if not angemeldet:
                faellig = (zuletzt is not False
                           or asyncio.get_running_loop().time() - gemeldet_um
                           > WACHE_WIEDERHOLUNG_SEK)
                if faellig:
                    weg = await hinausmelden(_betreff(), MELDUNG)
                    if weg:
                        gemeldet_um = asyncio.get_running_loop().time()
                        print(f"  ---- Anmeldung weg, Nachricht per {weg} raus")
                    else:
                        # Kein Weg nach draussen. Das ist die Lage, in
                        # der man am wenigsten erfaehrt und am meisten
                        # wissen muesste -- also wenigstens deutlich ins
                        # Protokoll.
                        print("  ---- Anmeldung weg -- und KEIN Weg, es zu "
                              "melden (Telegram-Bot nicht eingerichtet, "
                              "Google nicht angemeldet)")
                        print(f"    -> {RAT}")
                    if sagen is not None:
                        try:
                            await sagen(satz())
                        except Exception:
                            pass

            elif zuletzt is False:
                await hinausmelden(
                    f"Sarvis denkt wieder ({datetime.now():%d.%m.%Y %H:%M})",
                    ENTWARNUNG)
                print(f"  ---- Anmeldung wieder da ({wie})")
                # Die Sperre gehoert zu DIESEM Ausfall. Bleibt sie
                # stehen, koennte der naechste -- ein halbes Jahr
                # spaeter -- an einer Ruhefrist haengen, die fuer den
                # vorigen gedacht war.
                gemeldet_um = 0.0

            # Nur eine ANGEKOMMENE Warnung zaehlt als gemeldet. Sonst
            # haette ein Netzausfall im falschen Moment gereicht, um
            # zwoelf Stunden zu schweigen -- der Zustand galt als
            # gemeldet, obwohl nie etwas hinausging. Bleibt `zuletzt`
            # bei None, versucht es der naechste Durchgang erneut.
            if angemeldet or gemeldet_um:
                zuletzt = angemeldet

        except asyncio.CancelledError:
            raise
        except Exception as e:
            print(f"  ---- Anmeldewache stolperte: {e}")

        # Warten -- oder frueher aufwachen, wenn im Gespraech etwas nach
        # einem Anmeldefehler aussah.
        try:
            await asyncio.wait_for(_wecker.wait(), timeout=WACHE_ABSTAND_SEK)
        except asyncio.TimeoutError:
            pass
        _wecker.clear()
