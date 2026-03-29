/* =============================================================
   Contextly — App Logic
   ============================================================= */

'use strict';

// ─── DOM refs ────────────────────────────────────────────────

const tabText = document.getElementById('tab-text');
const tabImage = document.getElementById('tab-image');
const panelText = document.getElementById('panel-text');
const panelImage = document.getElementById('panel-image');

const slideTextarea = document.getElementById('slide-text');
const charCount = document.getElementById('char-count');
const analyzeTextBtn = document.getElementById('analyze-text-btn');
const analyzeImageBtn = document.getElementById('analyze-image-btn');

const dropZone = document.getElementById('drop-zone');
const fileInput = document.getElementById('file-input');
const dropPreview = document.getElementById('drop-preview');
const previewThumb = document.getElementById('preview-thumb');
const previewName = document.getElementById('preview-name');
const removeImageBtn = document.getElementById('remove-image');

const errorBanner = document.getElementById('error-banner');
const resultsSection = document.getElementById('results-section');
const conceptChips = document.getElementById('concept-chips');
const resultsCount = document.getElementById('results-count');
const iconGrid = document.getElementById('icon-grid');
const emptyState = document.getElementById('empty-state');
const toast = document.getElementById('toast');

// Customizer refs
const ctrlColor = document.getElementById('ctrl-color');
const ctrlColorHex = document.getElementById('ctrl-color-hex');
const ctrlStroke = document.getElementById('ctrl-stroke');
const ctrlStrokeVal = document.getElementById('ctrl-stroke-val');
const ctrlSize = document.getElementById('ctrl-size');
const ctrlSizeVal = document.getElementById('ctrl-size-val');
const ctrlAbsStroke = document.getElementById('ctrl-abs-stroke');
const ctrlCircle = document.getElementById('ctrl-circle');
const resetBtn = document.getElementById('reset-customizer');

// ─── State ───────────────────────────────────────────────────

let selectedFile = null;
let toastTimer = null;
let svgCache = {};   // name → raw svg string

const DEFAULTS = {
  color: '#e8edff',
  strokeWidth: 2,
  size: 40,
  absoluteStroke: false,
  circle: false,
};

const iconStyle = { ...DEFAULTS };

// ─── Tabs ────────────────────────────────────────────────────

function activateTab(tab) {
  [tabText, tabImage].forEach(t => {
    t.classList.toggle('active', t === tab);
    t.setAttribute('aria-selected', t === tab ? 'true' : 'false');
  });
  [panelText, panelImage].forEach(p => p.classList.remove('active'));
  (tab === tabText ? panelText : panelImage).classList.add('active');
  clearError();
}

tabText.addEventListener('click', () => activateTab(tabText));
tabImage.addEventListener('click', () => activateTab(tabImage));

// ─── Character count ─────────────────────────────────────────

slideTextarea.addEventListener('input', () => {
  const len = slideTextarea.value.length;
  charCount.textContent = `${len} / 4000`;
  charCount.style.color = len > 3500 ? '#f87171' : '';
});

// ─── Drag & drop / file picker ───────────────────────────────

dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('drag-over'); });
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));

dropZone.addEventListener('drop', e => {
  e.preventDefault();
  dropZone.classList.remove('drag-over');
  const file = e.dataTransfer.files[0];
  if (file) handleFileSelect(file);
});

fileInput.addEventListener('change', () => {
  if (fileInput.files[0]) handleFileSelect(fileInput.files[0]);
});

removeImageBtn.addEventListener('click', () => {
  selectedFile = null;
  fileInput.value = '';
  dropPreview.classList.remove('visible');
  previewThumb.src = '';
  previewName.textContent = '';
});

function handleFileSelect(file) {
  if (!file.type.startsWith('image/')) { showError('Please select a PNG, JPG, or WebP image.'); return; }
  if (file.size > 10 * 1024 * 1024) { showError('Image must be under 10 MB.'); return; }
  selectedFile = file;
  previewName.textContent = file.name;
  const reader = new FileReader();
  reader.onload = e => { previewThumb.src = e.target.result; };
  reader.readAsDataURL(file);
  dropPreview.classList.add('visible');
  clearError();
}

// ─── Analyze — text ──────────────────────────────────────────

