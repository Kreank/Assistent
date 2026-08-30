# Sarvis als Container.
#
# WARUM PYTHON 3.12 UND NICHT 3.13 ODER 3.14
#
# Nachgesehen, nicht angenommen -- am 30.08.2026 direkt gegen PyPI:
#
#   ctranslate2 4.8.1   liefert Raeder fuer cp39 bis cp314. Der Kern
#                       unter faster-whisper waere auf 3.14 also
#                       inzwischen KEIN Hindernis mehr; die alte Regel
#                       "ctranslate2 hat keine neuen Wheels" stimmt so
#                       nicht mehr.
#   piper-tts 1.7.0     cp39-abi3, laeuft auf allem ab 3.9.
#   av 18.1.0           cp311-abi3.
#   scipy / numpy       ab cp312.
#
#   tflite-runtime      steht seit 2.14.0 still und hat Raeder nur fuer
#                       cp38 bis cp311. openwakeword zieht es auf Linux
#                       fest mit ein (requires_dist: platform_system ==
#                       "Linux") -- und damit bricht "pip install -r
#                       requirements.txt" schon auf 3.12 ab. Wie das
#                       hier geloest ist, steht weiter unten bei den
#                       Python-Abhaengigkeiten.
#
# Bleibt 3.12, und dafuer gibt es einen zweiten, besseren Grund als
# Wheels: Der Transkript-Dienst auf demselben Server faehrt dieselbe
# CUDA-Kette (faster-whisper + nvidia-cublas-cu12 + nvidia-cudnn-cu12)
# auf python:3.12-slim. Eine Fassung, die sich als Ganzes bewaehrt hat,
# ist mehr wert als die neuere.
#
# Die .pyc im Quelltextbaum stammen von CPython 3.14 (Dev-PC) und sind
# hier belanglos -- .dockerignore laesst sie draussen.
FROM python:3.12-slim

ENV DEBIAN_FRONTEND=noninteractive

# --- Was das System beisteuert -------------------------------------------
#
#   git             Sarvis' Hintergrund-Arbeiter legt Zweige an und
#                   committet. Ohne git kein Arbeiter.
#   libsndfile1     soundfile/scipy beim Lesen von WAV.
#   libportaudio2   sounddevice. Es gibt hier kein Audiogeraet, aber
#                   audio.py importiert sounddevice auf Modulebene --
#                   ohne diese Bibliothek stirbt schon der IMPORT, und
#                   zwar mit "PortAudio library not found", was wie ein
#                   Konfigurationsfehler aussieht und keiner ist.
#   espeak-ng       Piper braucht die Lautschrift-Tabellen. Neuere
#                   piper-tts bringen sie ueber espeakng_loader selbst
#                   mit; das System-Paket ist der Rueckfall, wenn nicht.
#   libgomp1        OpenMP -- ctranslate2 rechnet damit auf der CPU
#                   (der Rueckfallpfad in ohren.py, wenn CUDA fehlt).
#   curl, xz-utils  nur zum Holen von Node, siehe unten.
#
# KEIN ffmpeg, und das ist kein Vergessen: Kein einziges .py ruft
# ffmpeg oder ffprobe auf (nachgesehen, nicht vermutet), und
# faster-whisper dekodiert seit 1.1 ueber av (PyAV) -- das bringt seine
# libav*-Bibliotheken im Rad selbst mit. Das apt-Paket zoege unter
# Trixie mesa und Vulkan hinterher; gemessen kostete es 0,6 GB Image
# (6,77 GB mit, 6,18 GB ohne), ohne dass irgendjemand es aufriefe.
#
# Nachgewiesen, nicht gehofft: Im Image OHNE ffmpeg wurden eine WAV
# (15,5 s -> 0,58 s) und eine Opus-Datei .oga (82,1 s -> 1,29 s)
# fehlerfrei transkribiert. Wer hier spaeter doch ffmpeg braucht,
# merkt es also an einem Dekodierfehler, nicht an Stille.
RUN apt-get update && apt-get install -y --no-install-recommends \
        git ca-certificates curl xz-utils \
        libsndfile1 libportaudio2 espeak-ng libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# --- Node und die Claude-Code-CLI ----------------------------------------
