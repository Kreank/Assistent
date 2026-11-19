# App: Satzenden werden verschluckt, wenn Sarvis länger redet

**Für den App-Agenten.** Stand 19.11.2026. Server-Vertrag: `einsatz/DRAHT.md`,
Grundlagen zum Ton: `einsatz/TON-IN-DER-APP.md`.

## Was Sascha beobachtet

> „Er verschluckt bei einem Satz öfter die letzten Wörter, wenn er viel redet.
> Wenn der Text gleich komplett da steht und nichts Neues dazukommt, dann macht
> er das nicht."

Also: Kurze Antworten sind vollständig zu hören. Bei langen Antworten, deren Text
im Verlauf Stück für Stück wächst, fehlen am Satzende Wörter.

## Der Server ist es nicht (gemessen)

Drei lange Sätze (18–24 Wörter) genau wie im Gespräch mit Pocket TTS erzeugt und
per Whisper zurückgeschrieben: **alle drei vollständig bis zum letzten Wort.**
Jedes `ton`-Stück enthält, was es enthalten soll.

## Wie der Ton seit dem 14.11. kommt (wichtig!)

Seit Pocket TTS kommt der Ton **nicht mehr als ein Stück je Satz**, sondern in
vielen kleinen Stücken, sobald sie fertig gerechnet sind:

- erstes Stück eines Satzes ≈ 0,5 s, danach Stücke à ≈ **0,24 s** (bleibt so — größere
  Stücke würden am Satzanfang stocken, weil Pocket kaum Vorlauf hat)
- Pocket rechnet nur **knapp schneller als Echtzeit** — die Stücke kommen also
  ungefähr in dem Tempo an, in dem sie abgespielt werden, ohne großen Vorrat
- am Satzende kommt ein letztes Stück mit ~0,3 s Stille (Ausklang)
- eine lange Antwort sind leicht **100–250 `ton`-Nachrichten**

Dazu schickt der Server nach dem Gesagten `zustand` (ruhig) und `nachhoeren`.
Wann das passiert, **schätzt der Server nur** (Summe der gesendeten Tondauer ab
Sendezeitpunkt). Er weiß nicht, wie weit die App mit dem Abspielen wirklich ist.

## Vermutete Ursache (nach Wahrscheinlichkeit)

1. **Die App bricht laufenden Ton ab, wenn `zustand: ruhig` oder `nachhoeren`
   kommt** — oder wenn sie daraufhin das Mikrofon öffnet (Dauerhorch/Weckwort).
   Öffnen des Mikrofons kann unter Android den Audio-Modus wechseln
   (`MODE_IN_COMMUNICATION`, Audiofokus, `AudioRecord`-Start), und ein
   `AudioTrack.flush()/pause()/release()` an dieser Stelle schneidet das ab, was
   noch im Puffer liegt — genau das Satzende.
2. **Kleine Lücken je Stück summieren sich.** Spielt die App jedes Stück mit einem
   neuen Abspielvorgang (neuer `AudioTrack`/`MediaPlayer`, `play()` je Stück,
   Warten auf „fertig" vor dem nächsten), kostet jedes Stück ein paar
   Millisekunden. Bei 200 Stücken ist die App Sekunden hinter der Schätzung des
   Servers — der meldet dann „ruhig", während die App noch spricht. Mit Piper
   (früher ein Stück je Satz) fiel das nicht auf. **Das erklärt, warum es nur bei
   langen Antworten passiert.**
3. Das leere/stille Schlussstück wird als Signal „Satz fertig → Track stoppen"
   behandelt.

## Was die App tun soll

- **Ein durchgehender `AudioTrack` (MODE_STREAM)** für die ganze Sitzung bzw. je
  Rate. Jedes `ton`-Stück nur per `write()` anhängen — kein neuer Track, kein
  `play()`/`stop()` je Stück. Rate aus der Nachricht; ändert sie sich, erst
  ausspielen lassen, dann neuen Track.
- **Abbrechen nur bei:** `ton_stopp` vom Server, oder wenn Sascha selbst die
  Sprechtaste drückt (Reinreden). Dann `pause()` + `flush()`.
- **Nicht abbrechen bei:** `zustand`, `nachhoeren`, neuem Text im Verlauf,
  Untertiteln, Denkkarte, Statuskarten, und nicht beim automatischen Öffnen des
  Mikrofons fürs Nachhören/Dauerhorch. Wenn das Mikrofon geöffnet wird, während
  noch Ton im Puffer liegt: den Ton zu Ende spielen lassen (Audio-Modus/Audiofokus
  so wählen, dass die Wiedergabe weiterläuft — oder das Mikrofon erst öffnen,
  wenn der Puffer leer ist, siehe nächster Punkt).
- **„Spricht noch" selbst bestimmen, nicht vom Server übernehmen:** geschriebene
  Frames mitzählen und mit `getPlaybackHeadPosition()` vergleichen. Erst wenn der
  Puffer wirklich leer ist, gilt die App als „ruhig" (für Ring/Anzeige und fürs
  Öffnen des Mikrofons).
- Die Runde (`runde`) wie gehabt: Stücke älterer Runden verwerfen
  (siehe TON-IN-DER-APP.md, Punkt 1).

## Abnahme

1. Sarvis um eine lange Antwort bitten (z. B. „Erzähl mir ausführlich, was heute
   in den Nachrichten war") — mindestens eine Minute Sprechen.
2. Jeder Satz endet hörbar vollständig; die letzte Silbe der Antwort ist zu hören.
3. Dasselbe mit eingeschaltetem Dauerhorch/Weckwort.
4. Reinreden per Sprechtaste schneidet weiterhin sofort ab.
5. Optional als Beleg ins Log: Anzahl empfangener `ton`-Stücke, Summe ihrer Dauer
   und tatsächlich abgespielte Dauer — die beiden Dauern müssen gleich sein.
