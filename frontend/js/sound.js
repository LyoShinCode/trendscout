// Звук выключен по умолчанию: это аналитический инструмент, а не медиаплеер.
// Включается одной кнопкой в шапке; каждый сигнал привязан к видимому событию.
let ctx = null;
let enabled = false;

export function setSound(on) { enabled = !!on; }
export function soundEnabled() { return enabled; }

function beep(freq, dur = .12, type = 'sine', gain = .035, delay = 0) {
  if (!enabled) return;
  try {
    ctx = ctx || new (window.AudioContext || window.webkitAudioContext)();
    if (ctx.state === 'suspended') ctx.resume();
    const t = ctx.currentTime + delay;
    const o = ctx.createOscillator(), g = ctx.createGain();
    o.type = type; o.frequency.value = freq;
    g.gain.setValueAtTime(0, t);
    g.gain.linearRampToValueAtTime(gain, t + .012);
    g.gain.exponentialRampToValueAtTime(.0001, t + dur);
    o.connect(g).connect(ctx.destination);
    o.start(t); o.stop(t + dur + .04);
  } catch (e) { /* среда без WebAudio — работаем молча */ }
}

export const snd = {
  tick: () => beep(660, .07, 'sine', .025),
  ui: () => beep(520, .05, 'sine', .02),
  warn: () => { beep(392, .16, 'sine', .03); beep(330, .2, 'sine', .028, .13); },
  alert: (type) => {
    const f = type === 'VIRAL' ? 587 : type === 'NEWCOMER' ? 659 : 523;
    beep(f, .14, 'sine', .035);
    beep(f * 1.25, .18, 'sine', .03, .11);
  },
};