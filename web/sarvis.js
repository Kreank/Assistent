/* Sarvis im Browser.
 *
 * Die Zeichenroutinen sind keine Neuerfindung, sondern eine Uebersetzung
 * von hud.py: dasselbe Raster 660x548, dieselbe Mitte bei 330/222,
 * derselbe Ring mit 58, derselbe Kranz mit 176, dieselben fuenf Farben.
 * Was dort QPainter tat, tut hier ein Canvas. Der Grund ist nicht
 * Nostalgie: Sarvis soll auf dem Handy nicht wie ein anderes Programm
 * aussehen als am Rechner.
 */
'use strict';

// --- Aus hud.py uebernommen ------------------------------------------
const BREITE = 660, HOEHE = 548;
const MITTE = { x: 330, y: 222 };
const RADIUS = 58;      // der Ring
const KRANZ = 176;      // Abstand der Werkzeuge von der Mitte
const BALKEN = 72;      // Striche rund um den Ring
const VERLAUF_LAENGE = BALKEN / 2;
const ICON = 17;

const FARBEN = {
  ruhig:   [126, 158, 200],
  hoert:   [0, 229, 255],
  denkt:   [180, 124, 255],
  spricht: [255, 179, 71],
  fragt:   [255, 120, 140],
};
const BESCHRIFTUNG = {
  ruhig: 'bereit', hoert: 'hört zu', denkt: 'denkt nach',
  spricht: 'spricht', fragt: 'wartet auf dich',
};
// Reihenfolge UND Lage wie config.WERKZEUGE. Die Lage ist kein
// Beiwerk: Ein Werkzeug, das noch nicht gebaut ist, wird nur blass
// angedeutet -- sonst behauptet der Kranz eine Faehigkeit, die es
// nicht gibt. Solange alles "bereit" ist, sieht man keinen
// Unterschied; genau deshalb faellt das Fehlen erst auf, wenn es zu
// spaet ist.
const WERKZEUG_BEREIT = 0.95;   // gebaut und nutzbar   (config.py)
const WERKZEUG_GEPLANT = 0.65;  // kommt noch, angedeutet
const WERKZEUGE = [
  ['Timer', 'bereit'], ['Gedächtnis', 'bereit'], ['Telegram', 'bereit'],
  ['Websuche', 'bereit'], ['Programme', 'bereit'], ['Musik', 'bereit'],
  ['Dateien', 'bereit'], ['Projekte', 'bereit'], ['Aufträge', 'bereit'],
  ['Kalender', 'bereit'], ['E-Mail', 'bereit'], ['Aufgaben', 'bereit'],
  ['Kontakte', 'bereit'], ['Drive', 'bereit'], ['Tabellen', 'bereit'],
  ['Entwicklung', 'bereit'], ['Finanzen', 'bereit'],
];

const KACHEL_ANTWORT = [255, 179, 71];
const KACHEL_ZUSTAND = [126, 224, 168];

// --- Zustand ----------------------------------------------------------
const S = {
  zustand: 'ruhig', pegel: 0, geglaettet: 0, verlauf: new Array(VERLAUF_LAENGE).fill(0),
  untertitel: '', wer: 'sarvis', hervor: 0, nachhoeren: 0, nachhoerenGanz: 1,
  glut: new Map(), hintergrund: [], hgGesamt: 0, hgSeit: 0, hgFertig: false,
  // Was gerade ohne Rueckfrage durchgeht. Steht da, solange es gilt --
  // eine Freigabe, die man nicht sieht, ist keine Zusage mehr, sondern
  // eine Gewohnheit. Der Rest laeuft hier herunter, damit die Anzeige
  // von selbst verschwindet, statt eine abgelaufene weiter zu behaupten.
  freigabe: '', freigabeRest: 0,
  tick: 0, kacheln: new Map(), verbunden: false,
};
WERKZEUGE.forEach(([name]) => S.glut.set(name, 0));

const rgb = (c, a) => `rgba(${c[0]},${c[1]},${c[2]},${a})`;
const mischen = (a, b, t) => a.map((v, i) => Math.round(v + (b[i] - v) * t));

// =====================================================================
// Zeichnen
// =====================================================================
const leinwand = document.getElementById('ring');
const p = leinwand.getContext('2d');
let skala = 1, versatzX = 0, versatzY = 0;

/* Eingepasst wird der INHALT, nicht das Raster.
 *
 * hud.py rechnet in 660x548, aber gemalt wird darin nur ein Kreis von
 * 176 Radius plus Beschriftung -- gut 470x460. Wer das ganze Raster
 * einpasst, bekommt auf einem hochkant gehaltenen Handy einen winzigen
 * Ring mit viel Schwarz darum: Der Platz geht an Flaeche verloren, die
 * nie bemalt wird.
 *
 * Also der Ausschnitt, in dem wirklich etwas steht -- und ein Deckel
 * nach oben, damit der Ring am grossen Bildschirm nicht ins Alberne
 * waechst. */
// 176 Kranzradius + 15 Abstand + bis zu 90 fuer das laengste Wort
// ("ENTWICKLUNG") ergeben 281 je Seite. Gemessen wurde das nicht
// geschaetzt: Bei 472 stand "PROGRAMME" halb ausserhalb des Bildes.
const INHALT_B = 580, INHALT_H = 470;
const INHALT_X = MITTE.x - INHALT_B / 2, INHALT_Y = MITTE.y - INHALT_H / 2 + 24;
const SKALA_MAX = 1.6;

function messen() {
  const dpr = window.devicePixelRatio || 1;
  // Das Canvas selbst messen, nicht seinen Elternteil. Hochkant ist es
  // ein Flex-Kind neben den Kacheln und damit KLEINER als die Bühne --
  // gemessen wurde der Ring dadurch zur Ellipse gestreckt, weil die
  // Pixelmaße des Canvas nicht mehr zu seiner Fläche im Layout passten.
  const b = leinwand.getBoundingClientRect();
  if (b.width < 2 || b.height < 2) return;
  leinwand.width = Math.round(b.width * dpr);
  leinwand.height = Math.round(b.height * dpr);
  skala = Math.min(b.width / INHALT_B, b.height / INHALT_H, SKALA_MAX) * dpr;
  versatzX = leinwand.width / 2 - MITTE.x * skala;
  versatzY = leinwand.height / 2 - (INHALT_Y + INHALT_H / 2) * skala;
}
window.addEventListener('resize', messen);
if (window.ResizeObserver) new ResizeObserver(messen).observe(leinwand);

function malen() {
  const farbeAus = () => {
    if (S.zustand === 'ruhig' && S.nachhoeren > 0) {
      // Der ruhige Ring zieht sich Richtung Cyan, je mehr Nachhoerfenster
      // noch offen ist -- damit man SIEHT, dass kein Weckwort noetig ist.
      const anteil = 0.30 + 0.35 * (S.nachhoeren / S.nachhoerenGanz);
      return mischen(FARBEN.ruhig, FARBEN.hoert, anteil);
    }
    return FARBEN[S.zustand] || FARBEN.ruhig;
  };
  const farbe = farbeAus();
  const atem = 0.5 + 0.5 * Math.sin(S.tick * 1.6);
  const staerke = (S.zustand === 'hoert' || S.zustand === 'spricht')
    ? S.geglaettet : Math.max(atem * 0.25, S.geglaettet);

  p.setTransform(1, 0, 0, 1, 0, 0);
  p.clearRect(0, 0, leinwand.width, leinwand.height);
  p.setTransform(skala, 0, 0, skala, versatzX, versatzY);

  untergrund(staerke);
  kranz(farbe);
  schein(farbe, staerke);
  if (S.zustand === 'denkt' || S.zustand === 'fragt') boegen(farbe);
  else striche(farbe);
  ring(farbe, staerke);
  kern(farbe, staerke);
  zustandswort(farbe);
  if (S.freigabe) freigabewort();
}

function untergrund(staerke) {
  // Ohne diese Scheibe ist helle Schrift auf hellem Grund unlesbar.
  const r = KRANZ * 1.85, ry = r * 0.92;
  p.save(); p.translate(MITTE.x, MITTE.y); p.scale(1, ry / r);
  const v = p.createRadialGradient(0, 0, 0, 0, 0, r);
  const f = 1.30 * (0.8 + 0.2 * staerke);
  [[0, 178], [0.45, 146], [0.72, 74], [1, 0]].forEach(([s, a]) =>
    v.addColorStop(s, `rgba(6,10,20,${Math.min(255, a * f) / 255})`));
  p.fillStyle = v; p.beginPath(); p.arc(0, 0, r, 0, 6.2832); p.fill();
  p.restore();
}

function kranz(farbe) {
  const n = WERKZEUGE.length;
  WERKZEUGE.forEach(([name, lage], i) => {
    const w = -Math.PI / 2 + 2 * Math.PI * i / n;
    const cx = MITTE.x + Math.cos(w) * KRANZ, cy = MITTE.y + Math.sin(w) * KRANZ;
    let glut = S.glut.get(name) || 0;
    if (name === 'Entwicklung' && (S.hintergrund.length || S.hgFertig)) {
      const puls = 0.5 + 0.5 * Math.sin(S.tick * 2.4);
      glut = Math.max(glut, 0.30 + 0.40 * puls);
    }
    // Die Lage steckt allein in der Deckkraft -- "wird nur blass
    // angedeutet". An der Farbe zu drehen brauchte es nicht: Ein
    // geplantes Werkzeug bekommt nie eine Glut, weil es nie laeuft.
    const grund = lage === 'bereit' ? WERKZEUG_BEREIT : WERKZEUG_GEPLANT;
    const kraft = Math.min(1, grund + glut * 0.9);
    const c = glut > 0.02 ? farbe : [150, 168, 196];

    // Speiche nach innen
    p.strokeStyle = rgb(c, kraft * 0.35); p.lineWidth = 1;
    p.beginPath();
    p.moveTo(MITTE.x + Math.cos(w) * (KRANZ - 30), MITTE.y + Math.sin(w) * (KRANZ - 30));
    p.lineTo(MITTE.x + Math.cos(w) * (KRANZ - 17), MITTE.y + Math.sin(w) * (KRANZ - 17));
    p.stroke();

    if (glut > 0.02) {
      // Ein Schein HINTER dem Zeichen: eine duenne Linie hat zu wenig
      // Flaeche, um aus dem Augenwinkel aufzufallen.
      const v = p.createRadialGradient(cx, cy, 0, cx, cy, ICON * 1.6);
      v.addColorStop(0, rgb(c, Math.min(1, 0.5 * glut)));
      v.addColorStop(1, rgb(c, 0));
      p.fillStyle = v; p.beginPath(); p.arc(cx, cy, ICON * 1.6, 0, 6.2832); p.fill();
    }
    p.fillStyle = rgb(c, kraft);
    p.beginPath(); p.arc(cx, cy, 2.6 + glut * 3.0, 0, 6.2832); p.fill();

    // Beschriftung nach aussen, gesperrt und in Grossbuchstaben
    p.save();
    p.font = '600 8px "Segoe UI",system-ui,sans-serif';
    p.textAlign = Math.cos(w) < -0.3 ? 'right' : (Math.cos(w) > 0.3 ? 'left' : 'center');
    p.textBaseline = 'middle';
    saum(name.toUpperCase(),
      cx + Math.cos(w) * 15, cy + Math.sin(w) * 19 - 2, rgb(c, kraft));
    p.restore();
  });
}

function schein(farbe, staerke) {
  const r = RADIUS * (2.6 + staerke * 0.8);
  const v = p.createRadialGradient(MITTE.x, MITTE.y, 0, MITTE.x, MITTE.y, r);
  v.addColorStop(0, rgb(farbe, 0.20 + 0.28 * staerke));
  v.addColorStop(0.45, rgb(farbe, Math.round(40 * (0.4 + staerke)) / 255));
  v.addColorStop(1, rgb(farbe, 0));
  p.fillStyle = v; p.beginPath(); p.arc(MITTE.x, MITTE.y, r, 0, 6.2832); p.fill();
}

function striche(farbe) {
  // 72 Striche, an der Senkrechten gespiegelt: links und rechts gleich.
  p.lineCap = 'round'; p.lineWidth = 2.2;
  for (let i = 0; i < BALKEN; i++) {
    const idx = i < VERLAUF_LAENGE ? i : BALKEN - 1 - i;
    const wert = S.verlauf[idx] || 0;
    const w = -Math.PI / 2 + 2 * Math.PI * i / BALKEN;
    const laenge = 5 + wert * 46;
    p.strokeStyle = rgb(farbe, 0.30 + 0.55 * Math.min(1, wert * 1.6));
    p.beginPath();
    p.moveTo(MITTE.x + Math.cos(w) * (RADIUS + 7), MITTE.y + Math.sin(w) * (RADIUS + 7));
    p.lineTo(MITTE.x + Math.cos(w) * (RADIUS + 7 + laenge),
             MITTE.y + Math.sin(w) * (RADIUS + 7 + laenge));
    p.stroke();
  }
}

function boegen(farbe) {
  // Beim Nachdenken kein Ausschlag, sondern drei kreisende Boegen.
  p.lineCap = 'round'; p.lineWidth = 2.4;
  [[RADIUS + 16, 1.0, 110, 0.55], [RADIUS + 28, -0.7, 70, 0.42],
   [RADIUS + 40, 0.45, 40, 0.29]].forEach(([r, tempo, spanne, alpha]) => {
    const start = (S.tick * tempo * 200) % 360;
    p.strokeStyle = rgb(farbe, alpha);
    p.beginPath();
    p.arc(MITTE.x, MITTE.y, r, -start * Math.PI / 180,
          (-start - spanne) * Math.PI / 180, true);
    p.stroke();
  });
}

function ring(farbe, staerke) {
  p.strokeStyle = rgb(farbe, 0.85); p.lineWidth = 2;
  p.beginPath(); p.arc(MITTE.x, MITTE.y, RADIUS + staerke * 5, 0, 6.2832); p.stroke();
}

function kern(farbe, staerke) {
  const r = 6 + staerke * 9;
  const v = p.createRadialGradient(MITTE.x, MITTE.y, 0, MITTE.x, MITTE.y, r * 2.2);
  v.addColorStop(0, rgb(farbe, 0.9)); v.addColorStop(1, rgb(farbe, 0));
  p.fillStyle = v; p.beginPath(); p.arc(MITTE.x, MITTE.y, r * 2.2, 0, 6.2832); p.fill();
  p.fillStyle = 'rgba(235,245,255,.9)';
  p.beginPath(); p.arc(MITTE.x, MITTE.y, r * 0.45, 0, 6.2832); p.fill();
}

function zustandswort(farbe) {
  let wort = BESCHRIFTUNG[S.zustand] || '';
  if (S.zustand === 'ruhig' && S.nachhoeren > 0) wort = 'hört noch zu';
  p.save();
  p.font = '8px "Segoe UI",system-ui,sans-serif';
  p.textAlign = 'center'; p.textBaseline = 'middle';
  saum(wort.toUpperCase().split('').join(' '),
       MITTE.x, MITTE.y + RADIUS + 83, rgb(farbe, 0.92));
  p.restore();
}

/* Was gerade ohne Rueckfrage durchgeht -- gesperrte Versalschrift in
 * einer Farbe, die zu keinem Zustand gehoert: Die Freigabe laeuft
 * weiter, egal ob er zuhoert, denkt oder schweigt.
 *
 * UNTER dem Kranz, nicht dicht unter dem Ring wie in hud.py. Dort
 * (RADIUS+100) kreuzt die Zeile auf halber Hoehe den Kranz: Auf y 380
 * sitzen die Werkzeuge bei x 252 und 407, ihre Beschriftungen gehen
 * nach aussen, und dazwischen bleiben 155 Punkte fuer einen Text, der
 * gemessen 291 breit ist. Gerendert und angesehen -- "frei: Dateien
 * lesen ..." lag quer ueber E-MAIL und PROJEKTE. Genau der Fall, den
 * hud.py im Kommentar zum Hintergrund beschreibt ("drei Texte
 * uebereinander, keiner davon lesbar"); er trifft die Freigabe dort
 * ebenso, faellt nur selten auf, weil selten eine anliegt.
 *
 * KRANZ+30 liegt unter dem tiefsten Werkzeug (y 395) und ueber dem
 * Untertitel, der ohnehin ein eigenes Element unter der Buehne ist.
 * Damit steht die ganze Breite zur Verfuegung. */
function freigabewort() {
  p.save();
  p.font = '7px "Segoe UI",system-ui,sans-serif';
  p.textAlign = 'center'; p.textBaseline = 'middle';
  saum(gesperrt(freigabeKuerzen(S.freigabe.toUpperCase())),
       MITTE.x, MITTE.y + KRANZ + 30, 'rgba(255,186,92,.88)');
  p.restore();
}

// Gesperrt wird ueber eingeschobene Leerzeichen -- letterSpacing kennt
// die Leinwand erst seit Chrome 99 und Safari 17.4, und ein stiller
// Rueckfall auf ungesperrt saehe aus wie ein anderer Text.
const gesperrt = (t) => t.split('').join(' ');

// Der Text kommt vom Server und kann lang werden ("frei: Dateien lesen
// in dem Ordner websearch · 5 min +2"). Gesperrt ist er doppelt so
// breit. Lieber sichtbar abschneiden als ueber den Rand hinausschreiben
// -- ein stummer Schnitt am Rand sieht aus wie der ganze Text. hud.py
// laesst Qt am Rechteck schneiden und hat deshalb keine Marke.
const FREIGABE_BREITE = BREITE - 120;
function freigabeKuerzen(text) {
  if (p.measureText(gesperrt(text)).width <= FREIGABE_BREITE) return text;
  let t = text;
  while (t.length > 1
         && p.measureText(gesperrt(t + '…')).width > FREIGABE_BREITE) {
    t = t.slice(0, -1);
  }
  return t + '…';
}

function saum(text, x, y, farbe) {
  // Fuenfmal dunkel versetzt, dann einmal in Farbe -- derselbe Saum wie
  // in hud.py. Er ist der Grund, warum die Schrift ueber jedem
  // Untergrund lesbar bleibt.
  p.fillStyle = 'rgba(4,8,16,.55)';
  [[-1, 0], [1, 0], [0, -1], [0, 1], [1, 1]].forEach(([dx, dy]) =>
    p.fillText(text, x + dx, y + dy));
  p.fillStyle = farbe; p.fillText(text, x, y);
}

function schlag() {
  S.tick += 0.016;
  // Steigend schneller als fallend: Der Ring soll sofort ausschlagen,
  // aber nicht flackern.
  const k = S.pegel > S.geglaettet ? 0.45 : 0.12;
  S.geglaettet += (S.pegel - S.geglaettet) * k;
  S.verlauf.push((S.zustand === 'hoert' || S.zustand === 'spricht')
    ? S.geglaettet
    : Math.max(S.geglaettet, (S.verlauf[S.verlauf.length - 1] || 0) * 0.85));
  if (S.verlauf.length > VERLAUF_LAENGE) S.verlauf.shift();
  S.glut.forEach((v, k2) => { if (v > 0.001) S.glut.set(k2, v * 0.975); });
  if (S.hervor > 0) S.hervor -= 0.016;
  if (S.nachhoeren > 0) S.nachhoeren -= 0.016;
  if (S.freigabe) {
    S.freigabeRest -= 0.016;
    if (S.freigabeRest <= 0) S.freigabe = '';
  }
  malen();
  requestAnimationFrame(schlag);
}

// =====================================================================
// Kacheln und Hintergrund
// =====================================================================
const kachelraum = document.getElementById('kacheln');

/* NEUN FORMEN, EIN AUSSEHEN -- uebersetzt aus kachel.py.
 *
 * Uebersetzt, nicht neu erfunden: Die Zahlen dort sind gemessen, und die
 * Begruendungen daneben gelten hier genauso. Was hier steht, sind nur
 * die Stellen, an denen der Browser etwas anderes verlangt als QPainter.
 *
 * DIE BREITE IST DER EINE GROSSE UNTERSCHIED.
 * kachel.py darf sich seine Breite aussuchen -- ein eigenes Fenster ist
 * so breit, wie sein Inhalt es braucht (bis 800 beim Fluss). Hier steckt
 * die Kachel in einer Spalte: am Rechner rechts neben dem Ring, hoechstens
 * 290 Punkte breit, auf dem Handy darunter ueber die volle Breite (rund
 * 390). Beides ist WENIGER als die 800 des Flusses und die 708 des
 * Ablaufs, und ein Bild einfach herunterzuskalieren waere die schlechteste
 * aller Antworten: Bei Faktor 0,36 ist die Schrift 4 Punkte hoch, und ein
 * Diagramm, dessen Beschriftung niemand lesen kann, ist ein Muster.
 *
 * Deshalb wird nicht skaliert, sondern GERECHNET: Jede Form bekommt die
 * wirklich vorhandene Breite und legt ihr Inneres darin aus. Was dabei je
 * Form entschieden wurde, steht bei der Form.
 *
 * KEIN HERVORHEBEN. kachel.py kann eine Zeile leuchten lassen (hervor),
 * aber ueber den Draht geht dafuer nichts -- leuchten() ist Qt-intern.
 * Was hier nicht ankommen kann, wird auch nicht gebaut.
 */

// --- Schriften ---------------------------------------------------------
// Messen und Malen holen sich ihre Schrift HIER, aus demselben Grund wie
// _schrift_klein() drueben: Stuenden die Zeilen an zwei Stellen, waere
// der Tag absehbar, an dem eine davon springt und der Umbruch nicht mehr
// zum Kasten passt.
const SCHRIFT_KLEIN = '11px "Segoe UI",system-ui,-apple-system,sans-serif';
const SCHRIFT_FUSS = '9px "Segoe UI",system-ui,-apple-system,sans-serif';
const ZH = 14;          // Zeilenhoehe der Datenschrift
const ZF = 12;          // ... der Fussschrift
const GRUND = [8, 13, 20];   // der Kachelgrund, gegen den gerechnet wird
/* WELCHER TEXT WELCHE FARBE TRAEGT.
   kachel.py schreibt ALLES in der Kachelfarbe -- dort ist eine Kachel
   ein eigenes Fenster ueber einem fremden Bildschirm, und die eine
   Farbe ist das, was sie zusammenhaelt. Hier liegt sie in Sarvis'
   eigener Oberflaeche, und die vorhandene Form "liste" setzt ihre
   Zeilen seit jeher in die Schriftfarbe der Seite. Zwei Regeln in
   einer Kachel saehen aus wie zwei Kacheln, also gilt durchgehend:

     Text, den man LIEST (Bezeichnungen, Betraege, Fliesstext,
     Nachrichten)                        -> Schriftfarbe der Seite
     Alles GEZEICHNETE und die Beschriftung AM Bild (Achsen, Marken,
     Zwischenueberschriften, Raender, Flaechen, Baender)
                                         -> Kachelfarbe

   Im Fluss faellt beides zusammen -- die Beschriftung liegt AUF dem
   Band. Dort wird gerechnet statt gewaehlt, siehe schriftAuf(). */
const TINTE = [232, 241, 253];

// Die Marken. Ein stummer Schnitt sieht aus wie ein vollstaendiger Text.
const MARKE = '[… gekürzt]';
const MARKE_ALT = '[… ältere ausgeblendet]';
const MARKE_OHNE = '[… ohne negative Werte]';
const MARKE_KANTEN = '[… unvollständige Bänder weggelassen]';
const MARKE_KREIS = '[… Kreis aufgetrennt]';
const MARKE_TIEF = '[… tiefere Stufen weggelassen]';

const _messer = document.createElement('canvas').getContext('2d');
function misst(text, schrift) {
  _messer.font = schrift || SCHRIFT_KLEIN;
  return _messer.measureText(String(text == null ? '' : text)).width;
}

/* Wortweiser Umbruch -- wie _umbrechen() drueben, und aus demselben Grund
 * selbst gemacht: Der Browser bricht erst beim Malen um, und dann ist es
 * zu spaet. Die Hoehe der Blase, der Deckel des Fliesstextes und die Zahl
 * der Zeilen in einem Ablauf-Kasten stehen VORHER fest oder gar nicht.
 *
 * Ein Wort, das allein nicht passt, wird hart getrennt: Eine URL liefe
 * sonst aus der Blase heraus und waere zur Haelfte weg. */
