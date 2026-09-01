# Sarvis im Auto: Lenkradtaste statt Google

## Das Problem

Der Ton geht bereits ins Fahrzeug (Android Auto, remote-submix), und der
Freisprecher ist verbunden. Aber die Mikrofontaste am Lenkrad landet
weiterhin beim Google Assistant, nicht bei Sarvis.

Beleg aus dem Fahrtenbuch vom 1. September 2026: Es gibt Einträge für
Tonweg und verbundene Freisprecher, aber **keinen einzigen Eintrag über
einen Tastendruck**. Die App bekommt das Ereignis also gar nicht erst.

## Die Ursache

Die Lenkrad-Mikrofontaste löst unter Android einen Assist-Aufruf aus. Den
bekommt ausschließlich die App, die als **Standard-Assistent** (Digital
Assistant App) eingetragen ist. Solange Sarvis sich nicht als solche
registriert, ist sie für dieses Ereignis unsichtbar.

## Der Weg

### 1. VoiceInteractionService in der App

Die App braucht drei Bausteine:

- einen `VoiceInteractionService` (der Dienst, den Android beim
  Assist-Aufruf startet)
- eine `VoiceInteractionSessionService` plus eigene `VoiceInteractionSession`
  (die eigentliche Sitzung: Mikrofon auf, Zuruf aufnehmen, an den Server)
- eine `RecognitionService`-Deklaration, weil Android eine Assist-App ohne
  Spracherkennungsdienst in der Auswahlliste teilweise ausblendet

### 2. Manifest

```xml
<service
    android:name=".auto.SarvisInteractionService"
    android:permission="android.permission.BIND_VOICE_INTERACTION"
    android:exported="true">
    <intent-filter>
        <action android:name="android.service.voice.VoiceInteractionService" />
    </intent-filter>
    <meta-data
        android:name="android.voice_interaction"
        android:resource="@xml/interaction_service" />
</service>
```

`res/xml/interaction_service.xml`:

```xml
<voice-interaction-service
    xmlns:android="http://schemas.android.com/apk/res/android"
    android:sessionService=".auto.SarvisSessionService"
    android:recognitionService=".auto.SarvisRecognitionService"
    android:supportsAssist="true"
    android:supportsLaunchVoiceAssistFromKeyguard="true" />
```

### 3. Auf dem Telefon einstellen

Einstellungen → Apps → Standard-Apps → Digitaler Assistent → **Sarvis**.

Ohne diesen Schritt passiert nichts, egal wie korrekt die App gebaut ist.
Android fragt das nicht von selbst.

### 4. Prüfen

- `adb shell settings get secure assistant` muss die Sarvis-Komponente zeigen
- Lenkradtaste drücken: im Fahrtenbuch muss jetzt eine Zeile zum
  Assist-Aufruf erscheinen. Kommt keine, greift die Registrierung nicht.

## Stolperstellen

- **Fahrzeuge mit eigener Zuordnung:** Manche Systeme schicken die
  Mikrofontaste über Bluetooth-HFP an die zuletzt gekoppelte Telefonie-App
  statt über den Assist-Weg. Dann hilft nur, zusätzlich auf den
  Bluetooth-Sprachbefehl-Aufruf zu hören.
- **Android Auto:** Die Projektion erlaubt nur freigegebene App-Kategorien.
  Für einen eigenen sichtbaren Knopf auf dem Fahrzeugbildschirm braucht es
  eine Android-Auto-taugliche App-Kategorie; der Assist-Weg über die
  Lenkradtaste funktioniert dagegen auch ohne Projektionsfreigabe.
- **Ton und Mikrofon gleichzeitig:** Läuft Sarvis' Antwort über
  remote-submix ins Fahrzeug, während das Mikrofon offen ist, braucht es
  Echo-Unterdrückung an und Verstärkungsautomatik aus — dieselbe
  Einstellung wie in `einsatz/TON-IN-DER-APP.md`.

## Wo gebaut wird

Die Android-App liegt auf dem Dev-Rechner, nicht auf diesem Server. Diese
Datei ist die Anleitung; die Umsetzung geschieht dort.

---

# Anhang: Nachrichten auf dem Fahrzeugbildschirm

## Beobachtung

Das Multimediasystem zeigt dauerhaft „Keine neuen Nachrichten dieser
Fahrt", obwohl Nachrichten da sind. Angezeigt werden sollten die letzten
Nachrichten als Kacheln.

## Warum das so ist

