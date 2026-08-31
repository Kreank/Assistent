# Sarvis als Container

Was `Dockerfile`, `docker-compose.yml` und `.dockerignore` tun, warum sie
es so tun, und was am 30.08.2026 wirklich gelaufen ist statt nur
behauptet zu werden.

    docker compose build                    bauen
    docker compose up -d                    starten
    docker compose logs -f                  zusehen
    docker compose run --rm sarvis bash     hineinschauen, ohne den
                                            Dienst anzufassen

## Die kurze Fassung

| | |
|---|---|
| Basis | `python:3.12-slim` (Debian 13 Trixie) |
| Netz | `network_mode: host`, der Dienst lauscht auf `127.0.0.1:8900` |
| Benutzer | `sarvis`, uid/gid 1000 — dieselbe wie Sascha auf dem Host |
| Arbeitsverzeichnis | `/srv/storage/projects/sarvis`, gleicher Pfad wie auf dem Host |
| Grafikkarte | `deploy.resources.reservations.devices`, wie beim Transkript-Dienst |
| Image | 6,18 GB auf der Platte, 2,07 GB Inhalt — davon 2,2 GB CUDA |

## Warum Host-Netz und keine Port-Abbildung

`netz/server.py` bindet fest auf `127.0.0.1:8900`, mit guter Begründung:
Nach außen soll ausschließlich Caddy führen. Im Brücken-Netz wäre das
aber die Loopback-Adresse **des Containers**. Eine Abbildung
`127.0.0.1:8900:8900` liefe ins Leere — abgebildet wird nur, was auf
`0.0.0.0` lauscht. Der Dienst wäre gestartet und trotzdem nicht
erreichbar, und zwar ohne Fehlermeldung auf beiden Seiten.

Mit `network_mode: host` ist das `127.0.0.1` des Containers das des
Servers. Damit gilt genau das, was gefordert war — 8900 nur auf
Loopback, davor Caddy — und `server.py` bleibt unangetastet.

Sollte `server.py` später eine Bindeadresse aus der Umgebung lesen, kann
man auf Brücken-Netz plus `ports: ["127.0.0.1:8900:8900"]` zurück; dann
muss aber `extra_hosts: host.docker.internal:host-gateway` dazu, damit
Ollama erreichbar bleibt.

## Warum überall dieselben Pfade wie auf dem Host

Der Quelltext liegt im Container unter `/srv/storage/projects/sarvis`,
der Benutzerordner unter `/home/server3070`, die Daten unter
`/srv/data/sarvis` — jeweils identisch zum Host. Das ist keine Bequem-
lichkeit, sondern Bedingung:

1. `schutz.py` vergleicht Pfade gegen die Freilisten aus `orte.py`, und
   dort steht `/srv/storage/projects`. Läge der Quelltext unter `/app`,
   wäre Sarvis' eigenes Projekt nicht mehr im Entwicklungsbereich — er
   müsste für jede Zeile an sich selbst nachfragen.
2. `orte.VERLAUF_ORDNER` rechnet den Ordnernamen der Sitzungsdateien aus
   `WURZEL` (`_verlauf_slug`). Ein anderer Pfad heißt anderer Slug, und
   `verlauf_nachschlagen` fiele **still** aus: Die Antwort wäre „Ich
   finde keinen gespeicherten Verlauf", kein Fehler.

Das Image enthält zusätzlich eine Kopie des Quelltextes am selben Ort,
damit es auch ohne Mount lauffähig ist. Im Betrieb legt das
bind-gemountete Verzeichnis sich darüber — eine Änderung an
`sarvis/*.py` wirkt also nach einem Neustart des Containers, ohne
Neubau.

## Die Anmeldung der Claude-Code-CLI

`claude_agent_sdk` redet nicht selbst mit der API, es startet die CLI
`claude` als Unterprozess. Node 24.20.0 liegt unter `/opt/node`, die CLI
kommt per `npm install -g @anthropic-ai/claude-code`.