#
# claude_agent_sdk redet nicht selbst mit der API -- es startet die CLI
# `claude` als Unterprozess und spricht ueber deren stdin/stdout. Fehlt
# sie, faellt das erst beim ersten Zuruf auf, und die Meldung nennt nicht
# den Grund.
#
# Node kommt als Tarball von nodejs.org nach /opt/node, nicht aus
# Debian: Trixie liefert eine aeltere Fassung, und ein zweites
# /usr/local (wie beim Kopieren aus dem node-Image) wuerde sich mit dem
# Python-Praefix ins Gehege kommen.
ARG NODE_VERSION=24.20.0
RUN curl -fsSL "https://nodejs.org/dist/v${NODE_VERSION}/node-v${NODE_VERSION}-linux-x64.tar.xz" -o /tmp/node.tar.xz \
    && mkdir -p /opt/node \
    && tar -xJf /tmp/node.tar.xz -C /opt/node --strip-components=1 \
    && rm /tmp/node.tar.xz
ENV PATH=/opt/node/bin:$PATH

ARG CLAUDE_CLI_VERSION=latest
RUN npm install -g "@anthropic-ai/claude-code@${CLAUDE_CLI_VERSION}" \
    && npm cache clean --force

# --- Python-Abhaengigkeiten ----------------------------------------------
# Eigene Schicht vor dem Quelltext: Eine Aenderung an sarvis/*.py soll
# nicht die 1,5 GB CUDA-Raeder neu ziehen.
#
# DIE ERSTE AUSNAHME: openwakeword.
#
# Es steht in requirements.txt allein wegen openwakeword.vad.VAD, dem
# Silero-Sprachdetektor -- der laeuft ueber onnxruntime. Das Paket
# verlangt auf Linux aber zusaetzlich tflite-runtime (fuer die
# Weckwortmodelle, die Sarvis gar nicht benutzt), und davon gibt es
# keine Raeder ab cp312. Ungeteilt bricht die GANZE Liste ab, und zwar
# als Erstes -- nichts anderes waere dann installiert.
#
# Deshalb in drei Schritten statt einem. Was fehlt, wenn man einfach
# --no-deps nimmt, wird danach nachgereicht: onnxruntime, scipy und
# requests kommen ohnehin aus der Liste, scikit-learn und tqdm nicht.
#
# requirements.txt bleibt dabei unangetastet -- sie beschreibt, was
# Sarvis braucht; wie es auf dieser Python-Fassung hineinkommt, ist
# Sache des Images.
#
# DIE ZWEITE UND UNANGENEHMSTE: aiohttp fehlt in requirements.txt.
#
# netz/server.py schreibt "from aiohttp import WSMsgType, web" -- der
# Endpunkt auf 8900 IST aiohttp. Die Liste nennt es trotzdem nicht;
# gemessen im ersten gebauten Image:
#
#   ModuleNotFoundError: No module named 'aiohttp'
#
# Vermutlich, weil sie mit ast ueber sarvis/*.py erhoben wurde, als
# netz/ noch nicht stand. Es gehoert in requirements.txt und nicht
# hierher -- aber solange es dort fehlt, faellt der Container erst beim
# Start auf die Nase, und dieser Ausfall waere teurer als die eine
# Zeile hier.
#
# DIE DRITTE: pynput.
#
# Es haengt auf Linux an evdev, und evdev liefert ueberhaupt keine
# Raeder -- es wird immer uebersetzt und braucht dafuer linux/input.h
# aus linux-libc-dev sowie einen Uebersetzer. Ohne die beiden bricht
# der Bau ab ("The 'linux/input.h' ... include files are missing",
# gemessen). Deshalb kommen gcc und die Header hier herein und im
# selben Schritt wieder heraus: In einer eigenen Schicht blieben sie
# sonst fuer immer im Image liegen.
COPY requirements.txt /tmp/requirements.txt
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends gcc libc6-dev linux-libc-dev; \
    pip install --no-cache-dir --upgrade pip; \
    grep -v '^openwakeword' /tmp/requirements.txt > /tmp/requirements-ohne-oww.txt; \
    pip install --no-cache-dir -r /tmp/requirements-ohne-oww.txt; \
    pip install --no-cache-dir --no-deps openwakeword; \
    pip install --no-cache-dir scikit-learn tqdm; \
    pip install --no-cache-dir aiohttp; \
    rm /tmp/requirements.txt /tmp/requirements-ohne-oww.txt; \
    apt-get purge -y --auto-remove gcc libc6-dev linux-libc-dev; \
    rm -rf /var/lib/apt/lists/*

# --- Das VAD-Modell -------------------------------------------------------
#
# openwakeword bringt silero_vad.onnx NICHT mit. Das Rad ist 60 KB
# gross, die ONNX-Datei fehlt darin, und nachgeladen wuerde sie nur
# ueber openwakeword.utils.download_models() -- das ruft in Sarvis
# niemand. Gemessen:
#
#   VAD() ohne Datei  ->  NoSuchFile [ONNXRuntimeError] : 3 : NO_SUCHFILE
#
# Und weil weckwort.py:194 genau diesen Fehler abfaengt und still auf
# "Weckwort aus" schaltet, sieht der Ausfall nach nichts aus: Es fehlt
# einfach eine Funktion, ohne Meldung.
#
# Die Datei liegt unter DATEN (1,8 MB, sha256 a35ebf52...) und damit im
# Volume. Hier steht deshalb ein Verweis, keine Kopie -- so bleibt das
# Modell dort, wo Modelle hingehoeren, das Image braucht den Datenordner
# nicht schon beim Bauen, und ein Austausch der Datei wirkt sofort.
#
# Der Zielpfad wird ermittelt, nicht geraten: find_spec liest ihn aus
# der Installation, ohne das Paket auszufuehren.
RUN set -eux; \
    OWW="$(python -c 'import importlib.util as u; print(u.find_spec("openwakeword").submodule_search_locations[0])')"; \
    echo "openwakeword liegt in $OWW"; \
    mkdir -p "$OWW/resources/models"; \
    ln -sfn /srv/data/sarvis/vad/silero_vad.onnx "$OWW/resources/models/silero_vad.onnx"; \
    ls -l "$OWW/resources/models/silero_vad.onnx"

# ctranslate2 sucht libcublas und libcudnn ueber den Linker-Pfad, nicht
# ueber Python. Die pip-Pakete nvidia-cublas-cu12/nvidia-cudnn-cu12
# legen sie unter site-packages/nvidia/*/lib ab -- ohne diese Zeile
# laedt das Modell zwar, aber die erste Rechnung stirbt (auf Windows
# hiess derselbe Fehler "cublas64_12.dll is not found", siehe
# ohren._cuda_dlls_finden; das hier ist die Linux-Entsprechung).
ENV LD_LIBRARY_PATH=/usr/local/lib/python3.12/site-packages/nvidia/cublas/lib:/usr/local/lib/python3.12/site-packages/nvidia/cudnn/lib