function umbrechen(text, breite, schrift) {
  const zeilen = [];
  for (const absatz of String(text == null ? '' : text).split('\n')) {
    const worte = absatz.split(/\s+/).filter(Boolean);
    if (!worte.length) { zeilen.push(''); continue; }
    let zeile = '';
    for (let wort of worte) {
      const probe = zeile ? zeile + ' ' + wort : wort;
      if (misst(probe, schrift) <= breite) { zeile = probe; continue; }
      if (zeile) { zeilen.push(zeile); zeile = ''; }
      while (misst(wort, schrift) > breite && wort.length > 1) {
        let n = 1;
        while (n < wort.length && misst(wort.slice(0, n + 1), schrift) <= breite) n++;
        zeilen.push(wort.slice(0, n));
        wort = wort.slice(n);
      }
      zeile = wort;
    }
    if (zeile) zeilen.push(zeile);
  }
  return zeilen;
}

function kuerzen(text, breite, schrift) {
  text = String(text == null ? '' : text);
  if (breite <= 0) return '';
  if (misst(text, schrift) <= breite) return text;
  let n = text.length;
  while (n > 0 && misst(text.slice(0, n) + '…', schrift) > breite) n--;
  return n > 0 ? text.slice(0, n) + '…' : '';
}

// --- Zahlen -------------------------------------------------------------
const zahlVon = v => (typeof v === 'number' && isFinite(v)) ? v : null;

/* 1234.5 -> "1.234,50". Ohne Vorzeichen, das setzt der Aufrufer.
   Zwei Nachkommastellen nur, wenn es welche gibt. */
function zahlDeutsch(wert) {
  const stellen = Math.abs(wert - Math.round(wert)) < 0.005 ? 0 : 2;
  return Math.abs(wert).toLocaleString('de-DE',
    { minimumFractionDigits: stellen, maximumFractionDigits: stellen });
}

/* Unter zehn Prozent eine Nachkommastelle, darueber keine. Was auf null
   runden wuerde, wird "<0,1 %": Eine gemalte Null neben einem sichtbaren
   Stueck waere ein Widerspruch. */
function prozentText(anteil) {
  const p = anteil * 100;
  if (p <= 0) return '0 %';
  if (p < 0.1) return '<0,1 %';
  if (p < 10) return p.toFixed(1).replace('.', ',') + ' %';
  return p.toFixed(0) + ' %';
}

/* Die Differenz rechnet die Kachel SELBST -- eine gerechnete Zahl kann
   nicht halluziniert sein, eine uebergebene schon. Fehlt eine der beiden
   Zahlen, wird nichts behauptet. */
function differenz(a, b) {
  a = zahlVon(a); b = zahlVon(b);
  if (a === null || b === null) return { text: '', richtung: 0 };
  const d = a - b;
  if (Math.abs(d) < 0.005) return { text: '±0', richtung: 0 };
  // Echtes Minuszeichen, kein Bindestrich: der ist neben einer Ziffer
  // zu kurz, um aufzufallen.
  return { text: (d > 0 ? '+' : '−') + zahlDeutsch(d), richtung: d > 0 ? 1 : -1 };
}

// --- Farbe ---------------------------------------------------------------
const FARBE_MEHR = [126, 224, 168];      // mehr, NICHT "gut"
const FARBE_WENIGER = [255, 138, 128];   // weniger, NICHT "schlecht"

function nachHsv(c) {
  const r = c[0] / 255, g = c[1] / 255, b = c[2] / 255;
  const max = Math.max(r, g, b), min = Math.min(r, g, b), d = max - min;
  let h = 0;
  if (d > 1e-9) {
    if (max === r) h = ((g - b) / d) % 6;
    else if (max === g) h = (b - r) / d + 2;
    else h = (r - g) / d + 4;
    h /= 6;
    if (h < 0) h += 1;
  } else h = -1;                          // unbunt
  return [h, max > 0 ? d / max : 0, max];
}

function ausHsv(h, s, v) {
  if (h < 0 || s <= 0) { const w = Math.round(v * 255); return [w, w, w]; }
  const i = Math.floor(h * 6), f = h * 6 - i;
  const p = v * (1 - s), q = v * (1 - f * s), t = v * (1 - (1 - f) * s);
  const tab = [[v, t, p], [q, v, p], [p, v, t], [p, q, v], [t, p, v], [v, p, q]];
  return tab[i % 6].map(x => Math.round(Math.max(0, Math.min(1, x)) * 255));
}

/* Die i-te Abstufung der Kachelfarbe -- kein Regenbogen.
 *
 * Drei Groessen wandern gleichzeitig (Ton, Saettigung, Helligkeit) statt
 * nur der Helligkeit: Wandert nur eine, faellt die ganze Unterscheidung
 * aus, sobald sie fuer einen Betrachter ausfaellt.
 *
 * Vergeben wird UEBER KREUZ (0, 4, 1, 5, …), damit zwei im Kreis
 * benachbarte Stuecke moeglichst weit auseinanderliegen. Der Reihe nach
 * lagen bei acht Stuecken zwei Nachbarn 1,08:1 auseinander -- die Kante
 * zwischen ihnen war keine. */
function stufe(farbe, i, anzahl) {
  if (anzahl <= 1) return farbe.slice();
  const [h, s, v] = nachHsv(farbe);
  const platz = (i % 2) * Math.ceil(anzahl / 2) + Math.floor(i / 2);
  const anteil = platz / (anzahl - 1);
  if (h < 0) return ausHsv(-1, 0, Math.max(0, v * (1 - 0.62 * anteil)));
  return ausHsv((h + 0.055 * anteil) % 1,
    Math.max(0, Math.min(1, s * (1 - 0.38 * anteil))),
    Math.max(0, Math.min(1, v * (1 - 0.58 * anteil))));
}

/* Relative Helligkeit nach WCAG -- nicht (r+g+b)/3: Gruen traegt zur
   empfundenen Helligkeit gut siebenmal so viel bei wie Blau, und ein
   Mittelwert schaetzte ausgerechnet die beiden Kachelfarben falsch ein,
   weil die eine orange und die andere gruen ist. */
