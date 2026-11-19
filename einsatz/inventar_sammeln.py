#!/usr/bin/env python3
"""Bestandsaufnahme des Servers fuer Sarvis' Sicherheitsabgleich.

WARUM ES DAS GIBT (19.11.2026)

Sarvis laeuft im Container. Sein Bash sieht den Container, nicht den
Server: `dpkg -l` liefert die Debian-Pakete des Images, `python3 -V` das
Python im Image, `docker` und die Host-Dienste gibt es dort gar nicht.
Am 19.11. meldete der Sicherheitsbericht deshalb "openssh-server hast du
nicht" -- auf dem Server laeuft er aber. Ein falsches "nicht betroffen"
ist schlimmer als gar keine Pruefung.

Den Docker-Socket in den Container zu haengen waere die bequeme Loesung
und die falsche: Wer den Socket hat, ist root auf dem Server. Stattdessen
sammelt dieses Skript auf dem Host (Cron als server3070, kein sudo) und
schreibt EINE Datei nach /srv/data/sarvis/inventar/inventar.json. Sarvis
liest nur diese Datei (werkzeuge/system.py). Lesen kann nichts kaputt
machen.

Nur Standardbibliothek -- laeuft mit dem System-Python des Hosts.
"""
import json
import os
import re
import subprocess
import sys
import tomllib
from datetime import datetime, timezone
from pathlib import Path

ZIEL = Path("/srv/data/sarvis/inventar/inventar.json")
# Wo Projekte liegen. node_modules und .venv werden nicht durchwandert --
# was dort steckt, steht in den Lockdateien bzw. kommt ueber site-packages.
PROJEKTWURZELN = [Path("/srv/storage/projects"), Path("/home/server3070/apps"),
                  Path("/home/server3070")]
UEBERSPRINGEN = {"node_modules", ".git", ".cache", ".npm", ".local", "__pycache__",
                 ".venv", "venv", ".gradle", "tools", "snap", ".claude"}
LOCKNAMEN = {"package-lock.json", "requirements.txt", "requirements-dev.txt",
             "pyproject.toml", "uv.lock", "poetry.lock", "package.json"}


def lauf(befehl: list[str], zeit: float = 30) -> str:
    try:
        r = subprocess.run(befehl, capture_output=True, text=True, timeout=zeit)
        return r.stdout if r.returncode == 0 else (r.stdout or "")
    except Exception:
        return ""


def erste_zeile(befehl: list[str]) -> str:
    try:
        r = subprocess.run(befehl, capture_output=True, text=True, timeout=10)
        return ((r.stdout or r.stderr).strip().splitlines() or [""])[0][:200]
    except Exception:
        return ""


# ------------------------------------------------------------------ Host

def host() -> dict:
    os_rel = {}
    for z in Path("/etc/os-release").read_text().splitlines():
        if "=" in z:
            k, v = z.split("=", 1)
            os_rel[k] = v.strip('"')
    versionen = {
        "kernel": os.uname().release,
        "system": os_rel.get("PRETTY_NAME", ""),
    }
    for name, befehl in {
        "python3": ["python3", "-V"], "node": ["node", "-v"],
        "docker": ["docker", "--version"], "caddy": ["caddy", "version"],
        "ollama": ["ollama", "--version"], "openssh": ["ssh", "-V"],
        "openssl": ["openssl", "version"], "git": ["git", "--version"],
        "java": ["java", "-version"], "tailscale": ["tailscale", "version"],
        "crowdsec": ["cscli", "version"],
    }.items():
        z = erste_zeile(befehl)
        if z and "not found" not in z and "No such file" not in z:
            versionen[name] = z
    return versionen


def dpkg_host() -> dict:
    aus = lauf(["dpkg-query", "-W", "-f=${db:Status-Abbrev}\t${Package}\t${Version}\n"])
    pakete = {}
    for z in aus.splitlines():
        teile = z.split("\t")
        if len(teile) == 3 and teile[0].startswith("ii"):
            pakete[teile[1]] = teile[2]
    return pakete


def snaps() -> dict:
    pakete = {}
    for z in lauf(["snap", "list"]).splitlines()[1:]:
        t = z.split()
        if len(t) >= 2:
            pakete[t[0]] = t[1]
    return pakete


def dienste() -> list[str]:
    aus = lauf(["systemctl", "list-units", "--type=service", "--state=running",
                "--no-legend", "--plain"])
    return sorted(z.split()[0] for z in aus.splitlines() if z.strip())


