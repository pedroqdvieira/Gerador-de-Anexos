// ── TOAST ──
function showToast(msg, type = 'info', duration = 3500) {
  const t = document.getElementById('toast');
  if (!t) return;
  t.textContent = msg;
  t.className = `toast ${type}`;
  clearTimeout(t._timer);
  t._timer = setTimeout(() => t.classList.add('hidden'), duration);
}

// ── TABS ──
function initTabs(containerSelector) {
  const container = document.querySelector(containerSelector);
  if (!container) return;
  const btns = container.querySelectorAll('.tab-btn');
  const panels = container.querySelectorAll('.tab-panel');
  btns.forEach(btn => {
    btn.addEventListener('click', () => {
      btns.forEach(b => b.classList.remove('active'));
      panels.forEach(p => p.classList.remove('active'));
      btn.classList.add('active');
      const target = btn.dataset.tab;
      const panel = container.querySelector(`#${target}`);
      if (panel) panel.classList.add('active');
    });
  });
}

// ── MODAL ──
function openModal(id) { document.getElementById(id)?.classList.add('open'); }
function closeModal(id) { document.getElementById(id)?.classList.remove('open'); }
document.addEventListener('click', e => {
  if (e.target.classList.contains('modal-overlay')) e.target.classList.remove('open');
});

// ── FORMAT CURRENCY ──
function formatBRL(val) {
  return parseFloat(val || 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
}

// ── CONFIRM ──
function confirmAction(msg, fn) {
  if (confirm(msg)) fn();
}

// ── API HELPERS ──
async function apiFetch(url, options = {}) {
  try {
    const res = await fetch(url, {
      headers: { 'Content-Type': 'application/json', ...options.headers },
      ...options,
      body: options.body ? JSON.stringify(options.body) : undefined,
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Erro desconhecido');
    return data;
  } catch (e) {
    showToast(e.message, 'error');
    throw e;
  }
}

// ── MEATBALL MENU ──
function toggleMeatball(id, btnEl) {
  const menu = document.getElementById(id);
  const isOpen = menu.classList.contains('open');

  // Close all open menus first
  document.querySelectorAll('.meatball-menu.open').forEach(m => m.classList.remove('open'));

  if (isOpen) return;

  // Position using fixed coords from button
  const rect = btnEl.getBoundingClientRect();
  menu.style.top = (rect.bottom + 6) + 'px';

  // Show temporarily to measure width
  menu.style.visibility = 'hidden';
  menu.classList.add('open');
  const menuW = menu.offsetWidth;
  menu.style.visibility = '';

  // Align right edge to button right edge, but keep on screen
  let left = rect.right - menuW;
  if (left < 8) left = 8;
  if (left + menuW > window.innerWidth - 8) left = window.innerWidth - menuW - 8;
  menu.style.left = left + 'px';
}

document.addEventListener('click', e => {
  if (!e.target.closest('.meatball-wrap') && !e.target.closest('.meatball-btn')) {
    document.querySelectorAll('.meatball-menu.open').forEach(m => m.classList.remove('open'));
  }
});

// Reposition on scroll/resize
window.addEventListener('scroll', () => {
  document.querySelectorAll('.meatball-menu.open').forEach(m => m.classList.remove('open'));
}, true);