Angemeldet wird **von außen und einmalig**, mit einem langlebigen Token —
und zwar in drei Schritten, nicht zwei:

    docker compose exec sarvis claude setup-token

Das fragt nach einer Anmeldung im Browser und **zeigt** danach ein Token
an (`sk-ant-oat01-…`). Gespeichert wird es nicht. Wer hier aufhört,
startet neu und steht vor derselben Meldung — am 31.08.2026 genau so
passiert. Also eintragen, als einzige Zeile in
`/srv/data/sarvis/claude.env`:

    CLAUDE_CODE_OAUTH_TOKEN=sk-ant-oat01-…

Die Datei hängt über `env_file` am Container, liegt bewusst außerhalb des
Repositories und hat `chmod 600`. Dann:

    docker compose restart sarvis

Sarvis' ganzes `HOME` ist `/srv/data/sarvis/home`, liegt also auf der
Datenplatte und nicht im Container. Das überlebt jeden Neubau — die
Anmeldung ebenso wie `.claude.json`.

Bewusst **nicht** `/home/server3070/.claude`: Das ist Saschas eigene
Anmeldung samt Sitzungsverlauf. Sarvis bekommt seine eigene.

Zwei Fallen, beide am 31.08.2026 eingetreten und behoben:

**Die Anmeldung nicht teilen.** Erst war sie kopiert, dann als einzelne
Datei aus Saschas Ordner gemountet. Beides hält nicht. Ein
Refresh-Token gilt für genau eine Einlösung, und ein Bind-Mount hängt am
Inode: Die CLI erneuert, indem sie die Datei *ersetzt* — danach zeigt
der Host auf die neue und der Container weiter auf die alte, ohne dass
einer der beiden es merkt. Gemessen: Host-Inode 1320965 (509 Bytes),
Container-Inode 1320968 (281 Bytes) mit leerem `accessToken` und leerem
`refreshToken`. Sarvis hatte sich beim Erneuern selbst ausgesperrt.
Einzelne Dateien also nie mounten, wenn sie jemand ersetzen könnte.

**`.claude.json` gehört auf die Datenplatte.** Sie stand vorher in
`/home/sarvis`, wo nur der Unterordner `.claude` herausgemountet war.
Ein `up --force-recreate` nahm sie ersatzlos mit — samt dem Vermerk,
dass `/srv/storage/projects/sarvis` ein vertrauter Ordner ist. Das
äußert sich nicht als Fehler, sondern als Schweigen: Die CLI wartet auf
eine Rückfrage, die im Dienst niemand beantwortet.

### Die Anmeldewache

`anmeldung.wache()` läuft als Hintergrundaufgabe neben dem Gespräch,
sieht alle 30 Minuten nach und schickt eine Mail, sobald der Zugang
kippt — noch einmal, wenn er zurück ist. Fliegt im Gespräch ein
Anmeldefehler, weckt `main.py` sie sofort (`jetzt_nachsehen()`).

Der Weg nach draußen ist ein Telegram-Bot, falls `SARVIS_TG_TOKEN` und
`SARVIS_TG_ERLAUBT` gesetzt sind, sonst eine Mail über Sarvis' eigenes
Google-Konto an dieses Konto selbst. Telethon scheidet aus: Das ist
Saschas eigener Account, und der kann sich selbst nicht anpiepen.

Gewarnt wird auf Flanken, nicht auf Zuständen, mit zwölf Stunden Ruhe
zwischen Erinnerungen — sonst wäre über Nacht aus einer Warnung ein
Postfach voller Warnungen geworden. Ein gescheiterter Versand zählt
nicht als gemeldet.

Die Flankenlogik prüft `wache_test.py`; der Melde-Weg wurde einmal echt
verschickt, weil eine Attrappe über den Posteingang nichts beweist.

## Die Git-Identität

Ohne `user.email`/`user.name` scheitert jeder Commit — und zwar nicht
beim Start, sondern spät, mitten in der Arbeit des Hintergrund-Arbeiters,
mit „Please tell me who you are".

Deshalb steht sie an zwei Stellen:

