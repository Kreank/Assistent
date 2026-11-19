"""Google-Maps-Links in Terminen (seit 16.11.2026).

Sascha gibt Sarvis fuer einen Termin gern einfach den Maps-Link aus dem
Teilen-Menue ("https://maps.app.goo.gl/..."). Steht der roh im Ort-Feld,
kann der Google-Kalender damit nichts anfangen: Tippen sucht in Maps nach
dem Link-TEXT, statt den Ort zu oeffnen.

Darum: Link aufloesen (der Kurzlink leitet auf .../maps/place/<Name, Adresse>/
um), die Adresse ins Ort-Feld, den Link selbst in die Notiz. Dann oeffnet
ein Tippen auf den Ort Maps -- im Google-Kalender und in der Sarvis-App
(Feld `karte`, siehe einsatz/DRAHT.md "Kalender").

Geht das Aufloesen schief (kein Netz, Google aendert die Form), bleibt
der Link einfach im Ort-Feld stehen -- wie vorher, nichts geht verloren.
"""
import logging
import re
from urllib.parse import quote, unquote_plus, urlparse

import aiohttp
from yarl import URL

log = logging.getLogger(__name__)

_LINK = re.compile(
    r"https?://(?:maps\.app\.goo\.gl|goo\.gl/maps|(?:www\.)?google\.[a-z.]+/maps"
    r"|maps\.google\.[a-z.]+)[^\s<>\"']*", re.I)


def maps_link(text: str) -> str:
    """Der erste Google-Maps-Link im Text, sonst ''."""
    m = _LINK.search(text or "")
    return m.group(0).rstrip(".,;:!?)") if m else ""


def _ort_aus_url(url: str) -> str:
    """'.../maps/place/Randori+Pro,+Alt-Mariendorf+19/...' -> Klartext."""
    teile = urlparse(url).path.split("/")
    for i, t in enumerate(teile[:-1]):
        if t in ("place", "search") and teile[i + 1]:
            ort = unquote_plus(teile[i + 1]).strip()
            # Reine Koordinaten ("52.4,13.3") sind keine lesbare Adresse.
            if ort and not re.fullmatch(r"[-\d.,\s+]+", ort):
                return ort
    return ""


async def aufloesen(url: str) -> str:
    """Kurzlink verfolgen und die Adresse herauslesen; '' wenn nicht."""
    ort = _ort_aus_url(url)
    if ort:
        return ort
    # Schritt fuer Schritt statt allow_redirects: am Ende der Kette steht
    # (vom Server aus, EU) Googles Cookie-Zustimmungsseite -- die Adresse
    # steckt im Sprung davor (gemessen 16.11.2026).
    try:
        zeit = aiohttp.ClientTimeout(total=6)
        async with aiohttp.ClientSession(timeout=zeit) as s:
            for _ in range(5):
                async with s.get(url, allow_redirects=False,
                                 headers={"User-Agent": "Mozilla/5.0"}) as r:
                    weiter = r.headers.get("Location")
                if not weiter:
                    return ""
                url = str(r.url.join(URL(weiter)))
                ort = _ort_aus_url(url)
                if ort:
                    return ort
            return ""
    except Exception as fehler:  # Netz, Zeit, Google -- dann eben roh
        log.info("karte: %s nicht aufgeloest (%s)", url, fehler)
        return ""


async def ort_und_notiz(ort: str, notiz: str) -> tuple[str, str]:
    """Steht im Ort ein Maps-Link: (Adresse, Notiz + Link). Sonst unveraendert."""
    link = maps_link(ort)
    if not link:
        return ort, notiz
    adresse = await aufloesen(link)
    if not adresse:
        return ort, notiz
    rest = ort.replace(link, "").strip(" ,;-–—\n")
    neuer_ort = f"{rest}, {adresse}" if rest else adresse
    if link not in (notiz or ""):
        notiz = f"{notiz.rstrip()}\n\nKarte: {link}" if notiz else f"Karte: {link}"
    return neuer_ort, notiz


def karte_fuer(ort: str, notiz: str) -> str:
    """Wohin ein Tippen auf den Ort fuehren soll ('' ohne Ort)."""
    link = maps_link(ort) or maps_link(notiz)
    if link:
        return link
    ort = (ort or "").strip()
    if not ort:
        return ""
    if re.match(r"https?://", ort):  # irgendein anderer Link: nicht raten
        return ""
    return "https://www.google.com/maps/search/?api=1&query=" + quote(ort)