# --- Der Browser ohne Kopf ------------------------------------------------
#
# Sarvis braucht einen eigenen Browser, um selbst eine Seite zu lesen,
# ein Formular auszufuellen oder einen Preis nachzuschlagen. Auf dem
# Dev-PC war das QWebEngineView im Overlay; hier ist es ein headless
# Chrome, gesteuert ueber CDP (sarvis/netz/browser_kopf.py).
#
# WARUM DAS ECHTE CHROME UND KEIN PLAYWRIGHT-CHROMIUM: Playwright braucht
# sein Rad, seinen Node-Treiber (rund 130 MB) UND ein eigenes Chromium.
# Gebraucht wird davon nichts -- browser_kopf.py spricht CDP direkt und
# hat ausser der Standardbibliothek keine Abhaengigkeit. Es bleibt also
# nur der Browser selbst.
#
# GEMESSEN: /opt/google/chrome sind 403 MB, mit den mitgezogenen
# Bibliotheken und Schriften landet das Image bei rund 6,7 statt 6,18 GB.
# Das ist der Preis, und es gibt keinen billigeren: Debians chromium
# kostet praktisch dasselbe.
#
# Die Schriften sind nicht Zierde. Ohne sie rendert Chrome jede Seite in
# Kaestchen -- egal beim reinen Textlesen, aber web_ansehen schickt ein
# BILD an den Nutzer, und ein Bild aus Kaestchen ist wertlos.
# fonts-noto-cjk und fonts-noto-color-emoji sind mit Absicht dabei:
# Emoji stehen heute in jeder zweiten Ueberschrift.
#
# Der Schluessel kommt in /etc/apt/keyrings und wird mit signed-by an
# genau diese eine Quelle gebunden -- nicht in den globalen Bund, wo er
# jedem anderen Repository die Unterschrift abnehmen koennte.
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends gnupg; \
    install -d -m 0755 /etc/apt/keyrings; \
    curl -fsSL https://dl.google.com/linux/linux_signing_key.pub \
        | gpg --dearmor -o /etc/apt/keyrings/google-chrome.gpg; \
    echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/google-chrome.gpg] \
