// ══════════════════════════════════════
//  SGAFAQ — alerts.js
//  Toast, validaciones y modales
// ══════════════════════════════════════

const $ = id => document.getElementById(id);

// ── TOAST ──────────────────────────────
function showToast(msg, type = 'success') {
  const icons = {
    success: 'bi-check-circle-fill',
    error:   'bi-x-circle-fill',
    info:    'bi-info-circle-fill'
  };
  const t = document.createElement('div');
  t.className = `toast toast-${type}`;
  t.innerHTML = `<i class="bi ${icons[type] || icons.success}" style="font-size:15px;flex-shrink:0"></i>${msg}`;
  document.getElementById('toastContainer').appendChild(t);
  setTimeout(() => {
    t.classList.add('hide');
    setTimeout(() => t.remove(), 400);
  }, 3400);
}

// ── MODALES ────────────────────────────
function openModal(id)  { $(id)?.classList.add('open');    }
function closeModal(id) { $(id)?.classList.remove('open'); }

// Cerrar modal al hacer clic fuera
document.querySelectorAll('.modal-overlay').forEach(o => {
  o.addEventListener('click', e => {
    if (e.target === o) o.classList.remove('open');
  });
});

// ── HELPERS DE VALIDACIÓN ──────────────
function setErr(inputId, errId, msg) {
  $(inputId)?.classList.add('error');
  if ($(errId)) { $(errId).textContent = msg; $(errId).style.display = 'block'; }
}
function clrErr(inputId, errId) {
  $(inputId)?.classList.remove('error');
  if ($(errId)) { $(errId).textContent = ''; $(errId).style.display = 'none'; }
}

// ── VALIDACIÓN: LOGIN ──────────────────
function validateLogin() {
  const u = $('loginUser')?.value.trim();
  const p = $('loginPass')?.value;
  let ok = true;
  if (!u) { setErr('loginUser', 'loginUserErr', 'El usuario es requerido');    ok = false; } else clrErr('loginUser', 'loginUserErr');
  if (!p) { setErr('loginPass', 'loginPassErr', 'La contraseña es requerida'); ok = false; } else clrErr('loginPass', 'loginPassErr');
  if (!ok) return false;
  // Aquí conectar con tu backend
  return true;
}
// Enter en el campo contraseña
$('loginPass')?.addEventListener('keydown', e => { if (e.key === 'Enter') validateLogin(); });

// ── VALIDACIÓN: REGISTRAR ACTIVO ───────
function validateRegistrar() {
  const n = $('rN')?.value.trim();
  const l = $('rL')?.value.trim();
  const w = $('rW')?.value;
  let ok = true;
  if (!n) { setErr('rN', 'rNe', 'El nombre es requerido');            ok = false; } else clrErr('rN', 'rNe');
  if (!l) { setErr('rL', 'rLe', 'La ubicación es requerida');         ok = false; } else clrErr('rL', 'rLe');
  if (!w) { setErr('rW', 'rWe', 'La fecha de garantía es requerida'); ok = false; } else clrErr('rW', 'rWe');
  if (ok) showToast('Activo registrado correctamente');
  return ok;
}

// ── VALIDACIÓN: EDITAR ACTIVO ──────────
function validateEditar() {
  const n = $('eN')?.value.trim();
  const l = $('eL')?.value.trim();
  const w = $('eW')?.value;
  let ok = true;
  if (!n) { setErr('eN', 'eNe', 'El nombre es requerido');    ok = false; } else clrErr('eN', 'eNe');
  if (!l) { setErr('eL', 'eLe', 'La ubicación es requerida'); ok = false; } else clrErr('eL', 'eLe');
  if (!w) { setErr('eW', 'eWe', 'La garantía es requerida');  ok = false; } else clrErr('eW', 'eWe');
  if (ok) showToast('Activo actualizado correctamente');
  return ok;
}

// ── VALIDACIÓN: USUARIO (modal) ────────
function validateUsuario() {
  const nm = $('uName')?.value.trim();
  const un = $('uUsername')?.value.trim();
  const pw = $('uPassword')?.value;
  const em = $('uEmail')?.value.trim();
  const esNuevo = !$('uId')?.value; // si no hay id, es nuevo usuario
  let ok = true;
  if (!nm) { setErr('uName',     'uNameErr',     'Nombre requerido');        ok = false; } else clrErr('uName',     'uNameErr');
  if (!un) { setErr('uUsername', 'uUsernameErr', 'Usuario requerido');       ok = false; } else clrErr('uUsername', 'uUsernameErr');
  if (esNuevo && !pw)        { setErr('uPassword', 'uPasswordErr', 'Contraseña requerida');     ok = false; }
  else if (pw && pw.length < 6) { setErr('uPassword', 'uPasswordErr', 'Mínimo 6 caracteres');  ok = false; }
  else clrErr('uPassword', 'uPasswordErr');
  if (!em || !/^\S+@\S+\.\S+$/.test(em)) { setErr('uEmail', 'uEmailErr', 'Correo válido requerido'); ok = false; } else clrErr('uEmail', 'uEmailErr');
  if (ok) {
    showToast(esNuevo ? 'Usuario creado correctamente' : 'Usuario actualizado correctamente');
    closeModal('userModal');
  }
  return ok;
}

// ── FOTO: preview al subir imagen ──────
function prevPhoto(input, previewId) {
  const f = input.files[0];
  if (!f) return;
  if (f.size > 5 * 1024 * 1024) {
    showToast('La imagen supera los 5 MB', 'error');
    return;
  }
  const r = new FileReader();
  r.onload = e => {
    const p = $(previewId);
    if (p) { p.src = e.target.result; p.style.display = 'block'; }
  };
  r.readAsDataURL(f);
}

// ── SIDEBAR MOBILE ─────────────────────
function openSidebar() {
  document.getElementById('sidebar')?.classList.add('open');
  document.getElementById('sidebarOverlay')?.classList.add('show');
  document.body.style.overflow = 'hidden';
}
function closeSidebar() {
  document.getElementById('sidebar')?.classList.remove('open');
  document.getElementById('sidebarOverlay')?.classList.remove('show');
  document.body.style.overflow = '';
}
document.getElementById('sidebarOverlay')?.addEventListener('click', closeSidebar);
document.getElementById('menuBtn')?.addEventListener('click', openSidebar);
window.addEventListener('resize', () => { if (window.innerWidth > 768) closeSidebar(); });