function leuchtdichte(c) {
  const k = v => { v /= 255; return v <= 0.04045 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
  return 0.2126 * k(c[0]) + 0.7152 * k(c[1]) + 0.0722 * k(c[2]);
}

/* Was man WIRKLICH sieht, wenn ton mit dieser Deckung ueber dem
   Kachelgrund liegt. Ein Band ist halbdurchsichtig; seine Farbe allein
   sagt nichts darueber, wie hell die Stelle am Ende ist. */
function ueberGrund(ton, deckung) {
  const rest = 1 - deckung;
  return ton.map((v, i) => Math.round(v * deckung + GRUND[i] * rest));
}

/* Welche Schrift auf DIESEM Grund noch zu lesen ist.
 *
 * Die Kachelfarbe bleibt, solange sie traegt -- eine Kachel, in der die
 * Beschriftung mal orange und mal weiss ist, sieht aus wie zwei Kacheln.
 * Erst wenn sie MESSBAR nicht mehr traegt, wird gewechselt. Die Schwelle
 * ist die 4,5:1 aus WCAG fuer normalen Fliesstext, nicht die 3,0:1 fuer
 * grosse Schrift: Hier steht 11 px, und das ist keine grosse Schrift. */
function schriftAuf(grund, kerze) {
  const hell = leuchtdichte(grund);
  const kontrast = c => {
    const dort = leuchtdichte(c);
    return (Math.max(hell, dort) + 0.05) / (Math.min(hell, dort) + 0.05);
  };
  if (kontrast(kerze) >= 4.5) return kerze;
  const dunkel = GRUND, weiss = [245, 248, 252];
  return kontrast(dunkel) >= kontrast(weiss) ? dunkel : weiss;
}

// --- Raenge: die eine Rechnung, die sich Fluss und Ablauf teilen ---------
/* Spalte (Fluss) bzw. Zeile (Ablauf) je Knoten -- der LAENGSTE Weg von
 * vorn, nicht der kuerzeste: Nur so zeigt jede Kante nach vorn. Beim
 * kuerzesten landet ein Knoten neben seinem eigenen Vorgaenger.
 *
 * DER KREIS IST DER PUNKT DIESER FUNKTION. Ein Modell kann "A -> B -> A"
 * schicken -- kein boeser Wille, sondern zwei Buchungen, die es beide
 * gesehen hat. Eine Rangrechnung, die einfach entspannt, bis sich nichts
 * mehr aendert, laeuft dann bis zum Stillstand der Anzeige. Gezaehlt
 * werden deshalb die offenen Eingaenge; bleiben nur noch Knoten im Kreis,
 * wird der mit den wenigsten aufgemacht und seine restlichen Eingaenge
 * werden AUFGETRENNT -- weggelassen und vermerkt. */
function raenge(knoten, kanten) {
  const aus = new Map(), ein = new Map(), rang = new Map();
  knoten.forEach(k => { aus.set(k, []); ein.set(k, 0); rang.set(k, 0); });
  kanten.forEach(([a, b], nr) => {
    if (!aus.has(a) || !ein.has(b)) return;
    aus.get(a).push(nr); ein.set(b, ein.get(b) + 1);
  });
  const fertig = new Set(), getrennt = new Set();
  const schlange = knoten.filter(k => ein.get(k) === 0);
  while (fertig.size < knoten.length) {
    if (!schlange.length) {
      const offen = knoten.filter(k => !fertig.has(k));
      let naechster = offen[0];
      for (const k of offen) if (ein.get(k) < ein.get(naechster)) naechster = k;
      kanten.forEach(([a, b], nr) => {
        if (b === naechster && !getrennt.has(nr) && !fertig.has(a)) {
          getrennt.add(nr); ein.set(naechster, ein.get(naechster) - 1);
        }
      });
      schlange.push(naechster);
    }
    const k = schlange.shift();
    if (fertig.has(k)) continue;
    fertig.add(k);
    for (const nr of aus.get(k)) {
      if (getrennt.has(nr)) continue;
      const b = kanten[nr][1];
      rang.set(b, Math.max(rang.get(b), rang.get(k) + 1));
      ein.set(b, ein.get(b) - 1);
      if (ein.get(b) <= 0 && !fertig.has(b)) schlange.push(b);
    }
  }
  return [rang, getrennt];
}

// --- Bausteine, die mehrere Formen brauchen -----------------------------
const markenZeilen = (marken, farbe) => marken
  .map(t => `<div class="marke" style="color:${rgb(farbe, 0.45)}">${sicher(t)}</div>`)
  .join('');

const svgText = (x, y, text, farbe, opt) => {
  const o = opt || {};
  return `<text x="${x.toFixed(1)}" y="${y.toFixed(1)}" fill="${farbe}"`
    + ` font-family="Segoe UI,system-ui,sans-serif"`
    + ` font-size="${o.gross || 11}"`
    + (o.gewicht ? ` font-weight="${o.gewicht}"` : '')
    + (o.sperr ? ` letter-spacing="${o.sperr}"` : '')
    + ` text-anchor="${o.anker || 'start'}" dominant-baseline="central"`
    + `>${sicher(text)}</text>`;
};

// =====================================================================
// 1  liste -- Zeilen mit Wert rechts und Balken hinter der Schrift
// =====================================================================
function formListe(punkte, farbe) {
  const zahlen = punkte.map(x => zahlVon(x.zahl)).filter(x => x !== null && x > 0);
  const groesste = zahlen.length ? Math.max(...zahlen) : 0;
  return punkte.map(x => {
    const z = zahlVon(x.zahl);
    // Nur positive Zahlen bekommen einen Balken: Einer fuer minus achtzig
    // muesste in die andere Richtung zeigen, und solange diese Ueberlegung
    // nicht angestellt ist, lieber keiner als ein falscher.
    const breite = (groesste && z !== null && z > 0) ? (100 * z / groesste) : 0;
    return `<div class="zeile">
      ${breite ? `<i class="balken" style="width:${breite}%;background:${rgb(farbe, 1)}"></i>` : ''}
      <span>${sicher(x.text)}</span><span>${sicher(x.wert)}</span></div>`;
  }).join('');
}

// =====================================================================
// 2  blasen -- Gespraechsblasen, links der andere, rechts ich
// =====================================================================
/* Die Seite ist die Auskunft darueber, wer geschrieben hat -- die
 * Sehgewohnheit aus jedem Messenger, und sie kostet keine Zeile Text.
 * Damit sie auch bei gleich breiten Blasen traegt, unterscheiden sie sich
 * zusaetzlich: meine ist gefuellt, seine traegt einen Balken an der Kante.
 *
 * Gekappt wird OBEN, am Aelteren: Ein Verlauf wird von unten gelesen. */
function formBlasen(punkte, farbe, W) {
  const ANTEIL = 0.78, R = 7, LUFT = 7, MAXZEILEN = 7, DECKEL = 340;
  const innen = Math.round(W * ANTEIL) - 2 * R;
  const blasen = punkte.map(pt => {
    let zeilen = umbrechen(pt.text, innen);
    if (!zeilen.length) zeilen = [''];
    if (zeilen.length > MAXZEILEN) zeilen = zeilen.slice(0, MAXZEILEN - 1).concat([MARKE]);
    // So breit wie ihre laengste Zeile, nicht so breit wie erlaubt: Ein
    // "ja" in einem 250 Punkte breiten Kasten sieht aus wie ein Fehler.
    const breit = Math.min(innen, Math.max(...zeilen.map(z => misst(z))));
    return {
      zeilen, wert: String(pt.wert || ''), mir: !!pt.von_mir,
      breite: Math.ceil(breit) + 2 * R, hoehe: zeilen.length * ZH + 2 * R,
      // Die Zeit steht UNTER der Blase, nicht darin: darin konkurriert
      // sie mit dem Text um die Breite, und bei kurzen Nachrichten
      // gewinnt sie.
      fuss: pt.wert ? ZF : 0,
    };
  });

  let platz = DECKEL, gekappt = false;
  const behalten = [];
  for (let i = blasen.length - 1; i >= 0; i--) {
    const braucht = blasen[i].hoehe + blasen[i].fuss + (behalten.length ? LUFT : 0);
    if (braucht > platz && behalten.length) { gekappt = true; break; }
    platz -= braucht;
    behalten.unshift(blasen[i]);
  }

  return (gekappt ? `<div class="marke" style="color:${rgb(farbe, 0.45)}">${MARKE_ALT}</div>` : '')
    + behalten.map(b => {
      const grund = rgb(farbe, b.mir ? 0.22 : 0.12);
      const kante = b.mir ? '' : `box-shadow:inset 2.5px 0 0 ${rgb(farbe, 0.70)};`;
      return `<div class="blase${b.mir ? ' mir' : ''}" style="width:${b.breite}px;background:${grund};${kante}">`
        + b.zeilen.map(z => `<div>${sicher(z) || '&nbsp;'}</div>`).join('')
        + `</div>`
        + (b.fuss ? `<div class="blasenzeit${b.mir ? ' mir' : ''}">${sicher(b.wert)}</div>` : '');
    }).join('');
}

// =====================================================================
// 3  vergleich -- zwei Wertspalten und eine selbst gerechnete Differenz
// =====================================================================
/* Drueben stehen feste Spaltenbreiten (68 / 68 / 74), weil QFontMetrics
 * dort einmal misst und das Fenster danach 360 breit ist. Hier gibt es
 * die 360 nicht -- also uebernimmt das Raster die Aufteilung: Die drei
 * Zahlenspalten bekommen, was sie brauchen, die Bezeichnung den Rest und
 * kuerzt sich selbst. Das ist dieselbe Rangfolge wie drueben (Zahlen
 * vollstaendig, Name notfalls gekuerzt), nur vom Browser gemessen. */
function formVergleich(punkte, farbe, W, m) {
  const spalten = (m.spalten || []).map(String);
  const kopf = spalten.length
    ? `<div class="k n"></div>`
    + `<div class="k z">${sicher(spalten[0] || '')}</div>`
    + `<div class="k z">${sicher(spalten[1] || '')}</div>`
    + `<div class="k z">Differenz</div>`
    : '';
  const zeilen = punkte.map(pt => {
    const d = differenz(pt.zahl, pt.zahl2);
    let dz = '';
    if (d.text) {
      const c = d.richtung === 0 ? rgb(farbe, 0.55)
        : rgb(d.richtung > 0 ? FARBE_MEHR : FARBE_WENIGER, 0.95);
      // Die Farbe ist nie das einzige Zeichen: Rot und Gruen sind fuer
      // rund jeden zwoelften Mann dieselbe Farbe. Vor der Zahl steht ihr
      // Vorzeichen, davor ein Dreieck in dieselbe Richtung -- und selbst
      // gemalt, nicht als Zeichen aus einer Schrift, die fehlen kann.
      const pfeil = d.richtung === 0 ? '' :
        `<svg width="7" height="6" viewBox="0 0 7 6" aria-hidden="true"><polygon points="${
          d.richtung > 0 ? '0,5 7,5 3.5,0' : '0,1 7,1 3.5,6'}" fill="${c}"/></svg>`;
      dz = `<span style="color:${c}">${pfeil}${sicher(d.text)}</span>`;
    }
    return `<div class="n">${sicher(pt.text)}</div>`
      + `<div class="z">${sicher(pt.wert)}</div>`
      + `<div class="z">${sicher(pt.wert2)}</div>`
      + `<div class="z d">${dz}</div>`;
  }).join('');
  return `<div class="vgl">${kopf}${zeilen}</div>`;
}

// =====================================================================
// 4  text -- Fliesstext fuer eine Zusammenfassung oder einen Auszug
// =====================================================================
function formText(punkte, farbe, W) {
  const DECKEL = 18;
  let zeilen = [];
  punkte.forEach(pt => {
    if (zeilen.length) zeilen.push('');        // Absatzabstand
    zeilen = zeilen.concat(umbrechen(pt.text, W));
  });
  // Die Marke ERSETZT die letzte Zeile, sie kommt nicht dazu: sonst waere
  // die gekuerzte Fassung hoeher als der Deckel.
  if (zeilen.length > DECKEL) zeilen = zeilen.slice(0, DECKEL - 1).concat([MARKE]);
  return `<div class="fliess">`
    + zeilen.map(z => z === MARKE
      ? `<div class="marke" style="color:${rgb(farbe, 0.45)}">${sicher(z)}</div>`
      : `<div>${sicher(z) || '&nbsp;'}</div>`).join('')
    + `</div>`;
}

// =====================================================================
// 5  balken -- senkrechte Saeulen mit Grundlinie
// =====================================================================
/* DIE GRUNDLINIE LIEGT NICHT AM BODEN, sondern dort, wo die Null liegt:
 * Sind Ausgaben und Einnahmen in einem Bild, geht ein Teil der Balken
 * nach unten. Beide Richtungen teilen sich die Hoehe im Verhaeltnis ihrer
 * Betraege. Zwei getrennte Massstaebe waeren bequemer zu rechnen und eine
 * Luege: Dann waere ein Minus von 20 so lang wie ein Plus von 2.000.
 *
 * NACH UNTEN WIRD NICHT ROT, sondern UMRISSEN. Die Richtung sagt es
 * schon; eine zweite Farbe daneben waere ausgerechnet das Paar
 * Gruen/Rot, das rund jeder zwoelfte Mann nicht trennt. Die Form bleibt
 * auch in Graustufen stehen.
 *
 * DIE BESCHRIFTUNG duennt in drei Stufen aus: ungekuerzt, sonst drei
 * Zeichen, sonst nur noch jeder n-te Balken. Drei Zeichen ohne
 * Auslassungspunkte -- bei dieser Groesse frisst das "…" ein Drittel des
 * Platzes, und "Ja…" sagt weniger als "Jan". */
function formBalken(punkte, farbe, W) {
  if (!punkte.length) return '';           // Kein Balken, keine Achse.
  const HOCH = 96, FUSS = 3, SCHMAL = 3, SCHRITTE = [2, 3, 4, 6];
  const n = punkte.length;
  const fach = W / n;
  const luft = Math.max(2, Math.min(5, fach * 0.22));
  const breit = Math.max(SCHMAL, fach - luft);

  const zahlen = punkte.map(p => zahlVon(p.zahl));
  const pos = zahlen.filter(z => z !== null && z > 0);
  const neg = zahlen.filter(z => z !== null && z < 0);
  const dach = pos.length ? Math.max(...pos) : 0;
  const boden = neg.length ? Math.min(...neg) : 0;
  const spanne = dach - boden;
  const nulllinie = spanne > 0 ? HOCH * (dach / spanne) : HOCH;

  const voll = punkte.map(p => String(p.text || ''));
  const kurz = voll.map(t => t.slice(0, 3));
  const passt = (texte, schritt) => {
    const platz = fach * schritt - 2;
    for (let i = 0; i < n; i += schritt)
      if (misst(texte[i], SCHRIFT_FUSS) > platz) return false;
    return true;
  };
  let texte = voll, schritt = 1;
  if (!passt(voll, 1)) {
    texte = kurz;
    if (!passt(kurz, 1)) schritt = SCHRITTE.find(s => passt(kurz, s)) || SCHRITTE[SCHRITTE.length - 1];
  }

  // Der hoechste und der tiefste Balken werden angeschrieben. Ohne das
  // waere die Kachel ein Muster: Man saehe, dass Juli groesser ist als
  // Juni, aber nicht, ob es um 30 oder 3.000 Euro geht.
  let obenI = -1, untenI = -1;
  zahlen.forEach((z, i) => {
    if (z === null) return;
    if (z > 0 && (obenI < 0 || z > zahlen[obenI])) obenI = i;
    if (z < 0 && (untenI < 0 || z < zahlen[untenI])) untenI = i;
  });
  const geschrieben = i => {
    if (punkte[i].wert) return String(punkte[i].wert);
    const z = zahlen[i];
    return z === null ? '' : (z < 0 ? '−' : '') + zahlDeutsch(z);
  };

  const yF = ZF + 2, yNull = yF + nulllinie;
  let yM = yF + HOCH + FUSS;
  const H = yM + ZF + (untenI >= 0 ? ZF : 0);

  let s = '';
  zahlen.forEach((z, i) => {
    if (z === null || spanne <= 0 || Math.abs(z) < 1e-9) return;   // keine gemalte Null
    const laenge = HOCH * (Math.abs(z) / spanne);
    const x = i * fach + (fach - breit) / 2;
    if (z > 0) {
      s += `<rect x="${x.toFixed(1)}" y="${(yNull - laenge).toFixed(1)}" width="${breit.toFixed(1)}" height="${laenge.toFixed(1)}" fill="${rgb(farbe, 0.58)}"/>`;
    } else {
      s += `<rect x="${(x + 0.5).toFixed(1)}" y="${(yNull + 0.5).toFixed(1)}" width="${Math.max(1, breit - 1).toFixed(1)}" height="${Math.max(1, laenge - 1).toFixed(1)}" fill="${rgb(farbe, 0.16)}" stroke="${rgb(farbe, 0.62)}" stroke-width="1"/>`;
    }
  });
  // Die Grundlinie zuletzt und ueber den Balken: Sie ist die Achse, an
  // der abgelesen wird, und darf von keinem Balken verdeckt werden.
  s += `<line x1="0" y1="${yNull.toFixed(1)}" x2="${W}" y2="${yNull.toFixed(1)}" stroke="${rgb(farbe, 0.55)}" stroke-width="1"/>`;

  const anschreiben = (text, mitte, oben) => {
    const b = misst(text, SCHRIFT_FUSS) + 2;
    const x = Math.min(Math.max(mitte - b / 2, 0), Math.max(0, W - b)) + b / 2;
    return svgText(x, oben + ZF / 2, text, rgb(farbe, 0.80), { gross: 9, anker: 'middle' });
  };
  if (obenI >= 0) s += anschreiben(geschrieben(obenI), (obenI + 0.5) * fach, 0);
  if (untenI >= 0) { s += anschreiben(geschrieben(untenI), (untenI + 0.5) * fach, yM); yM += ZF; }

  texte.forEach((t, i) => {
    if (i % schritt !== 0 || !t) return;
    const platz = fach * schritt - 2;
    s += svgText((i + 0.5) * fach, yM + ZF / 2, kuerzen(t, platz, SCHRIFT_FUSS),
      rgb(farbe, 0.62), { gross: 9, anker: 'middle' });
  });

  return `<svg class="bild" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}">${s}</svg>`;
}

// =====================================================================
// 6  torte -- Kreis und Legende
// =====================================================================
/* KEIN STUECK WIRD AUFGEBLASEN. Ein Bild, das 0,5 Prozent wie 5 Prozent
 * aussehen laesst, behauptet etwas Falsches -- und zwar lautlos. Eine
 * Prozentzahl steht nur IM Stueck, wenn der Winkel mindestens 30 Grad
 * hat UND die Sehne auf dem Beschriftungsradius breit genug ist.
 *
 * NEGATIVE UND FEHLENDE WERTE bekommen kein Stueck: Ein negativer Anteil
 * ist keiner. Sie stehen aber mit ihrem Betrag in der Legende, ohne
 * Prozentzahl und mit leerem Kaestchen, und eine Marke sagt, dass die
 * 100 Prozent sie nicht enthalten.
 *
 * WO DIE LEGENDE STEHT, entscheidet die Breite. Drueben stehen Kreis und
 * Legende immer nebeneinander, weil das Fenster dafuer 320 breit sein
 * darf: 104 Kreis + 14 Luft + 174 Legende. Hier sind am Rechner nur rund
 * 264 Punkte da -- nebeneinander bliebe der Legende 146, und aus
 * "Lebensmittel 612,40 21 %" wuerde "Lebens… 612,40 21 %". Also: unter
 * 300 Punkten Kreis oben, Legende darunter ueber die volle Breite. Auf
 * dem Handy (rund 364) passt beides nebeneinander, und dort steht es
 * auch so. */
function formTorte(punkte, farbe, W) {
  if (!punkte.length) return '';
  const AUS = 4, LUFT = 14, ZEILE = 16;
  const stapeln = W < 300;
  const RING = stapeln ? 124 : 104;
  const rad = (RING - 2 * AUS) / 2;

  const werte = punkte.map(p => { const z = zahlVon(p.zahl); return (z !== null && z > 0) ? z : null; });
  const summe = werte.reduce((s, w) => s + (w || 0), 0);
  const fehlt = werte.some(w => w === null);
  const ring = summe > 0;
  const anzahl = punkte.length;

  // Die Winkel entstehen als Fliesskommagrad und werden AUFSUMMIERT
  // weitergereicht: Rundet man acht Stuecke einzeln, fehlen am Ende ein
  // paar Zehntelgrad, und der Kreis hat einen feinen Spalt bei zwoelf Uhr.
  let winkel = 90;
  const stuecke = werte.map((w, i) => {
    const anteil = (w !== null && summe > 0) ? w / summe : 0;
    const spanne = -360 * anteil;
    const prozent = w !== null ? prozentText(anteil) : '';
    const halb = rad * 0.62;
    const sehne = 2 * halb * Math.sin(Math.abs(spanne) * Math.PI / 360);
    const st = {
      i, start: winkel, spanne, prozent, stueck: w !== null,
      innen: (w !== null && Math.abs(spanne) >= 30
        && sehne >= misst(prozent) + 4) ? prozent : '',
    };
    winkel += spanne;
    return st;
  });

  let kreis = '';
  if (ring) {
    const cx = RING / 2, cy = RING / 2;
    const punktAuf = (a, r) => [cx + r * Math.cos(a * Math.PI / 180),
    cy - r * Math.sin(a * Math.PI / 180)];
    let pfade = '';
    stuecke.forEach(st => {
      if (!st.stueck || Math.abs(st.spanne) < 1e-9) return;
      const f = rgb(stufe(farbe, st.i, anzahl), 0.86);
      if (Math.abs(st.spanne) >= 359.99) {
        pfade += `<circle cx="${cx}" cy="${cy}" r="${rad}" fill="${f}"/>`;
        return;
      }
      const [x0, y0] = punktAuf(st.start, rad);
      const [x1, y1] = punktAuf(st.start + st.spanne, rad);
      const gross = Math.abs(st.spanne) > 180 ? 1 : 0;
      // Die Fuge zwischen zwei Stuecken hat die Farbe des Grundes. Sie
      // ist der eigentliche Grund, warum benachbarte Abstufungen
      // auseinanderzuhalten sind: Selbst wenn zwei Toene fuer jemanden
      // gleich aussehen, bleibt die Kante sichtbar.
      pfade += `<path d="M${cx},${cy} L${x0.toFixed(2)},${y0.toFixed(2)}`
        + ` A${rad},${rad} 0 ${gross} 1 ${x1.toFixed(2)},${y1.toFixed(2)} Z"`
        + ` fill="${f}" stroke="${rgb(GRUND, 0.85)}" stroke-width="1"/>`;
    });
    // Die Prozentzahlen zuletzt, damit keine Fuge darueber laeuft.
    stuecke.forEach(st => {
      if (!st.innen) return;
      const a = (st.start + st.spanne / 2) * Math.PI / 180;
      const x = cx + Math.cos(a) * rad * 0.62, y = cy - Math.sin(a) * rad * 0.62;
      // Auf dunklen Stuecken hell schreiben, auf hellen dunkel -- sonst
      // verschwindet die Zahl in der eigenen Abstufung.
      const g = stufe(farbe, st.i, anzahl);
      const c = (Math.max(g[0], g[1], g[2]) / 255 > 0.62) ? GRUND : [245, 248, 252];
      pfade += svgText(x, y, st.innen, rgb(c, 0.95), { anker: 'middle' });
    });
    kreis = `<svg class="bild ring" viewBox="0 0 ${RING} ${RING}" width="${RING}" height="${RING}">${pfade}</svg>`;
  }

  const legende = stuecke.map(st => {
    const pt = punkte[st.i];
    const tupf = st.stueck
      ? `<i class="tupf" style="background:${rgb(stufe(farbe, st.i, anzahl), 1)}"></i>`
      // Kein Stueck, kein Tupfer: ein leeres Kaestchen sagt, dass dieser
      // Posten im Kreis nicht vorkommt.
      : `<i class="tupf leer" style="border-color:${rgb(farbe, 0.35)}"></i>`;
    return `<div class="leg">${tupf}<span class="nm">${sicher(pt.text)}</span>`
      + `<span class="wt">${sicher(pt.wert)}</span>`
      + `<span class="pz">${sicher(st.prozent)}</span></div>`;
  }).join('');

  return `<div class="torte${stapeln ? ' hoch' : ''}">`
    + kreis + `<div class="legende">${legende}</div></div>`
    + (fehlt ? `<div class="marke" style="color:${rgb(farbe, 0.45)}">${MARKE_OHNE}</div>` : '');
}

// =====================================================================
// 7  kategorien -- Zwischenueberschriften und Gruppensummen
// =====================================================================
/* Gruppiert wird in der Reihenfolge des ERSTEN Auftretens, nicht
 * alphabetisch: Der Aufrufer hat eine Reihenfolge im Kopf.
 *
 * Die Gruppensumme rechnet die Kachel -- aber nur, wenn JEDER Eintrag
 * der Gruppe eine Zahl hat. Eine Summe ueber unvollstaendige Posten
 * sieht aus wie ein Ergebnis und ist keines.
 *
 * Gekappt wird UNTEN, anders als bei den Blasen: Ein Verlauf wird von
 * unten gelesen, eine aufgeschluesselte Ausgabenliste von oben.
 *
 * Der Balken hinter der Schrift misst sich am groessten Posten
 * UEBERHAUPT, nicht am groessten der eigenen Gruppe -- sonst saehen die
 * 40 Euro Freizeit aus wie die 1.098 Euro Wohnen. */
function formKategorien(punkte, farbe) {
  if (!punkte.length) return '';
  const KOPF = 18, LUFT = 6, ZEILE = 15, DECKEL = 360;
  const ordnung = [], mitglieder = new Map();
  punkte.forEach((pt, i) => {
    const g = String(pt.gruppe || '');
    if (!mitglieder.has(g)) { mitglieder.set(g, []); ordnung.push(g); }
    mitglieder.get(g).push(i);
  });
  const zahlen = punkte.map(p => zahlVon(p.zahl));

  const reihen = [];
  ordnung.forEach((g, nr) => {
    const leute = mitglieder.get(g);
    // Punkte ohne Gruppe stehen ohne Ueberschrift da. Eine erfundene
    // Ueberschrift ("Sonstiges") waere eine Auskunft, die niemand gab.
    if (g) {
      const teile = leute.map(i => zahlen[i]);
      const summe = teile.every(t => t !== null) ? teile.reduce((a, b) => a + b, 0) : null;
      reihen.push({
        art: 'kopf', text: g,
        summe: summe === null ? '' : (summe < -0.005 ? '−' : '') + zahlDeutsch(summe),
        hoehe: KOPF + (nr ? LUFT : 0),
      });
    }
    leute.forEach(i => reihen.push({ art: 'zeile', punkt: i, hoehe: ZEILE }));
  });

  let hoehe = 0, gekappt = false;
  const behalten = [];
  for (const r of reihen) {
    if (hoehe + r.hoehe > DECKEL) { gekappt = true; break; }
    hoehe += r.hoehe; behalten.push(r);
  }
  if (gekappt) {
    // Platz fuer die Marke freiraeumen statt sie anzuhaengen -- und keine
    // Ueberschrift ohne Zeilen stehen lassen: Die sagt nur, dass etwas
    // fehlt, ohne zu zeigen, was.
    while (behalten.length && (hoehe + ZH > DECKEL || behalten[behalten.length - 1].art === 'kopf'))
      hoehe -= behalten.pop().hoehe;
  }

  const groesste = Math.max(0, ...zahlen.filter(z => z !== null && z > 0));
  return behalten.map(r => {
    if (r.art === 'kopf')
      return `<div class="grkopf" style="color:${rgb(farbe, 0.62)};border-color:${rgb(farbe, 0.22)}">`
        + `<span>${sicher(r.text)}</span><span>${sicher(r.summe)}</span></div>`;
    const pt = punkte[r.punkt], z = zahlen[r.punkt];
    const breite = (groesste > 0 && z !== null && z > 0) ? 100 * Math.min(1, z / groesste) : 0;
    return `<div class="zeile ein">`
      + (breite ? `<i class="balken" style="width:${breite}%;background:${rgb(farbe, 1)}"></i>` : '')
      + `<span>${sicher(pt.text)}</span><span>${sicher(pt.wert)}</span></div>`;
  }).join('')
    + (gekappt ? `<div class="marke" style="color:${rgb(farbe, 0.45)}">${MARKE}</div>` : '');
}

// =====================================================================
// 8  fluss -- Sankey: die DICKE eines Bandes ist der Betrag
// =====================================================================
/* HIER LIEGT DIE ACHSE ANDERS ALS DRUEBEN, und das ist die eine grosse
 * Entscheidung dieser Datei.
 *
 * kachel.py legt die Stufen NEBENEINANDER und braucht dafuer Breite:
 * 14 + n*9 Knotenbalken + n*111 Namensspur + (n-1)*72 Schwung. Drei
 * Stufen sind 532 Punkte, fuenf sind 800. Diese Kachel hat 264 (Rechner)
 * bzw. rund 364 (Handy). Rechnet man die Spur auf 264 herunter, bleiben
 * bei drei Stufen 49 Punkte je Spur -- davon gehen 5 Innenabstand und
 * 42 Betragsspalte ab, und fuer den Namen bleibt nichts. Der Ausweg
 * "dann eben ohne Namen" ist keiner: Ein Sankey ohne Knotennamen ist
 * ein Ornament.
 *
 * Also wird die Achse getauscht: Die Stufen liegen UNTEREINANDER, die
 * Baender fliessen nach unten, die Dicke eines Bandes ist seine BREITE.
 * Damit ist die knappe Groesse (Breite) die, ueber die sich alle Knoten
 * EINER Stufe teilen -- und die reichliche (Hoehe) die, in der die
 * Stufen liegen. Genau das ist die Lage in einer schmalen Spalte.
 *
 * Alles andere bleibt, wie es drueben steht, nur um 90 Grad gedreht:
 *
 *   GERADE STRECKE. Die Beschriftung hat ihre eigene Spur -- hier
 *   UNTER dem Knotenbalken statt rechts davon. Dort laufen die
 *   abgehenden Baender dieses einen Knotens noch senkrecht, also auf
 *   genau seiner Breite; fremde Baender koennen nicht hinein, weil die
 *   auf der Breite IHRES Knotens liegen. Unter der Beschriftung liegt
 *   deshalb eine BEKANNTE Farbe, und die Schriftfarbe laesst sich
 *   ausrechnen (schriftAuf) statt raten.
 *
 *   DIE SPUR IST ZWEIZEILIG (Name, darunter der Betrag). Drueben stehen
 *   beide nebeneinander, weil dort die Breite reichlich war. Hier ist
 *   sie es nicht und die Hoehe schon -- also untereinander. Beide
 *   bekommen so die ganze Breite des Knotens statt der Haelfte.
 *
 *   DER ABSTAND ZWEIER KNOTEN ist eine Beschriftung breit (drueben: eine
 *   Textzeile hoch). Das ist es, was die Namen duenner Baender rettet:
 *   Zwei Knoten liegen immer so weit auseinander, dass ihre Namen sich
 *   nicht ueberlappen koennen, egal wie duenn sie sind.
 *
 *   DER MASSSTAB ist der KLEINSTE, den irgendeine Stufe vertraegt. Einer
 *   je Stufe waere bequemer und eine Luege: Dann waere ein Band unten
 *   dicker als sein eigener Zufluss oben.
 *
 *   UNGLEICHE SUMMEN sind der Normalfall: Von 3.400 Euro gehen 1.098
 *   nach Wohnen, der Rest ist nicht aufgeschluesselt. Der Knoten ist so
 *   breit wie das GROESSERE von Ein- und Ausgang; was nicht
 *   weitergereicht wird, bleibt als unbebaenderter Balkenrest stehen.
 */
function formFluss(punkte, farbe, W, m) {
  const BAR = 9, SPALTEN_MAX = 5, BOGEN = 42, STRICH = 0.8;
  const SPUR = 2 * ZH;                       // Name + Betrag
  const marken = [];
  if (Number(m.weggelassen)) marken.push('[… zu viele Punkte, gekürzt]');

  // --- 1. Was ist ueberhaupt eine Kante?
  let kanten = [], unklar = false;
  punkte.forEach(pt => {
    const von = String(pt.von || '').trim(), nach = String(pt.nach || '').trim();
    const z = zahlVon(pt.zahl);
    // Die Dicke IST der Betrag, und ein negativer Betrag hat keine Dicke.
    if (!von || !nach || von === nach || z === null || z <= 0) { unklar = true; return; }
    kanten.push({ von, nach, wert: z });
  });
  if (unklar) marken.push(MARKE_KANTEN);
  if (!kanten.length) return markenZeilen(marken, farbe);

  // --- 2. Knoten in der Reihenfolge des ersten Auftretens
  let namen = [];
  kanten.forEach(k => [k.von, k.nach].forEach(nm => { if (!namen.includes(nm)) namen.push(nm); }));

  // --- 3. Stufen, Kreise auftrennen
  const [rang, getrennt] = raenge(namen, kanten.map(k => [k.von, k.nach]));
  if (getrennt.size) {
    marken.push(MARKE_KREIS);
    kanten = kanten.filter((k, nr) => !getrennt.has(nr));
  }
  // --- 4. Zu tief? Dann faellt der Rest weg, aber nicht stumm.
  if (namen.some(nm => rang.get(nm) >= SPALTEN_MAX)) {
    marken.push(MARKE_TIEF);
    namen = namen.filter(nm => rang.get(nm) < SPALTEN_MAX);
    const bleibt = new Set(namen);
    kanten = kanten.filter(k => bleibt.has(k.von) && bleibt.has(k.nach));
  }
  if (!kanten.length || !namen.length) return markenZeilen(marken, farbe);

  const tiefe = Math.max(...namen.map(nm => rang.get(nm)));
  const reihen = [];
  for (let r = 0; r <= tiefe; r++) reihen.push([]);
  namen.forEach(nm => reihen[rang.get(nm)].push(nm));

  // --- 5. Reihenfolge der Knoten je Stufe (Schwerpunkt der Nachbarn).
  // Die uebliche Heuristik, vier Durchgaenge hin und zurueck. Mehr als
  // eine Heuristik ist hier nicht zu holen -- das Problem ist NP-schwer.
  const vorher = new Map(namen.map(n => [n, []])), nachher = new Map(namen.map(n => [n, []]));
  kanten.forEach(k => { vorher.get(k.nach).push(k.von); nachher.get(k.von).push(k.nach); });
  const ort = new Map();
  const merken = () => reihen.forEach(r => r.forEach((n, i) => ort.set(n, i)));
  const schwerpunkt = (reihe, nachbarn) => {
    const mitte = n => {
      const w = nachbarn.get(n).filter(x => ort.has(x)).map(x => ort.get(x));
      return w.length ? w.reduce((a, b) => a + b, 0) / w.length : ort.get(n);
    };
    return reihe.map((n, i) => [n, i])
      .sort((a, b) => (mitte(a[0]) - mitte(b[0])) || (a[1] - b[1]))
      .map(x => x[0]);
  };
  merken();
  for (let d = 0; d < 4; d++) {
    for (let c = 1; c < reihen.length; c++) { reihen[c] = schwerpunkt(reihen[c], vorher); merken(); }
    for (let c = reihen.length - 2; c >= 0; c--) { reihen[c] = schwerpunkt(reihen[c], nachher); merken(); }
  }

  // --- 6. Wie breit ist ein Knoten?
  const ein = new Map(namen.map(n => [n, 0])), aus = new Map(namen.map(n => [n, 0]));
  kanten.forEach(k => { aus.set(k.von, aus.get(k.von) + k.wert); ein.set(k.nach, ein.get(k.nach) + k.wert); });
  const durch = new Map(namen.map(n => [n, Math.max(ein.get(n), aus.get(n))]));

  const breiteste = Math.max(...reihen.map(r => r.length));
  // Die Fuge zwischen zwei Knoten soll eine Beschriftung breit sein (44).
  // Bei vielen Knoten in einer Stufe frassen die Fugen sonst die ganze
  // Breite auf -- deshalb bekommen sie hoechstens 55 Prozent davon.
  const fuge = Math.max(10, Math.min(44, (W * 0.55) / Math.max(1, breiteste)));
  // n Fugen, nicht n-1: Auch der LETZTE Knoten einer Stufe braucht rechts
  // von sich eine Fuge, denn dort steht seine Beschriftung. Ohne diese
  // eine Fuge stand der aeusserste Balken buendig am Rand und sein Name
  // gar nicht -- gemessen an "Auto" ganz rechts, das schlicht fehlte.
  const moeglich = reihen
    .filter(r => r.length && r.reduce((s, n) => s + durch.get(n), 0) > 0)
    .map(r => (W - r.length * fuge) / r.reduce((s, n) => s + durch.get(n), 0));
  const massstab = moeglich.length ? Math.max(0, Math.min(...moeglich)) : 0;

  const knoten = [], nummer = new Map();
  reihen.forEach((reihe, r) => {
    const stapel = reihe.reduce((s, n) => s + durch.get(n) * massstab, 0)
      + fuge * Math.max(0, reihe.length - 1);
    // Die Fuge des letzten Knotens zaehlt mit, sonst laege der Stapel
    // um eine halbe Fuge zu weit rechts.
    let x = (W - stapel - fuge) / 2;
    const y = r * (BAR + SPUR + BOGEN);
    reihe.forEach((nm, platz) => {
      const br = durch.get(nm) * massstab;
      nummer.set(nm, knoten.length);
      knoten.push({
        name: nm, platz, anzahl: Math.max(2, reihe.length), x, y,
        breite: br, aus: aus.get(nm) * massstab,
        betrag: zahlDeutsch(durch.get(nm)),
        // Die Spur reicht bis zum naechsten Knoten -- das ist der Sinn
        // der Fuge, und beim letzten der Stufe ist sie durch die
        // Reservierung oben genauso sicher vorhanden.
        spur: br + fuge,
      });
      x += br + fuge;
    });
  });
  const flaeche = reihen.length * (BAR + SPUR + BOGEN) - BOGEN;

  // --- 7. Stapelreihenfolge an jedem Knoten. Keine Heuristik, sondern
  // eine Sortierung -- und sie schliesst Kreuzungen IM Knoten aus:
  // abgehende nach der Lage ihres Ziels, eingehende nach der der Quelle.
  const mitteVon = nm => { const k = knoten[nummer.get(nm)]; return k.x + k.breite / 2; };
  namen.forEach(nm => {
    const k = knoten[nummer.get(nm)];
    let x = k.x;
    kanten.filter(e => e.von === nm).sort((a, b) => mitteVon(a.nach) - mitteVon(b.nach))
      .forEach(e => { e.x0 = x; x += e.wert * massstab; });
    x = k.x;
    kanten.filter(e => e.nach === nm).sort((a, b) => mitteVon(a.von) - mitteVon(b.von))
      .forEach(e => { e.x1 = x; x += e.wert * massstab; });
  });

  // --- 8. Die Baender. Erst gerade durch die Namensspur, dann der Bogen.
  // Ein Band ist halbdurchsichtig, ein Balken nicht: Zwei Baender, die
  // sich kreuzen, muessen als zwei lesbar bleiben -- deckend waere das
  // obere einfach vorn und das untere weg. Der Balken dagegen ist die
  // Marke, an der abgelesen wird, und die darf nicht durchscheinen.
  let s = '';
  kanten.forEach(e => {
    const a = knoten[nummer.get(e.von)], b = knoten[nummer.get(e.nach)];
    const y0 = a.y + BAR, yg = y0 + SPUR, y1 = b.y, ym = (yg + y1) / 2;
    const d = e.wert * massstab;
    const c = rgb(stufe(farbe, a.platz, a.anzahl), 0.38);
    s += `<path d="M${e.x0.toFixed(2)},${y0.toFixed(1)} L${e.x0.toFixed(2)},${yg.toFixed(1)}`
      + ` C${e.x0.toFixed(2)},${ym.toFixed(1)} ${e.x1.toFixed(2)},${ym.toFixed(1)} ${e.x1.toFixed(2)},${y1.toFixed(1)}`
      + ` L${(e.x1 + d).toFixed(2)},${y1.toFixed(1)}`
      + ` C${(e.x1 + d).toFixed(2)},${ym.toFixed(1)} ${(e.x0 + d).toFixed(2)},${ym.toFixed(1)} ${(e.x0 + d).toFixed(2)},${yg.toFixed(1)}`
      + ` L${(e.x0 + d).toFixed(2)},${y0.toFixed(1)} Z" fill="${c}"/>`;
  });

  knoten.forEach(k => {
    s += `<rect x="${k.x.toFixed(2)}" y="${k.y.toFixed(1)}" width="${Math.max(k.breite, STRICH).toFixed(2)}" height="${BAR}"`
      + ` fill="${rgb(stufe(farbe, k.platz, k.anzahl), 0.95)}"/>`;
    // Was liegt unter dieser Zeile? Die abgehenden Baender fuellen den
    // Knoten von links auf k.aus Punkte auf -- deckt das mehr als die
    // halbe Spur, ist der Bandton der Grund, sonst der Kachelgrund.
    // Gemessen wird die wirkliche Ueberlappung und nicht "hat der Knoten
    // Ausgaenge": Ein Knoten, der 1.098 aufnimmt und 820 weitergibt, hat
    // unter dem Anfang seiner Zeile noch Band, unter dem Ende nicht mehr.
    const ueber = Math.max(0, Math.min(k.spur, k.aus));
    const grund = ueber >= k.spur / 2
      ? ueberGrund(stufe(farbe, k.platz, k.anzahl), 0.38) : GRUND;
    const tinte = rgb(schriftAuf(grund, TINTE), 1);
    s += svgText(k.x + 2, k.y + BAR + ZH / 2, kuerzen(k.name, k.spur - 4), tinte);
    s += svgText(k.x + 2, k.y + BAR + ZH + ZH / 2, k.betrag, tinte, { gross: 9 });
  });

  const H = flaeche;
  return `<svg class="bild" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}">${s}</svg>`
    + markenZeilen(marken, farbe);
}

// =====================================================================
// 9  ablauf -- Kaesten und Pfeile, ein Weg durch Schritte
// =====================================================================
/* Ein Punkt ist ein KASTEN, kein Pfeil: Leuchten soll der Kasten, und
 * die gerade Kette ist der Regelfall -- steht "von" nicht da, ist der
 * vorige Punkt gemeint. Nennt "von" einen Namen, den es nicht gibt, gilt
 * ebenfalls der vorige: Ein Kasten ohne Vorgaenger stuende als zweiter
 * Anfang daneben, und ein Ablauf mit zwei Anfaengen sieht kaputt aus,
 * obwohl nur ein Name falsch geschrieben war.
 *
 * WAS HIER DAZUKOMMT: DER UMBRUCH EINER STUFE.
 * Drueben duerfen vier Kaesten nebeneinander stehen, dafuer ist das
 * Fenster 708 breit. Hier sind 264 da. Ein Kasten unter rund 78 Punkten
 * traegt keine zwei lesbaren Zeilen mehr ("Ergebnis geprüft" waere
 * "Erge…"), und Kaesten wegzulassen ist keine Option -- ein Ablauf, dem
 * der vierte Zweig fehlt, ist ein anderer Ablauf.
 *
 * Also bricht eine zu breite Stufe UM: Ihre Kaesten laufen wie Text in
 * eine zweite Reihe. Der Rang bleibt derselbe -- es sind weiterhin die
 * Zweige EINER Verzweigung --, nur die Zeile ist eine andere. Die
 * Pfeile brauchen dafuer nichts Neues: Die Regel "geht der Pfeil ueber
 * mehr als eine Zeile, laeuft er durch die Gasse am Rand" trifft die
 * umgebrochenen von selbst, und damit geht keiner durch einen Kasten. */
function formAblauf(punkte, farbe, W, m) {
  if (!punkte.length) return '';
  const KASTEN_MAX = 150, KASTEN_MIN = 78, LUFT_MAX = 22, LUFT_MIN = 8;
  const RAND_K = 5, ECKE = 5, PFEIL = 24, GASSE = 14, KOPF = 3.2;
  const ZEILEN_MAX = 2, DECKEL = 470;
  const marken = [];
  if (Number(m.weggelassen)) marken.push('[… zu viele Punkte, gekürzt]');
  const n = punkte.length;

  // Namen -> ERSTER Punkt mit diesem Namen. Wer zweimal "fertig"
  // schickt, meint beim Verweisen das erste.
  const wo = new Map();
  punkte.forEach((pt, i) => {
    const t = String(pt.text || '').trim();
    if (t && !wo.has(t)) wo.set(t, i);
  });
  const kanten = [], aufschrift = new Map();
  punkte.forEach((pt, i) => {
    const v = String(pt.von || '').trim();
    const eltern = wo.has(v) ? wo.get(v) : (i ? i - 1 : null);
    if (eltern !== null && eltern !== i) {
      kanten.push([eltern, i]);
      if (pt.wert) aufschrift.set(eltern + '>' + i, String(pt.wert));
    }
  });
  // "nach" ist eine ZUSAETZLICHE Kante: darueber laufen Zweige wieder
  // zusammen. Beide zusammen gehen durch raenge(), und deshalb rutscht
  // ein Kasten, in den zwei Zweige muenden, von selbst unter den
  // tieferen der beiden -- sonst zeigte einer der Pfeile zur Seite.
  punkte.forEach((pt, i) => {
    const ziel = wo.get(String(pt.nach || '').trim());
    if (ziel !== undefined && ziel !== i && !kanten.some(k => k[0] === i && k[1] === ziel))
      kanten.push([i, ziel]);
  });

  const alle = Array.from({ length: n }, (_, i) => i);
  const [rang, getrennt] = raenge(alle, kanten);
  let kanten2 = kanten.filter((k, nr) => !getrennt.has(nr));
  if (getrennt.size) marken.push(MARKE_KREIS);

  const tiefe = Math.max(...alle.map(i => rang.get(i)));
  const stufen = [];
  for (let r = 0; r <= tiefe; r++) stufen.push([]);
  alle.forEach(i => stufen[rang.get(i)].push(i));

  // --- Zeilen: eine Stufe kann umbrechen. Zwei Durchgaenge, weil die
  // Gasse erst noetig ist, wenn ein Pfeil eine Zeile ueberspringt --
  // und das haengt am Umbruch. Mehr als zwei braucht es nicht: Weniger
  // Kaesten je Zeile koennen die Zahl der Spruenge nur erhoehen, und
  // die Gasse kostet danach keine weitere Breite.
  let gasse = 0, zeilen = [], zeileVon = new Map(), kastenBreit = 0, luft = 0;
  for (let durchgang = 0; durchgang < 2; durchgang++) {
    const zone = W - gasse;
    const proZeile = Math.max(1, Math.floor((zone + LUFT_MIN) / (KASTEN_MIN + LUFT_MIN)));
    zeilen = [];
    stufen.forEach(stufe0 => {
      const teile = Math.ceil(stufe0.length / proZeile);
      const jeZeile = Math.ceil(stufe0.length / teile);   // gleichmaessig, nicht 3+1
      for (let i = 0; i < stufe0.length; i += jeZeile) zeilen.push(stufe0.slice(i, i + jeZeile));
    });
    zeileVon = new Map();
    zeilen.forEach((z, nr) => z.forEach(i => zeileVon.set(i, nr)));
    const breiteste = Math.max(...zeilen.map(z => z.length));
    luft = Math.min(LUFT_MAX, zone / (2 * breiteste));
    kastenBreit = Math.min(KASTEN_MAX, (zone - (breiteste - 1) * luft) / breiteste);
    const braucht = kanten2.some(([a, b]) => zeileVon.get(b) - zeileVon.get(a) > 1) ? GASSE : 0;
    if (braucht === gasse) break;
    gasse = braucht;
  }

  /* WIE VIELE PFEILE VERLASSEN EINE ZEILE DURCH DIE GASSE?
     Die Frage muss VOR dem Layout beantwortet sein, denn sie kostet
     Hoehe: Zwei Gassenpfeile aus derselben Zeile brauchen zwei
     Querstuecke uebereinander, und jedes traegt eine Aufschrift.
     Beide in die 24 Punkte zwischen zwei Zeilen zu zwaengen ging nicht
     -- gemessen lag "WRT" halb auf "NOT". Also bekommt die Luecke fuer
     jeden weiteren Gassenpfeil eine Zeilenhoehe dazu. */
  const gassenSpur = new Map(), gassenZahl = new Map();
  kanten2.forEach(([a, b]) => {
    if (zeileVon.get(b) - zeileVon.get(a) <= 1) return;
    const r = zeileVon.get(a), k = gassenZahl.get(r) || 0;
    gassenSpur.set(a + '>' + b, k);
    gassenZahl.set(r, k + 1);
  });
  const zusatz = r => 13 * Math.min(2, Math.max(0, (gassenZahl.get(r) || 0) - 1));

  const innen = Math.max(1, kastenBreit - 2 * RAND_K);
  const texte = punkte.map(pt => {
    let u = umbrechen(pt.text, innen);
    if (!u.length) u = [''];
    if (u.length > ZEILEN_MAX)
      u = u.slice(0, ZEILEN_MAX - 1).concat([kuerzen(u.slice(ZEILEN_MAX - 1).join(' '), innen)]);
    return u;
  });

  // --- Lage der Kaesten, von oben nach unten
  const lage = new Map();
  let y = 0, gekappt = false;
  const zone = W - gasse;
  zeilen.forEach((reihe, r) => {
    if (gekappt) return;
    const hoch = Math.max(...reihe.map(i => texte[i].length)) * ZH + 2 * RAND_K;
    const luecke = PFEIL + (r ? zusatz(r - 1) : 0);
    if (r && y + luecke + hoch > DECKEL) { gekappt = true; return; }
    if (r) y += luecke;
    const gesamt = reihe.length * kastenBreit + (reihe.length - 1) * luft;
    let x = (zone - gesamt) / 2;
    reihe.forEach(i => { lage.set(i, { x, y, b: kastenBreit, h: hoch }); x += kastenBreit + luft; });
    y += hoch;
  });
  // Gekappt wird UNTEN. Beim Ablauf ist das der schlechtere Schnitt (das
  // Ende ist das Ziel), aber der einzige, der nicht luegt: Oben zu kappen
  // hiesse, einen Weg ohne Anfang zu zeigen.
  if (gekappt) marken.push(MARKE);

  // --- Pfeile zuerst, Kaesten darueber: Die Spitze endet auf der
  // Oberkante ihres Kastens, und der deckt sie nicht zu, sondern
  // schliesst an sie an.
  let s = '', beschriftung = '';
  kanten2.forEach(([a, b]) => {
    if (!lage.has(a) || !lage.has(b)) return;
    const o = lage.get(a), u = lage.get(b);
    const sx = o.x + o.b / 2, sy = o.y + o.h;
    const tx = u.x + u.b / 2, ty = u.y;
    const strich = rgb(farbe, 0.55);
    let ecken, sch, anker;
    const neben = h => ({ x: sx + 4, y: h + ZF / 2, w: Math.min(kastenBreit / 2, W - sx - 4) });
    if (zeileVon.get(b) - zeileVon.get(a) > 1) {
      // Ueber die Gasse aussen herum -- ohne sie waere das genau der
      // Fehler, den man bei jedem vierten Graphen sieht: ein Pfeil, der
      // durch einen Kasten geht. Zwei Spuren nebeneinander reichen.
      const nr = gassenSpur.get(a + '>' + b) || 0;
      const gx = W - 5 - (nr % 2) * 6;
      // Auch das Querstueck wird gestaffelt, nicht nur die senkrechte
      // Spur: Zwei Pfeile aus DEMSELBEN Kasten verlassen ihn auf
      // derselben Hoehe, und dann laege Strich auf Strich. Der Platz
      // dafuer steht schon im Layout, siehe zusatz().
      const quer0 = sy + 6 + Math.min(2, nr) * 13;
      ecken = [[sx, sy], [sx, quer0], [gx, quer0], [gx, ty - 8], [tx, ty - 8], [tx, ty]];
      // Die Aufschrift sitzt UNTER ihrem eigenen Querstueck und am
      // Ende, kurz vor der Gasse -- nicht neben dem Kasten: Dort
      // haetten zwei Pfeile aus demselben Kasten denselben Ort.
      sch = { x: gx - 4, y: quer0 + ZF / 2 + 1, w: Math.max(20, gx - sx - 8) };
      anker = 'end';
    } else if (Math.abs(sx - tx) < 0.6) {
      ecken = [[sx, sy], [tx, ty]];
      // Auf derselben Hoehe wie die Beschriftung der geknickten
      // Geschwister, naemlich unter deren Querstrich: Ein Kasten mit
      // drei Ausgaengen hat einen geraden Pfeil in der Mitte und zwei
      // geknickte daneben -- stuende sein Wort weiter oben, laege es
      // genau auf dem Querstrich der beiden anderen.
      sch = neben(sy + PFEIL / 2 + 1); anker = 'start';
    } else {
      const quer = sy + PFEIL / 2;
      ecken = [[sx, sy], [sx, quer], [tx, quer], [tx, ty]];
      // UNTER dem Querstueck, nicht darueber: Darueber stiesse sie an
      // die Unterkante des Kastens, aus dem der Pfeil kommt.
      sch = { x: (sx + tx) / 2, y: quer + 1 + ZF / 2, w: Math.abs(tx - sx) };
      anker = 'middle';
    }
    s += `<polyline points="${ecken.map(e => e[0].toFixed(1) + ',' + e[1].toFixed(1)).join(' ')}"`
      + ` fill="none" stroke="${strich}" stroke-width="1"/>`;
    s += `<polygon points="${(tx - KOPF).toFixed(1)},${(ty - 5).toFixed(1)} ${(tx + KOPF).toFixed(1)},${(ty - 5).toFixed(1)} ${tx.toFixed(1)},${ty.toFixed(1)}" fill="${strich}"/>`;
    const wort = aufschrift.get(a + '>' + b);
    if (wort) beschriftung += svgText(sch.x, sch.y, kuerzen(wort, sch.w, SCHRIFT_FUSS),
      rgb(farbe, 0.72), { gross: 9, anker });
  });
  s += beschriftung;

  Array.from(lage.keys()).sort((a, b) => a - b).forEach(i => {
    const k = lage.get(i);
    s += `<rect x="${(k.x + 0.5).toFixed(1)}" y="${(k.y + 0.5).toFixed(1)}" width="${(k.b - 1).toFixed(1)}" height="${(k.h - 1).toFixed(1)}"`
      + ` rx="${ECKE}" fill="${rgb(farbe, 0.12)}" stroke="${rgb(farbe, 0.50)}" stroke-width="1"/>`;
    texte[i].forEach((z, nr) => {
      s += svgText(k.x + k.b / 2, k.y + RAND_K + nr * ZH + ZH / 2, z,
        rgb(TINTE, 0.92), { anker: 'middle' });
    });
  });

  const H = Math.max(1, y);
  return `<svg class="bild" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}">${s}</svg>`
    + markenZeilen(marken, farbe);
}

// =====================================================================
// Die Kachel selbst
// =====================================================================
const FORMEN = {
  liste: formListe, blasen: formBlasen, vergleich: formVergleich,
  text: formText, balken: formBalken, torte: formTorte,
  kategorien: formKategorien, fluss: formFluss, ablauf: formAblauf,
};

function kachelZeigen(m) {
  let el = S.kacheln.get(m.name);
  if (!el) {
    el = document.createElement('div');
    el.className = 'kachel';
    kachelraum.appendChild(el);
    S.kacheln.set(m.name, el);
  }
  // Die WIRKLICH vorhandene Innenbreite, nicht eine geratene: Am Rechner
  // rund 264, auf dem Handy rund 364. Die gerechneten Formen legen ihr
  // Inneres darin aus -- siehe den Kopf dieses Abschnitts. Der leere
  // Kasten steht schon im Baum, also hat er seine Breite; nur beim
  // allerersten Bild vor dem ersten Layout ist sie 0, dafuer der Notnagel.
  const breite = Math.max(180, (el.clientWidth || Math.min(290, kachelraum.clientWidth || 290)) - 24);
  kachelFuellen(el, m, breite);

  const sek = Number(m.sekunden) || (m.sorte === 'zustand' ? 0 : 45);
  clearTimeout(el._uhr);
  if (sek > 0) el._uhr = setTimeout(() => kachelWeg(m.name), sek * 1000);
}

/* Den Inhalt einer Kachel malen -- auf der Bühne UND als Karte im
 * Verlauf. Eine Stelle, damit die Karte nicht anders aussieht als das,
 * was vorher neben dem Ring stand. */
function kachelFuellen(el, m, breite) {
  const farbe = m.sorte === 'zustand' ? KACHEL_ZUSTAND : KACHEL_ANTWORT;
  el.style.borderColor = rgb(farbe, 0.30);
  const punkte = m.punkte || [];

  // Etwas Unbekanntes faellt auf "liste" zurueck: Eine Kachel, die wegen
  // eines Tippfehlers gar nicht aufgeht, ist schlechter als eine, die
  // schlicht aussieht.
  const bauen = FORMEN[m.form] || formListe;
  let rumpf = '';
  try {
    rumpf = bauen(punkte, farbe, breite, m);
  } catch (e) {
    // Lieber schlicht als gar nicht -- aus demselben Grund wie oben.
    rumpf = formListe(punkte, farbe, breite, m);
    if (window.console) console.warn('Kachelform', m.form, e);
  }

  const weg = Number(m.weggelassen) || 0;
  el.innerHTML = `<div class="strich" style="background:${rgb(farbe, 0.85)}"></div>
    <h4 style="color:${rgb(farbe, 0.95)}">${sicher(m.kopf)}</h4>
    ${m.gross ? `<div class="gross" style="color:${rgb(farbe, 1)}">${sicher(m.gross)}</div>` : ''}
    ${rumpf}
    ${weg ? `<div class="fuss">und ${weg} weitere</div>` : ''}
    ${m.stand ? `<div class="fuss">${sicher(m.stand)}</div>` : ''}`;
}

function kachelWeg(name) {
  const el = S.kacheln.get(name);
  if (!el) return;
  clearTimeout(el._uhr);
  el.style.transition = 'opacity .35s'; el.style.opacity = '0';
  setTimeout(() => el.remove(), 360);
  S.kacheln.delete(name);
}

const sicher = t => String(t == null ? '' : t)
  .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

// =====================================================================
// Eine angebotene Seite
// =====================================================================
/* Sarvis schickt "browser", wenn er dem Nutzer eine Seite zeigen will --
 * eine Route, ein Suchergebnis, einen Kalender. Am Rechner oeffnet hud.py
 * dafuer ein eingebautes Fenster. Hier gibt es das nicht, und
 * window.open() ist KEIN Ersatz: Ohne vorausgegangenen Klick blockiert
 * jeder Browser das Popup, und zwar stumm -- Sarvis sagt dann "die Route
 * liegt auf deinem Bildschirm", und da liegt nichts. Ein Zuruf ist kein
 * Klick.
 *
 * Also wird die Seite ANGEBOTEN statt geoeffnet: eine Leiste mit einem
 * Knopf. Der Klick entsteht dort, wo er entstehen muss, und geht immer
 * auf. Sie ist das einzige anklickbare Stueck ueber der Buehne -- die
 * Kacheln bleiben tot, siehe die Begruendung am #kacheln.
 *
 * WAS DRAUFSTEHT, ist nicht die Adresse. Eine Google-Maps-Adresse ist
 * 120 Zeichen Query-String und sagt weniger als nichts:
 *   maps/dir/?api=1&destination=Leipzig&travelmode=transit
 * Draufsteht deshalb, was fuer eine Seite es ist ("Google Maps") und
 * worum es geht ("Route nach Leipzig"). Die ganze Adresse haengt am
 * title, fuer den Fall, dass jemand sie doch sehen will. */
const SEITEN_NAMEN = {
  'google.com': 'Google', 'google.de': 'Google',
  'youtube.com': 'YouTube', 'youtu.be': 'YouTube',
  'wikipedia.org': 'Wikipedia', 'openstreetmap.org': 'OpenStreetMap',
  'github.com': 'GitHub', 'bahn.de': 'Deutsche Bahn',
  'amazon.de': 'Amazon', 'ebay.de': 'eBay',
  'hero-software.de': 'HERO', 'tech-artist.de': 'tech-artist',
};

function seiteBenennen(adresse) {
  let u;
  try { u = new URL(String(adresse)); } catch (e) { return { ort: String(adresse), dazu: '' }; }
  const host = u.hostname.replace(/^www\./, '');
  let ort = host;
  // Von hinten aufloesen, damit auch maps.google.com und
  // login.hero-software.de ihren Namen bekommen.
  for (let h = host; h.includes('.'); h = h.slice(h.indexOf('.') + 1)) {
    if (SEITEN_NAMEN[h]) { ort = SEITEN_NAMEN[h]; break; }
  }
  if (/(^|\.)google\.[a-z.]+$/.test(host) && u.pathname.startsWith('/maps'))
    ort = 'Google Maps';

  const q = u.searchParams;
  const ziel = q.get('destination') || q.get('daddr');
  const suche = q.get('q') || q.get('query') || q.get('search_query') || q.get('text');
  let dazu = '';
  if (ziel) dazu = 'Route nach ' + ziel;
  else if (suche) dazu = suche;
  else {
    // Sonst der letzte Wegabschnitt -- aber nur, wenn er wie ein Wort
    // aussieht. Eine Kennung wie /a7f3c1e9b2d4 ist keine Auskunft.
    const teile = u.pathname.split('/').filter(Boolean);
    let letzt = teile.length ? teile[teile.length - 1] : '';
    try { letzt = decodeURIComponent(letzt); } catch (e) { /* roh lassen */ }
    if (letzt && letzt.length <= 48 && /[a-zA-ZäöüÄÖÜß]{3}/.test(letzt)
      && !/^[0-9a-f]{12,}$/i.test(letzt))
      dazu = letzt.replace(/\.\w{2,5}$/, '').replace(/[-_+]/g, ' ');
  }
  if (dazu.length > 64) dazu = dazu.slice(0, 63) + '…';
  return { ort, dazu };
}

function seiteZeigen(adresse) {
  const el = document.getElementById('seite');
  adresse = String(adresse || '');
  // Nur, was ein Browser auch oeffnen soll. Ein javascript:-Ziel in
  // einem href waere ein fremder Befehl an einem Knopf, den der Nutzer
  // fuer harmlos haelt.
  if (!/^https?:\/\//i.test(adresse)) { seiteZu(); return; }
  const wie = seiteBenennen(adresse);
  el.querySelector('.ort').textContent = wie.ort;
  el.querySelector('.dazu').textContent = wie.dazu;
  const knopf = el.querySelector('.auf');
  knopf.href = adresse;
  knopf.title = adresse;
  el.classList.add('an');
}

function seiteZu() {
  document.getElementById('seite').classList.remove('an');
}

// =====================================================================
// Das Blatt -- was gelesen statt gehoert wird
// =====================================================================
/* Drei Sorten in einem Kasten, weil es fuer den Nutzer eine Sache ist:
 *
 *   markdown  der Text kommt MIT der Nachricht und wird hier gesetzt
 *   html      ein ganzer Bericht, geholt von /blatt/<kennung>
 *   datei     dasselbe, aber als Knopf zum Herunterladen
 *
 * WARUM DER MARKDOWN-WANDLER HIER STEHT UND NICHT AUF DEM SERVER
 *
 * Der Server koennte fertiges HTML schicken -- er hat den Wandler
 * ohnehin (werkzeuge/markdown_lesen.py, fuer PDF und Word). Dann kaeme
 * aber HTML ueber den Draht, das hier in innerHTML landet, und die
 * Sicherheit des Blattes haenge an einer Datei auf der anderen Seite
 * der Leitung. So haengt sie an dieser Funktion: Es gibt hier keinen
 * Pfad, auf dem ein Zeichen aus der Nachricht ununtersucht in den Baum
 * kommt. Jeder Text geht durch sicher(), jedes Tag entsteht hier.
 *
 * Der Preis sind zwei Wandler statt einem. Sie muessen dieselbe
 * Teilmenge koennen, nicht denselben Code sein -- und die Teilmenge
 * steht in beiden Dateien im Kopf. */

/* Was als Linkziel durchgeht. Dieselbe Liste wie in markdown_lesen.py
 * und aus demselben Grund wie bei seiteZeigen: Ein javascript:-Ziel in
 * einem href ist ein fremder Befehl an einem Knopf, den der Nutzer
 * fuer harmlos haelt. */
const ZIEL_OK = /^(https?:\/\/|mailto:|tel:)/i;

/* Inline-Auszeichnung. Code zuerst: Was in Ruecktikken steht, ist
 * woertlich und darf nicht noch einmal nach Sternchen abgesucht
 * werden -- sonst wird aus `a*b*c` ein Kursivsatz mitten im Code. */
/* Das Bild VOR dem Link, sonst frisst der Link die Klammern und das
 * Ausrufezeichen bleibt einzeln stehen. Bilder werden nicht geladen,
 * sondern benannt -- siehe markdown_lesen.py, dieselbe Begruendung. */
const INLINE = /(`[^`\n]+`)|(!\[[^\]\n]*\]\([^)\s]+\))|(\[[^\]\n]+\]\([^)\s]+\))|(\*\*[^*\n]+\*\*|__[^_\n]+__)|(~~[^~\n]+~~)|(\*[^*\n]+\*|_[^_\n]+_)/g;

function mdInline(zeile) {
  let aus = '', zuletzt = 0, t;
  INLINE.lastIndex = 0;
  while ((t = INLINE.exec(zeile)) !== null) {
    if (t.index > zuletzt) aus += sicher(zeile.slice(zuletzt, t.index));
    const roh = t[0];
    if (t[1]) {
      aus += `<code>${sicher(roh.slice(1, -1))}</code>`;
    } else if (t[2]) {
      const schnitt = roh.indexOf('](');
      const bez = roh.slice(2, schnitt).trim();
      aus += `<em>${sicher('[' + (bez || 'Bild') + ']')}</em>`;
    } else if (t[3]) {
      const schnitt = roh.indexOf('](');
      const text = roh.slice(1, schnitt), ziel = roh.slice(schnitt + 2, -1);
      // Nicht wegwerfen, nur entschaerfen: Der Nutzer soll sehen, was
      // dastand -- er soll es nur nicht anklicken koennen.
      aus += ZIEL_OK.test(ziel)
        ? `<a href="${sicher(ziel).replace(/"/g, '&quot;')}" target="_blank" rel="noopener noreferrer">${sicher(text)}</a>`
        : sicher(`${text} (${ziel})`);
    } else if (t[4]) {
      aus += `<strong>${sicher(roh.slice(2, -2))}</strong>`;
    } else if (t[5]) {
      aus += `<s>${sicher(roh.slice(2, -2))}</s>`;
    } else {
      aus += `<em>${sicher(roh.slice(1, -1))}</em>`;
    }
    zuletzt = t.index + roh.length;
  }
  if (zuletzt < zeile.length) aus += sicher(zeile.slice(zuletzt));
  return aus;
}

