"""Klangbearbeitung hinter Piper -- aus einer Sprecherstimme wird Sarvis.

Der Umweg, den man sich hier spart: Sci-Fi-Stimmen sind fast nie eigene
Modelle. HAL 9000, GLaDOS, JARVIS -- alles Schauspieler mit einer
Effektkette dahinter. Genauso hier: Piper liefert saubere Sprache, und
was danach passiert, macht den Charakter.

Der Vorteil gegenüber einem Klon-Modell ist nicht Klangtreue, sondern
Tempo. Die ganze Kette hier kostet Millisekunden und laeuft auf der CPU;
ein Klon-Modell braucht die GPU, und die hat Whisper.

Die Tonhoehe wird bewusst NICHT hier verschoben, sondern ueber Pipers
Sprechtempo vorkompensiert -- siehe mund.py. Ein Phasenvocoder wuerde
Zischlaute verwaschen, und genau die traegt eine Assistentenstimme.
"""
import numpy as np
from scipy import signal


def _bandpass(x, rate, unten, oben, ordnung=2):
    nyq = rate / 2
    unten = max(20.0, min(unten, nyq * 0.95))
    oben = max(unten + 50.0, min(oben, nyq * 0.95))
    b, a = signal.butter(ordnung, [unten / nyq, oben / nyq], btype="band")
    return signal.lfilter(b, a, x).astype("float32")


def _hochregal(x, rate, ab, verstaerkung):
    """Luft obenherum -- macht die Stimme praesenter, ohne sie zu schaerfen."""
    nyq = rate / 2
    b, a = signal.butter(2, min(ab / nyq, 0.95), btype="high")
    return (x + signal.lfilter(b, a, x) * verstaerkung).astype("float32")


def _chorus(x, rate, tiefe_ms=14.0, geschwindigkeit=0.6, anteil=0.35):
    """Leicht verstimmte Kopie darueber. Erzeugt den 'nicht ganz
    menschlichen' Schimmer, ohne nach Roboter zu klingen."""
    n = len(x)
    t = np.arange(n) / rate
    versatz = (tiefe_ms / 1000.0) * rate * (0.5 + 0.5 *
                                            np.sin(2 * np.pi * geschwindigkeit * t))
    stellen = np.clip(np.arange(n) - versatz, 0, n - 1)
    kopie = np.interp(stellen, np.arange(n), x).astype("float32")
    return ((1.0 - anteil * 0.5) * x + anteil * kopie).astype("float32")


def _ringmod(x, rate, hertz=70.0, tiefe=0.12):
    """Ganz wenig Ringmodulation: metallischer Beiklang, kein Blech."""
    t = np.arange(len(x)) / rate
    return (x * (1.0 - tiefe + tiefe * np.sin(2 * np.pi * hertz * t))).astype("float32")


def _hall(x, rate, dauer=0.28, anteil=0.16, vorlauf=0.012):
    """Kurzer, synthetischer Raum. Kein echter Faltungshall -- ein
    abklingendes Rauschen reicht voellig und kostet nichts."""
    n = int(rate * dauer)
    if n < 8:
        return x
    rng = np.random.default_rng(7)          # fest, damit es reproduzierbar ist
    fahne = rng.standard_normal(n).astype("float32")
    fahne *= np.exp(-np.linspace(0, 6.5, n)).astype("float32")
    fahne = _bandpass(fahne, rate, 300, 6000)
    fahne /= (np.max(np.abs(fahne)) or 1.0)
    nass = signal.fftconvolve(x, fahne)[: len(x)].astype("float32")
    vor = int(rate * vorlauf)
    if vor:
        nass = np.concatenate([np.zeros(vor, "float32"), nass])[: len(x)]
    nass /= (np.max(np.abs(nass)) or 1.0)
    return ((1.0 - anteil) * x + anteil * nass * (np.max(np.abs(x)) or 1.0)).astype("float32")