analyzeTextBtn.addEventListener('click', async () => {
  const text = slideTextarea.value.trim();
  if (!text) { showError('Please paste some slide text first.'); return; }

  setLoading(analyzeTextBtn, true);
  clearError();
  showSkeletons();

  try {
    const res = await fetch('/analyze/text', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Something went wrong');
    renderResults(data);
  } catch (err) {
    showError(err.message);
    hideResults();
  } finally {
    setLoading(analyzeTextBtn, false);
  }
});

// ─── Analyze — image ─────────────────────────────────────────

analyzeImageBtn.addEventListener('click', async () => {
  if (!selectedFile) { showError('Please upload a slide image first.'); return; }

  setLoading(analyzeImageBtn, true);
  clearError();
  showSkeletons();

  try {
    const form = new FormData();
    form.append('file', selectedFile);
    const res = await fetch('/analyze/image', { method: 'POST', body: form });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Something went wrong');
    renderResults(data);
  } catch (err) {
    showError(err.message);
    hideResults();
  } finally {
    setLoading(analyzeImageBtn, false);
  }
});

// ─── Render results ──────────────────────────────────────────

function renderResults({ concepts, icons }) {
  // Concepts chips
  conceptChips.innerHTML = '';
  concepts.forEach((c, i) => {
    const chip = document.createElement('span');
    chip.className = 'concept-chip';
    chip.textContent = c;
    chip.style.animationDelay = `${i * 0.05}s`;
    conceptChips.appendChild(chip);
  });

  resultsCount.textContent = `${icons.length} icon${icons.length !== 1 ? 's' : ''} found`;

  // Build grid
  iconGrid.innerHTML = '';
  emptyState.classList.toggle('visible', icons.length === 0);

  icons.forEach((icon, i) => {
    const card = buildCard(icon, i);
    iconGrid.appendChild(card);

    // Async inline SVG injection
    loadSvg(icon.name).then(svgText => {
      const preview = card.querySelector('.icon-preview');
      if (!preview || !svgText) return;

      const temp = document.createElement('div');
      temp.innerHTML = svgText.trim();
      const svgEl = temp.querySelector('svg');
      if (!svgEl) return;

      // Normalise: let CSS control all visual properties
      svgEl.setAttribute('width', '100%');
      svgEl.setAttribute('height', '100%');
      svgEl.removeAttribute('stroke');      // will come from CSS currentColor
      svgEl.removeAttribute('stroke-width');// will come from CSS variable
      // Keep fill="none" from the original SVG — CSS overrides it when needed

      preview.innerHTML = '';
      preview.appendChild(svgEl);
    });
  });

  resultsSection.style.display = 'block';
  resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function buildCard(icon, index) {
  const card = document.createElement('div');
  card.className = 'icon-card';
  card.setAttribute('role', 'listitem');
  card.style.animationDelay = `${Math.min(index * 0.03, 0.3)}s`;

  card.innerHTML = `
    <span class="icon-score">${Math.round(icon.score * 100)}%</span>
    <div class="icon-preview">
      <div class="icon-placeholder"></div>
    </div>
    <span class="icon-name">${icon.name}</span>
    <div class="card-actions">
      <button class="card-action" data-action="copy" data-name="${icon.name}" aria-label="Copy PNG for ${icon.name}">
        <svg viewBox="0 0 24 24"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
        Copy
      </button>
      <button class="card-action" data-action="download-png" data-name="${icon.name}" aria-label="Download for ${icon.name}">
        <svg viewBox="0 0 24 24"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
        Download
      </button>
    </div>
  `;

  card.addEventListener('click', e => {
    const btn = e.target.closest('[data-action]');
    if (!btn) return;
    e.stopPropagation();
    if (btn.dataset.action === 'copy') copyPng(btn.dataset.name);
    if (btn.dataset.action === 'download-png') downloadPng(btn.dataset.name);
  });

  return card;
}

// ─── SVG loading ─────────────────────────────────────────────

async function loadSvg(name) {
  if (svgCache[name]) return svgCache[name];
  try {
    const res = await fetch(`/icon/${name}`);
    if (!res.ok) return null;
    const text = await res.text();
    svgCache[name] = text;
    return text;
  } catch {
    return null;
  }
}

// ─── Customizer — apply styles to an SVG string for export ───

/**
 * Bake the current iconStyle settings directly into the SVG element
 * attributes so the exported file looks correct outside the browser.
 */
function applyStylesToSvg(rawSvgText) {
  const doc = new DOMParser().parseFromString(rawSvgText, 'image/svg+xml');
  const svg = doc.documentElement;
  if (!svg || svg.tagName !== 'svg') return rawSvgText;

  const s = iconStyle;

  // Size
  svg.setAttribute('width', s.size);
  svg.setAttribute('height', s.size);

  // Stroke mode
  svg.setAttribute('fill', 'none');
  svg.setAttribute('stroke', s.color);
  svg.setAttribute('stroke-width', s.strokeWidth);
  svg.setAttribute('stroke-linecap', 'round');
  svg.setAttribute('stroke-linejoin', 'round');

  if (s.absoluteStroke) {
    svg.querySelectorAll('*').forEach(el =>
      el.setAttribute('vector-effect', 'non-scaling-stroke')
    );
  }

  // Circle background: inject a translucent circle behind everything
  if (s.circle) {
    const vbParts = (svg.getAttribute('viewBox') || '0 0 24 24').trim().split(/\s+/).map(Number);
    const [vbX, vbY, vw, vh] = vbParts;
    const cx = vw / 2;
    const cy = vh / 2;
    const r = Math.max(vw, vh) / 2 * 1.15;

    // Expand the viewBox so the circle is not clipped during PNG export
    const pad = Math.ceil(r - Math.min(vw, vh) / 2 + 1);
    svg.setAttribute('viewBox', `${vbX - pad} ${vbY - pad} ${vw + pad * 2} ${vh + pad * 2}`);

    // Convert hex color → rgba for the circle fill
    const hex = s.color.replace('#', '');
    const ri = parseInt(hex.slice(0, 2), 16);
    const gi = parseInt(hex.slice(2, 4), 16);
    const bi = parseInt(hex.slice(4, 6), 16);

    const circle = doc.createElementNS('http://www.w3.org/2000/svg', 'circle');
    circle.setAttribute('cx', cx);
    circle.setAttribute('cy', cy);
    circle.setAttribute('r', r);
    circle.setAttribute('fill', `rgb(${ri},${gi},${bi})`);
    circle.setAttribute('fill-opacity', '0.12');
    circle.setAttribute('stroke', 'none');
    svg.insertBefore(circle, svg.firstChild);
  }

  return new XMLSerializer().serializeToString(svg);
}

// ─── Copy / Download ─────────────────────────────────────────

function getPngBlob(name) {
  return new Promise(async (resolve) => {
    const raw = await loadSvg(name);
    if (!raw) return resolve(null);
    const styled = applyStylesToSvg(raw);

    const img = new Image();
    const canvas = document.createElement('canvas');
    const size = iconStyle.size;
    // Export at 4x resolution for small sizes to keep it crisp, otherwise 2x
    const scale = (size > 0 && size < 64) ? 4 : 2;
    canvas.width = size * scale;
    canvas.height = size * scale;
    const ctx = canvas.getContext('2d');

    img.onload = () => {
      ctx.scale(scale, scale);
      ctx.drawImage(img, 0, 0, size, size);
      canvas.toBlob(blob => resolve(blob), 'image/png');
    };
    img.onerror = () => resolve(null);

    const svgBlob = new Blob([styled], { type: 'image/svg+xml;charset=utf-8' });
    img.src = URL.createObjectURL(svgBlob);
  });
}

async function copyPng(name) {
  const blob = await getPngBlob(name);
  if (!blob) { showToast('Icon not available :('); return; }
  try {
    const item = new ClipboardItem({ [blob.type]: blob });
    await navigator.clipboard.write([item]);
    showToast(`Copied ${name}.png!`);
  } catch (err) {
    console.error(err);
    showToast('Clipboard access denied. Try Download instead.');
  }
}

async function downloadPng(name) {
  const blob = await getPngBlob(name);
  if (!blob) { showToast('Icon not available :('); return; }
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${name}.png`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
  showToast(`Downloading ${name}.png`);
}



// ─── Customizer logic ─────────────────────────────────────────

/** Update CSS custom properties and class modifiers on the grid */
function applyCustomizer() {
  const root = document.documentElement;

  // CSS variables for live icon preview
  root.style.setProperty('--icon-color', iconStyle.color);
  root.style.setProperty('--icon-stroke-width', iconStyle.strokeWidth);
  root.style.setProperty('--icon-size', `${iconStyle.size}px`);

  // Compute a translucent version of the color for the circle
  const hex = iconStyle.color.replace('#', '');
  const r = parseInt(hex.slice(0, 2), 16);
  const g = parseInt(hex.slice(2, 4), 16);
  const b = parseInt(hex.slice(4, 6), 16);
  root.style.setProperty('--icon-circle-bg', `rgba(${r},${g},${b},0.12)`);
  root.style.setProperty('--icon-circle-border', `rgba(${r},${g},${b},0.25)`);

  // Class modifiers toggle visual modes on the grid
  iconGrid.classList.toggle('icon-circle', iconStyle.circle);
  iconGrid.classList.toggle('icon-abs-stroke', iconStyle.absoluteStroke);
}

/** Set the slider's CSS gradient fill to match the thumb position */
function updateSliderFill(slider) {
  const min = parseFloat(slider.min);
  const max = parseFloat(slider.max);
  const val = parseFloat(slider.value);
  const pct = ((val - min) / (max - min)) * 100;
  slider.style.setProperty('--pct', `${pct}%`);
}

// Color picker
ctrlColor.addEventListener('input', () => {
  iconStyle.color = ctrlColor.value;
  ctrlColorHex.textContent = ctrlColor.value;
  applyCustomizer();
});

// Stroke width slider
updateSliderFill(ctrlStroke);
ctrlStroke.addEventListener('input', () => {
  iconStyle.strokeWidth = parseFloat(ctrlStroke.value);
  ctrlStrokeVal.textContent = `${iconStyle.strokeWidth}`;
  updateSliderFill(ctrlStroke);
  applyCustomizer();
});

// Size slider
updateSliderFill(ctrlSize);
ctrlSize.addEventListener('input', () => {
  iconStyle.size = parseInt(ctrlSize.value, 10);
  ctrlSizeVal.textContent = `${iconStyle.size}px`;
  updateSliderFill(ctrlSize);
  applyCustomizer();
});

// Absolute stroke width toggle
ctrlAbsStroke.addEventListener('change', () => {
  iconStyle.absoluteStroke = ctrlAbsStroke.checked;
  applyCustomizer();
});

// Circle background toggle
ctrlCircle.addEventListener('change', () => {
  iconStyle.circle = ctrlCircle.checked;
  applyCustomizer();
});

// Reset button
resetBtn.addEventListener('click', () => {
  Object.assign(iconStyle, DEFAULTS);

  // Sync controls to defaults
  ctrlColor.value = DEFAULTS.color;
  ctrlColorHex.textContent = DEFAULTS.color;
  ctrlStroke.value = DEFAULTS.strokeWidth;
  ctrlStrokeVal.textContent = `${DEFAULTS.strokeWidth}`;
  ctrlSize.value = DEFAULTS.size;
  ctrlSizeVal.textContent = `${DEFAULTS.size}px`;
  ctrlAbsStroke.checked = DEFAULTS.absoluteStroke;
  ctrlCircle.checked = DEFAULTS.circle;

  updateSliderFill(ctrlStroke);
  updateSliderFill(ctrlSize);
  applyCustomizer();
  showToast('Customizer reset');
});

// Apply defaults on load
applyCustomizer();

// ─── UI helpers ──────────────────────────────────────────────

function setLoading(btn, on) {
  btn.classList.toggle('loading', on);
  btn.disabled = on;
}

function showSkeletons(n = 12) {
  iconGrid.innerHTML = '';
  for (let i = 0; i < n; i++) {
    const card = document.createElement('div');
    card.className = 'icon-card skeleton';
    card.innerHTML = '<div class="icon-preview"><div class="icon-placeholder"></div></div><div class="icon-name-skel"></div>';
    iconGrid.appendChild(card);
  }
  conceptChips.innerHTML = '';
  resultsCount.textContent = '';
  emptyState.classList.remove('visible');
  resultsSection.style.display = 'block';
}

function hideResults() {
  iconGrid.innerHTML = '';
  resultsSection.style.display = 'none';
}

function showError(msg) {
  errorBanner.textContent = msg;
  errorBanner.classList.add('visible');
}

function clearError() {
  errorBanner.textContent = '';
  errorBanner.classList.remove('visible');
}

function showToast(msg, duration = 2500) {
  toast.textContent = msg;
  toast.classList.add('visible');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove('visible'), duration);
}