http://dl.google.com/linux/chrome/deb/ stable main" \
        > /etc/apt/sources.list.d/google-chrome.list; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        google-chrome-stable \
        fonts-liberation fonts-dejavu-core fonts-noto-core \
        fonts-noto-cjk fonts-noto-color-emoji; \
    apt-get purge -y --auto-remove gnupg; \
    rm -rf /var/lib/apt/lists/*; \
    google-chrome --version

# --- Wer hier arbeitet ----------------------------------------------------
#
# Nicht root. Sarvis schreibt in /srv/data/sarvis und -- wenn er an
# einem Projekt arbeitet -- nach /srv/storage/projects und
# /home/server3070. Alles davon gehoert auf dem Host uid 1000; liefe der
# Container als root, gehoerte jede erzeugte Datei danach root, und
# Sascha kaeme an sein eigenes Projekt nicht mehr heran.
ARG UID=1000
ARG GID=1000
RUN groupadd -g "${GID}" sarvis \
    && useradd -u "${UID}" -g "${GID}" -m -d /home/sarvis -s /bin/bash sarvis

# --- Die Git-Identitaet ---------------------------------------------------
#
# Ohne user.email/user.name scheitert JEDER Commit -- und zwar nicht
# beim Start, sondern spaet, mitten in der Arbeit des Hintergrund-
# Arbeiters, mit "Please tell me who you are". Deshalb steht sie fest im
# Image; docker-compose.yml kann sie ueber GIT_AUTHOR_* uebersteuern.
#
# safe.directory: Das Repository kommt als Mount vom Host. Gehoerte es
# einer anderen uid als dem Prozess, verweigerte git mit "detected
# dubious ownership" jede Operation. Der Stern deckt auch die anderen
# Projekte ab, an denen Sarvis arbeiten darf.
RUN git config --system user.name  "Sarvis" \
    && git config --system user.email "sarvis@tech-artist.de" \
    && git config --system init.defaultBranch main \
    && git config --system --add safe.directory '*'

# --- Orte -----------------------------------------------------------------
#
# SARVIS_DATEN liest orte.py; alles Erzeugte haengt daran. HF_HOME muss
# darunter liegen, sonst laedt jeder Neubau die 1,6 GB von
# large-v3-turbo neu -- und landete in einer Image-Schicht.
ENV SARVIS_DATEN=/srv/data/sarvis \
    HF_HOME=/srv/data/sarvis/modelle/hf \
    XDG_CACHE_HOME=/srv/data/sarvis/cache \
    HOME=/home/sarvis \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=Europe/Berlin

# --- Der Quelltext --------------------------------------------------------
#
# An denselben Pfad wie auf dem Host. Zwei Gruende, beide unscheinbar
# und beide teuer, wenn man sie uebersieht:
#
#   1. schutz.py vergleicht Pfade gegen die Freilisten aus orte.py, und
#      dort steht "/srv/storage/projects". Laege der Quelltext im
#      Container unter /app, waere Sarvis' eigenes Projekt nicht mehr im
#      Entwicklungsbereich -- er muesste fuer jede Zeile an sich selbst
#      fragen.
#   2. VERLAUF_ORDNER rechnet den Ordnernamen der Sitzungsdateien aus
#      WURZEL (orte._verlauf_slug). Ein anderer Pfad heisst anderer
#      Slug, und verlauf_nachschlagen fiele STILL aus -- die Antwort
#      waere "Ich finde keinen gespeicherten Verlauf", nicht ein Fehler.
#
# Beim Betrieb legt docker-compose.yml das echte Verzeichnis darueber;
# diese Kopie ist der Stand, mit dem das Image auch allein laeuft.
WORKDIR /srv/storage/projects/sarvis
COPY --chown=sarvis:sarvis . /srv/storage/projects/sarvis

USER sarvis

# `python -m sarvis.main` ist derselbe Aufruf wie in starten.bat, nur
# ohne Windows drumherum.
CMD ["python", "-m", "sarvis.main"]