const MD_UEBER = /^(#{1,6})\s+(.*)$/;
// Die Einrueckung wird mitgelesen (Gruppe 1) -- daraus wird die Stufe.
const MD_PUNKT = /^([ \t]*)[-*+]\s+(.*)$/;
const MD_ZAHL = /^([ \t]*)(\d{1,3})[.)]\s+(.*)$/;
// Mehrfache > gelten als ein Zitat: ein stehengebliebenes ">" ist
// schlechter als eine nicht dargestellte Verschachtelung.
const MD_ZITAT = /^\s*>+\s?(.*)$/;
const MD_HAKEN = /^\[([ xX])\]\s+(.*)$/;
const HAKEN_AN = '\u2611', HAKEN_AUS = '\u2610';
const STUFE_BREITE = 2, STUFEN_TIEF = 2;

// Wie weit eine Zeile eingerueckt ist. Tabulator zaehlt vier, nicht
// acht -- Schreiber mischen Tabulator und zwei Leerzeichen.
function einzug(zeile) {
  const roh = zeile.slice(0, zeile.length - zeile.replace(/^[ \t]+/, '').length);
  return (roh.match(/ /g) || []).length + (roh.match(/\t/g) || []).length * 4;
}
const MD_LINIE = /^\s*([-*_])(\s*\1){2,}\s*$/;
const MD_ZAUN = /^\s*```+\s*(\w*)\s*$/;
const MD_TRENN = /^\s*\|?[\s:|-]+\|[\s:|-]*$/;

function mdZellen(zeile) {
  let roh = zeile.trim();
  if (roh.startsWith('|')) roh = roh.slice(1);
  if (roh.endsWith('|')) roh = roh.slice(0, -1);
  return roh.split('|').map(z => mdInline(z.trim()));
}

/* Eine Liste samt ihrer Unterebenen.
 *
 * Verschachtelt wird richtig, also INNERHALB des vorigen <li> -- ein
 * <ul> als Geschwister waere zwar auch eingerueckt, aber
 * Vorleseprogramme lesen es dann als eigene Liste vor, und die
 * Zugehoerigkeit ist weg. Gleiche Bauart wie _liste_html in
 * werkzeuge/markdown_lesen.py; beide muessen dasselbe koennen. */
function listeHtml(punkte, geordnet) {
  const tag = geordnet ? 'ol' : 'ul';
  const aus = [`<${tag}>`];
  let stufe = 0, offen = false;
  for (const p of punkte) {
    const ziel = p.stufe || 0;
    while (ziel > stufe) {
      // Ohne offenes <li> zuerst eines aufmachen: Eine Liste, die mit
      // einem Unterpunkt beginnt, waere ungueltiges HTML.
      if (!offen) { aus.push('<li>'); offen = true; }
      aus.push(`<${tag}>`); stufe++; offen = false;
    }
    while (ziel < stufe) {
      if (offen) { aus.push('</li>'); offen = false; }
      aus.push(`</${tag}></li>`); stufe--;
    }
    if (offen) aus.push('</li>');
    const marke = p.haken == null ? ''
      : `<span class="haken">${p.haken ? HAKEN_AN : HAKEN_AUS}</span> `;
    aus.push(`<li>${marke}${p.html}`);
    offen = true;
  }
  if (offen) aus.push('</li>');
  while (stufe > 0) { aus.push(`</${tag}></li>`); stufe--; }
  aus.push(`</${tag}>`);
  return aus.join('');
}

function markdown(text) {
  const zeilen = String(text == null ? '' : text)
    .replace(/\r\n?/g, '\n').split('\n');
  const aus = [];
  let absatz = [];
  const absatzZu = () => {
    if (absatz.length) { aus.push(`<p>${mdInline(absatz.join(' '))}</p>`); absatz = []; }
  };

  for (let i = 0; i < zeilen.length; i++) {
    const zeile = zeilen[i];

    const zaun = MD_ZAUN.exec(zeile);
    if (zaun) {
      absatzZu();
      const inhalt = [];
      i++;
      while (i < zeilen.length && !MD_ZAUN.test(zeilen[i])) inhalt.push(zeilen[i++]);
      // Ein Codeblock ohne schliessenden Zaun ist kein Fehler, sondern
      // ein Modell, dem die Zeichen ausgegangen sind. Was da ist, wird
      // gezeigt.
      aus.push(`<pre><code>${sicher(inhalt.join('\n'))}</code></pre>`);
      continue;
    }
    if (!zeile.trim()) { absatzZu(); continue; }
    if (MD_LINIE.test(zeile)) { absatzZu(); aus.push('<hr>'); continue; }

    const ueber = MD_UEBER.exec(zeile);
    if (ueber) {
      absatzZu();
      const stufe = Math.min(ueber[1].length, 3);
      aus.push(`<h${stufe}>${mdInline(ueber[2].trim())}</h${stufe}>`);
      continue;
    }

    // Eine Tabelle erkennt man erst an der ZWEITEN Zeile: Die erste
    // sieht aus wie jede andere mit Strichen darin.
    if (zeile.includes('|') && i + 1 < zeilen.length && MD_TRENN.test(zeilen[i + 1])) {
      absatzZu();
      const kopf = mdZellen(zeile);
      i += 2;
      const reihen = [];
      while (i < zeilen.length && zeilen[i].includes('|') && zeilen[i].trim()) {
        reihen.push(mdZellen(zeilen[i++]));
      }
      i--;
      aus.push('<div class="tabelle"><table><thead><tr>'
        + kopf.map(z => `<th>${z}</th>`).join('')
        + '</tr></thead><tbody>'
        + reihen.map(r => '<tr>' + r.map(z => `<td>${z}</td>`).join('') + '</tr>').join('')
        + '</tbody></table></div>');
      continue;
    }

    const zitat = MD_ZITAT.exec(zeile);
    if (zitat) {
      absatzZu();
      const teile = [zitat[1]];
      while (i + 1 < zeilen.length && MD_ZITAT.test(zeilen[i + 1])) {
        teile.push(MD_ZITAT.exec(zeilen[++i])[1]);
      }
      aus.push(`<blockquote>${mdInline(teile.join(' ').trim())}</blockquote>`);
      continue;
    }

    const punkt = MD_PUNKT.exec(zeile), zahl = MD_ZAHL.exec(zeile);
    if (punkt || zahl) {
      absatzZu();
      // Die Sorte der ERSTEN Zeile bestimmt die Liste. Ein nummerierter
      // Unterpunkt unter einer Aufzaehlung bleibt derselbe Block --
      // sonst zerfaellt die Liste in drei, sobald jemand mischt.
      const geordnet = !!zahl;
      const grund = einzug(zeile);
      const punkte = [];
      while (i < zeilen.length) {
        const p = MD_PUNKT.exec(zeilen[i]) || MD_ZAHL.exec(zeilen[i]);
        if (!p) break;
        let roh = p[p.length - 1];
        const stufe = Math.max(0, Math.min(
          Math.floor((einzug(zeilen[i]) - grund) / STUFE_BREITE), STUFEN_TIEF));
        let haken = null;
        const kasten = MD_HAKEN.exec(roh.trim());
        if (kasten) { haken = kasten[1].toLowerCase() === 'x'; roh = kasten[2]; }
        punkte.push({ html: mdInline(roh.trim()), stufe, haken });
        i++;
      }
      i--;
      aus.push(listeHtml(punkte, geordnet));
      continue;
    }

    absatz.push(zeile.trim());
  }
  absatzZu();
  return aus.join('');
}

/* Wie gross ist die Datei -- in etwas, das man vorlesen koennte. */
function menge(bytes) {
  const b = Number(bytes) || 0;
  if (!b) return '';
  if (b < 1024) return b + ' Bytes';
  if (b < 1024 * 1024) return Math.round(b / 1024) + ' KB';
  return (b / (1024 * 1024)).toFixed(1).replace('.', ',') + ' MB';
}

let blattJetzt = '';

const VORSCHAU_OK = /^https:\/\/test\.tech-artist\.de\/(vorschau|offen)\/[a-z0-9-]+\/$/;

function blattZeigen(m) {
  const el = document.getElementById('blatt');
  const kennung = String(m.kennung || '');
  if (!kennung) return;
  const sorte = String(m.sorte || 'markdown');
  const text = el.querySelector('.text');
  const rahmen = el.querySelector('.rahmen');
  const laden = el.querySelector('.laden');

  el.querySelector('.titel').textContent = String(m.titel || 'Blatt');
  blattJetzt = kennung;

  // Immer erst alles zurueck auf null. Sonst steht beim Wechsel von
  // einer Datei zu einem Text noch der Download-Knopf da und laedt das
  // Vorige herunter -- ein Knopf, der etwas anderes tut, als daneben
  // steht.
  text.innerHTML = '';
  rahmen.hidden = true;
  rahmen.removeAttribute('src');
  const vrahmen = el.querySelector('.vorschaurahmen');
  vrahmen.hidden = true;
  vrahmen.removeAttribute('src');
  laden.hidden = true;
  laden.removeAttribute('href');
  laden.removeAttribute('target');
  laden.removeAttribute('rel');
  laden.setAttribute('download', '');
  laden.textContent = 'Herunterladen';

  if (sorte === 'markdown') {
    el.querySelector('.dazu').textContent = '';
    text.innerHTML = markdown(m.inhalt);
    text.scrollTop = 0;
  } else if (sorte === 'html') {
    el.querySelector('.dazu').textContent = 'Bericht';
    // Nur ein Pfad auf DIESEN Server. Eine fremde Adresse in diesem
    // Rahmen waere eine fremde Seite mit unserem Aussehen -- der Draht
    // ist authentifiziert, aber was ueber ihn kommt, ist Modellausgabe.
    const adresse = String(m.adresse || '');
    if (!adresse.startsWith('/blatt/')) { blattZu(); return; }
    rahmen.src = adresse;
    rahmen.hidden = false;
  } else if (sorte === 'datei') {
    const name = String(m.datei || 'datei');
    const gross = menge(m.bytes);
    el.querySelector('.dazu').textContent = gross ? `${name} · ${gross}` : name;
    const adresse = String(m.adresse || '');
    if (!adresse.startsWith('/blatt/')) { blattZu(); return; }
    laden.href = adresse;
    laden.setAttribute('download', name);
    laden.hidden = false;
    // Ein PDF liesse sich rahmen -- aber nicht in einem sandbox-iframe
    // ohne Skripte, denn Chromes eigener Betrachter ist selbst eine
    // Anwendung. Also ehrlich: ein Satz und ein Knopf.
    // Ein Bild zeigen wir gleich -- ein <img> fuehrt nichts aus, und
    // die Adresse ist dieselbe wie die zum Herunterladen.
    const bild = BILD_ENDUNG.test(name)
      ? `<img class="vorschau" alt="" src="${sicher(adresse)}">` : '';
    text.innerHTML = bild + `<p>Diese Datei liegt für dich bereit. `
      + `<strong>${sicher(name)}</strong>${gross ? ' · ' + sicher(gross) : ''}</p>`
      + `<p>Du findest sie auch später oben unter „Dateien“.</p>`;
    // Die Liste nachziehen, damit sie dort sofort steht.
    setTimeout(dateienLaden, 300);
  } else if (sorte === 'seite') {
    // Eine Webseiten-Vorschau (werkzeuge/vorschau.py). Nicht gerahmt --
    // der Rahmen laesst keine Skripte zu, und eine React-Seite ohne
    // Skripte ist weiss. Also ein Knopf, der sie in einem neuen Tab
    // oeffnet. Nur unsere beiden Vorschau-Orte, keine fremde Adresse.
    const adresse = String(m.adresse || '');
    if (!VORSCHAU_OK.test(adresse)) { blattZu(); return; }
    el.querySelector('.dazu').textContent = 'Webseite';
    laden.href = adresse;
    laden.removeAttribute('download');
    laden.target = '_blank';
    laden.rel = 'noopener';
    laden.textContent = 'Im Browser öffnen';
    laden.hidden = false;
    // Die Seite selbst, eingebettet. Der Knopf daneben bleibt fuer den
    // grossen Tab -- und fuer /vorschau/ mit Passwort, falls der Browser
    // die Anmeldung im Rahmen nicht anbietet.
    const vrahmen = el.querySelector('.vorschaurahmen');
    vrahmen.src = adresse;
    vrahmen.hidden = false;
  } else {
    // Unbekannte Sorte: still ueberspringen, wie ueberall am Draht.
    return;
  }

  el.hidden = false;
  clearTimeout(el._uhr);
  const sek = Number(m.sekunden) || 0;
  if (sek > 0) el._uhr = setTimeout(() => blattWeg(kennung), sek * 1000);
}

function blattWeg(kennung) {
  // Nur zumachen, wenn das gemeinte Blatt auch das offene ist. Sonst
  // reisst eine abgelaufene Uhr das Blatt weg, das inzwischen ein
  // anderes ist.
  if (kennung && blattJetzt && kennung !== blattJetzt) return;
  blattZu();
}

function blattZu() {
  const el = document.getElementById('blatt');
  clearTimeout(el._uhr);
  el.hidden = true;
  blattJetzt = '';
  // Die Quelle wirklich loesen und nicht nur verstecken: Ein
  // verborgener Rahmen laedt sonst weiter und haelt die Seite im
  // Speicher. Dieselbe Ueberlegung wie beim Radio.
  const rahmen = el.querySelector('.rahmen');
  rahmen.hidden = true;
  rahmen.removeAttribute('src');
  const vrahmen = el.querySelector('.vorschaurahmen');
  vrahmen.hidden = true;
  vrahmen.removeAttribute('src');
  el.querySelector('.text').innerHTML = '';
}

function hintergrundZeigen() {
  const kasten = document.getElementById('hintergrund');
  const leiste = document.getElementById('hgleiste');
  if (!S.hintergrund.length && !S.hgFertig) {
    kasten.classList.remove('an'); leiste.hidden = true; return;
  }
  // Dieselbe Auskunft schmal über der Eingabe -- in der Verlaufsansicht
  // ist die Bühne mit ihrer Ecke nicht zu sehen.
  const zahl = Math.max(S.hgGesamt, S.hintergrund.length);
  leiste.hidden = false;
  leiste.style.color = S.hgFertig ? 'rgb(120,226,140)' : 'rgba(255,196,120,.92)';
  leiste.textContent = S.hgFertig ? 'Im Hintergrund: fertig'
    : `Im Hintergrund${zahl > 1 ? ' · ' + zahl : ''}: ${S.hintergrund.join(' · ')}`;
  kasten.classList.add('an');
  // Die WIRKLICHE Zahl, nicht die der angezeigten Zeilen.
  const gesamt = Math.max(S.hgGesamt, S.hintergrund.length);
  const farbe = S.hgFertig ? [120, 226, 140]
    : (S.hgSeit < 90 ? [255, 104, 104] : [255, 176, 72]);
  kasten.style.color = rgb(farbe, 0.95);
  kasten.innerHTML = `<div class="kopf">im Hintergrund${gesamt > 1 ? ' · ' + gesamt : ''}</div>`
    + S.hintergrund.slice(0, 3).map(z => `<div class="zeile">${sicher(z)}</div>`).join('');
}

// =====================================================================
// Die Leitung
// =====================================================================
let draht = null, schluessel = localStorage.getItem('sarvis-schluessel') || '';
let wiederIn = 1000;

function lage(text, an) {
  document.getElementById('lage').textContent = text;
  document.getElementById('ampel').classList.toggle('an', !!an);
  document.getElementById('reden').disabled = !an;
  S.verbunden = !!an;
  const fern = document.getElementById('fernsicht');
  if (fern) fern.disabled = !an;
  // Verbindung weg heißt: Es kommen keine Bilder mehr, und ein Klick
  // ginge ins Leere. Den Live-Betrieb DANN weiterlaufen zu lassen wäre
  // die schlimmste Variante -- ein stehendes Bild, das noch aussieht,
  // als wäre es live. Der Server hat unterdessen ohnehin abgeschaltet
  // (server.py ruft fernsicht.weg beim Verbindungsende).
  //
  // `live` steht weiter unten und ist hier trotzdem gültig: lage() wird
  // erst aus verbinden() heraus gerufen, und das steht am Dateiende.
  if (!an && live) fernsichtAus(true);
}

function verbinden() {
  const wo = (location.protocol === 'https:' ? 'wss://' : 'ws://')
    + location.host + '/draht';
  lage('verbindet …', false);
  bereit = false;
  draht = new WebSocket(wo);

  draht.onopen = () => draht.send(JSON.stringify({
    schluessel,
    // Nur ein Geraet mit grossem Bildschirm bekommt Browser-Fragen.
    kann_browser: window.innerWidth >= 900,
    // Was diese Oberfläche über das Anzeigen hinaus kann. `kann_rechner`
    // fehlt hier mit Absicht -- ein Browser darf keine Programme starten.
    // Ein Audio-Element für einen Radiostream hat er sehr wohl, und
    // Sarvis fragt danach, bevor er einen Sender losschickt.
    kann: ['kann_radio'],
  }));

  draht.onmessage = e => {
    let m; try { m = JSON.parse(e.data); } catch { return; }
    empfangen(m);
  };

  draht.onclose = ev => {
    if (ev.code === 4401) {          // Schlüssel gilt nicht
      localStorage.removeItem('sarvis-schluessel');
      document.getElementById('torhinweis').textContent =
        'Dieser Schlüssel gilt nicht. Leg auf dem Server ein Gerät an.';
      document.getElementById('tor').classList.remove('weg');
      lage('kein Zugang', false);
      return;
    }
    bereit = false;
    lage('getrennt', false);
    setTimeout(verbinden, wiederIn);
    wiederIn = Math.min(wiederIn * 1.6, 20000);   // nicht im Kreis hämmern
  };
}

function empfangen(m) {
  switch (m.art) {
    case 'willkommen':
      wiederIn = 1000;
      bereit = true;
      lage('verbunden', true);
      warteschlangeLeeren();
      document.getElementById('geraet').textContent = m.geraet || '';
      document.getElementById('tor').classList.add('weg');
      localStorage.setItem('sarvis-schluessel', schluessel);
      // Nach jeder (Wieder-)Verbindung den Verlauf neu holen: Was kam,
      // während die Leitung weg war, steht nur auf dem Server.
      F.geladen = '';
      dateienLaden();
      geteiltAbholen();
      pushStand();
      break;
    case 'faeden':   faedenZeigen(m); break;
    case 'eintrag':  eintragZeigen(m); break;
    case 'zustand':
      if (m.strom) break;            // gehört einem Vorgang, nicht dem Ring
      liveZustand(m.zustand);
      if (m.zustand !== S.zustand) {
        S.zustand = m.zustand;
        if (m.zustand === 'hoert') {
          S.verlauf.fill(0);
          S.untertitel = ''; zeigeUntertitel();
        }
      }
      break;
    case 'pegel':
      // Solange wir selbst aufnehmen, gilt UNSER Pegel. Der Server
      // kennt ihn nicht -- das Mikrofon steht hier. Ohne diese
      // Bedingung überschreibt eine Meldung von dort den Ausschlag,
      // und der Ring steht still, während man redet.
      if (!nimmtAuf) S.pegel = Math.max(0, Math.min(1, Number(m.pegel) || 0));
      break;
    case 'untertitel':
      if (m.strom) break;
      S.untertitel = m.text || ''; S.wer = m.wer || 'sarvis'; S.hervor = 4;
      zeigeUntertitel();
      if (m.wer === 'sarvis') liveText(m.text || '');
      break;
    case 'nachhoeren':
      S.nachhoeren = Number(m.sekunden) || 0;
      S.nachhoerenGanz = Math.max(0.1, S.nachhoeren);
      break;
    case 'werkzeug':
      if (m.aktiv) S.glut.set(m.name, 1.0);
      break;
    case 'freigabe':
      // Leerer Text heisst: nichts steht mehr frei. Der Server schickt
      // ihn bei jeder Aenderung neu -- die Minutenzahl IM Text friert
      // also nur ein, wenn nichts passiert, und dann laeuft ohnehin
      // der Rest darunter ab.
      S.freigabe = m.text || '';
      S.freigabeRest = Number(m.sekunden) || 0;
      break;
    case 'hintergrund':
      S.hintergrund = m.zeilen || [];
      S.hgGesamt = Number(m.gesamt) || S.hintergrund.length;
      S.hgSeit = Number(m.seit) || 0;
      S.hgFertig = !!m.fertig;
      hintergrundZeigen();
      break;
    case 'kachel':     kachelZeigen(m); break;
    case 'kachel_weg': kachelWeg(m.name); break;
    // Nicht oeffnen, sondern anbieten -- siehe seiteZeigen().
    case 'blatt':      blattZeigen(m); break;
    case 'blatt_weg':  blattWeg(m.kennung); break;
    case 'browser':    seiteZeigen(m.adresse); break;
    case 'web_bild':   blickZeigen(m); break;
    // Der Bildstrom. Kommt nur, solange wir ihn angefordert haben --
    // der Server schickt ihn an niemanden sonst.
    case 'schirm':     schirmBild(m); break;
    // Der Server hat abgeschaltet: Browser zu, Ruhezeit abgelaufen,
    // oder er konnte gar nicht erst anfangen. Immer ein Grund, den
    // Schalter zurückzulegen -- sonst behauptet er "läuft".
    case 'schirm_aus': fernsichtAus(true); break;
    case 'browser_zu': seiteZu(); break;
    case 'ton':        tonSpielen(m); break;
    case 'ton_stopp':  tonStopp(m.runde); break;
    // Radio: nicht der Ton selbst, nur die Adresse. Siehe radioAn().
    case 'radio':      radioAn(m); break;
    case 'radio_aus':  radioAus(); break;
    case 'horchen':
      // Während Sarvis redet oder eine Rückfrage läuft, braucht er den
      // Strom nicht. Ohne dieses Wort sendet die Oberfläche weiter, der
      // Rückstand läuft auf, und am Ende wirft der Deckel echte Sprache
      // weg -- ausgerechnet die, die nach dem Reden kommt.
      horchPause = !m.an;
      break;
  }
}

function zeigeUntertitel() {
  const el = document.getElementById('untertitel');
  el.textContent = S.untertitel;
  el.style.color = S.wer === 'du' ? 'rgba(232,241,253,.94)'
    : rgb(FARBEN[S.zustand] || FARBEN.ruhig, 0.92);
}

// Getippte Zeilen und Antwort-Knöpfe gehen NICHT mehr verloren, wenn die
// Leitung gerade weg ist. Vorher warf senden() sie stumm weg, während die
// Oberfläche sie schon als gesagt anzeigte. Gemessen 13.11.2026: Sascha
// tippt "ja" auf eine Rückfrage, das Handy hatte nach dem Aufwachen noch
// keine Verbindung, der Server sah nichts, die Frage lief ab ("Ich habe
// keine Antwort bekommen"). Zurufe warten jetzt bis zum nächsten
// 'willkommen' und gehen dann raus -- aber nur, wenn sie frisch sind.
let bereit = false;                 // erst nach 'willkommen' wirklich drin
const wartet = [];                  // {o, zeit}
const WARTET_HOECHSTENS = 90000;    // ältere Zurufe wären nicht mehr gemeint

function senden(o) {
  if (bereit && draht && draht.readyState === 1) {
    draht.send(JSON.stringify(o));
    return;
  }
  if (o.art === 'zuruf' || o.art === 'formular_antwort') {
    wartet.push({ o, zeit: Date.now() });
    // Steht die Leitung gar nicht, sofort neu verbinden statt auf den
    // nächsten Wiederholversuch zu warten.
    if (!draht || draht.readyState > 1) frischVerbinden();
  }
}

function warteschlangeLeeren() {
  const jetzt = Date.now();
  while (wartet.length) {
    const { o, zeit } = wartet.shift();
    if (jetzt - zeit <= WARTET_HOECHSTENS) draht.send(JSON.stringify(o));
  }
}

// Alte Leitung abhängen und sofort neu aufbauen. Das alte onclose darf
// danach nichts mehr anstoßen, sonst verbinden wir doppelt.
function frischVerbinden() {
  if (draht) {
    draht.onclose = null; draht.onmessage = null; draht.onopen = null;
    try { draht.close(); } catch {}
  }
  draht = null; bereit = false;
  wiederIn = 1000;
  verbinden();
}

// Ein Handy, das geschlafen hat, hält oft noch eine Leitung für "offen",
// die längst tot ist -- was man dann tippt, verschwindet im Nichts. Nach
// längerem Wegsein deshalb beim Zurückkommen gleich frisch verbinden.
let verstecktSeit = 0;
document.addEventListener('visibilitychange', () => {
  if (document.hidden) { verstecktSeit = Date.now(); return; }
  if (verstecktSeit && Date.now() - verstecktSeit > 20000 && schluessel) {
    frischVerbinden();
  }
  verstecktSeit = 0;
});

// =====================================================================
// Ton: hin und zurück
// =====================================================================
let hoerer = null, quelle = null, knoten = null, gesammelt = [], nimmtAuf = false;
// Wie viele Werte davon der Vorlauf beisteuert -- siehe aufnahmeStop().
let vorlaufWerte = 0;

async function aufnahmeStart() {
  if (nimmtAuf) return;
  // SOFORT abgreifen, vor getUserMedia: Was danach im Ring liegt,
  // waere schon die Zeit NACH dem Tastendruck und ueberlappte mit
  // dem, was das Aufnahmemikrofon gleich selbst hoert.
  const vorn = vorlaufNehmen();
  vorlaufWerte = vorn.reduce((n, a) => n + a.length, 0);
  try {
    if (!hoerer) {
      // 16 kHz direkt anfordern -- dann muss nichts umgetastet werden,
      // und Whisper bekommt genau das, was es erwartet.
      hoerer = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
    }
    if (hoerer.state === 'suspended') await hoerer.resume();
    const gewaehlt = localStorage.getItem('sarvis-mikro') || '';
    const strom = await navigator.mediaDevices.getUserMedia({
      audio: {
        ...(gewaehlt ? { deviceId: { exact: gewaehlt } } : {}),
        // Der Echo-Filter auf dem Server vergleicht TEXT, keine Wellen.
        // Was hier nicht unterdrückt wird, hört Sarvis von sich selbst.
        echoCancellation: true, noiseSuppression: true,
        // Aus: Die Weckwort-Schwelle ist ein absoluter Pegel und wird
        // von einer Verstärkungsautomatik wertlos gemacht.
        autoGainControl: false,
      },
    });
    quelle = hoerer.createMediaStreamSource(strom);
    knoten = hoerer.createScriptProcessor(2048, 1, 1);
    // Der Vorlauf steht VOR dem, was jetzt aufgenommen wird. Zwischen
    // beiden bleibt die Anlaufzeit des Mikrofons als Luecke stehen --
    // die ist nicht zurueckzuholen, solange die Aufnahme ein eigenes
    // Mikrofon oeffnet. Ein fehlendes Phonem verkraftet Whisper besser
    // als ein doppeltes, deshalb lieber die Luecke als ein Ueberlapp.
    gesammelt = vorn;
    knoten.onaudioprocess = e => {
      const d = e.inputBuffer.getChannelData(0);
      gesammelt.push(new Float32Array(d));
      let summe = 0; for (let i = 0; i < d.length; i++) summe += d[i] * d[i];
      S.pegel = Math.min(1, Math.pow(Math.sqrt(summe / d.length) / 0.14, 0.6));
    };
    quelle.connect(knoten); knoten.connect(hoerer.destination);
    // Wer zu reden anfängt, während Sarvis noch spricht, unterbricht
    // ihn -- und zwar SOFORT hier, ohne auf den Server zu warten. Der
    // schickt sein ton_stopp gleich hinterher; bis das ankommt, hätte
    // man sich sonst selbst zugehört.
    tonStopp(null);
    nimmtAuf = true;
    S.zustand = 'hoert';
    mikrofoneListen();      // jetzt gibt es auch Namen
  } catch (e) {
    lage('kein Mikrofon', S.verbunden);
  }
}

function aufnahmeStop() {
  if (!nimmtAuf) return;
  nimmtAuf = false; S.pegel = 0;
  try { quelle.disconnect(); knoten.disconnect(); } catch {}
  quelle.mediaStream && quelle.mediaStream.getTracks().forEach(t => t.stop());

  const gesamt = gesammelt.reduce((n, a) => n + a.length, 0);
  // Gemessen wird, was WIRKLICH gedrueckt wurde -- ohne den Vorlauf.
  // Sonst hebt er die Schwelle des Servers (0,4 s) aus: Ein
  // versehentliches Antippen kaeme mit 300 ms geschenkter Zeit
  // darueber und ginge als Aufnahme durch.
  if (gesamt - vorlaufWerte < 16000 * 0.4) { S.zustand = 'ruhig'; return; }

  const alles = new Int16Array(gesamt);
  let i = 0, spitze = 0;
  for (const stueck of gesammelt)
    for (let j = 0; j < stueck.length; j++) {
      const w = stueck[j];
      if (Math.abs(w) > spitze) spitze = Math.abs(w);
      alles[i++] = Math.max(-32768, Math.min(32767, w * 32768));
    }
  gesammelt = [];

  /* Es NICHT stillschweigend hinschicken, wenn nichts drin ist.
   *
   * Genau das ist passiert: 60 Sekunden Aufnahme kamen beim Server an,
   * Whisper war nach einer Zehntelsekunde fertig und verstand nichts,
   * und auf dem Bildschirm stand -- gar nichts. Man drückt dann fester
   * und länger, statt nachzusehen, ob das richtige Mikrofon anliegt.
   *
   * Die Schwelle ist bewusst niedrig: 0,01 trennt "gar kein Signal"
   * von "leise gesprochen". Wer bei 0,02 flüstert, soll durchkommen. */
  if (spitze < 0.01) {
    S.zustand = 'ruhig';
    S.wer = 'sarvis'; S.hervor = 4;
    S.untertitel = 'Da kam kein Ton an. Ist das richtige Mikrofon '
      + 'ausgewählt und nicht stummgeschaltet?';
    zeigeUntertitel();
    return;
  }
  senden({ art: 'sprache', rate: 16000, daten: alsBase64(alles.buffer) });
  S.zustand = 'denkt';
  S.untertitel = ''; zeigeUntertitel();
}

function alsBase64(puffer) {
  const b = new Uint8Array(puffer);
  let s = '';
  for (let i = 0; i < b.length; i += 8192)
    s += String.fromCharCode.apply(null, b.subarray(i, i + 8192));
  return btoa(s);
}

let tonZeit = 0, tonRunde = -1;
const laufendeToene = new Set();

/* Sofort still -- der Gegenpart zum Abbruch auf dem Server.
 *
 * Reinreden ist bei Sarvis ausdrücklich erlaubt ("Wer einen Assistenten
 * nicht unterbrechen kann, wartet jedes Mal eine falsche Antwort zu Ende
 * ab"). Lokal genügte dafür ein sd.stop(): Wenn es zurückkehrt, ist es
 * still. Über Netz gibt es diese Garantie nicht -- der Server kann nur
 * ein Kommando absetzen, und was hier schon im AudioContext eingeplant
 * ist, läuft ohne dieses Zutun weiter.
 *
 * Deshalb zweierlei: alle eingeplanten Quellen abbrechen UND die Runde
 * hochsetzen, damit ein Satz, der beim Abbruch schon unterwegs war,
 * beim Eintreffen verworfen wird. */
function tonStopp(runde) {
  if (runde != null) tonRunde = Math.max(tonRunde, runde);
  laufendeToene.forEach(q => { try { q.stop(); } catch {} });
  laufendeToene.clear();
  tonZeit = hoerer ? hoerer.currentTime : 0;
  // Sarvis ist still -- also darf das Radio sofort wieder laut werden.
  // Auf den eingeplanten Zeitpunkt zu warten hieße, dass es nach einer
  // Unterbrechung noch sekundenlang leise bliebe, ohne dass jemand redet.
  radioLauter(0);
}

function tonSpielen(m) {
  if (!hoerer) hoerer = new (window.AudioContext || window.webkitAudioContext)();
  // Was aus einer alten Runde stammt, ist ungültig -- der Abbruch kann
  // schon unterwegs gewesen sein, als dieser Satz losgeschickt wurde.
  if (m.runde != null && m.runde < tonRunde) return;
  if (m.runde != null) tonRunde = m.runde;
  const roh = atob(m.daten || '');
  const zahlen = new Int16Array(roh.length / 2);
  for (let i = 0; i < zahlen.length; i++)
    zahlen[i] = (roh.charCodeAt(i * 2) | (roh.charCodeAt(i * 2 + 1) << 8)) << 16 >> 16;
  const puffer = hoerer.createBuffer(1, zahlen.length, m.rate || 22050);
  const ziel = puffer.getChannelData(0);
  for (let i = 0; i < zahlen.length; i++) ziel[i] = zahlen[i] / 32768;
  const q = hoerer.createBufferSource();
  q.buffer = puffer; q.connect(hoerer.destination);
  // Nahtlos anhängen, damit zwischen zwei Sätzen keine Lücke entsteht.
  tonZeit = Math.max(tonZeit, hoerer.currentTime);
  q.start(tonZeit); tonZeit += puffer.duration;
  laufendeToene.add(q);
  q.onended = () => laufendeToene.delete(q);
  // Das Radio duckt sich, solange gesprochen wird. Wann das ist, steht
  // genau hier und nirgends sonst: Der Server sagt nicht, wann er zu
  // reden aufhört -- er schickt Ton, und wie lange der dauert, weiß nur,
  // wer ihn eingeplant hat.
  radioDucken(tonZeit - hoerer.currentTime);
}

// =====================================================================
// Radio: der Ton, den nicht Sarvis macht
// =====================================================================
/* Ein Radiostream kommt NICHT über den Draht. Der Server schickt nur die
 * Adresse (`radio`), und das Audio-Element holt sich den Sender direkt.
 * Alles andere hieße: Der Server lädt stundenlang Musik herunter, um sie
 * unverändert weiterzureichen.
 *
 * Bewusst ein <audio> und kein AudioContext-Knoten. Der Kontext hier ist
 * mit 16 kHz für die Aufnahme angefordert; ein Sender in 44,1 kHz müsste
 * dafür umgetastet werden, und ein <audio> kann außerdem puffern,
 * nachladen und eine abgerissene Verbindung überstehen.
 *
 * Getrennt von der Sprachwiedergabe -- das ist der eigentliche Punkt.
 * Sarvis soll ÜBER das Radio reden können, nicht statt seiner. Also
 * leiser drehen, solange Ton ankommt, und danach wieder auf. Abwürgen
 * wäre einfacher und falsch: Wer nach der Uhrzeit fragt, will nicht,
 * dass die Musik aus ist. */
let radio = null, radioSoll = 1.0, radioHeben = null, radioBlende = null;
const RADIO_LEISE = 0.15;
const RADIO_ZUGABE = 0.35;   // Sekunden, bis wieder aufgedreht wird

function radioAn(m) {
  const url = String(m.url || '');
  if (!url) return;
  if (!radio) {
    radio = new Audio();
    radio.preload = 'none';
    // Kein crossOrigin: Wir lesen die Daten nicht, wir spielen sie nur
    // ab. Mit crossOrigin verlangte der Browser CORS-Kopfzeilen, die die
    // wenigsten Sender schicken -- und dann liefe gar nichts.
  }
  radio.src = url;
  radio.volume = laufendeToene.size ? RADIO_LEISE : radioSoll;
  radio.play().catch(() => {
    /* Autoplay-Sperre: Ohne eine Geste des Nutzers auf DIESER Seite gibt
     * der Browser keinen Ton frei. Das ist kein Fehler, den man melden
     * müsste -- es ist einer, den man nachholt. */
    const nachholen = () => radio && radio.play().catch(() => {});
    addEventListener('pointerdown', nachholen, { once: true });
    addEventListener('keydown', nachholen, { once: true });
  });
}

function radioAus() {
  clearTimeout(radioHeben);
  clearInterval(radioBlende);
  if (!radio) return;
  try { radio.pause(); } catch {}
  // src leeren und neu laden: Sonst zieht der Browser den Stream im
  // Hintergrund weiter -- unhörbar, aber Tag und Nacht.
  radio.removeAttribute('src');
  try { radio.load(); } catch {}
}

/* Leiser, solange geredet wird -- und von selbst wieder lauter.
 *
 * `sekunden` ist, wie lange der eingeplante Ton noch dauert. Ein Timer
 * und keine Rückmeldung des Servers: Der weiß gar nicht, wann sein Satz
 * hier verklungen ist. Kommt der nächste Satz früher, schiebt er den
 * Termin einfach weiter. */
function radioDucken(sekunden) {
  if (!radio || radio.paused) return;
  radioBlenden(RADIO_LEISE);
  clearTimeout(radioHeben);
  radioHeben = setTimeout(() => radioBlenden(radioSoll),
    (Math.max(0, sekunden) + RADIO_ZUGABE) * 1000);
}

function radioLauter(verzoegerung) {
  clearTimeout(radioHeben);
  if (!radio || radio.paused) return;
  radioHeben = setTimeout(() => radioBlenden(radioSoll), verzoegerung * 1000);
}

/* Über 200 ms blenden statt springen. Ein Sprung klingt nach Störung;
 * ein Übergang klingt nach Absicht. HTMLMediaElement.volume kann keine
 * Rampe, also von Hand in Schritten. */
function radioBlenden(ziel) {
  clearInterval(radioBlende);
  if (!radio) return;
  const schritte = 8, von = radio.volume, weg = ziel - von;
  let i = 0;
  radioBlende = setInterval(() => {
    i++;
    if (!radio) { clearInterval(radioBlende); return; }
    radio.volume = Math.max(0, Math.min(1, von + weg * (i / schritte)));
    if (i >= schritte) clearInterval(radioBlende);
  }, 25);
}

// =====================================================================
// Mithören: „Hey Sarvis" ohne Tastendruck
// =====================================================================
/* Das Mikrofon bleibt offen, und was es hört, geht blockweise zum
 * Server. Dort läuft dieselbe Erkennung wie früher lokal: erst der
 * Sprach-Erkenner (billig, auf der CPU), und nur wenn wirklich jemand
 * redet, Whisper.
 *
 * Was hier NICHT passiert, ist die Erkennung selbst. Die Schwellen sind
 * mühsam vermessen (sarvis 1,00 · jarvis 0,83 · service 0,62), und sie
 * gehören an EINE Stelle — nicht in jede Oberfläche einzeln, wo sie
 * dreimal auseinanderlaufen.
 *
 * Gebündelt wird auf etwa eine Viertelsekunde. Einzeln zu senden wären
 * acht Nachrichten je Sekunde, nur für Rahmen-Overhead; länger zu
 * sammeln würde das Weckwort träge machen. */
let horchQuelle = null, horchKnoten = null, horcht = false;
let horchPuffer = [], horchPause = false;
const HORCH_BUENDEL = 4096;   // ≈ 256 ms bei 16 kHz

/* Der Vorlauf -- die letzten Millisekunden VOR dem Tastendruck.
 *
 * Menschen druecken die Sprechtaste eine Silbe zu spaet, und
 * aufnahmeStart() oeffnet danach erst das Mikrofon. Beides zusammen
 * frisst regelmaessig das erste Wort. DRAHT.md verlangt deshalb einen
 * Ringpuffer, aus dem beim Loslassen die Zeit davor mitgeht.
 *
 * Gespeist wird er aus dem Mithoer-Strom, weil DER schon laeuft: Ein
 * eigenes Mikrofon nur fuer den Vorlauf hiesse, es dauerhaft offen zu
 * halten -- die Lampe im Tab an, ohne dass jemand zuhoert. Ohne
 * Mithoeren gibt es also keinen Vorlauf; das ist der ehrliche Preis
 * und kein Fehler.
 *
 * Gefuellt wird nur, wenn ohnehin gesendet wuerde -- nicht waehrend
 * horchPause. Sonst stuende Sarvis' eigene Stimme im Vorlauf, und der
 * Echo-Filter auf dem Server vergleicht Text: Er merkt es erst,
 * nachdem Whisper es als Frage des Nutzers gelesen hat. */
const VORLAUF_WERTE = 4800;   // 300 ms bei 16 kHz
let vorlauf = [];

function vorlaufSchieben(block) {
  vorlauf.push(block);
  let summe = vorlauf.reduce((n, a) => n + a.length, 0);
  // Vorn abwerfen, bis es wieder passt. Ein angebrochener Block wird
  // beschnitten statt ganz verworfen -- sonst schwankt der Vorlauf
  // zwischen 170 und 300 ms, je nachdem, wann die Taste faellt.
  while (vorlauf.length > 1 && summe - vorlauf[0].length >= VORLAUF_WERTE) {
    summe -= vorlauf.shift().length;
  }
  if (summe > VORLAUF_WERTE) {
    vorlauf[0] = vorlauf[0].subarray(summe - VORLAUF_WERTE);
  }
}

// Nimmt den Vorlauf heraus und leert ihn -- zweimal dasselbe Stueck
// waere ein Echo im eigenen Satz.
function vorlaufNehmen() {
  const s = vorlauf; vorlauf = [];
  return s;
}

async function horchenStart() {
  if (horcht) return;
  try {
    if (!hoerer) hoerer = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
    if (hoerer.state === 'suspended') await hoerer.resume();
    const gewaehlt = localStorage.getItem('sarvis-mikro') || '';
    const strom = await navigator.mediaDevices.getUserMedia({
      audio: {
        ...(gewaehlt ? { deviceId: { exact: gewaehlt } } : {}),
        echoCancellation: true, noiseSuppression: true, autoGainControl: false,
      },
    });
    horchQuelle = hoerer.createMediaStreamSource(strom);
    horchKnoten = hoerer.createScriptProcessor(2048, 1, 1);
    horchPuffer = [];
    horchKnoten.onaudioprocess = e => {
      // Während des Push-to-talk und während Sarvis redet: nichts
      // schicken. Sonst hört er sich selbst zu, und der Rückstand
      // läuft auf.
      if (nimmtAuf || horchPause) { horchPuffer = []; return; }
      const block = new Float32Array(e.inputBuffer.getChannelData(0));
      vorlaufSchieben(block);
      horchPuffer.push(block);
      const summe = horchPuffer.reduce((n, a) => n + a.length, 0);
      if (summe < HORCH_BUENDEL) return;
      const alles = new Int16Array(summe);
      let i = 0;
      for (const st of horchPuffer)
        for (let k = 0; k < st.length; k++)
          alles[i++] = Math.max(-32768, Math.min(32767, st[k] * 32768));
      horchPuffer = [];
      senden({ art: 'strom', rate: 16000, daten: alsBase64(alles.buffer) });
    };
    horchQuelle.connect(horchKnoten);
    horchKnoten.connect(hoerer.destination);
    horcht = true;
    document.getElementById('mithoeren').classList.add('laeuft');
    mikrofoneListen();
  } catch (e) {
    document.getElementById('horchen').checked = false;
    lage('Mikrofon abgelehnt', S.verbunden);
  }
}

function horchenStop() {
  if (!horcht) return;
  horcht = false; horchPuffer = []; vorlauf = [];
  try {
    horchQuelle.disconnect(); horchKnoten.disconnect();
    horchQuelle.mediaStream.getTracks().forEach(t => t.stop());
  } catch {}
  document.getElementById('mithoeren').classList.remove('laeuft');
}

document.getElementById('horchen').addEventListener('change', e => {
  localStorage.setItem('sarvis-horchen', e.target.checked ? '1' : '');
  e.target.checked ? horchenStart() : horchenStop();
});

/* Ein Blick in Sarvis' Browser.
 *
 * Bewusst ohne Zeitablauf: Eine Kachel liest man im Vorbeigehen, ein
 * Bild sieht man sich an. Was von selbst verschwindet, während man
 * darauf schaut, ist ärgerlicher als eines, das man wegtippen muss. */
function blickZeigen(m) {
  const kasten = document.getElementById('blick');
  const bild = document.getElementById('blickbild');
  if (!m.daten) return;
  // Ein Standbild verdrängt den Live-Strom nicht: Wer zusieht, will
  // weiter zusehen, und das Einzelbild wäre nach einer Achtelsekunde
  // ohnehin überschrieben.
  if (live) return;
  bild.src = 'data:image/webp;base64,' + m.daten;
  bild.alt = m.titel || m.adresse || 'Seite';
  kasten.querySelector('.titel').textContent = m.titel || '(ohne Titel)';
  // Nur der Wirt, nicht die ganze Adresse: Ein Query-String mit
  // sechzig Zeichen sagt weniger als der Name der Seite.
  let ort = m.adresse || '';
  try { ort = new URL(ort).host + new URL(ort).pathname; } catch {}
  kasten.querySelector('.ort').textContent = ort.slice(0, 90);
  kasten.hidden = false;
}

document.getElementById('blattzu').addEventListener('click', blattZu);

/* Escape macht zu, was oben liegt. Erst das Blatt, dann der Blick --
   die Reihenfolge ist die der Stapelung, sonst schliesst eine Taste
   etwas im Hintergrund, waehrend vorn noch etwas steht. */
document.addEventListener('keydown', e => {
  if (e.key !== 'Escape') return;
  if (!document.getElementById('blatt').hidden) { blattZu(); return; }
});

document.getElementById('blickzu').addEventListener('click', () => {
  if (live) { fernsichtAus(); return; }   // Zumachen heißt hier: abschalten
  const kasten = document.getElementById('blick');
  kasten.hidden = true;
  // Das Bild wirklich freigeben. Ein 1280er WebP als data-URI hängt
  // sonst im Speicher, und bei jedem Blick kommt eines dazu.
  document.getElementById('blickbild').removeAttribute('src');
});

// =====================================================================
// Fernsicht: zusehen UND eingreifen
// =====================================================================
/* Auf dem alten Rechner war Sarvis' Browser DER Browser -- er machte
 * ihn auf, man sah hinein und klickte selbst weiter, wenn er nicht
 * weiterkam. Auf dem Server sind es zwei geworden. Das hier näht sie
 * wieder zusammen: Bilder herein ("schirm"), Klicks und Tasten hinaus.
 *
 * ANTEILE, KEINE PIXEL. Was hinausgeht, sind Zahlen zwischen 0 und 1.
 * Der Server rechnet sie mit seiner Fenstergröße in Pixel um. Andersherum
 * müsste die Oberfläche wissen, wie groß Sarvis' Fenster ist, UND ihre
 * eigene Skalierung dazurechnen -- die kennt aber nur sie, und sie
 * ändert sich bei jedem Ziehen am Fensterrand.
 *
 * NICHT AUFS HANDY. Der Schalter steht unter 700 Punkten Breite auf
 * display:none (index.html, mit Begründung). Dort führt der bessere Weg
 * über die Art `browser`: Sarvis schickt die Adresse, und die Seite geht
 * im eigenen Browser auf -- lesbar, mit richtiger Tastatur. */
let live = false;

const SONDERTASTEN = new Set(['Enter', 'Backspace', 'Tab', 'Escape', 'Delete',
  'ArrowLeft', 'ArrowUp', 'ArrowRight', 'ArrowDown',
  'Home', 'End', 'PageUp', 'PageDown']);

/* Getippte Zeichen werden kurz gesammelt.
 *
 * Wer "Wärmepumpe" tippt, löst zehn Tastendrücke aus. Zehn Nachrichten
 * wären zehn Rahmen für zusammen zehn Zeichen -- der Draht bestünde
 * dann fast nur aus Umschlag. 60 ms sind kürzer, als ein Mensch
 * zwischen zwei Anschlägen braucht, und deshalb unbemerkt. Eine
 * Sondertaste leert den Puffer SOFORT, sonst überholte "Enter" den Text
 * davor und die Suchmaske bekäme ein leeres Feld abgeschickt. */
let tippPuffer = '', tippUhr = null;

function tippLeeren() {
  if (tippUhr) { clearTimeout(tippUhr); tippUhr = null; }
  if (!tippPuffer) return;
  senden({ art: 'taste', text: tippPuffer });
  tippPuffer = '';
}

const platz = document.querySelector('#blick .bildplatz');

function fernsichtAn() {
  if (live || !S.verbunden) return;
  live = true;
  const kasten = document.getElementById('blick');
  kasten.hidden = false;
  kasten.classList.add('live');
  kasten.querySelector('.titel').textContent = 'Sarvis’ Browser';
  kasten.querySelector('.ort').textContent =
    'Klicken, tippen und scrollen wirkt dort drüben.';
  const perle = document.getElementById('liveperle');
  perle.hidden = false; perle.classList.add('pause');
  perle.textContent = 'wartet';
  const knopf = document.getElementById('fernsicht');
  knopf.classList.add('an'); knopf.textContent = 'Mitsehen beenden';
  document.getElementById('blickzu').textContent = 'Beenden';
  senden({ art: 'schirm_an', an: true });
  platz.focus();
}

function fernsichtAus(vomServer) {
  if (!live) return;
  live = false;
  tippPuffer = '';
  if (tippUhr) { clearTimeout(tippUhr); tippUhr = null; }
  // Nur sagen, wenn WIR aufhören. Kommt das "schirm_aus" vom Server
  // (Browser zugemacht, Ruhezeit abgelaufen), wäre die Antwort darauf
  // ein Echo ins Leere.
  if (!vomServer) senden({ art: 'schirm_an', an: false });
  const kasten = document.getElementById('blick');
  kasten.classList.remove('live');
  const knopf = document.getElementById('fernsicht');
  knopf.classList.remove('an'); knopf.textContent = 'Browser mitsehen';
  document.getElementById('blickzu').textContent = 'Schließen';
  document.getElementById('liveperle').hidden = true;
  if (vomServer) {
    /* Das letzte Bild bleibt stehen, ABER es ist nicht mehr bedienbar:
     * An `live` hängt jeder Handler. Genau so herum -- wer gerade
     * hinsah, soll sehen, wo es endete, aber nicht in ein Bild klicken,
     * hinter dem keine Seite mehr steht.
     *
     * Kam nie ein Bild, ist der Grund ein anderer und die Meldung
     * auch: Sarvis hatte gar keine Seite offen. Der Kasten bleibt dann
     * trotzdem stehen -- ein Schalter, den man umlegt und bei dem
     * sichtbar nichts passiert, ist die schlechteste Antwort. */
    const hatBild = !!document.getElementById('blickbild').getAttribute('src');
    kasten.querySelector('.titel').textContent =
      hatBild ? 'Sarvis’ Browser' : 'Kein Bild';
    kasten.querySelector('.ort').textContent = hatBild
      ? 'Der Browser ist zu — das hier ist ein Standbild.'
      : 'Sarvis hat gerade keine Seite offen. Es gibt nichts mitzusehen.';
  } else {
    kasten.hidden = true;
    document.getElementById('blickbild').removeAttribute('src');
  }
}

function schirmBild(m) {
  if (!live || !m.daten) return;
  document.getElementById('blickbild').src =
    'data:image/jpeg;base64,' + m.daten;
  const perle = document.getElementById('liveperle');
  if (perle.classList.contains('pause')) {
    perle.classList.remove('pause'); perle.textContent = 'live';
  }
}

/* Wo im BILD wurde geklickt -- als Anteil.
 *
 * Nicht so einfach, wie es aussieht: Das Bild sitzt mit object-fit
 * contain im Kasten und füllt ihn fast nie ganz aus. Wer nur
 * getBoundingClientRect nimmt, rechnet die schwarzen Ränder mit und
 * trifft je nach Seitenverhältnis um bis zu hundert Punkte daneben --
 * und zwar gleichmäßig, was es besonders unangenehm macht: Es sieht
 * aus, als säßen die Knöpfe der Seite woanders, nicht als läge die
 * Rechnung falsch.
 *
 * Also der wirklich gemalte Ausschnitt: eine Skala für beide Achsen,
 * die kleinere gewinnt (das IST contain), der Rest ist Rand, und der
 * Rand liegt zu gleichen Teilen auf beiden Seiten (object-position:
 * center, gesetzt in #blick.live). */
function bildAnteil(ev) {
  const bild = document.getElementById('blickbild');
  const r = bild.getBoundingClientRect();
  const nb = bild.naturalWidth, nh = bild.naturalHeight;
  if (!nb || !nh || !r.width || !r.height) return null;
  const skal = Math.min(r.width / nb, r.height / nh);
  const bb = nb * skal, bh = nh * skal;
  const x = (ev.clientX - (r.left + (r.width - bb) / 2)) / bb;
  const y = (ev.clientY - (r.top + (r.height - bh) / 2)) / bh;
  if (x < 0 || x > 1 || y < 0 || y > 1) return null;   // auf den Rand geklickt
  const pr = platz.getBoundingClientRect();
  return { x, y, px: ev.clientX - pr.left, py: ev.clientY - pr.top };
}

/* Der Mauszeiger fehlt im Bild -- Chrome zeichnet ihn nicht mit. Ohne
 * irgendeine Rückmeldung weiß niemand, ob sein Klick angekommen ist,
 * und klickt ein zweites Mal; bei einem Absende-Knopf ist das genau
 * einmal zu viel. Also ein Ring an der Klickstelle. */
function klickringZeigen(px, py) {
  const ring = document.getElementById('klickring');
  ring.hidden = true;
  ring.style.left = px + 'px';
  ring.style.top = py + 'px';
  // Erzwungenes Neuberechnen: Sonst läuft die Animation beim zweiten
  // Klick auf dieselbe Stelle gar nicht -- der Browser sieht keine
  // Änderung und startet sie nicht neu.
  void ring.offsetWidth;
  ring.hidden = false;
}

platz.addEventListener('pointerdown', ev => {
  if (!live) return;
  const a = bildAnteil(ev);
  if (!a) return;
  ev.preventDefault();
  // Erst der Ring, dann das Senden: Die Rückmeldung soll am Finger
  // hängen und nicht an der Netzlaufzeit.
  klickringZeigen(a.px, a.py);
  platz.focus();
  senden({
    art: 'klick', x: a.x, y: a.y,
    knopf: ev.button === 2 ? 'rechts' : ev.button === 1 ? 'mitte' : 'links',
  });
});

// Das Kontextmenü des EIGENEN Browsers gehört hier nicht hin: Ein
// Rechtsklick ist für die Seite dort drüben gemeint.
platz.addEventListener('contextmenu', ev => { if (live) ev.preventDefault(); });

platz.addEventListener('wheel', ev => {
  if (!live) return;
  const a = bildAnteil(ev);
  if (!a) return;
  ev.preventDefault();
  // `hoch` zählt nach OBEN, deltaY zählt nach unten. Das Vorzeichen
  // dreht hier und nicht auf dem Server: Dort steht der Name, hier
  // steht der Browser, der es andersherum meint.
  senden({ art: 'rollen', x: a.x, y: a.y, hoch: -ev.deltaY });
}, { passive: false });

platz.addEventListener('keydown', ev => {
  if (!live) return;
  // Modifikatoren bleiben HIER. Strg+R soll diese Seite neu laden und
  // nicht die dort drüben, F12 die eigenen Werkzeuge öffnen. Wer die
  // Tastenkürzel der fremden Seite braucht, klickt sie an.
  if (ev.ctrlKey || ev.metaKey || ev.altKey) return;
  if (SONDERTASTEN.has(ev.key)) {
    ev.preventDefault();
    tippLeeren();                       // erst der Text, dann die Taste
    senden({ art: 'taste', sonder: ev.key });
    return;
  }
  if (ev.key.length !== 1) return;      // Shift, F5, CapsLock …
  ev.preventDefault();
  tippPuffer += ev.key;
  if (!tippUhr) tippUhr = setTimeout(tippLeeren, 60);
});

document.getElementById('fernsicht').addEventListener('click', () => {
  live ? fernsichtAus() : fernsichtAn();
});

// =====================================================================
// Bedienung
// =====================================================================
const reden = document.getElementById('reden');
['pointerdown'].forEach(e => reden.addEventListener(e, ev => {
  ev.preventDefault(); reden.classList.add('haelt');
  reden.setPointerCapture && reden.setPointerCapture(ev.pointerId);
  aufnahmeStart();
}));
['pointerup', 'pointercancel', 'pointerleave'].forEach(e =>
  reden.addEventListener(e, () => {
    reden.classList.remove('haelt'); aufnahmeStop();
  }));

/* Am Rechner tut die Leertaste dasselbe wie die Fläche.
 *
 * Nicht, während in Sarvis' Browser getippt wird. Sonst hieße jedes
 * Leerzeichen in "Wärmepumpe Vaillant" gleichzeitig: Aufnahme an. Die
 * Bedingung ist bewusst am FOKUS und nicht an `live` -- wer den
 * Bildstrom nur ansieht, ohne hineingeklickt zu haben, soll die
 * Leertaste behalten. */
const tipptDrueben = () =>
  document.activeElement === document.querySelector('#blick .bildplatz');

document.addEventListener('keydown', e => {
  if (e.code === 'Space' && !e.repeat && !tipptDrueben()
      && document.activeElement.tagName !== 'INPUT') {
    e.preventDefault(); reden.classList.add('haelt'); aufnahmeStart();
  }
});
document.addEventListener('keyup', e => {
  if (e.code === 'Space' && !tipptDrueben()
      && document.activeElement.tagName !== 'INPUT') {
    reden.classList.remove('haelt'); aufnahmeStop();
  }
});

document.getElementById('tippen').addEventListener('submit', e => {
  e.preventDefault();
  const feld = document.getElementById('zeile');
  const text = feld.value.trim();
  if (!text) return;
  senden({ art: 'zuruf', text });
  S.untertitel = text; S.wer = 'du'; S.hervor = 4; zeigeUntertitel();
  feld.value = '';
});

document.getElementById('anmelden').addEventListener('click', () => {
  schluessel = document.getElementById('schluessel').value.trim();
  if (!schluessel) return;
  document.getElementById('torhinweis').textContent = 'verbindet …';
  if (draht) draht.close();
  verbinden();
});
document.getElementById('schluessel').addEventListener('keydown', e => {
  if (e.key === 'Enter') document.getElementById('anmelden').click();
});

/* Welche Mikrofone es gibt.
 *
 * Die Namen bekommt man erst NACH der ersten Erlaubnis -- vorher liefert
 * der Browser leere Beschriftungen, aus Sorge, dass eine Seite Geräte
 * zum Wiedererkennen benutzt. Deshalb wird die Liste nach der ersten
 * Aufnahme noch einmal geholt. */
async function mikrofoneListen() {
  if (!navigator.mediaDevices || !navigator.mediaDevices.enumerateDevices) return;
  let geraete;
  try { geraete = await navigator.mediaDevices.enumerateDevices(); }
  catch { return; }
  const mikros = geraete.filter(g => g.kind === 'audioinput');
  const feld = document.getElementById('mikro');
  if (mikros.length < 2) { feld.classList.remove('zeigen'); return; }
  const gewaehlt = localStorage.getItem('sarvis-mikro') || '';
  feld.innerHTML = '<option value="">Mikrofon: Standard</option>'
    + mikros.map((m, i) =>
        `<option value="${m.deviceId}"${m.deviceId === gewaehlt ? ' selected' : ''}>`
        + `${sicher(m.label || 'Mikrofon ' + (i + 1))}</option>`).join('');
  feld.classList.add('zeigen');
}

document.getElementById('mikro').addEventListener('change', e => {
  localStorage.setItem('sarvis-mikro', e.target.value);
  // Den alten Strom fallen lassen, damit die neue Wahl beim nächsten
  // Drücken wirklich greift.
  if (hoerer) { try { hoerer.close(); } catch {} hoerer = null; }
});

// --- Los --------------------------------------------------------------
messen();
mikrofoneListen();
if (localStorage.getItem('sarvis-horchen')) {
  document.getElementById('horchen').checked = true;
  // Erst nach der Verbindung -- ohne Draht ginge das Senden ins Leere.
  setTimeout(() => { if (S.verbunden) horchenStart(); }, 1500);
}
requestAnimationFrame(schlag);
if (schluessel) { document.getElementById('tor').classList.add('weg'); verbinden(); }
// An der WURZEL registriert -- unter /dabei/ reichte er nur bis /dabei/
// und sah das Teilen aus dem Android-Menue nie (POST /teilen).
if ('serviceWorker' in navigator)
{
  navigator.serviceWorker.register('/waechter.js', { scope: '/' }).catch(() => {});
  // Den alten unter /dabei/ abmelden -- er speicherte jede Antwort.
  navigator.serviceWorker.getRegistrations().then(alle => alle
    .filter(r => r.scope.endsWith('/dabei/')).forEach(r => r.unregister()))
    .catch(() => {});
}

// =====================================================================
// Dateien: hin (Büroklammer, Einfügen, Ziehen, Teilen) und her (Ablage)
// =====================================================================
const BILD_ENDUNG = /\.(jpe?g|png|gif|webp|bmp)$/i;
const FEHLER_DATEI = {
  401: 'kein Zugang — Schlüssel prüfen',
  413: 'zu groß',
  415: 'diese Art Datei nimmt er nicht',
};

function hinweis(text) {
  S.untertitel = text; S.wer = 'du'; S.hervor = 4; zeigeUntertitel();
}

/* Eine Datei hochladen, mit Fortschritt. XMLHttpRequest statt fetch,
 * weil nur er den Upload-Fortschritt meldet -- bei 40 MB über Mobilfunk
 * ist "es passiert nichts" sonst nicht von "es hängt" zu unterscheiden. */
function einsHochladen(datei) {
  return new Promise(fertig => {
    const x = new XMLHttpRequest();
    x.open('POST', '/datei');
    x.setRequestHeader('X-Sarvis-Schluessel', schluessel);
    x.upload.onprogress = e => {
      if (e.lengthComputable && e.total > 300000)
        hinweis(`Schicke ${datei.name} … ${Math.round(e.loaded / e.total * 100)} %`);
    };
    x.onload = () => {
      let a = {}; try { a = JSON.parse(x.responseText); } catch {}
      if (x.status === 200 && a.gut) { fertig(true); return; }
      const warum = FEHLER_DATEI[x.status] || a.fehler || `Fehler ${x.status}`;
      const dazu = a.endung ? ` (${a.endung})` : '';
      hinweis(`${datei.name}: ${warum}${dazu}`);
      fertig(false);
    };
    x.onerror = () => { hinweis(`${datei.name}: Verbindung abgebrochen`); fertig(false); };
    const form = new FormData();
    form.append('datei', datei, datei.name || 'datei');
    x.send(form);
  });
}

async function hochladen(dateien) {
  const liste = Array.from(dateien || []).filter(d => d && d.size !== undefined);
  if (!liste.length) return;
  if (!schluessel) { hinweis('Erst verbinden, dann schicken.'); return; }
  let gut = 0;
  for (const d of liste) {
    hinweis(`Schicke ${d.name} …`);
    if (await einsHochladen(d)) gut++;
  }
  if (gut) {
    const was = gut === 1 ? liste[0].name : `${gut} Dateien`;
    hinweis(`${was} ist bei Sarvis — frag ihn einfach dazu.`);
    document.getElementById('zeile').focus();
  }
  dateienLaden();
}

// Büroklammer
document.getElementById('anhang').addEventListener('click', () =>
  document.getElementById('dateiwahl').click());
document.getElementById('dateiwahl').addEventListener('change', e => {
  hochladen(e.target.files);
  e.target.value = '';      // dieselbe Datei zweimal hintereinander geht sonst nicht
});

// Einfügen (Strg+V) -- ein Bildschirmfoto direkt an Sarvis.
document.addEventListener('paste', e => {
  const dateien = e.clipboardData && e.clipboardData.files;
  if (dateien && dateien.length) { e.preventDefault(); hochladen(dateien); }
});

// Ziehen und Loslassen am Rechner.
let ziehTiefe = 0;
const ziehfeld = document.getElementById('ziehfeld');
const hatDateien = e => e.dataTransfer && Array.from(e.dataTransfer.types || []).includes('Files');
document.addEventListener('dragenter', e => {
  if (!hatDateien(e)) return;
  e.preventDefault(); ziehTiefe++; ziehfeld.hidden = false;
});
document.addEventListener('dragover', e => { if (hatDateien(e)) e.preventDefault(); });
document.addEventListener('dragleave', e => {
  if (!hatDateien(e)) return;
  if (--ziehTiefe <= 0) { ziehTiefe = 0; ziehfeld.hidden = true; }
});
document.addEventListener('drop', e => {
  if (!hatDateien(e)) return;
  e.preventDefault(); ziehTiefe = 0; ziehfeld.hidden = true;
  hochladen(e.dataTransfer.files);
});

/* Teilen aus dem Android-Menü. Der Service Worker hat die Dateien in
 * einen eigenen Zwischenspeicher gelegt (er kennt den Schlüssel nicht,
 * der liegt hier im localStorage) -- jetzt holen wir sie ab und
 * schicken sie mit Schlüssel hoch. */
async function geteiltAbholen() {
  const such = new URLSearchParams(location.search);
  if (!such.has('geteilt')) return;
  history.replaceState(null, '', '/');
  if (such.get('geteilt') === 'verpasst') {
    hinweis('Das Teilen kam nicht durch — bitte noch einmal teilen.');
    return;
  }
  if (!('caches' in window)) return;
  const lager = await caches.open('sarvis-teilen');
  const schluesselListe = await lager.keys();
  const dateien = []; let text = '';
  for (const anfrage of schluesselListe) {
    const antwort = await lager.match(anfrage);
    if (antwort) {
      if (antwort.headers.get('X-Text')) text = await antwort.text();
      else {
        const name = decodeURIComponent(antwort.headers.get('X-Name') || 'geteilt');
        const blob = await antwort.blob();
        dateien.push(new File([blob], name, { type: blob.type }));
      }
    }
    await lager.delete(anfrage);
  }
  if (dateien.length) await hochladen(dateien);
  // Geteilter Text oder Link: ins Eingabefeld, damit man noch sagen
  // kann, was damit passieren soll -- nicht blind abschicken.
  if (text) { const z = document.getElementById('zeile'); z.value = text; z.focus(); }
}

/* Die Ablage -- seit 11.11.2026 alles, was Sarvis erzeugt hat: Blätter,
 * Berichte, Dateien. Kommt von GET /ablage (gespraeche.py). Die alte
 * Dateiliste (GET /dateien) gibt es für andere Apps weiter. */
let ablageDaten = { eintraege: [], von_dir: [] };
let ablageFilter = '';
const zeitDeutsch = sek => {
  const d = new Date(sek * 1000), heute = new Date();
  const uhr = d.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' });
  return d.toDateString() === heute.toDateString() ? `heute ${uhr}`
    : d.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit' }) + ' ' + uhr;
};
// Für Attributwerte: sicher() lässt Anführungszeichen stehen.
const attr = t => sicher(t).replace(/"/g, '&quot;');
const mitSchluessel = (mehr) => Object.assign({ 'X-Sarvis-Schluessel': schluessel }, mehr || {});

async function dateienLaden() {
  if (!schluessel) return;
  try {
    const a = await fetch('/ablage', { headers: mitSchluessel(), cache: 'no-store' });
    if (!a.ok) return;
    ablageDaten = await a.json();
  } catch { return; }
  // "Neu" zählt nur Dateien und Berichte -- ein Blatt hat man gerade im
  // Verlauf gesehen, das ist keine Nachricht.
  const gesehen = Number(localStorage.getItem('sarvis-dateien-gesehen') || 0);
  const neu = (ablageDaten.eintraege || [])
    .filter(d => d.sorte !== 'markdown' && d.seit > gesehen).length;
  const marke = document.getElementById('dateienneu');
  marke.textContent = neu; marke.hidden = !neu;
  if (!document.getElementById('ablage').hidden) ablageMalen();
}

const ABLAGE_ZEICHEN = { markdown: '&#128221;', html: '&#128202;', datei: '&#128196;' };

function ablageMalen() {
  const gesehen = Number(localStorage.getItem('sarvis-dateien-gesehen') || 0);
  const alle = (ablageDaten.eintraege || []).filter(d => !ablageFilter || d.sorte === ablageFilter);
  const hin = ablageDaten.von_dir || [];
  let html = '';
  if (ablageFilter !== 'dir') {
    html += alle.length ? alle.map(d => {
      const name = sicher(d.titel || d.datei || 'Ohne Titel');
      const unter = d.faden_titel ? `<small>aus „${sicher(d.faden_titel)}“</small>`
        : (d.datei && d.datei !== d.titel ? `<small>${sicher(d.datei)}</small>` : '');
      const groesse = d.sorte !== 'markdown' && d.bytes ? menge(d.bytes) + '<br>' : '';
      const neu = d.sorte !== 'markdown' && d.seit > gesehen ? ' neu' : '';
      return `<button type="button" class="datei${d.vorhanden ? '' : ' weg'}${neu}" `
        + `data-schluessel="${attr(d.schluessel)}"${d.vorhanden ? '' : ' disabled'}>`
        + `<span class="art">${ABLAGE_ZEICHEN[d.sorte] || ABLAGE_ZEICHEN.datei}</span>`
        + `<span class="name">${name}${unter}</span>`
        + `<span class="neben">${d.vorhanden ? groesse : 'nicht mehr da<br>'}${zeitDeutsch(d.seit)}</span>`
        + `</button>`;
    }).join('') : '<div class="leer">Hier liegt noch nichts. Sag einfach „schick mir …“ '
      + 'oder „zeig mir das als Blatt“.</div>';
  }
  if (!ablageFilter || ablageFilter === 'dir') {
    html += '<h3>Von dir geschickt</h3>' + (hin.length ? hin.map(d =>
      `<div class="datei"><span class="art">&#128206;</span><span class="name">${sicher(d.datei)}</span>`
      + `<span class="neben">${menge(d.bytes)}<br>${zeitDeutsch(d.seit)}</span></div>`).join('')
      : '<div class="leer">Noch nichts — Büroklammer unten, Einfügen oder Teilen.</div>');
  }
  document.querySelector('#ablage .liste').innerHTML = html;
}

