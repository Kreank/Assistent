"""Was auf Saschas Server wirklich installiert ist -- fuer den Sicherheitsabgleich.

WARUM NICHT EINFACH BASH (19.11.2026)

Sarvis' Bash laeuft im Container. `dpkg -l`, `python3 -V`, `pip list`
zeigen dort das Image, nicht den Server; `docker` und die Host-Dienste
gibt es gar nicht. Der Sicherheitsbericht vom 19.11. hat daraus
"openssh-server hast du nicht" gemacht -- auf dem Server laeuft er.

Die Wahrheit sammelt einsatz/inventar_sammeln.py auf dem HOST (Cron,
ohne sudo) in /srv/data/sarvis/inventar/inventar.json: Systempakete,
Programmversionen, laufende Dienste, offene Ports, jeder laufende
Container mit seinen System-, Python- und npm-Paketen, alle Lockdateien
der Projekte und die Python-Umgebungen. Dieses Werkzeug liest nur die
Datei. Den Docker-Socket in den Container zu haengen waere root auf dem
Server gewesen.
"""
import json
from datetime import datetime
from pathlib import Path

from claude_agent_sdk import tool

INVENTAR = Path("/srv/data/sarvis/inventar/inventar.json")
ALT_STUNDEN = 26          # Sammler laeuft alle 6 h; darueber stimmt was nicht
JE_BEGRIFF = 30           # Treffer je Begriff, mehr hoert und liest keiner


def _laden():
    try:
        return json.loads(INVENTAR.read_text())
    except (OSError, ValueError):
        return None


def _alter_stunden(inv) -> float:
    try:
        stand = datetime.fromisoformat(inv["stand"])
        return (datetime.now(stand.tzinfo) - stand).total_seconds() / 3600
    except (KeyError, ValueError, TypeError):
        return 999.0


def _passt(begriff: str, name: str, genau: bool) -> bool:
    n = name.lower()
    return n == begriff if genau else begriff in n


def suchen(inv: dict, begriff: str, genau: bool = False) -> list[str]:
    b = begriff.strip().lower()
    if not b:
        return []
    treffer = []
    for name, v in (inv.get("host") or {}).items():
        if _passt(b, name, genau) or (not genau and b in v.lower()):
            treffer.append(f"Server-Programm {name}: {v}")
    for p, v in (inv.get("pakete_host") or {}).items():
        if _passt(b, p, genau):
            treffer.append(f"Server-Systempaket {p} {v}")
    for p, v in (inv.get("snaps") or {}).items():
        if _passt(b, p, genau):
            treffer.append(f"Server-Snap {p} {v}")
    for d in inv.get("dienste") or []:
        if _passt(b, d.removesuffix(".service"), genau):
            treffer.append(f"Server-Dienst läuft: {d}")
    for c in inv.get("container") or []:
        name = c.get("name", "")
        if _passt(b, c.get("image", ""), genau) or (not genau and b in c.get("image", "").lower()):
            treffer.append(f"Container {name}: Image {c.get('image')}")
        for p, v in (c.get("pakete") or {}).items():
            if _passt(b, p, genau):
                treffer.append(f"Container {name} ({c.get('os')}): Systempaket {p} {v}")
        for p, v in (c.get("python") or {}).items():
            if _passt(b, p, genau):
                treffer.append(f"Container {name}: Python-Paket {p} {v}")
        for p, v in (c.get("npm_global") or {}).items():
            if _passt(b, p, genau):
                treffer.append(f"Container {name}: npm global {p} {v}")
        for p, v in (c.get("versionen") or {}).items():
            if _passt(b, p, genau):
                treffer.append(f"Container {name}: {v}")
        if b == "node" and c.get("node"):
            treffer.append(f"Container {name}: node {c['node']}")
    for p, v, datei in inv.get("projekt_pakete") or []:
        if _passt(b, p, genau):
            treffer.append(f"Projekt {datei}: {p} {v}".rstrip())
    for p, v, ort in inv.get("python_umgebungen") or []:
        if _passt(b, p, genau):
            treffer.append(f"Python-Umgebung {ort}: {p} {v}")
    # Doppelte (dasselbe Paket in package-lock UND package.json) zusammen
    return list(dict.fromkeys(treffer))


