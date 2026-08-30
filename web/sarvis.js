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
const WERKZEUGE = ['Timer', 'Gedächtnis', 'Telegram', 'Websuche', 'Programme',
  'Musik', 'Dateien', 'Projekte', 'Aufträge', 'Kalender', 'E-Mail', 'Aufgaben',
  'Kontakte', 'Drive', 'Tabellen', 'Entwicklung', 'Finanzen'];

const KACHEL_ANTWORT = [255, 179, 71];
const KACHEL_ZUSTAND = [126, 224, 168];

// --- Zustand ----------------------------------------------------------
const S = {
  zustand: 'ruhig', pegel: 0, geglaettet: 0, verlauf: new Array(VERLAUF_LAENGE).fill(0),
  untertitel: '', wer: 'sarvis', hervor: 0, nachhoeren: 0, nachhoerenGanz: 1,
  glut: new Map(), hintergrund: [], hgGesamt: 0, hgSeit: 0, hgFertig: false,
  tick: 0, kacheln: new Map(), verbunden: false,
};
WERKZEUGE.forEach(w => S.glut.set(w, 0));

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
  WERKZEUGE.forEach((name, i) => {
    const w = -Math.PI / 2 + 2 * Math.PI * i / n;
    const cx = MITTE.x + Math.cos(w) * KRANZ, cy = MITTE.y + Math.sin(w) * KRANZ;
    let glut = S.glut.get(name) || 0;
    if (name === 'Entwicklung' && (S.hintergrund.length || S.hgFertig)) {
      const puls = 0.5 + 0.5 * Math.sin(S.tick * 2.4);
      glut = Math.max(glut, 0.30 + 0.40 * puls);
    }
    const kraft = Math.min(1, 0.95 + glut * 0.9);
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
  malen();
  requestAnimationFrame(schlag);
}

// =====================================================================
// Kacheln und Hintergrund
// =====================================================================
const kachelraum = document.getElementById('kacheln');

function kachelZeigen(m) {
  const farbe = m.sorte === 'zustand' ? KACHEL_ZUSTAND : KACHEL_ANTWORT;
  let el = S.kacheln.get(m.name);
  if (!el) {
    el = document.createElement('div');
    el.className = 'kachel';
    kachelraum.appendChild(el);
    S.kacheln.set(m.name, el);
  }
  el.style.borderColor = rgb(farbe, 0.30);
  const punkte = m.punkte || [];
  const zahlen = punkte.map(x => Number(x.zahl)).filter(x => x > 0);
  const groesste = zahlen.length ? Math.max(...zahlen) : 0;
  const zeilen = punkte.map(x => {
    const breite = groesste && x.zahl > 0 ? (100 * x.zahl / groesste) : 0;
    return `<div class="zeile">
      ${breite ? `<i class="balken" style="width:${breite}%;background:${rgb(farbe, 1)}"></i>` : ''}
      <span>${sicher(x.text)}</span><span>${sicher(x.wert)}</span></div>`;
  }).join('');
  const weg = Number(m.weggelassen) || 0;
  el.innerHTML = `<div class="strich" style="background:${rgb(farbe, 0.85)}"></div>
    <h4 style="color:${rgb(farbe, 0.95)}">${sicher(m.kopf)}</h4>
    ${m.gross ? `<div class="gross" style="color:${rgb(farbe, 1)}">${sicher(m.gross)}</div>` : ''}
    ${zeilen}
    ${weg ? `<div class="fuss">und ${weg} weitere</div>` : ''}
    ${m.stand ? `<div class="fuss">${sicher(m.stand)}</div>` : ''}`;

  const sek = Number(m.sekunden) || (m.sorte === 'zustand' ? 0 : 45);
  clearTimeout(el._uhr);
  if (sek > 0) el._uhr = setTimeout(() => kachelWeg(m.name), sek * 1000);
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

function hintergrundZeigen() {
  const kasten = document.getElementById('hintergrund');
  if (!S.hintergrund.length && !S.hgFertig) { kasten.classList.remove('an'); return; }
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
}

function verbinden() {
  const wo = (location.protocol === 'https:' ? 'wss://' : 'ws://')
    + location.host + '/draht';
  lage('verbindet …', false);
  draht = new WebSocket(wo);

  draht.onopen = () => draht.send(JSON.stringify({
    schluessel,
    // Nur ein Geraet mit grossem Bildschirm bekommt Browser-Fragen.
    kann_browser: window.innerWidth >= 900,
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
    lage('getrennt', false);
    setTimeout(verbinden, wiederIn);
    wiederIn = Math.min(wiederIn * 1.6, 20000);   // nicht im Kreis hämmern
  };
}

function empfangen(m) {
  switch (m.art) {
    case 'willkommen':
      wiederIn = 1000;
      lage('verbunden', true);
      document.getElementById('geraet').textContent = m.geraet || '';
      document.getElementById('tor').classList.add('weg');
      localStorage.setItem('sarvis-schluessel', schluessel);
      break;
    case 'zustand':
      if (m.strom) break;            // gehört einem Vorgang, nicht dem Ring
      if (m.zustand !== S.zustand) {
        S.zustand = m.zustand;
        if (m.zustand === 'hoert') {
          S.verlauf.fill(0);
          S.untertitel = ''; zeigeUntertitel();
        }
      }
      break;
    case 'pegel':    S.pegel = Math.max(0, Math.min(1, Number(m.pegel) || 0)); break;
    case 'untertitel':
      if (m.strom) break;
      S.untertitel = m.text || ''; S.wer = m.wer || 'sarvis'; S.hervor = 4;
      zeigeUntertitel();
      break;
    case 'nachhoeren':
      S.nachhoeren = Number(m.sekunden) || 0;
      S.nachhoerenGanz = Math.max(0.1, S.nachhoeren);
      break;
    case 'werkzeug':
      if (m.aktiv) S.glut.set(m.name, 1.0);
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
    case 'ton':        tonSpielen(m); break;
  }
}

function zeigeUntertitel() {
  const el = document.getElementById('untertitel');
  el.textContent = S.untertitel;
  el.style.color = S.wer === 'du' ? 'rgba(232,241,253,.94)'
    : rgb(FARBEN[S.zustand] || FARBEN.ruhig, 0.92);
}

function senden(o) {
  if (draht && draht.readyState === 1) draht.send(JSON.stringify(o));
}

// =====================================================================
// Ton: hin und zurück
// =====================================================================
let hoerer = null, quelle = null, knoten = null, gesammelt = [], nimmtAuf = false;

async function aufnahmeStart() {
  if (nimmtAuf) return;
  try {
    if (!hoerer) {
      // 16 kHz direkt anfordern -- dann muss nichts umgetastet werden,
      // und Whisper bekommt genau das, was es erwartet.
      hoerer = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
    }
    if (hoerer.state === 'suspended') await hoerer.resume();
    const strom = await navigator.mediaDevices.getUserMedia({
      audio: {
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
    gesammelt = [];
    knoten.onaudioprocess = e => {
      const d = e.inputBuffer.getChannelData(0);
      gesammelt.push(new Float32Array(d));
      let summe = 0; for (let i = 0; i < d.length; i++) summe += d[i] * d[i];
      S.pegel = Math.min(1, Math.pow(Math.sqrt(summe / d.length) / 0.14, 0.6));
    };
    quelle.connect(knoten); knoten.connect(hoerer.destination);
    nimmtAuf = true;
    S.zustand = 'hoert';
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
  if (gesamt < 16000 * 0.4) { S.zustand = 'ruhig'; return; }  // zu kurz
  const alles = new Int16Array(gesamt);
  let i = 0;
  for (const stueck of gesammelt)
    for (let j = 0; j < stueck.length; j++)
      alles[i++] = Math.max(-32768, Math.min(32767, stueck[j] * 32768));
  gesammelt = [];
  senden({ art: 'sprache', rate: 16000, daten: alsBase64(alles.buffer) });
  S.zustand = 'denkt';
}

function alsBase64(puffer) {
  const b = new Uint8Array(puffer);
  let s = '';
  for (let i = 0; i < b.length; i += 8192)
    s += String.fromCharCode.apply(null, b.subarray(i, i + 8192));
  return btoa(s);
}

let tonZeit = 0, tonRunde = -1;
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
}

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

// Am Rechner tut die Leertaste dasselbe wie die Fläche.
document.addEventListener('keydown', e => {
  if (e.code === 'Space' && !e.repeat && document.activeElement.tagName !== 'INPUT') {
    e.preventDefault(); reden.classList.add('haelt'); aufnahmeStart();
  }
});
document.addEventListener('keyup', e => {
  if (e.code === 'Space' && document.activeElement.tagName !== 'INPUT') {
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

// --- Los --------------------------------------------------------------
messen();
requestAnimationFrame(schlag);
if (schluessel) { document.getElementById('tor').classList.add('weg'); verbinden(); }
if ('serviceWorker' in navigator)
  navigator.serviceWorker.register('/dabei/waechter.js').catch(() => {});