def _tiefregal(x, rate, bis=320.0, verstaerkung=0.5):
    """Koerper unten drunter.

    Werden die Formanten nach oben geschoben, wird die Stimme duenn --
    genau das laesst sie nach Comic klingen statt nach Maschine. Ein
    bisschen Tiefe darunter holt den Ernst zurueck.
    """
    nyq = rate / 2
    b, a = signal.butter(2, min(bis / nyq, 0.95), btype="low")
    return (x + signal.lfilter(b, a, x) * verstaerkung).astype("float32")


def _formanten(x, rate, faktor=0.88, fenster=1024, sprung=256, glaette=6.0):
    """Verschiebt die Klangfarbe, ohne die Tonhoehe anzufassen.

    Das ist der eigentliche Hebel gegen "klingt immer noch nach Thorsten".
    Eine Stimme erkennt man an den Formanten -- den Resonanzen des
    Sprechapparats --, nicht an der Tonlage. Wer nur tiefer stimmt, klingt
    wie derselbe Mensch mit Halsschmerzen.

    Verfahren: Die Huellkurve des Spektrums wird geglaettet, auf der
    Frequenzachse gestaucht oder gedehnt und wieder aufgepraegt. Die
    Obertoene bleiben, wo sie sind -- deshalb bleibt die Tonhoehe stehen
    und es klingt nicht abgehackt. Ein Vocoder wuerde genau hier den
    Roboter erzeugen.

    faktor < 1 : Formanten nach unten -> groesser, dunkler wirkender Kopf
    faktor > 1 : nach oben -> kleiner, heller
    """
    from scipy.ndimage import gaussian_filter1d

    if abs(faktor - 1.0) < 1e-3 or len(x) < fenster:
        return x
    f, t, Z = signal.stft(x, rate, nperseg=fenster, noverlap=fenster - sprung)
    betrag = np.abs(Z)
    log = np.log(betrag + 1e-7)

    huelle = gaussian_filter1d(log, sigma=glaette, axis=0, mode="nearest")
    achse = np.arange(huelle.shape[0])
    verschoben = np.empty_like(huelle)
    for i in range(huelle.shape[1]):
        verschoben[:, i] = np.interp(achse / faktor, achse, huelle[:, i])

    Z = Z * np.exp(verschoben - huelle)
    _, y = signal.istft(Z, rate, nperseg=fenster, noverlap=fenster - sprung)
    y = y[: len(x)].astype("float32")
    if len(y) < len(x):
        y = np.pad(y, (0, len(x) - len(y)))
    return y


def _doppeln(x, rate, stimmen=3, streuung_ms=9.0, verstimmung=0.004, anteil=0.5):
    """Mehrere leicht versetzte und verstimmte Kopien uebereinander.

    Klingt nach "spricht mit mehr als einem Mund", ohne abgehackt zu
    werden -- der Klassiker fuer Filmcomputer. Deutlich unmenschlicher
    als ein einzelner Chorus, aber weiterhin fluessig.
    """
    n = len(x)
    summe = x.astype("float32").copy()
    for k in range(1, stimmen + 1):
        richtung = 1 if k % 2 else -1
        verzug = int(rate * (streuung_ms / 1000.0) * k / stimmen)
        rate_k = 1.0 + richtung * verstimmung * k
        laenge = max(8, int(n / rate_k))
        kopie = np.interp(np.linspace(0, n - 1, laenge),
                          np.arange(n), x).astype("float32")
        kopie = np.interp(np.linspace(0, laenge - 1, n),
                          np.arange(laenge), kopie).astype("float32")
        if verzug:
            kopie = np.concatenate([np.zeros(verzug, "float32"), kopie])[:n]
        summe += kopie * (anteil / stimmen)
    return (summe / (1.0 + anteil)).astype("float32")