/* Ein Stück aus der Ablage holen. Die Adresse unter /blatt/ läuft nach
 * 7 bzw. 30 Tagen ab -- mit Schlüssel bekommt sie hier eine neue Frist. */
async function ablageHolen(schl) {
  let a, r;
  try {
    r = await fetch('/ablage/oeffnen', { method: 'POST', cache: 'no-store',
      headers: mitSchluessel({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ schluessel: schl }) });
    a = await r.json();
  } catch { hinweis('Die Ablage ist gerade nicht erreichbar.'); return; }
  if (r.status === 410) { hinweis('Diese Datei liegt nicht mehr da.'); return; }
  if (!r.ok) { hinweis(a.fehler || `Fehler ${r.status}`); return; }
  document.getElementById('ablage').hidden = true;
  blattZeigen({ kennung: schl, sorte: a.sorte === 'html' ? 'html'
    : a.sorte === 'markdown' ? 'markdown' : 'datei',
    titel: a.titel, adresse: a.adresse, datei: a.datei, bytes: a.bytes, inhalt: a.inhalt });
}

document.getElementById('dateienknopf').addEventListener('click', () => {
  const el = document.getElementById('ablage');
  el.hidden = !el.hidden;
  if (el.hidden) return;
  ablageMalen();
  dateienLaden();
  // Ab jetzt gilt alles bis hierhin als gesehen.
  const neuestes = Math.max(0, ...(ablageDaten.eintraege || []).map(d => d.seit));
  if (neuestes) localStorage.setItem('sarvis-dateien-gesehen', String(neuestes));
  document.getElementById('dateienneu').hidden = true;
});
document.getElementById('ablagezu').addEventListener('click', () => {
  document.getElementById('ablage').hidden = true;
});
document.querySelector('#ablage .filter').addEventListener('click', e => {
  const b = e.target.closest('button[data-sorte]');
  if (!b) return;
  ablageFilter = b.dataset.sorte;
  document.querySelectorAll('#ablage .filter button')
    .forEach(x => x.classList.toggle('an', x === b));
  ablageMalen();
});
document.querySelector('#ablage .liste').addEventListener('click', e => {
  const b = e.target.closest('button[data-schluessel]');
  if (b && !b.disabled) ablageHolen(b.dataset.schluessel);
});

