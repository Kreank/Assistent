"""Web Push -- Sarvis meldet sich, auch wenn die App zu ist.

Bis 11.11.2026 gingen Meldungen nur an Oberflächen, die gerade verbunden
waren (main._melden_sprechen). Ein Timer bei geschlossener App klingelte
ins Leere, ein fertiger Auftrag ebenso. Web Push ist der Weg, den jeder
Browser dafür hat: Die Seite meldet beim Push-Dienst des Browsers (bei
Chrome FCM, bei Firefox Mozilla, bei Safari Apple) ein Abo an und gibt
uns dessen Adresse. Wir schicken eine VERSCHLÜSSELTE Nachricht dorthin,
der Dienst weckt den Service Worker (web/waechter.js), der zeigt sie.

WARUM VON HAND UND OHNE pywebpush

Die beiden Verfahren sind klein und genau beschrieben -- RFC 8291
(Verschlüsselung, aes128gcm) und RFC 8292 (VAPID, ein ES256-JWT). Beides
geht mit `cryptography` und `httpx`, die ohnehin im Image liegen.
pywebpush hätte requests, py-vapid und http-ece mitgebracht, und eine
neue Zeile in requirements.txt baut wegen der Schichtung im Dockerfile
den ganzen CUDA-Teil neu. Geprüft wird gegen eine unabhängige
Implementierung (http_ece) -- siehe einsatz/push_pruefen.py.

WAS DER PUSH-DIENST SIEHT

Wer die Nachricht ausliefert (Google, Mozilla, Apple), sieht Größe und
Zeitpunkt, nicht den Inhalt -- der ist mit dem Schlüssel des Browsers
verschlüsselt. Trotzdem steht im Text nur, was auf einen Sperrbildschirm
gehört: "Timer abgelaufen: Wäsche", nicht der Kontostand.

WOHIN GESCHICKT WERDEN DARF

Ein Abo ist eine Adresse, die ein angemeldetes Gerät uns nennt -- und an
die der Server danach von sich aus POSTet. Ohne Liste wäre das ein Weg,
den Server Anfragen an beliebige Ziele schicken zu lassen (auch an
127.0.0.1). Erlaubt sind deshalb nur https und die Push-Dienste aus
config.PUSH_DIENSTE.
"""
import base64
import json
import logging
import os
import threading
import time
from urllib.parse import urlsplit

from cryptography.hazmat.primitives import hashes, hmac, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .. import config, gespraeche

log = logging.getLogger("sarvis.push")

# Der private VAPID-Schlüssel. Er identifiziert UNS gegenüber den
# Push-Diensten; wer ihn hat, kann sich als Sarvis ausgeben. chmod 600,
# nie im Repository, nie in einer Ausgabe.
SCHLUESSEL_DATEI = config.DATEN / "vapid_privat.pem"

# Wen der Push-Dienst anschreibt, wenn etwas schiefläuft. Pflicht bei
# Apple, empfohlen bei den anderen.
KONTAKT = getattr(config, "PUSH_KONTAKT", "mailto:sarvis@tech-artist.de")

# Wie lange der Dienst eine Nachricht aufhebt, wenn das Gerät gerade
# nicht erreichbar ist. Ein Timer von vor einem Tag ist keine Nachricht
# mehr, sondern Rauschen.
TTL_SEK = 6 * 3600

_sperre = threading.Lock()
_schluessel = None


def _b64(daten: bytes) -> str:
    return base64.urlsafe_b64encode(daten).rstrip(b"=").decode("ascii")


def _unb64(text: str) -> bytes:
    text = str(text or "")
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


# --- Der eigene Schlüssel -------------------------------------------------

