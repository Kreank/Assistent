# Kein Ton in der App — woran es liegt

**Der Server ist es nicht.** Gemessen am 30.08.2026 mit einem eigenen
WebSocket-Client gegen den laufenden Sarvis:

```
Du:  "Sag bitte einen kurzen Satz."
     TON: 107 KB, rate=22050, runde=5
     Sarvis sagte: "Hier ist ein kurzer Satz."
```

Und die Weboberfläche spielt genau das ab — nachgemessen im Browser:

```
abgespielt: [{ dauer: 1.59 s, zeit: 0 }]
Context:    running, 48000 Hz
```

Wenn also Text ankommt und Ton nicht, liegt es an der Verarbeitung von
`ton` in der App. Vier Ursachen, nach Häufigkeit sortiert.

---

## 1. Die Runde verwirft alles

Der häufigste Fehler, und der unauffälligste: Die App verwirft **jedes**
Tonstück, und es sieht aus, als käme keines an.

```
ton kommt mit runde = 5
```

Die Runde zählt hoch, solange Sarvis läuft — sie fängt **nicht** bei
null an, wenn die App sich verbindet. Wer seinen eigenen Zähler mit 0
oder mit dem ersten empfangenen Wert vorbelegt und dann `<=` statt `<`
vergleicht, wirft alles weg.

**Richtig:**

```
eigeneRunde = -1                       // vor der ersten Nachricht
beim Empfang von ton:
    wenn runde != null und runde < eigeneRunde:  verwerfen
    sonst: eigeneRunde = runde; abspielen
```

Zum Prüfen: Log ausgeben, wie viele `ton`-Nachrichten ankommen und wie
viele davon verworfen werden. Wenn ankommen > 0 und abgespielt == 0, ist
es das hier.

## 2. Das Format falsch gelesen

```
daten   base64, OHNE "data:"-Präfix
inhalt  rohes PCM: int16, LITTLE ENDIAN, mono
rate    kommt in der Nachricht mit, üblich 22050
```

Drei Stolpersteine:

- **Kein WAV-Kopf.** Das sind nackte Samples. Wer sie an einen Decoder
  gibt, der einen Kopf erwartet, bekommt nichts. Entweder selbst einen
  44-Byte-WAV-Kopf davorsetzen oder die Samples direkt in einen
  Audiopuffer schreiben.
- **int16, nicht float.** Werte von −32768 bis 32767. Als float
  interpretiert kommt Rauschen oder Stille.
- **Little Endian.** Falsch herum gelesen ergibt lautes Kratzen — wenn
  du das hörst, ist es dieser Punkt.

Unter Android: `AudioTrack` mit `ENCODING_PCM_16BIT`,
`CHANNEL_OUT_MONO`, Abtastrate aus der Nachricht.

## 3. Die Abtastrate ignoriert

Der Ton kommt mit **22050 Hz** (Piper), die Aufnahme geht mit **16000 Hz**
hinaus (Whisper). Wer eine Rate für beides nimmt, bekommt einen zu
schnellen oder zu langsamen, verstimmten Ton — oder je nach Gerät gar
keinen, weil die Rate nicht unterstützt wird.

**Nimm die Rate aus der Nachricht**, nicht eine feste.

## 4. Ton nur nach einer Nutzergeste

Betrifft eher Browser als native Apps, aber die Weboberfläche in einem
WebView zählt: Ein AudioContext startet erst nach einer Berührung. Wer
ihn beim Verbinden anlegt, bekommt ihn im Zustand `suspended` und hört
nichts, ohne dass ein Fehler auftritt.

**Prüfen:** Zustand des Kontexts ausgeben. Steht dort `suspended`, ist es
das. `resume()` beim ersten Antippen der Sprechtaste löst es.

---

## Satzweise, nicht am Stück

Wichtig fürs Verständnis: `ton` kommt **je Satz**, nicht als eine
Antwort. Während Satz eins klingt, baut der Server schon Satz zwei. Das
ist der Unterschied zwischen „fühlt sich an wie reden" und „fühlt sich
an wie ein Formular".

Die App muss die Stücke also **nahtlos aneinanderhängen**, nicht jedes
einzeln abspielen und dazwischen eine Lücke lassen. Wer jedes Stück mit
einem neuen Abspielvorgang beginnt, bekommt ein Stottern zwischen den
Sätzen.

In der Weboberfläche sieht das so aus:

```js
tonZeit = Math.max(tonZeit, hoerer.currentTime);
quelle.start(tonZeit);
tonZeit += puffer.duration;      // der nächste hängt genau hier an
```

## Prüfen, ob die Daten stimmen

Das Skript `einsatz/ton_pruefen.py` verbindet sich, stellt eine Frage
und schreibt die Antwort als WAV-Datei. Wenn die sich abspielen lässt,
sind die Daten in Ordnung und der Fehler liegt in der App:

```bash
python einsatz/ton_pruefen.py <geräteschlüssel>
```