// =====================================================================
// Gesprächsfäden und Verlauf (seit 11.11.2026)
// =====================================================================
/* Der Verlauf liegt auf dem Server (gespraeche.py) und kommt auf zwei
 * Wegen: GET /verlauf beim Verbinden und Wechseln, der Draht ("eintrag")
 * für alles, was danach geschieht. Dieselbe id heißt derselbe Eintrag mit
 * neuem Stand. Es gibt EINEN aktiven Faden für alle Oberflächen -- wer
 * wechselt, wechselt überall ("faeden"). */
const F = { aktiv: '', liste: [], wechselt: false, geladen: '', alle: [],
            mehr: false, treffer: [], archivAuf: false };
const eintraegeEl = document.getElementById('eintraege');
const verlaufEl = document.getElementById('verlauf');
const liveEl = document.getElementById('live');
const fadenTitel = f => (f && f.titel) || 'Neues Gespräch';
const uhrzeit = sek => new Date(sek * 1000)
  .toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' });
const tagVon = sek => new Date(sek * 1000).toDateString();

function tagName(sek) {
  const d = new Date(sek * 1000), heute = new Date();
  const gestern = new Date(); gestern.setDate(heute.getDate() - 1);
  if (d.toDateString() === heute.toDateString()) return 'Heute';
  if (d.toDateString() === gestern.toDateString()) return 'Gestern';
  return d.toLocaleDateString('de-DE', { weekday: 'long', day: 'numeric', month: 'long' });
}