def _privat() -> ec.EllipticCurvePrivateKey:
    """Laden -- oder beim ersten Mal anlegen, mit 0600 von Anfang an.

    Erst anlegen und danach chmod hiesse: Für einen Augenblick liegt der
    Schlüssel lesbar da. os.open mit Modus schließt diese Lücke.
    """
    global _schluessel
    with _sperre:
        if _schluessel is not None:
            return _schluessel
        if SCHLUESSEL_DATEI.is_file():
            _schluessel = serialization.load_pem_private_key(
                SCHLUESSEL_DATEI.read_bytes(), password=None)
            return _schluessel
        neu = ec.generate_private_key(ec.SECP256R1())
        pem = neu.private_bytes(serialization.Encoding.PEM,
                                serialization.PrivateFormat.PKCS8,
                                serialization.NoEncryption())
        SCHLUESSEL_DATEI.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(str(SCHLUESSEL_DATEI),
                     os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(pem)
        _schluessel = neu
        log.info("VAPID-Schlüssel angelegt: %s", SCHLUESSEL_DATEI)
        return _schluessel


def oeffentlich() -> str:
    """Der öffentliche Schlüssel, wie ihn PushManager.subscribe will.

    65 Bytes, unkomprimierter Punkt, base64url ohne Auffüllung.
    """
    punkt = _privat().public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    return _b64(punkt)


def _vapid(endpunkt: str) -> str:
    """Der Authorization-Kopf nach RFC 8292: ein ES256-JWT plus Schlüssel."""
    teile = urlsplit(endpunkt)
    kopf = {"typ": "JWT", "alg": "ES256"}
    inhalt = {"aud": f"{teile.scheme}://{teile.netloc}",
              "exp": int(time.time()) + 12 * 3600, "sub": KONTAKT}
    roh = (_b64(json.dumps(kopf, separators=(",", ":")).encode()) + "."
           + _b64(json.dumps(inhalt, separators=(",", ":")).encode()))
    der = _privat().sign(roh.encode("ascii"), ec.ECDSA(hashes.SHA256()))
    r, s = decode_dss_signature(der)
    signatur = r.to_bytes(32, "big") + s.to_bytes(32, "big")
    return f"vapid t={roh}.{_b64(signatur)}, k={oeffentlich()}"


# --- Verschlüsseln (RFC 8291, aes128gcm) ----------------------------------

def _hmac(schluessel: bytes, daten: bytes) -> bytes:
    h = hmac.HMAC(schluessel, hashes.SHA256())
    h.update(daten)
    return h.finalize()


def verschluesseln(klartext: bytes, p256dh: str, auth: str,
                   salz: bytes | None = None,
                   wegwerf: ec.EllipticCurvePrivateKey | None = None) -> bytes:
    """Der Rumpf einer Push-Nachricht, fertig zum Senden.

    salz und wegwerf nur für die Prüfung von außen -- im Betrieb sind
    beide jedes Mal neu und zufällig.
    """
    ua_oeffentlich = _unb64(p256dh)
    auth_geheim = _unb64(auth)
    if len(ua_oeffentlich) != 65 or len(auth_geheim) < 16:
        raise ValueError("Abo-Schlüssel haben die falsche Länge")
    ua = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(),
                                                     ua_oeffentlich)
    wegwerf = wegwerf or ec.generate_private_key(ec.SECP256R1())
    as_oeffentlich = wegwerf.public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    geteilt = wegwerf.exchange(ec.ECDH(), ua)

    # IKM = HKDF(auth, ecdh, "WebPush: info\0" || ua || as, 32)
    prk_key = _hmac(auth_geheim, geteilt)
    ikm = _hmac(prk_key, b"WebPush: info\x00" + ua_oeffentlich
                + as_oeffentlich + b"\x01")
    salz = salz or os.urandom(16)
    prk = _hmac(salz, ikm)
    cek = _hmac(prk, b"Content-Encoding: aes128gcm\x00\x01")[:16]
    nonce = _hmac(prk, b"Content-Encoding: nonce\x00\x01")[:12]

    # Ein einziger Datensatz: Klartext, dann 0x02 als "letzter Satz".
    chiffre = AESGCM(cek).encrypt(nonce, klartext + b"\x02", None)
    satzgroesse = 4096
    kopf = (salz + satzgroesse.to_bytes(4, "big")
            + bytes([len(as_oeffentlich)]) + as_oeffentlich)
    return kopf + chiffre


# --- Abos -----------------------------------------------------------------

_TABELLE = """
CREATE TABLE IF NOT EXISTS push_abos (
    endpunkt    TEXT PRIMARY KEY,
    p256dh      TEXT NOT NULL,
    auth        TEXT NOT NULL,
    geraet      TEXT NOT NULL,
    angelegt    REAL NOT NULL,
    zuletzt_ok  REAL NOT NULL DEFAULT 0,
    fehler      INTEGER NOT NULL DEFAULT 0
);
"""


def _db():
    gespraeche._sicher_offen()
    v = gespraeche._verbindung()
    v.executescript(_TABELLE)
    return v


def erlaubt(endpunkt: str) -> bool:
    """Nur https, nur bekannte Push-Dienste. Siehe Modulkopf."""
    try:
        teile = urlsplit(str(endpunkt or ""))
    except ValueError:
        return False
    if teile.scheme != "https" or not teile.hostname or teile.port not in (None, 443):
        return False
    host = teile.hostname.lower()
    return any(host == d or host.endswith("." + d) for d in config.PUSH_DIENSTE)


def abo_speichern(abo: dict, geraet: str) -> str:
    """Ein Abo annehmen. Gibt "" zurück oder den Grund der Ablehnung."""
    endpunkt = str((abo or {}).get("endpoint") or "")
    schl = (abo or {}).get("keys") or {}
    p256dh, auth = str(schl.get("p256dh") or ""), str(schl.get("auth") or "")
    if not erlaubt(endpunkt):
        return "dieser Push-Dienst ist nicht erlaubt"
    try:
        if len(_unb64(p256dh)) != 65 or len(_unb64(auth)) < 16:
            return "Schlüssel des Abos unbrauchbar"
    except Exception:
        return "Schlüssel des Abos unbrauchbar"
    with gespraeche._sperre, _db() as v:
        v.execute("INSERT INTO push_abos (endpunkt, p256dh, auth, geraet,"
                  " angelegt) VALUES (?, ?, ?, ?, ?) ON CONFLICT(endpunkt)"
                  " DO UPDATE SET p256dh = excluded.p256dh, auth = excluded.auth,"
                  " geraet = excluded.geraet, fehler = 0",
                  (endpunkt, p256dh, auth, geraet, time.time()))
    return ""