Android Auto baut die Nachrichtenkacheln **nicht** aus einer App-Oberfläche,
sondern ausschließlich aus **Benachrichtigungen** eines ganz bestimmten
Zuschnitts. Alles andere blendet die Projektion aus. Nötig ist:

- `NotificationCompat.MessagingStyle` — kein `BigTextStyle`, kein
  einfacher Text. Ohne MessagingStyle gibt es keine Kachel.
- ein `Person`-Objekt für den Absender, mit Namen und möglichst Bild
- `CarExtender` mit `UnreadConversation`, darin die Antwort-Aktion
  (`RemoteInput` für „per Sprache antworten") und die Gelesen-Aktion
- Kanal mit mindestens `IMPORTANCE_DEFAULT`; alles darunter wird im
  Fahrzeug stumm verworfen
- `setCategory(NotificationCompat.CATEGORY_MESSAGE)`

Der Satz „dieser Fahrt" ist wörtlich zu nehmen: Android Auto sammelt nur,
was **während der laufenden Verbindung** neu hereinkommt. Nachrichten von
vorher tauchen nie auf, auch wenn sie ungelesen sind. Eine Verlaufsliste
gibt es in der Nachrichtenansicht grundsätzlich nicht.

## Was daraus folgt

Zwei getrennte Baustellen, nicht eine:

1. **Neue Nachrichten sollen als Kachel erscheinen.** Dann muss Sarvis
   eingehende Telegram-Nachrichten als MessagingStyle-Benachrichtigung
   mit CarExtender ausgeben, solange das Fahrzeug verbunden ist. Das ist
   der reguläre, von Android Auto vorgesehene Weg.

2. **Die letzten Nachrichten sollen zum Nachlesen dasein**, auch die von
   vor Fahrtbeginn. Das geht über die Nachrichtenansicht nicht. Dafür
   braucht es eine eigene Android-Auto-App-Oberfläche über die Car App
   Library, mit einem `ListTemplate` — dort darf ein Verlauf stehen.
   Achtung: Die Templates sind in Zeilenzahl und Textlänge gedeckelt, und
   während der Fahrt gelten strengere Grenzen als im Stand.

## Drittens: Wer spricht eigentlich?

Beobachtet am 1. September 2026 abends: Die Benachrichtigung kommt an, im
Fahrzeug lässt sie sich vorlesen — aber es spricht die Stimme des
Systems, nicht Sarvis. Und der eigene Tonweg brach mehrfach weg (nichts
mehr hörbar), kam kurz zurück und war dann wieder fort.

Das sind zwei verschiedene Dinge, die man nicht vermischen darf:

- **Vorlesen einer Benachrichtigung** macht Android Auto selbst, mit
  seiner eigenen Stimme. Es liest ausschließlich den Text der
  Benachrichtigung vor. Sarvis' Stimme ist hier grundsätzlich nicht zu
  bekommen — das ist keine Fehleinstellung, sondern so gebaut.
- **Sarvis' eigene Stimme** entsteht nur, wenn die App den erzeugten Ton
  selbst über den Medienweg ins Fahrzeug schickt. Genau dieser Weg ist
  instabil: Im Fahrtenbuch steht dutzendfach „Weg hat sich mitten im Ton
  geaendert", und in den Lücken hört man nichts.

Daraus folgt für den Entwurf: Antworten dürfen **nicht** über den
Umweg einer vorlesbaren Benachrichtigung gehen. Sie brauchen einen
stabilen eigenen Tonweg mit gehaltenem Audio-Fokus
(`AUDIOFOCUS_GAIN_TRANSIENT_MAY_DUCK` für die Dauer der Antwort), damit
der Weg nicht mitten im Satz umgeschaltet wird. Das Umschalten während
laufender Wiedergabe ist der eigentliche Fehler, dem nachzugehen ist.

## Prüfen

- Desktop Head Unit (DHU) starten und eine Testnachricht auslösen: Kommt
  keine Kachel, fehlt in aller Regel der MessagingStyle oder der Kanal ist
  zu leise eingestuft.
- Im Fahrtenbuch mitschreiben, wann eine Benachrichtigung abgesetzt wurde.
  Steht dort ein Eintrag und im Fahrzeug erscheint trotzdem nichts, liegt
  es am Zuschnitt der Benachrichtigung, nicht an der Zustellung.
- Benachrichtigungszugriff prüfen: Ohne erteilten Zugriff sieht Android
  Auto nichts, ganz gleich wie korrekt gebaut wurde.