def ports() -> list[str]:
    """Lauschende TCP-Ports. Ohne sudo ohne Prozessnamen -- reicht, um zu
    sehen, was offen ist und ob nur auf 127.0.0.1."""
    aus = lauf(["ss", "-Htln"])
    return sorted({z.split()[3] for z in aus.splitlines() if len(z.split()) > 3})


# ---------------------------------------------------------------- Docker

def docker() -> list[dict]:
    aus = lauf(["docker", "ps", "--format", "{{json .}}"])
    behaelter = []
    for z in aus.splitlines():
        try:
            d = json.loads(z)
        except ValueError:
            continue
        name = d.get("Names", "")
        eintrag = {"name": name, "image": d.get("Image", ""),
                   "status": d.get("Status", ""), "ports": d.get("Ports", "")}
        eintrag.update(im_behaelter(name))
        behaelter.append(eintrag)
    return behaelter


# Ein Skript, das in JEDEM Image laeuft (sh, auch busybox): erst das
# System, dann was an Python- und Node-Paketen drin ist. Abschnitte mit
# Markern, damit die Auswertung nicht raten muss.
IM_BEHAELTER = r"""
echo '###OS'; cat /etc/os-release 2>/dev/null | grep -E '^PRETTY_NAME='
echo '###DPKG'; command -v dpkg-query >/dev/null && dpkg-query -W -f='${Package}\t${Version}\n' 2>/dev/null
echo '###APK'; command -v apk >/dev/null && apk info -v 2>/dev/null
echo '###PY'; for p in python3 python; do command -v $p >/dev/null && { $p -m pip list --format=freeze 2>/dev/null; break; }; done
echo '###NODE'; command -v node >/dev/null && node -v
echo '###NPMG'; command -v npm >/dev/null && npm ls -g --depth=0 --json 2>/dev/null
echo '###BIN'; for b in nginx java postgres redis-server caddy openssl; do command -v $b >/dev/null && echo "$b"; done
"""


def im_behaelter(name: str) -> dict:
    aus = lauf(["docker", "exec", name, "sh", "-c", IM_BEHAELTER], zeit=40)
    teile, aktuell = {}, None
    for z in aus.splitlines():
        if z.startswith("###"):
            aktuell = z[3:]
            teile[aktuell] = []
        elif aktuell:
            teile[aktuell].append(z)
    erg = {"os": "", "pakete": {}, "python": {}, "npm_global": {}, "node": ""}
    for z in teile.get("OS", []):
        erg["os"] = z.split("=", 1)[-1].strip('"')
    for z in teile.get("DPKG", []):
        if "\t" in z:
            p, v = z.split("\t", 1)
            erg["pakete"][p] = v
    for z in teile.get("APK", []):
        # apk info -v: "musl-1.2.4-r2" -> Name bis zur Versionsziffer
        m = re.match(r"^(.+?)-(\d[^-]*-r\d+)$", z.strip())
        if m:
            erg["pakete"][m.group(1)] = m.group(2)
    for z in teile.get("PY", []):
        if "==" in z:
            p, v = z.split("==", 1)
            erg["python"][p.lower()] = v
    erg["node"] = (teile.get("NODE") or [""])[0]
    try:
        npm = json.loads("\n".join(teile.get("NPMG", [])) or "{}")
        for p, info in (npm.get("dependencies") or {}).items():
            erg["npm_global"][p] = info.get("version", "")
    except ValueError:
        pass
    erg["programme"] = teile.get("BIN", [])
    # Versionen der Programme, die in Meldungen oft vorkommen
    for b in erg["programme"]:
        befehl = {"nginx": "nginx -v 2>&1", "java": "java -version 2>&1 | head -1",
                  "postgres": "postgres --version", "openssl": "openssl version",
                  "redis-server": "redis-server --version", "caddy": "caddy version"}.get(b)
        if befehl:
            v = lauf(["docker", "exec", name, "sh", "-c", befehl], zeit=15).strip()
            erg.setdefault("versionen", {})[b] = v.splitlines()[0][:200] if v else ""
    return erg


# ------------------------------------------------------------ Projekte