* im Image als `git config --system` (`Sarvis <sarvis@tech-artist.de>`),
* in `docker-compose.yml` als `GIT_AUTHOR_*`/`GIT_COMMITTER_*`.

Die Umgebungsvariablen sind der Knopf, an dem man dreht — sie
übersteuern auch ein `[user]` in der `.git/config` eines Projekts. Das
ist hier gewollt: In `/srv/storage/projects/sarvis/.git/config` steht
`Kreank <tech.artist89@gmail.com>`; Sarvis' eigene Commits sollen aber
als Sarvis erkennbar sein.

Dazu kommt `git config --system --add safe.directory '*'`. Ohne das
verweigerte git in jedem gemounteten Repository die Arbeit mit „detected
dubious ownership".

## Modelle

Nichts davon liegt im Image — alles unter `/srv/data/sarvis`:

| Was | Wo | Wie groß |
|---|---|---|
| Whisper `large-v3-turbo` | `modelle/hf/hub/models--mobiuslabsgmbh--faster-whisper-large-v3-turbo` | 1,6 GB |
| Piper-Stimme | `stimmen/de_DE-thorsten-high.onnx` (+ `.onnx.json`) | 109 MB |
| Silero-VAD | `vad/silero_vad.onnx` | 1,8 MB |

`HF_HOME` zeigt auf `modelle/hf`, deshalb lädt Whisper aus dem Cache
statt aus dem Netz.

**Das VAD-Modell ist der Sonderfall.** `openwakeword` bringt
`silero_vad.onnx` nicht mit (das Rad ist 60 KB groß), und nachgeladen
würde es nur über `openwakeword.utils.download_models()` — das ruft in
Sarvis niemand. `weckwort.py:194` fängt den daraus folgenden
`NO_SUCHFILE` ab und schaltet **still** auf „Weckwort aus": Es fehlt
einfach eine Funktion, ohne Meldung.

Das Image legt deshalb beim Bauen einen Symlink von
`<site-packages>/openwakeword/resources/models/silero_vad.onnx` auf
`/srv/data/sarvis/vad/silero_vad.onnx`. Der Zielpfad wird über
`importlib.util.find_spec` ermittelt, nicht geraten. Verweis statt
Kopie, weil das Modell dorthin gehört, wo Modelle liegen — und weil ein
Austausch der Datei dann sofort wirkt.

## Drei Stellen, an denen `pip install -r requirements.txt` nicht reicht

Das Image installiert deshalb in mehreren Schritten. `requirements.txt`
selbst bleibt unangetastet.

**openwakeword** verlangt auf Linux `tflite-runtime`. Davon gibt es nur
Räder bis cp311 (2.14.0 ist der letzte Stand, geprüft am 30.08.2026),
also keines für 3.12. Ungeteilt bricht dadurch die *ganze* Liste ab.
Sarvis braucht von dem Paket allein `openwakeword.vad.VAD`, und das
läuft über onnxruntime — deshalb `--no-deps` plus `scikit-learn` und
`tqdm` von Hand.

**aiohttp fehlt in `requirements.txt`.** `netz/server.py` schreibt
`from aiohttp import WSMsgType, web` — der Endpunkt auf 8900 *ist*
aiohttp. Gemessen im ersten gebauten Image:
`ModuleNotFoundError: No module named 'aiohttp'`. Vermutlich, weil die
Liste mit `ast` über `sarvis/*.py` erhoben wurde, als `netz/` noch nicht
stand. **Das gehört in `requirements.txt` nachgetragen**; bis dahin
installiert das Dockerfile es zusätzlich.

**pynput** hängt an `evdev`, und `evdev` liefert überhaupt keine Räder —
es wird immer übersetzt und braucht `linux/input.h`. Deshalb kommen
`gcc`, `libc6-dev` und `linux-libc-dev` im selben Schritt herein und
wieder heraus.

## Was noch nicht läuft

Der Container **startet noch nicht durch**, und das liegt nicht am
Container:

    docker compose run --rm sarvis python -c "import sarvis.main"
    ImportError: this platform is not supported:
      ('failed to acquire X connection: Bad display name ""', ...)