def abo_loeschen(endpunkt: str, geraet: str | None = None) -> int:
    with gespraeche._sperre, _db() as v:
        if geraet is None:
            return v.execute("DELETE FROM push_abos WHERE endpunkt = ?",
                             (endpunkt,)).rowcount
        return v.execute("DELETE FROM push_abos WHERE endpunkt = ? AND geraet = ?",
                         (endpunkt, geraet)).rowcount


def abos(geraet: str | None = None) -> list[dict]:
    with gespraeche._sperre, _db() as v:
        if geraet is None:
            zeilen = v.execute("SELECT * FROM push_abos").fetchall()
        else:
            zeilen = v.execute("SELECT * FROM push_abos WHERE geraet = ?",
                               (geraet,)).fetchall()
    return [dict(z) for z in zeilen]


# --- Senden ---------------------------------------------------------------

def senden_an(abo: dict, nachricht: dict, ttl: int = TTL_SEK,
              dringend: str = "high") -> int:
    """Eine Nachricht an EIN Abo. Gibt den HTTP-Status zurück (0 = Netz)."""
    import httpx
    rumpf = verschluesseln(json.dumps(nachricht, ensure_ascii=False).encode(),
                           abo["p256dh"], abo["auth"])
    try:
        antwort = httpx.post(abo["endpunkt"], content=rumpf, timeout=15.0,
                             headers={"Authorization": _vapid(abo["endpunkt"]),
                                      "Content-Encoding": "aes128gcm",
                                      "Content-Type": "application/octet-stream",
                                      "TTL": str(int(ttl)), "Urgency": dringend})
    except Exception as e:
        log.warning("Push an %s: %s", abo.get("geraet"), type(e).__name__)
        return 0
    if antwort.status_code >= 300:
        # Den Text nicht ausgeben -- er kann die Abo-Adresse enthalten.
        log.warning("Push an %s: HTTP %d", abo.get("geraet"), antwort.status_code)
    return antwort.status_code


def _gueltige_geraete() -> set[str]:
    from . import geraete
    return {str(g.get("name") or "") for g in geraete.liste()}


def alle_senden(nachricht: dict, nur_geraet: str | None = None) -> dict:
    """An alle Abos, deren Gerät noch einen gültigen Schlüssel hat.

    Ein widerrufenes Gerät bekommt nichts mehr -- auch wenn sein Abo noch
    in der Tabelle steht. Es wird dabei gleich mit entfernt. Dasselbe gilt
    für Abos, die der Dienst mit 404/410 als erloschen meldet.
    """
    gueltig = _gueltige_geraete()
    ergebnis = {"gesendet": 0, "fehler": 0, "entfernt": 0}
    for abo in abos(nur_geraet):
        if abo["geraet"] not in gueltig:
            abo_loeschen(abo["endpunkt"])
            ergebnis["entfernt"] += 1
            continue
        status = senden_an(abo, nachricht)
        with gespraeche._sperre, _db() as v:
            if 200 <= status < 300:
                ergebnis["gesendet"] += 1
                v.execute("UPDATE push_abos SET zuletzt_ok = ?, fehler = 0"
                          " WHERE endpunkt = ?", (time.time(), abo["endpunkt"]))
            elif status in (404, 410):
                v.execute("DELETE FROM push_abos WHERE endpunkt = ?",
                          (abo["endpunkt"],))
                ergebnis["entfernt"] += 1
            else:
                ergebnis["fehler"] += 1
                v.execute("UPDATE push_abos SET fehler = fehler + 1"
                          " WHERE endpunkt = ?", (abo["endpunkt"],))
    return ergebnis


def benachrichtigen(titel: str, text: str, art: str = "meldung") -> None:
    """Von überall aufrufbar, kehrt sofort zurück. Versand im eigenen Faden.

    Die Netzanfragen gehen an Google, Mozilla oder Apple -- jede kann
    Sekunden dauern. Das gehört nicht in die Ereignisschleife, die
    gleichzeitig ein Gespräch trägt.
    """
    nachricht = {"titel": str(titel or "Sarvis")[:120],
                 "text": str(text or "")[:400], "art": str(art or "meldung"),
                 "zeit": time.time()}

    def los():
        try:
            if not abos():
                return
            e = alle_senden(nachricht)
            log.info("Push %s: %s", art, e)
        except Exception as e:
            log.warning("Push %s ging nicht: %s", art, e)

    threading.Thread(target=los, name="push", daemon=True).start()
