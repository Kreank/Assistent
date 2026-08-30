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
#   ffmpeg          faster-whisper laesst Audio darueber dekodieren;
#                   av (ElevenLabs-MP3) bringt seine eigenen Bibliotheken
#                   mit, ffmpeg ist der Weg fuer alles Uebrige.
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
RUN apt-get update && apt-get install -y --no-install-recommends \
        git ca-certificates curl xz-utils \
        ffmpeg libsndfile1 libportaudio2 espeak-ng libgomp1 \
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
# DIE EINE AUSNAHME: openwakeword.
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
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && grep -v '^openwakeword' /tmp/requirements.txt > /tmp/requirements-ohne-oww.txt \
    && pip install --no-cache-dir -r /tmp/requirements-ohne-oww.txt \
    && pip install --no-cache-dir --no-deps openwakeword \
    && pip install --no-cache-dir scikit-learn tqdm \
    && rm /tmp/requirements.txt /tmp/requirements-ohne-oww.txt

# ctranslate2 sucht libcublas und libcudnn ueber den Linker-Pfad, nicht
# ueber Python. Die pip-Pakete nvidia-cublas-cu12/nvidia-cudnn-cu12
# legen sie unter site-packages/nvidia/*/lib ab -- ohne diese Zeile
# laedt das Modell zwar, aber die erste Rechnung stirbt (auf Windows
# hiess derselbe Fehler "cublas64_12.dll is not found", siehe
# ohren._cuda_dlls_finden; das hier ist die Linux-Entsprechung).
ENV LD_LIBRARY_PATH=/usr/local/lib/python3.12/site-packages/nvidia/cublas/lib:/usr/local/lib/python3.12/site-packages/nvidia/cudnn/lib

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