function wannKurz(sek) {
  if (!sek) return '';
  const d = new Date(sek * 1000), heute = new Date();
  if (d.toDateString() === heute.toDateString()) return uhrzeit(sek);
  if ((heute - d) < 6 * 86400000) return d.toLocaleDateString('de-DE', { weekday: 'short' });
  return d.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit', year: '2-digit' });
}

function istUnten() {
  return verlaufEl.scrollHeight - verlaufEl.scrollTop - verlaufEl.clientHeight < 80;
}
function nachUnten() {
  requestAnimationFrame(() => { verlaufEl.scrollTop = verlaufEl.scrollHeight; });
}

// --- Fäden -------------------------------------------------------------
function faedenZeigen(m) {
  F.liste = Array.isArray(m.liste) ? m.liste : [];
  F.wechselt = !!m.wechselt;
  const vorher = F.aktiv;
  F.aktiv = String(m.aktiv || '');
  const jetzt = F.liste.find(f => f.id === F.aktiv);
  const t = document.getElementById('fadentitel');
  t.textContent = F.wechselt ? 'wechselt …' : fadenTitel(jetzt);
  t.classList.toggle('wechselt', F.wechselt);
  document.title = jetzt && jetzt.titel ? `${jetzt.titel} · Sarvis` : 'Sarvis';
  fadenlisteMalen();
  if (F.aktiv && (F.aktiv !== vorher || F.geladen !== F.aktiv)) verlaufLaden();
}