def ueberblick(inv: dict) -> str:
    h = inv.get("host") or {}
    zeilen = [f"{k}: {v}" for k, v in h.items()]
    zeilen.append(f"{len(inv.get('pakete_host') or {})} Systempakete auf dem Server, "
                  f"{len(inv.get('dienste') or [])} laufende Dienste")
    zeilen.append("Offene Ports: " + ", ".join(inv.get("ports") or []))
    zeilen.append("Container: " + "; ".join(
        f"{c['name']} ({c.get('image')}, {c.get('os') or '?'})"
        for c in inv.get("container") or []))
    zeilen.append(f"{len(inv.get('projekt_pakete') or [])} Paketangaben aus Projekt-Lockdateien")
    return "\n".join(zeilen)


def werkzeuge(protokoll=None, leuchten=None) -> list:

    @tool(
        "system_pruefen",
        "Prüft, ob Software auf Saschas SERVER installiert ist oder läuft — "
        "Systempakete, Programmversionen, Dienste, offene Ports, jeder "
        "laufende Docker-Container samt seiner System-, Python- und "
        "npm-Pakete, alle Projekt-Lockdateien und Python-Umgebungen. "
        "Benutze das für JEDE Frage 'betrifft mich das / habe ich das' "
        "und für den Abgleich im Sicherheitsbericht — NICHT Bash: Dein "
        "Bash läuft im eigenen Container und sieht nicht den Server "
        "(dpkg, pip, python3 -V, systemctl zeigen dort das Image; docker "
        "fehlt ganz). Ohne Begriffe kommt ein Überblick (Versionen, "
        "Container, Ports). Mehrere Begriffe auf einmal geben. Die "
        "Treffer nennen die Version — ob die verwundbar ist, entscheidest "
        "du anhand der Meldung. Saschas Windows-PC und Handy deckt das "
        "nicht ab.",
        {
            "type": "object",
            "properties": {
                "begriffe": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Paket- oder Programmnamen, z. B. "
                                   "['openssh', 'agent-framework', 'nginx']. "
                                   "Teilwörter genügen.",
                },
                "genau": {
                    "type": "boolean",
                    "description": "Nur exakte Paketnamen (für kurze, "
                                   "mehrdeutige Namen wie 'ws' oder 'ip').",
                },
            },
        },
    )
    async def system_pruefen(args):
        if leuchten:
            leuchten("System")
        inv = _laden()
        if inv is None:
            return {"content": [{"type": "text", "text":
                    "Die Bestandsaufnahme des Servers fehlt "
                    f"({INVENTAR}). Prüfung nicht möglich — so sagen, "
                    "nicht raten."}], "is_error": True}
        alter = _alter_stunden(inv)
        kopf = f"Bestandsaufnahme vom {inv.get('stand', '?')}"
        if alter > ALT_STUNDEN:
            kopf += (f" — ACHTUNG, {alter:.0f} Stunden alt, der Sammler "
                     "läuft offenbar nicht. Das im Bericht erwähnen.")
        begriffe = [b for b in (args.get("begriffe") or []) if str(b).strip()]
        if not begriffe:
            return {"content": [{"type": "text", "text":
                    kopf + "\n\n" + ueberblick(inv)}]}
        teile = [kopf]
        for b in begriffe[:25]:
            t = suchen(inv, str(b), bool(args.get("genau")))
            if not t:
                teile.append(f"\n«{b}»: nirgends gefunden (Server, Container, Projekte).")
            else:
                mehr = f" (+{len(t) - JE_BEGRIFF} weitere)" if len(t) > JE_BEGRIFF else ""
                teile.append(f"\n«{b}»: {len(t)} Treffer{mehr}\n- "
                             + "\n- ".join(t[:JE_BEGRIFF]))
        teile.append("\nNicht abgedeckt: " + "; ".join(inv.get("nicht_abgedeckt") or []))
        return {"content": [{"type": "text", "text": "\n".join(teile)}]}

    return [system_pruefen]