`config.KLANG_QUELLE` steht fest auf `"lokal"`, und `main.py:35` lädt
daraufhin `pynput` — das braucht X11 oder uinput, beides gibt es hier
nicht. Zwei Dinge fehlen dafür noch, beide im Umbau:

* `KLANG_QUELLE = "netz"` (und `klang.py` muss die Netzfassung dann
  wirklich anbieten statt abzubrechen),
* `sarvis/weckwort_leer.py` — `main.py:45` importiert es im
  Netzbetrieb, die Datei gibt es noch nicht.

Sobald beides steht, startet `python -m sarvis.main` im Container ohne
weitere Änderung an Image oder Compose.

Ebenfalls noch offen: `gedaechtnis.kern` sucht die Vorlage unter
`config.GEDAECHTNIS / "kern.VORLAGE.md"`, also
`/srv/data/sarvis/gedaechtnis/kern.VORLAGE.md`. Im Repository liegt sie
unter `gedaechtnis/kern.VORLAGE.md`. Beim Umzug muss der Inhalt von
`gedaechtnis/` also einmal nach `/srv/data/sarvis/gedaechtnis/`.

## Was am 30.08.2026 wirklich geprüft wurde

Im gebauten Image, mit `docker compose run --rm`:

    Python 3.12.13
    faster_whisper 1.2.1   aiohttp 3.14.3   numpy 2.5.2
    scipy 1.18.1           httpx 0.28.1     telethon 1.44.0
    import torch  ->  ModuleNotFoundError  (richtig so, wird nicht gebraucht)
    piper import ok
    node v24.20.0 / npm 11.19.0 / claude 2.1.251 (Claude Code)
    git version 2.47.3, system user.email = sarvis@tech-artist.de

CUDA, echtes Modell, echte Datei:

    NVIDIA GeForce RTX 3070, 190 MiB von 8192 MiB belegt (Ollama war unten)
    WhisperModel("large-v3-turbo", device="cuda",
                 compute_type="int8_float16")  ->  geladen in 2,53 s
    danach 1405 MiB belegt  (also rund 1.215 MiB fuer das Modell)
    15,5 s WAV   ->  0,581 s
    82,1 s .oga  ->  1,293 s   (Opus, ohne ffmpeg im Image)

Git, VAD, Piper:

    git commit in frischem Repo
      Autor:     Sarvis <sarvis@tech-artist.de>
      Committer: Sarvis <sarvis@tech-artist.de>
    Symlink .../openwakeword/resources/models/silero_vad.onnx
      -> /srv/data/sarvis/vad/silero_vad.onnx   (existiert: True)
    VAD().predict(stille)  ->  0.0389
    Piper de_DE-thorsten-high: 22050 Hz, 2,01 s, Spitzenpegel 32767

Schreibrechte im Datenordner: eine Datei entsteht als
`sarvis:sarvis` = uid/gid 1000 — also Sascha auf dem Host.

**Nicht geprüft**, weil dafür Zustand von außen nötig ist: die Anmeldung
der Claude-CLI (kein Login im Volume), ein echter Zuruf über den
WebSocket (der Dienst startet noch nicht, siehe oben), und Telegram/
Google (keine Zugangsdaten hinterlegt).

## Die Grafikkarte ist knapp

8 GB, und Ollama belegt mit `qwen3.5:9b` davon rund 5,6 GB. Whisper
`large-v3-turbo` mit `compute_type="int8_float16"` braucht gemessen
1,2 GB — das passt, aber nicht zweimal und nicht mit einem größeren
Modell. Wer `config.WHISPER_MODELL` hochdreht, nimmt es Ollama weg.

Zur Messung oben: Ollama hatte gerade nichts geladen (190 MiB
Grundlast). Unter Vollast bleiben für Whisper etwa 2,4 GB — reicht für
`int8_float16`, nicht für `float16` (`config.WHISPER_GENAUIGKEIT` steht
noch auf `float16`; für den Container ist `int8_float16` die gemessene
Empfehlung).