def _phaser(x, rate, geschwindigkeit=0.25, tiefe=0.7, stufen=4):
    """Langsam wandernde Ausloeschungen -- gibt der Stimme einen
    'bearbeiteten' Schimmer, ohne den Rhythmus anzutasten.

    Der LFO wurde frueher mit lfo.mean() zu EINER Zahl eingedampft. Damit
    standen die Kerben fuer den ganzen Satz fest -- es wanderte nichts,
    'geschwindigkeit' war praktisch wirkungslos, und der Klang hing
    stattdessen an der Satzlaenge, weil der Mittelwert eines Sinus ueber
    ein endliches Fenster laengenabhaengig ist (gemessen bei fester
    Geschwindigkeit 0.2: oberste Kerbe 2843 Hz bei 0.8 s, 3091 Hz bei
    2.0 s, 2400 Hz bei 5.0 s). Jetzt wird blockweise gefiltert, mit dem
    LFO-Wert aus der Blockmitte. Der Filterzustand laeuft ueber die
    Blockgrenzen mit (zi) -- ohne das knackt jeder Blockwechsel.
    """
    n = len(x)
    if n == 0:
        return x.astype("float32")
    y = x.astype("float32").copy()
    t = np.arange(n) / rate
    lfo = 0.5 + 0.5 * np.sin(2 * np.pi * geschwindigkeit * t)
    block = 512
    zustand = [None] * stufen
    for anfang in range(0, n, block):
        ende = min(anfang + block, n)
        wert = float(lfo[(anfang + ende) // 2])
        teil = y[anfang:ende]
        for stufe in range(stufen):
            mitte = 300.0 * (2 ** stufe) * (0.6 + 0.8 * wert)
            b, a = signal.iirnotch(min(mitte, rate / 2 * 0.9), Q=1.4, fs=rate)
            if zustand[stufe] is None:
                zustand[stufe] = np.zeros(max(len(a), len(b)) - 1)
            teil, zustand[stufe] = signal.lfilter(b, a, teil, zi=zustand[stufe])
        y[anfang:ende] = teil.astype("float32")
    return ((1.0 - tiefe * 0.5) * x + tiefe * 0.5 * y).astype("float32")


def _saettigung(x, mass=1.4):
    """Sanftes Anzerren -- gibt Koerper, ohne hoerbar zu verzerren."""
    return (np.tanh(x * mass) / np.tanh(mass)).astype("float32")


# Jede Farbe ist eine Liste von Schritten. halbtoene wird nicht hier
# angewandt, sondern von mund.py vorkompensiert.
FARBEN = {
    "aus": {"halbtoene": 0.0, "schritte": []},

    # Ruhig und praesent, ein Hauch Raum. Das ist die JARVIS-Richtung:
    # klingt nach Technik, aber nicht nach Maschine.
    "hologramm": {
        "halbtoene": -1.5,
        "schritte": [
            ("hochregal", {"ab": 3500, "verstaerkung": 0.28}),
            ("chorus", {"tiefe_ms": 11.0, "geschwindigkeit": 0.5, "anteil": 0.22}),
            ("hall", {"dauer": 0.30, "anteil": 0.14}),
        ],
    },

    # --- Die zurueckhaltenden drei -------------------------------------
    #
    # Entstanden am 01.09.2026 aus einer Ansage: "momentan klingt sie
    # sehr nach Roboter -- weniger Roboter, mehr Richtung menschlich,
    # aber nicht zu menschlich. Eher Star Trek."
    #
    # WORAN DER ROBOTER HAENGT: an den Formanten. "sarvis" schiebt sie
    # um Faktor 1,32 nach oben, und das ist der blecherne Beiklang --
    # nicht der Hall, nicht die Doppelung. Eine Verschiebung nach oben
    # macht den Resonanzkoerper rechnerisch kleiner, und "kleiner Kopf"
    # hoert das Ohr als "kein Kopf".
    #
    # Diese drei fassen die Formanten deshalb gar nicht an oder schieben
    # sie leicht NACH UNTEN. Was sie kuenstlich macht, ist Raum und ein
    # Hauch Doppelung -- also das, was auch eine Lautsprecherdurchsage
    # kuenstlich macht. Der Mensch bleibt hoerbar.

    # Stufe eins, am dichtesten am Menschen: eine gute Aufnahme, ein
    # guter Lautsprecher, ein kleiner Raum. Sonst nichts.
    "praesent": {
        "halbtoene": -0.5,
        "schritte": [
            ("tiefregal", {"bis": 220, "verstaerkung": 0.25}),
            ("hochregal", {"ab": 3800, "verstaerkung": 0.20}),
            ("hall", {"dauer": 0.20, "anteil": 0.09, "vorlauf": 0.010}),
        ],
    },

    # Stufe zwei, die Star-Trek-Richtung: ruhig, klar, eine Spur
    # ueberirdisch -- aber jederzeit verstaendlich. Der Bordcomputer der
    # Enterprise klingt nicht nach Maschine, er klingt nach jemandem,
    # der nicht im Raum steht.
    "sternenschiff": {
        "halbtoene": -1.0,
        "schritte": [
            ("hochregal", {"ab": 3600, "verstaerkung": 0.26}),
            # Zwei Stimmen, kaum verstimmt: Das ist der Unterschied
            # zwischen "leicht entrueckt" und "Chor". Ab etwa 0,3
            # Anteil hoert man zwei Sprecher statt einen.
            ("doppeln", {"stimmen": 2, "streuung_ms": 4.0,
                         "verstimmung": 0.0012, "anteil": 0.18}),
            ("hall", {"dauer": 0.28, "anteil": 0.13, "vorlauf": 0.014}),
        ],
    },

    # Stufe drei, einen Schritt weiter weg: hier werden die Formanten
    # angefasst, aber nach UNTEN -- das macht die Stimme voller statt
    # blechern. Nicht mehr ganz Thorsten, immer noch ein Mensch.
    "begleiter": {
        "halbtoene": -1.0,
        "schritte": [
            ("formanten", {"faktor": 0.94}),
            ("hochregal", {"ab": 3800, "verstaerkung": 0.24}),
            ("doppeln", {"stimmen": 2, "streuung_ms": 5.0,
                         "verstimmung": 0.002, "anteil": 0.24}),
            ("hall", {"dauer": 0.26, "anteil": 0.12}),
        ],
    },

    # Wie aus einer Sprechanlage: schmaler, direkter, mit leichtem Biss.
    "bordcomputer": {
        "halbtoene": -1.0,
        "schritte": [
            ("bandpass", {"unten": 260, "oben": 7000}),
            ("ringmod", {"hertz": 62.0, "tiefe": 0.09}),
            ("saettigung", {"mass": 1.7}),
            ("hall", {"dauer": 0.16, "anteil": 0.10}),
        ],
    },

    # Tiefer, ruhiger, mit Weite. Fuer die grosse Halle.
    "halle": {
        "halbtoene": -3.0,
        "schritte": [
            ("hochregal", {"ab": 3000, "verstaerkung": 0.22}),
            ("chorus", {"tiefe_ms": 18.0, "geschwindigkeit": 0.35, "anteil": 0.30}),
            ("hall", {"dauer": 0.55, "anteil": 0.26, "vorlauf": 0.022}),
        ],
    },

    # Deutlich synthetisch, aber noch mit Mensch darin.
    "kuenstlich": {
        "halbtoene": -2.0,
        "schritte": [
            ("chorus", {"tiefe_ms": 8.0, "geschwindigkeit": 1.4, "anteil": 0.45}),
            ("ringmod", {"hertz": 95.0, "tiefe": 0.20}),
            ("hochregal", {"ab": 4000, "verstaerkung": 0.35}),
            ("hall", {"dauer": 0.22, "anteil": 0.14}),
        ],
    },

    # Ab hier wird die KLANGFARBE verschoben, nicht nur die Tonhoehe --
    # das ist der Unterschied zwischen "Thorsten tiefer" und "nicht mehr
    # Thorsten". Trotzdem fluessig: keine Vocoder, keine Rasterung.

    # Der Sprecher ist nicht mehr wiederzuerkennen, klingt aber noch
    # organisch. Fuer einen Assistenten die runde Wahl.
    "fremd": {
        "halbtoene": -1.5,
        "schritte": [
            ("formanten", {"faktor": 0.82}),
            ("doppeln", {"stimmen": 3, "streuung_ms": 8.0,
                         "verstimmung": 0.004, "anteil": 0.45}),
            ("hochregal", {"ab": 3600, "verstaerkung": 0.30}),
            ("hall", {"dauer": 0.30, "anteil": 0.15}),
        ],
    },

    # Deutlich weiter weg vom Menschen: mehrstimmig, schimmernd, weit.
    "entrueckt": {
        "halbtoene": -2.0,
        "schritte": [
            ("formanten", {"faktor": 0.74}),
            ("doppeln", {"stimmen": 4, "streuung_ms": 12.0,
                         "verstimmung": 0.006, "anteil": 0.6}),
            ("phaser", {"geschwindigkeit": 0.2, "tiefe": 0.5, "stufen": 3}),
            ("hochregal", {"ab": 3200, "verstaerkung": 0.32}),
            ("hall", {"dauer": 0.42, "anteil": 0.22, "vorlauf": 0.018}),
        ],
    },

    # So kuenstlich wie es geht, ohne abgehackt zu werden.
    "maschine": {
        "halbtoene": -1.0,
        "schritte": [
            ("formanten", {"faktor": 0.68}),
            ("doppeln", {"stimmen": 4, "streuung_ms": 6.0,
                         "verstimmung": 0.009, "anteil": 0.7}),
            ("ringmod", {"hertz": 88.0, "tiefe": 0.16}),
            ("phaser", {"geschwindigkeit": 0.35, "tiefe": 0.7, "stufen": 4}),
            ("bandpass", {"unten": 190, "oben": 8200}),
            ("hall", {"dauer": 0.24, "anteil": 0.16}),
        ],
    },

    # --- heller, Richtung weiblich ---------------------------------------
    # Formanten NACH OBEN: kuerzerer Sprechapparat, hellerer Klang. Zusammen
    # mit hoeherer Tonlage kippt das Geschlecht der Stimme -- der wirksamste
    # Weg weg von "das ist ja immer noch Thorsten".

    # Hell und klar, noch nah am Menschen.
    "hell": {
        "halbtoene": +3.0,
        "schritte": [
            ("formanten", {"faktor": 1.18}),
            ("hochregal", {"ab": 3800, "verstaerkung": 0.25}),
            ("hall", {"dauer": 0.26, "anteil": 0.13}),
        ],
    },

    # Weder maennlich noch weiblich -- das kuenstliche Dazwischen.
    "androgyn": {
        "halbtoene": +4.0,
        "schritte": [
            ("formanten", {"faktor": 1.26}),
            ("doppeln", {"stimmen": 3, "streuung_ms": 8.0,
                         "verstimmung": 0.005, "anteil": 0.5}),
            ("hochregal", {"ab": 3500, "verstaerkung": 0.30}),
            ("hall", {"dauer": 0.30, "anteil": 0.16}),
        ],
    },

    # Hell, mehrstimmig, schimmernd. Deutlich Maschine, aber fluessig.
    "sirene": {
        "halbtoene": +5.0,
        "schritte": [
            ("formanten", {"faktor": 1.34}),
            ("doppeln", {"stimmen": 4, "streuung_ms": 11.0,
                         "verstimmung": 0.007, "anteil": 0.65}),
            ("phaser", {"geschwindigkeit": 0.22, "tiefe": 0.5, "stufen": 3}),
            ("hochregal", {"ab": 3200, "verstaerkung": 0.34}),
            ("hall", {"dauer": 0.38, "anteil": 0.20, "vorlauf": 0.016}),
        ],
    },

    # Hell und zugleich technisch -- Bordcomputer mit heller Stimme.
    "hell_technisch": {
        "halbtoene": +3.5,
        "schritte": [
            ("formanten", {"faktor": 1.28}),
            ("doppeln", {"stimmen": 3, "streuung_ms": 6.0,
                         "verstimmung": 0.008, "anteil": 0.6}),
            ("ringmod", {"hertz": 96.0, "tiefe": 0.13}),
            ("bandpass", {"unten": 240, "oben": 9000}),
            ("hall", {"dauer": 0.22, "anteil": 0.14}),
        ],
    },

    # Sehr hell, fast entrueckt. Die aeusserste Stufe in diese Richtung.
    "hoch": {
        "halbtoene": +7.0,
        "schritte": [
            ("formanten", {"faktor": 1.42}),
            ("doppeln", {"stimmen": 3, "streuung_ms": 9.0,
                         "verstimmung": 0.006, "anteil": 0.5}),
            ("hochregal", {"ab": 3000, "verstaerkung": 0.30}),
            ("hall", {"dauer": 0.34, "anteil": 0.18}),
        ],
    },

    # --- die Sci-Fi-Reihe --------------------------------------------------
    # Der Fehler bei "sirene" war die Tonhoehe: +5 Halbtoene ergeben
    # Quietschen. Die Identitaet steckt in den FORMANTEN. Hohe Formanten
    # bei ruhiger Tonlage gibt es bei Menschen nicht -- kurzer Sprech-
    # apparat, aber tiefe Stimme. Genau das liest das Ohr als kuenstlich,
    # ohne dass es albern wird. Dazu Koerper unten drunter, sonst wird es
    # duenn und klingt nach Comic.

    # Ruhig, hell, klar unmenschlich. Die Hauptempfehlung.
    "sarvis": {
        "halbtoene": +1.0,
        "schritte": [
            ("formanten", {"faktor": 1.32}),
            ("tiefregal", {"bis": 300, "verstaerkung": 0.55}),
            ("doppeln", {"stimmen": 2, "streuung_ms": 5.0,
                         "verstimmung": 0.0025, "anteil": 0.32}),
            ("hochregal", {"ab": 4200, "verstaerkung": 0.22}),
            ("hall", {"dauer": 0.26, "anteil": 0.13}),
        ],
    },

    # Dasselbe, aber kuehler und weiter -- mehr Raum, mehr Distanz.
    "sarvis_kuehl": {
        "halbtoene": 0.0,
        "schritte": [
            ("formanten", {"faktor": 1.38}),
            ("tiefregal", {"bis": 320, "verstaerkung": 0.6}),
            ("doppeln", {"stimmen": 3, "streuung_ms": 7.0,
                         "verstimmung": 0.0035, "anteil": 0.42}),
            ("phaser", {"geschwindigkeit": 0.18, "tiefe": 0.35, "stufen": 3}),
            ("hochregal", {"ab": 3800, "verstaerkung": 0.26}),
            # In zwei Runden eingegrenzt: erst 0.20/0.16/0.12/0.08, dann
            # feiner 0.10/0.08/0.06/0.04. Bei einer Stimme, die vorgelesen
            # wird, gewinnt Deutlichkeit gegen Raum -- Hall verschmiert
            # genau die Zischlaute, an denen man Woerter auseinanderhaelt.
            ("hall", {"dauer": 0.14, "anteil": 0.04, "vorlauf": 0.012}),
        ],
    },

    # Der Widerspruch bis zum Anschlag: heller Klang, TIEFERE Tonlage.
    # Physisch unmoeglich, deshalb am deutlichsten kuenstlich -- und
    # trotzdem ruhig, weil nichts quietscht.
    "sarvis_streng": {
        "halbtoene": -1.5,
        "schritte": [
            ("formanten", {"faktor": 1.36}),
            ("tiefregal", {"bis": 340, "verstaerkung": 0.65}),
            ("doppeln", {"stimmen": 3, "streuung_ms": 6.0,
                         "verstimmung": 0.004, "anteil": 0.45}),
            ("ringmod", {"hertz": 74.0, "tiefe": 0.10}),
            ("hochregal", {"ab": 4000, "verstaerkung": 0.24}),
            ("hall", {"dauer": 0.28, "anteil": 0.15}),
        ],
    },

    # Etwas zurueckhaltender, falls die anderen zu weit gehen.
    "sarvis_sanft": {
        "halbtoene": +1.5,
        "schritte": [
            ("formanten", {"faktor": 1.24}),
            ("tiefregal", {"bis": 300, "verstaerkung": 0.45}),
            ("doppeln", {"stimmen": 2, "streuung_ms": 6.0,
                         "verstimmung": 0.002, "anteil": 0.28}),
            ("hochregal", {"ab": 4200, "verstaerkung": 0.20}),
            ("hall", {"dauer": 0.24, "anteil": 0.12}),
        ],
    },

    # Nah, warm, leise -- als saesse er neben dir.
    "nah": {
        "halbtoene": -2.5,
        "schritte": [
            ("bandpass", {"unten": 90, "oben": 9000}),
            ("saettigung", {"mass": 1.3}),
            ("hall", {"dauer": 0.12, "anteil": 0.07}),
        ],
    },
}

_TUN = {
    "bandpass": _bandpass, "hochregal": _hochregal, "chorus": _chorus,
    "ringmod": _ringmod, "hall": _hall, "saettigung": _saettigung,
    "formanten": _formanten, "doppeln": _doppeln, "phaser": _phaser,
    "tiefregal": _tiefregal,
}


_GEMELDET = set()


def _bekannt(farbe: str) -> bool:
    """Unbekannter Farbname -- einmal melden statt still nichts zu tun.

    Ein Tippfehler in config.STIMMFARBE fiel vorher lautlos durch:
    tonhoehe_faktor() nahm 'aus', faerben() gab jeden Satz unbearbeitet
    zurueck, und die Startzeile von mund.py bestaetigte trotzdem die
    gewuenschte Farbe. Man hoerte die rohe Sprecherstimme und suchte den
    Fehler ueberall, nur nicht im Namen. Gemeldet wird beim ersten
    Nachschlagen -- das ist der Start, nicht jeder Satz.
    """
    if farbe in FARBEN:
        return True
    if farbe not in _GEMELDET:
        _GEMELDET.add(farbe)
        print(f"  ! Stimmfarbe {farbe!r} gibt es nicht -- möglich: "
              f"{', '.join(sorted(FARBEN))}")
    return False


def tonhoehe_faktor(farbe: str) -> float:
    """Wie stark Piper vorkompensieren muss (1.0 = gar nicht)."""
    if not _bekannt(farbe):
        farbe = "aus"
    return 2.0 ** (FARBEN[farbe]["halbtoene"] / 12.0)


def faerben(x: np.ndarray, rate: int, farbe: str) -> tuple[np.ndarray, int]:
    """Wendet die Farbe an. Gibt Audio und (unveraenderte) Abtastrate zurueck."""
    if not _bekannt(farbe) or not len(x):
        return x, rate
    rezept = FARBEN[farbe]

    # Tonhoehe: sauber ueber Neuabtastung. Die Dauer stimmt trotzdem,
    # weil mund.py Piper entsprechend schneller sprechen laesst.
    faktor = tonhoehe_faktor(farbe)
    if abs(faktor - 1.0) > 1e-3:
        neu = int(round(len(x) / faktor))
        if neu > 8:
            x = signal.resample_poly(x, neu, len(x)).astype("float32")

    spitze_vorher = float(np.max(np.abs(x))) or 1.0
    for name, werte in rezept["schritte"]:
        fn = _TUN.get(name)
        if fn is None:
            continue
        x = fn(x, rate, **werte) if name != "saettigung" else fn(x, **werte)

    # Auf die ursprüngliche Lautheit zurück, sonst wird jede Farbe
    # gefühlt lauter oder leiser als die andere.
    spitze = float(np.max(np.abs(x))) or 1.0
    return (x * (spitze_vorher / spitze) * 0.98).astype("float32"), rate
