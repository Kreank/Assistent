#!/usr/bin/env python3
"""Prueft den Web-Push-Versand (sarvis/netz/push.py) von aussen.

push.py verschluesselt und signiert von Hand (RFC 8291 / RFC 8292). Ob
das stimmt, laesst sich nicht an push.py selbst ablesen -- eine eigene
Entschluesselung daneben haette denselben Denkfehler zweimal. Deshalb:

  1. ein Schluesselpaar wie im Browser anlegen (P-256 + 16 Byte auth),
  2. einen Empfaenger auf 127.0.0.1 starten, der spielt den Push-Dienst,
  3. mit push.senden_an() WIRKLICH per HTTP dorthin schicken,
  4. den Rumpf mit http_ece entschluesseln -- einer unabhaengigen
     Implementierung (dieselbe, die pywebpush benutzt),
  5. das VAPID-JWT gegen den oeffentlichen Schluessel pruefen.

http_ece liegt NICHT im Image (siehe push.py, warum). Aufruf daher z. B.:

    pip install --target /tmp/pp http_ece
    SARVIS_DATEN=/tmp/pp-daten PYTHONPATH=/tmp/pp:. python einsatz/push_pruefen.py

SARVIS_DATEN auf einen Wegwerf-Ordner: Sonst legt die Pruefung den
VAPID-Schluessel im echten Datenordner an (oder benutzt ihn).
"""
import base64
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cryptography.hazmat.primitives import hashes, serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import ec  # noqa: E402
from cryptography.hazmat.primitives.asymmetric.utils import (  # noqa: E402
    encode_dss_signature)


def b64(d: bytes) -> str:
    return base64.urlsafe_b64encode(d).rstrip(b"=").decode()


def unb64(t: str) -> bytes:
    return base64.urlsafe_b64decode(t + "=" * (-len(t) % 4))


def main() -> int:
    try:
        import http_ece
    except ImportError:
        print("http_ece fehlt -- siehe Kopf dieser Datei.")
        return 2
    from sarvis.netz import push

    # 1. Der "Browser"
    ua = ec.generate_private_key(ec.SECP256R1())
    ua_pub = ua.public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    auth = b"0123456789abcdef"

    # 2. Der "Push-Dienst"
    bekommen = {}

    class Empfaenger(BaseHTTPRequestHandler):
        def do_POST(self):
            n = int(self.headers.get("Content-Length") or 0)
            bekommen["rumpf"] = self.rfile.read(n)
            bekommen["koepfe"] = dict(self.headers)
            self.send_response(201)
            self.end_headers()

        def log_message(self, *a):
            pass

    dienst = HTTPServer(("127.0.0.1", 0), Empfaenger)
    threading.Thread(target=dienst.handle_request, daemon=True).start()
    endpunkt = f"http://127.0.0.1:{dienst.server_port}/push/abc"

    # 3. Wirklich senden
    nachricht = {"titel": "Timer abgelaufen", "text": "Wäsche aufhängen ✓",
                 "art": "wecker"}
    status = push.senden_an({"endpunkt": endpunkt, "p256dh": b64(ua_pub),
                             "auth": b64(auth), "geraet": "pruefung"},
                            nachricht)
    fehler = []
    if status != 201:
        fehler.append(f"Status {status} statt 201")
    k = {a.lower(): b for a, b in bekommen.get("koepfe", {}).items()}
    if k.get("content-encoding") != "aes128gcm":
        fehler.append("Content-Encoding fehlt/falsch")
    if not k.get("ttl"):
        fehler.append("TTL fehlt")

    # 4. Unabhaengig entschluesseln
    try:
        klar = http_ece.decrypt(bekommen["rumpf"], private_key=ua,
                                auth_secret=auth, version="aes128gcm")
        zurueck = json.loads(klar.decode("utf-8"))
        if zurueck.get("text") != nachricht["text"]:
            fehler.append(f"Inhalt weicht ab: {zurueck!r}")
        else:
            print(f"entschlüsselt (http_ece): {zurueck}")
    except Exception as e:
        fehler.append(f"Entschluesseln: {type(e).__name__}: {e}")

    # 5. VAPID pruefen
    try:
        kopf = k["authorization"]
        assert kopf.startswith("vapid t="), kopf[:12]
        t, k_teil = kopf[len("vapid t="):].split(", k=")
        if k_teil != push.oeffentlich():
            fehler.append("k= ist nicht unser oeffentlicher Schluessel")
        h, c, s = t.split(".")
        anspruch = json.loads(unb64(c))
        if anspruch.get("aud") != f"http://127.0.0.1:{dienst.server_port}":
            fehler.append(f"aud falsch: {anspruch.get('aud')}")
        sig = unb64(s)
        oeff = ec.EllipticCurvePublicKey.from_encoded_point(
            ec.SECP256R1(), unb64(k_teil))
        oeff.verify(encode_dss_signature(int.from_bytes(sig[:32], "big"),
                                         int.from_bytes(sig[32:], "big")),
                    f"{h}.{c}".encode(), ec.ECDSA(hashes.SHA256()))
        print(f"VAPID-Signatur gültig, aud={anspruch['aud']}, sub={anspruch['sub']}")
    except Exception as e:
        fehler.append(f"VAPID: {type(e).__name__}: {e}")

    # Die Erlaubnisliste
    for adresse, soll in (("https://fcm.googleapis.com/fcm/send/x", True),
                          ("https://web.push.apple.com/abc", True),
                          ("http://fcm.googleapis.com/x", False),
                          ("https://127.0.0.1/x", False),
                          ("https://fcm.googleapis.com.boese.de/x", False),
                          ("https://fcm.googleapis.com:8443/x", False)):
        if push.erlaubt(adresse) != soll:
            fehler.append(f"erlaubt({adresse}) sollte {soll} sein")

    if fehler:
        print("FEHLER:\n  " + "\n  ".join(fehler))
        return 1
    print("Web Push: Verschlüsselung, VAPID und Erlaubnisliste stimmen.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
