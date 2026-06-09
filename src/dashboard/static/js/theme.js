const PRESETS = {
  'dark-gold':    { vars: { '--bg':'#07090E','--surface':'#0C1118','--surface-2':'#111927','--ink':'#E6EDF3','--ink-2':'#CDD9E5','--muted':'#7D8590','--line':'#21262D','--line-2':'#2D3748','--ok':'#3FB950','--warn':'#D29922','--danger':'#F85149' }, defaultAccent:'gold',    label:'Gold',    dot:'#0C1118' },
  'dark-ocean':   { vars: { '--bg':'#080D18','--surface':'#0E1525','--surface-2':'#131E30','--ink':'#D6E8FF','--ink-2':'#A8C8F0','--muted':'#607090','--line':'#1A2540','--line-2':'#243050','--ok':'#2ED8A0','--warn':'#E0A020','--danger':'#F06060' }, defaultAccent:'ocean',   label:'Ocean',   dot:'#080D18' },
  'dark-emerald': { vars: { '--bg':'#07100C','--surface':'#0C1A12','--surface-2':'#102018','--ink':'#D4EDE0','--ink-2':'#A8D4B8','--muted':'#4A7060','--line':'#1A2E20','--line-2':'#243828','--ok':'#34C76C','--warn':'#D4A020','--danger':'#F06060' }, defaultAccent:'emerald', label:'Emerald', dot:'#07100C' },
  'dark-crimson': { vars: { '--bg':'#100808','--surface':'#1A0E0E','--surface-2':'#201414','--ink':'#EDDAD8','--ink-2':'#D0B0A8','--muted':'#704848','--line':'#2E1A1A','--line-2':'#382424','--ok':'#50C878','--warn':'#D4A020','--danger':'#F85149' }, defaultAccent:'crimson', label:'Crimson', dot:'#100808' },
  'dark-violet':  { vars: { '--bg':'#0D0814','--surface':'#130F1E','--surface-2':'#1A1428','--ink':'#E0D6F5','--ink-2':'#C0A8E8','--muted':'#5A4880','--line':'#231840','--line-2':'#2E2050','--ok':'#3FB950','--warn':'#D29922','--danger':'#F85149' }, defaultAccent:'violet',  label:'Violet',  dot:'#0D0814' },
  'light-ivory':  { vars: { '--bg':'#F8F5EE','--surface':'#FFFFFF','--surface-2':'#F0EAE0','--ink':'#1A1208','--ink-2':'#3A2E18','--muted':'#8A7060','--line':'#E5DDD0','--line-2':'#D0C8B8','--ok':'#1A7A40','--warn':'#8A6000','--danger':'#C03020' }, defaultAccent:'gold',    label:'Ivory',   dot:'#F8F5EE' },
};

const ACCENTS = [
  { id:'gold',    hex:'#C9A227', ivoryHex:'#7A5A0A' },
  { id:'ocean',   hex:'#3891F0', ivoryHex:'#1060C0' },
  { id:'emerald', hex:'#34C76C', ivoryHex:'#1A8040' },
  { id:'crimson', hex:'#DC4040', ivoryHex:'#A02020' },
  { id:'violet',  hex:'#8B5CF6', ivoryHex:'#5A30C0' },
  { id:'teal',    hex:'#2EC4B6', ivoryHex:'#1A8A80' },
  { id:'amber',   hex:'#F59E0B', ivoryHex:'#905800' },
  { id:'rose',    hex:'#EC4899', ivoryHex:'#B02070' },
];

let _theme = { presetId:'dark-gold', accentId:'gold' };

function hexToRgb(hex) {
  return { r:parseInt(hex.slice(1,3),16), g:parseInt(hex.slice(3,5),16), b:parseInt(hex.slice(5,7),16) };
}
function lightenHex(hex, amount=50) {
  const {r,g,b} = hexToRgb(hex);
  const clamp = v => Math.min(255, v+amount);
  return '#'+[clamp(r),clamp(g),clamp(b)].map(v=>v.toString(16).padStart(2,'0')).join('');
}
function hexToRgba(hex, alpha) {
  const {r,g,b} = hexToRgb(hex);
  return `rgba(${r},${g},${b},${alpha})`;
}

function applyTheme(presetId, accentId) {
  const preset = PRESETS[presetId];
  const accent = ACCENTS.find(a => a.id === accentId);
  const accentHex = presetId === 'light-ivory' ? accent.ivoryHex : accent.hex;
  Object.entries(preset.vars).forEach(([k,v]) => document.documentElement.style.setProperty(k, v));
  document.documentElement.style.setProperty('--primary', accentHex);
  document.documentElement.style.setProperty('--primary-light', lightenHex(accentHex, 40));
  document.documentElement.style.setProperty('--primary-dim', hexToRgba(accentHex, 0.12));
  _theme = { presetId, accentId };
  try { localStorage.setItem('drishti-theme', JSON.stringify(_theme)); } catch(e) {}
  renderThemePicker();
  rethemeCharts();
}

function rethemeCharts() {
  const surfaceColor = getComputedStyle(document.documentElement).getPropertyValue('--surface-2').trim();
  const mutedColor   = getComputedStyle(document.documentElement).getPropertyValue('--muted').trim();
  const patch = { paper_bgcolor: 'transparent', plot_bgcolor: surfaceColor, 'font.color': mutedColor };
  ['var-chart','contrib-chart','dd-chart','dy-chart','dcc-chart','regime-chart'].forEach(id => {
    const el = document.getElementById(id);
    if (el && el.data && el.data.length) Plotly.relayout(id, patch);
  });
}

function toggleThemePicker(e) {
  e.stopPropagation();
  const pop = document.getElementById('theme-popover');
  if (pop.style.display === 'none') {
    renderThemePicker();
    pop.style.display = 'block';
  } else {
    pop.style.display = 'none';
  }
}

function renderThemePicker() {
  const presetsEl = document.getElementById('tp-presets');
  if (!presetsEl) return;
  presetsEl.innerHTML = Object.entries(PRESETS).map(([id, p]) => `
    <div class="tp-preset-card ${_theme.presetId===id?'active':''}"
         onclick="applyTheme('${id}','${id===_theme.presetId ? _theme.accentId : p.defaultAccent}')">
      <div class="tp-preset-dot" style="background:${p.dot};${id==='light-ivory'?'border-color:rgba(0,0,0,0.15)':''}"></div>
      <div class="tp-preset-name">${p.label}</div>
    </div>`).join('');
  const accentsEl = document.getElementById('tp-accents');
  accentsEl.innerHTML = ACCENTS.map(a => {
    const displayHex = _theme.presetId === 'light-ivory' ? a.ivoryHex : a.hex;
    return `<div class="tp-accent-dot ${_theme.accentId===a.id?'active':''}"
         style="background:${displayHex}" title="${a.id}"
         onclick="applyTheme('${_theme.presetId}','${a.id}')"></div>`;
  }).join('');
}

document.addEventListener('mousedown', e => {
  const pop = document.getElementById('theme-popover');
  const btn = document.getElementById('theme-btn');
  if (pop && pop.style.display !== 'none' && !pop.contains(e.target) && e.target !== btn)
    pop.style.display = 'none';
});
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') { const pop = document.getElementById('theme-popover'); if (pop) pop.style.display = 'none'; }
});

function initTheme() {
  let saved = { presetId:'dark-gold', accentId:'gold' };
  try { const raw = localStorage.getItem('drishti-theme'); if (raw) saved = JSON.parse(raw); } catch(e) {}
  applyTheme(saved.presetId, saved.accentId);
}

initTheme();