def dateien() -> list[Path]:
    gefunden, gesehen = [], set()
    for wurzel in PROJEKTWURZELN:
        tiefe_wurzel = len(wurzel.parts)
        for ort, ordner, namen in os.walk(wurzel):
            p = Path(ort)
            # Der Benutzerordner nur flach, die Projektordner haben ihre
            # eigenen Wurzeln oben.
            grenze = 3 if wurzel == Path("/home/server3070") else 6
            if len(p.parts) - tiefe_wurzel >= grenze:
                ordner[:] = []
            ordner[:] = [o for o in ordner if o not in UEBERSPRINGEN
                         and not o.startswith(".")]
            for n in namen:
                if n in LOCKNAMEN:
                    datei = (p / n).resolve()
                    if datei not in gesehen:
                        gesehen.add(datei)
                        gefunden.append(p / n)
    return gefunden


def aus_lockdatei(datei: Path) -> list[tuple[str, str]]:
    """(paket, version) -- Version leer, wenn nur eine Angabe ohne Bindung."""
    n = datei.name
    try:
        text = datei.read_text(errors="replace")
    except OSError:
        return []
    paare = []
    try:
        if n == "package-lock.json":
            d = json.loads(text)
            for schluessel, info in (d.get("packages") or {}).items():
                if schluessel.startswith("node_modules/") or "/node_modules/" in schluessel:
                    paare.append((schluessel.rsplit("node_modules/", 1)[-1],
                                  info.get("version", "")))
            for p, info in (d.get("dependencies") or {}).items():
                paare.append((p, info.get("version", "")))
        elif n == "package.json":
            d = json.loads(text)
            for feld in ("dependencies", "devDependencies"):
                for p, v in (d.get(feld) or {}).items():
                    paare.append((p, f"Angabe {v}"))
        elif n.startswith("requirements"):
            for z in text.splitlines():
                z = z.split("#")[0].strip()
                m = re.match(r"^([A-Za-z0-9_.\-\[\]]+)\s*(.*)$", z)
                if m and not z.startswith("-"):
                    paare.append((m.group(1).split("[")[0].lower(), m.group(2).strip()))
        elif n in ("uv.lock", "poetry.lock"):
            for paket in tomllib.loads(text).get("package", []):
                paare.append((str(paket.get("name", "")).lower(), str(paket.get("version", ""))))
        elif n == "pyproject.toml":
            d = tomllib.loads(text)
            for angabe in (d.get("project", {}).get("dependencies") or []):
                m = re.match(r"^([A-Za-z0-9_.\-]+)(.*)$", angabe)
                if m:
                    paare.append((m.group(1).lower(), f"Angabe {m.group(2).strip()}"))
    except (ValueError, tomllib.TOMLDecodeError):
        return []
    return paare


def projekte() -> list[list[str]]:
    zeilen = []
    for datei in dateien():
        for p, v in aus_lockdatei(datei):
            if p:
                zeilen.append([p, v, str(datei)])
    return zeilen


def site_packages() -> list[list[str]]:
    """Python-Umgebungen auf dem Host (venvs in Projekten)."""
    zeilen = []
    for wurzel in (Path("/srv/storage/projects"), Path("/home/server3070/apps")):
        for sp in wurzel.glob("*/**/site-packages"):
            if "node_modules" in sp.parts:
                continue
            for info in sp.glob("*.dist-info"):
                m = re.match(r"^(.+?)-(\d[^-]*)\.dist-info$", info.name)
                if m:
                    zeilen.append([m.group(1).lower().replace("_", "-"), m.group(2), str(sp)])
    return zeilen


def main() -> int:
    beginn = datetime.now(timezone.utc)
    inventar = {
        "stand": beginn.astimezone().isoformat(timespec="seconds"),
        "host": host(),
        "pakete_host": dpkg_host(),
        "snaps": snaps(),
        "dienste": dienste(),
        "ports": ports(),
        "container": docker(),
        "projekt_pakete": projekte(),
        "python_umgebungen": site_packages(),
        "nicht_abgedeckt": [
            "Saschas Windows-PC und Handy (Browser-Erweiterungen, Programme)",
            "Images, die gerade nicht laufen",
            "FRITZ!Box-Firmware",
        ],
    }
    inventar["dauer_s"] = round((datetime.now(timezone.utc) - beginn).total_seconds(), 1)
    ZIEL.parent.mkdir(parents=True, exist_ok=True)
    tmp = ZIEL.with_suffix(".tmp")
    tmp.write_text(json.dumps(inventar, ensure_ascii=False))
    os.chmod(tmp, 0o600)
    tmp.replace(ZIEL)
    print(f"{inventar['stand']} inventar: {len(inventar['pakete_host'])} Host-Pakete, "
          f"{len(inventar['container'])} Container, {len(inventar['projekt_pakete'])} "
          f"Projektangaben, {inventar['dauer_s']} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