function fadenZeile(f) {
  const zurueck = f.archiviert;
  return `<div class="faden${f.id === F.aktiv ? ' aktiv' : ''}" data-faden="${attr(f.id)}">`
    + `<div class="was"><div class="name">${sicher(fadenTitel(f))}</div>`
    + `<div class="wann">${wannKurz(f.zuletzt)}${f.eintraege ? ' · ' + f.eintraege : ''}</div></div>`
    + `<button type="button" data-tun="umbenennen" title="Umbenennen" aria-label="Umbenennen">&#9998;</button>`
    + `<button type="button" data-tun="${zurueck ? 'zurueck' : 'archivieren'}" `
    + `title="${zurueck ? 'Aus dem Archiv holen' : 'Archivieren'}" `
    + `aria-label="${zurueck ? 'Aus dem Archiv holen' : 'Archivieren'}">${zurueck ? '&#8634;' : '&#128451;'}</button>`
    + `</div>`;
}

function fadenlisteMalen() {
  const wort = document.getElementById('fadensuche').value.trim().toLowerCase();
  const passt = f => !wort || fadenTitel(f).toLowerCase().includes(wort);
  const offen = F.liste.filter(f => !f.archiviert && passt(f));
  const archiv = F.liste.filter(f => f.archiviert && passt(f));
  let html = offen.map(fadenZeile).join('')
    || `<div class="leer" style="padding:6px 8px;font-size:12px;opacity:.5">${wort ? 'Kein Titel passt.' : 'Noch keine Gespräche.'}</div>`;
  if (archiv.length) {
    const auf = F.archivAuf || !!wort;
    html += `<h3 class="archivkopf" style="cursor:pointer">Archiv · ${archiv.length} ${auf ? '&#9662;' : '&#9656;'}</h3>`
      + (auf ? archiv.map(fadenZeile).join('') : '');
  }
  if (wort.length >= 2 && F.treffer.length) {
    html += '<h3>Im Verlauf gefunden</h3>' + F.treffer.map(t =>
      `<div class="treffer" data-faden="${attr(t.faden)}">${sicher(t.text.slice(0, 120))}`
      + `<small>${sicher(t.faden_titel || 'Neues Gespräch')} · ${wannKurz(t.zeit)}</small></div>`).join('');
  }
  document.getElementById('fadenliste').innerHTML = html;
}

function schubladeAuf() {
  document.getElementById('faeden').classList.add('offen');
  document.getElementById('schleier').hidden = false;
}
function schubladeZu() {
  document.getElementById('faeden').classList.remove('offen');
  document.getElementById('schleier').hidden = true;
}

function umbenennen(kennung) {
  const f = F.liste.find(x => x.id === kennung);
  const titel = window.prompt('Wie soll das Gespräch heißen?', f ? f.titel : '');
  if (titel === null) return;
  senden({ art: 'faden_umbenennen', faden: kennung, titel: titel.trim() });
}

function fadenNeu() {
  senden({ art: 'faden_neu' });
  schubladeZu();
  document.getElementById('zeile').focus();
}

document.getElementById('faedenknopf').addEventListener('click', schubladeAuf);
document.getElementById('faedenzu').addEventListener('click', schubladeZu);
document.getElementById('schleier').addEventListener('click', schubladeZu);
document.getElementById('fadenneu').addEventListener('click', fadenNeu);
document.getElementById('fadenneu2').addEventListener('click', fadenNeu);
document.getElementById('fadentitel').addEventListener('click', () => {
  if (F.aktiv) umbenennen(F.aktiv);
});
document.getElementById('fadenliste').addEventListener('click', e => {
  if (e.target.closest('.archivkopf')) {
    F.archivAuf = !F.archivAuf; fadenlisteMalen(); return;
  }
  const knopf = e.target.closest('button[data-tun]');
  const zeile = e.target.closest('[data-faden]');
  if (!zeile) return;
  const kennung = zeile.dataset.faden;
  if (knopf) {
    const tun = knopf.dataset.tun;
    if (tun === 'umbenennen') umbenennen(kennung);
    else senden({ art: 'faden_archivieren', faden: kennung, an: tun === 'archivieren' });
    return;
  }
  if (kennung !== F.aktiv) senden({ art: 'faden_wechseln', faden: kennung });
  schubladeZu();
});

let sucheUhr = 0;
document.getElementById('fadensuche').addEventListener('input', e => {
  fadenlisteMalen();
  clearTimeout(sucheUhr);
  const wort = e.target.value.trim();
  if (wort.length < 2) { F.treffer = []; return; }
  sucheUhr = setTimeout(async () => {
    try {
      const r = await fetch('/suche?q=' + encodeURIComponent(wort),
                            { headers: mitSchluessel(), cache: 'no-store' });
      if (!r.ok) return;
      F.treffer = (await r.json()).treffer || [];
      fadenlisteMalen();
    } catch { /* still */ }
  }, 300);
});

// --- Verlauf -----------------------------------------------------------
async function verlaufLaden(vor) {
  if (!schluessel || !F.aktiv) return;
  const faden = F.aktiv;
  const q = new URLSearchParams({ faden, anzahl: '60' });
  if (vor) q.set('vor', String(vor));
  let a;
  try {
    const r = await fetch('/verlauf?' + q, { headers: mitSchluessel(), cache: 'no-store' });
    if (!r.ok) return;
    a = await r.json();
  } catch { return; }
  if (faden !== F.aktiv) return;          // inzwischen gewechselt
  const neu = a.eintraege || [];
  if (vor) {
    const vorher = verlaufEl.scrollHeight;
    F.alle = neu.concat(F.alle);
    F.mehr = !!a.mehr;
    alleMalen();
    verlaufEl.scrollTop += verlaufEl.scrollHeight - vorher;
    return;
  }
  // Was während des Ladens schon über den Draht kam, nicht verlieren.
  const hoechste = neu.length ? neu[neu.length - 1].id : 0;
  const spaeter = F.alle.filter(e => e.faden === faden && e.id > hoechste);
  F.alle = neu.concat(spaeter);
  F.mehr = !!a.mehr;
  F.geladen = faden;
  alleMalen();
  nachUnten();
}

function alleMalen() {
  eintraegeEl.innerHTML = '';
  let tag = '';
  for (const e of F.alle) {
    if (tagVon(e.zeit) !== tag) { tag = tagVon(e.zeit); eintraegeEl.appendChild(tagEl(e.zeit)); }
    eintraegeEl.appendChild(eintragEl(e));
  }
  document.getElementById('aelter').hidden = !F.mehr;
  leerPruefen();
}

function tagEl(sek) {
  const el = document.createElement('div');
  el.className = 'tag'; el.textContent = tagName(sek);
  return el;
}

function leerPruefen() {
  document.getElementById('vorschlaege').hidden = !(F.geladen === F.aktiv && !F.alle.length);
}

function eintragZeigen(m) {
  if (!m || m.faden !== F.aktiv) return;
  const e = { id: m.id, faden: m.faden, zeit: m.zeit, wer: m.wer, sorte: m.sorte,
              text: m.text || '', daten: m.daten || {}, geraet: m.geraet || '' };
  const i = F.alle.findIndex(x => x.id === e.id);
  if (i >= 0) {
    F.alle[i] = e;
    const alt = eintraegeEl.querySelector(`[data-id="${e.id}"]`);
    if (alt) alt.replaceWith(eintragEl(e));
    return;
  }
  const unten = istUnten();
  const letzt = F.alle[F.alle.length - 1];
  F.alle.push(e);
  if (!letzt || tagVon(letzt.zeit) !== tagVon(e.zeit)) eintraegeEl.appendChild(tagEl(e.zeit));
  eintraegeEl.appendChild(eintragEl(e));
  if (e.wer === 'sarvis' && (e.sorte === 'text' || e.sorte === 'meldung')) liveWeg();
  leerPruefen();
  if (unten || e.wer === 'du') nachUnten();
}

const AUSGANG = { ja: 'Du hast ja gesagt.', nein: 'Nicht ausgeführt.',
                  anders: 'Du wolltest es anders.', abgebrochen: 'Abgebrochen.' };

function klartext(md) {
  return String(md || '').replace(/```[\s\S]*?```/g, ' ')
    .replace(/[#>*_`~|]+/g, ' ').replace(/\[([^\]]*)\]\([^)]*\)/g, '$1')
    .replace(/^\s*[-+]\s+(\[[ x]\]\s*)?/gm, '· ').replace(/\s+/g, ' ').trim();
}

// Adressen in einer Textblase anklickbar machen. Erst sicher(), dann
// verlinken -- es entsteht kein Tag aus der Nachricht selbst, nur <a>
// um eine https-Adresse, die schon entschaerft ist.
function verlinkt(text) {
  return sicher(text).replace(/https:\/\/[^\s<>"')\]]+/g, url => {
    const sauber = url.replace(/[.,;:!?]+$/, '');
    const rest = url.slice(sauber.length);
    return `<a href="${sauber}" target="_blank" rel="noopener noreferrer">${sauber}</a>${rest}`;
  });
}

// Offene Fragen eines Auftrags als Formular. Offen: Eingabefelder und
// "Absenden". Beantwortet: die Antworten zum Nachlesen.
function formularKarte(e) {
  const d = e.daten || {};
  const fragen = Array.isArray(d.fragen) ? d.fragen : [];
  const antworten = d.antworten || {};
  let h = `<div class="blase"><strong>${sicher(e.text || 'Fragen')}</strong>`;
  fragen.forEach((f, i) => {
    const nr = String(f.nr != null ? f.nr : i + 1);
    const titel = f.titel || f.frage || `Frage ${nr}`;
    const hinweis = f.titel ? (f.frage || '') : '';
    h += `<div class="feld"><label for="f-${e.id}-${sicher(nr)}">${sicher(nr)}. ${sicher(titel)}</label>`
      + (hinweis ? `<div class="hinweis">${sicher(hinweis)}</div>` : '');
    h += d.offen
      ? `<textarea id="f-${e.id}-${sicher(nr)}" data-nr="${sicher(nr)}" rows="1"
           placeholder="leer lassen = weiß ich noch nicht"></textarea>`
      : `<div class="antwort">${sicher(antworten[nr] || '— offen gelassen')}</div>`;
    h += `</div>`;
  });
  h += d.offen
    ? `<div class="knoepfe"><button type="button" data-formular="${e.id}">Absenden</button>`
      + `<span class="klein">Sarvis gibt es an den Arbeiter weiter.</span></div>`
    : `<div class="knoepfe"><span class="klein">Beantwortet und weitergegeben.</span></div>`;
  return h + `</div>`;
}

function blattKarte(e) {
  const d = e.daten || {};
  const art = d.sorte === 'html' ? 'Bericht' : d.sorte === 'datei' ? 'Datei'
    : d.sorte === 'seite' ? 'Webseite' : 'Blatt';
  const kopf = sicher(e.text || d.titel || d.datei || art);
  const vor = d.sorte === 'seite' ? String(d.adresse || '')
    : d.sorte === 'markdown' ? klartext(d.inhalt).slice(0, 240)
    : d.sorte === 'datei' ? [d.datei, menge(d.bytes)].filter(Boolean).join(' · ') : '';
  return `<div class="karte"><div class="art">${art}</div><div class="kopf">${kopf}</div>`
    + (vor ? `<div class="vorschau">${sicher(vor)}</div>` : '')
    + `<div class="tun"><button type="button" data-oeffnen="${e.id}">`
    + `${d.sorte === 'datei' ? 'Holen' : 'Öffnen'}</button></div></div>`;
}

function eintragEl(e) {
  const el = document.createElement('div');
  el.dataset.id = e.id;
  const d = e.daten || {};
  if (e.wer === 'system') {
    el.className = 'e system';
    el.textContent = e.text;
    return el;
  }
  el.className = `e ${e.wer === 'du' ? 'du' : 'sarvis'}`;
  let innen = '';
  if (e.sorte === 'frage') {
    el.classList.add('frage');
    innen = `<div class="blase">${sicher(e.text)}</div>` + (d.offen
      ? `<div class="knoepfe"><button type="button" data-antwort="Ja">Ja</button>`
        + `<button type="button" class="nein" data-antwort="Nein">Nein</button></div>`
      : `<div class="ausgang">${sicher(AUSGANG[d.entscheidung] || '')}</div>`);
  } else if (e.sorte === 'formular') {
    el.classList.add('formular');
    innen = formularKarte(e);
  } else if (e.sorte === 'blatt') {
    innen = blattKarte(e);
  } else if (e.sorte === 'datei') {
    innen = `<div class="karte"><div class="art">Geschickt</div>`
      + `<div class="kopf">&#128206; ${sicher(d.datei || e.text)}</div>`
      + (d.bytes ? `<div class="vorschau">${menge(d.bytes)}</div>` : '') + `</div>`;
  } else if (e.sorte !== 'kachel') {
    if (e.sorte === 'meldung') el.classList.add('meldung');
    innen = `<div class="blase">${verlinkt(e.text)}</div>`;
  }
  el.innerHTML = innen;
  if (e.sorte === 'kachel') {
    // Eine Kachel bleibt ein Bild: gemalt wie auf der Bühne, nicht anklickbar.
    const huelle = document.createElement('div');
    huelle.className = 'kachelkarte';
    const k = document.createElement('div');
    k.className = 'kachel';
    huelle.appendChild(k);
    el.appendChild(huelle);
    const breite = Math.max(200, Math.min(320, (verlaufEl.clientWidth || 360) * 0.8)) - 24;
    try { kachelFuellen(k, d, breite); } catch { k.textContent = e.text; }
  }
  const zeit = document.createElement('div');
  zeit.className = 'zeit';
  zeit.innerHTML = uhrzeit(e.zeit)
    + (d.unterbrochen ? ' · <span class="unterbrochen">unterbrochen</span>' : '');
  el.appendChild(zeit);
  return el;
}

eintraegeEl.addEventListener('click', e => {
  const absenden = e.target.closest('button[data-formular]');
  if (absenden) {
    const karte = absenden.closest('.formular');
    const antworten = {};
    karte.querySelectorAll('textarea[data-nr]').forEach(t => {
      antworten[t.dataset.nr] = t.value.trim();
    });
    senden({ art: 'formular_antwort', eintrag: Number(absenden.dataset.formular), antworten });
    absenden.disabled = true;
    karte.querySelectorAll('textarea').forEach(t => { t.disabled = true; });
    return;
  }
  const antwort = e.target.closest('button[data-antwort]');
  if (antwort) {
    // Dieselbe Antwort, als wäre sie gesagt worden -- der Server sieht
    // einen gewöhnlichen Zuruf während der offenen Rückfrage.
    senden({ art: 'zuruf', text: antwort.dataset.antwort });
    antwort.parentElement.querySelectorAll('button').forEach(b => { b.disabled = true; });
    return;
  }
  const auf = e.target.closest('button[data-oeffnen]');
  if (!auf) return;
  const eintrag = F.alle.find(x => String(x.id) === auf.dataset.oeffnen);
  if (!eintrag) return;
  const d = eintrag.daten || {};
  if (d.sorte === 'seite') {
    blattZeigen({ kennung: d.kennung || ('verlauf-' + eintrag.id),
                  sorte: 'seite', titel: eintrag.text || d.titel,
                  adresse: d.adresse });
  } else if (d.sorte === 'markdown') {
    blattZeigen({ kennung: 'verlauf-' + eintrag.id, sorte: 'markdown',
                  titel: eintrag.text || d.titel, inhalt: d.inhalt });
  } else if (d.kennung) {
    ablageHolen(d.kennung);
  }
});

document.getElementById('aelter').addEventListener('click', () => {
  if (F.alle.length) verlaufLaden(F.alle[0].id);
});

document.getElementById('vorschlaege').addEventListener('click', e => {
  const b = e.target.closest('button[data-satz]');
  if (!b) return;
  const z = document.getElementById('zeile');
  z.value = b.dataset.satz; z.focus();
});

// --- Was gerade gesprochen wird ---------------------------------------
function liveZustand(z) {
  if (z === 'denkt') {
    const unten = istUnten();
    liveEl.innerHTML = '<div class="blase punkte"><span></span><span></span><span></span></div>';
    liveEl.hidden = false;
    if (unten) nachUnten();
  } else if (z === 'ruhig' || z === 'hoert') {
    liveWeg();
  }
}
function liveText(text) {
  text = String(text || '').trim();
  if (!text) return;
  // Steht derselbe Satz schon als Eintrag da, nicht doppelt zeigen.
  const letzt = F.alle[F.alle.length - 1];
  if (letzt && letzt.wer === 'sarvis' && letzt.text.trim() === text) { liveWeg(); return; }
  const unten = istUnten();
  liveEl.innerHTML = `<div class="blase">${sicher(text)}</div>`;
  liveEl.hidden = false;
  if (unten) nachUnten();
}
function liveWeg() { liveEl.hidden = true; liveEl.innerHTML = ''; }

// --- Ansicht: Verlauf oder Ring ---------------------------------------
function ansicht(welche) {
  const ring = welche === 'ring';
  document.body.classList.toggle('ansicht-ring', ring);
  document.body.classList.toggle('ansicht-verlauf', !ring);
  const k = document.getElementById('ansichtknopf');
  k.innerHTML = ring ? '&#128172;' : '&#9678;';
  k.title = ring ? 'Zum Verlauf' : 'Zum Ring (Sprechansicht)';
  try { localStorage.setItem('sarvis-ansicht', ring ? 'ring' : 'verlauf'); } catch { /* egal */ }
  if (!ring) nachUnten();
}
document.getElementById('ansichtknopf').addEventListener('click', () =>
  ansicht(document.body.classList.contains('ansicht-ring') ? 'verlauf' : 'ring'));
// Wer freihändig mithört, schaut nicht auf Text -- dann der Ring.
document.getElementById('horchen').addEventListener('change', e => {
  if (e.target.checked) ansicht('ring');
});
ansicht(localStorage.getItem('sarvis-ansicht') || 'verlauf');

// =====================================================================
// Benachrichtigungen bei geschlossener App (Web Push)
// =====================================================================
const pushFeld = document.getElementById('push');
const pushProbe = document.getElementById('pushprobe');
function pushHinweis(text) { document.getElementById('pushhinweis').textContent = text; }
const PUSH_TEXT = 'Timer, Erinnerungen und fertige Aufträge — auch wenn die App zu ist.';

function bytesAus(b64) {
  const roh = atob(b64.replace(/-/g, '+').replace(/_/g, '/') + '='.repeat((4 - b64.length % 4) % 4));
  return Uint8Array.from(roh, c => c.charCodeAt(0));
}
const pushMoeglich = () => 'serviceWorker' in navigator && 'PushManager' in window
  && 'Notification' in window;

async function pushStand() {
  if (!pushMoeglich()) {
    pushFeld.disabled = true;
    pushHinweis(/iPhone|iPad/.test(navigator.userAgent)
      ? 'Am iPhone geht das nur, wenn Sarvis auf dem Home-Bildschirm liegt (Teilen → Zum Home-Bildschirm).'
      : 'Dieser Browser kann keine Benachrichtigungen.');
    return;
  }
  try {
    const reg = await navigator.serviceWorker.ready;
    const abo = await reg.pushManager.getSubscription();
    const an = !!abo && Notification.permission === 'granted';
    pushFeld.checked = an;
    pushProbe.hidden = !an;
    if (an && schluessel) {
      // Dem Server sagen, dass es dieses Abo gibt -- falls er es
      // inzwischen verworfen hat (Gerät neu angelegt, Dienst meldete 410).
      await fetch('/push/abo', { method: 'POST', headers: mitSchluessel(
        { 'Content-Type': 'application/json' }), body: JSON.stringify(abo.toJSON()) });
    }
  } catch { /* bleibt aus */ }
}

async function pushAn() {
  pushHinweis('Einen Moment …');
  try {
    const erlaubt = await Notification.requestPermission();
    if (erlaubt !== 'granted') {
      pushFeld.checked = false;
      pushHinweis('Nicht erlaubt. In den Einstellungen des Browsers für diese Seite freigeben.');
      return;
    }
    const r = await fetch('/push/schluessel', { headers: mitSchluessel(), cache: 'no-store' });
    if (!r.ok) throw new Error('Schlüssel ' + r.status);
    const oeffentlich = (await r.json()).schluessel;
    const reg = await navigator.serviceWorker.ready;
    let abo = await reg.pushManager.getSubscription();
    // Ein Abo mit fremdem Server-Schlüssel taugt nicht -- neu anmelden.
    if (abo && abo.options && abo.options.applicationServerKey) {
      const alt = new Uint8Array(abo.options.applicationServerKey);
      const neu = bytesAus(oeffentlich);
      if (alt.length !== neu.length || alt.some((b, i) => b !== neu[i])) {
        await abo.unsubscribe(); abo = null;
      }
    }
    if (!abo) abo = await reg.pushManager.subscribe({
      userVisibleOnly: true, applicationServerKey: bytesAus(oeffentlich) });
    const a = await fetch('/push/abo', { method: 'POST', headers: mitSchluessel(
      { 'Content-Type': 'application/json' }), body: JSON.stringify(abo.toJSON()) });
    if (!a.ok) {
      const f = await a.json().catch(() => ({}));
      throw new Error(f.fehler || 'Server ' + a.status);
    }
    pushFeld.checked = true;
    pushProbe.hidden = false;
    pushHinweis('An. ' + PUSH_TEXT);
  } catch (e) {
    pushFeld.checked = false;
    pushProbe.hidden = true;
    pushHinweis('Ging nicht: ' + (e && e.message ? e.message : e));
  }
}

async function pushAus() {
  try {
    const reg = await navigator.serviceWorker.ready;
    const abo = await reg.pushManager.getSubscription();
    if (abo) {
      await fetch('/push/abmelden', { method: 'POST', headers: mitSchluessel(
        { 'Content-Type': 'application/json' }), body: JSON.stringify({ endpoint: abo.endpoint }) });
      await abo.unsubscribe();
    }
  } catch { /* aus ist aus */ }
  pushProbe.hidden = true;
  pushHinweis('Aus. ' + PUSH_TEXT);
}

pushFeld.addEventListener('change', () => (pushFeld.checked ? pushAn() : pushAus()));
pushProbe.addEventListener('click', async () => {
  pushHinweis('Schicke eine Probe …');
  try {
    const r = await fetch('/push/probe', { method: 'POST', headers: mitSchluessel() });
    const a = await r.json();
    pushHinweis(a.gesendet ? 'Probe ist raus — sie sollte gleich erscheinen.'
      : `Nichts angekommen (Fehler: ${a.fehler || 0}, entfernt: ${a.entfernt || 0}). Schalte es aus und wieder an.`);
  } catch { pushHinweis('Probe ging nicht raus.'); }
});
