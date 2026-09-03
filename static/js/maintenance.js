// maintenance.js
// =======================================================================
// FIX BUG 3: Las funciones openDeleteModal/closeDeleteModal se
//            renombraron para no sobrescribir las de update.js.
//            Ahora usan el prefijo "maintenance_" y solo se activan
//            si el modal específico de mantenimiento existe.
// =======================================================================

function maintenance_openDeleteModal() {
  const modal = document.getElementById("deleteModal");
  if (!modal) return;
  modal.classList.remove("hidden");
  setTimeout(() => {
    modal.classList.remove("opacity-0");
    // Buscar div.transform de forma segura
    const transformDiv = modal.querySelector("div.transform");
    if (transformDiv) {
      transformDiv.classList.remove("scale-95");
      transformDiv.classList.add("scale-100");
    }
  }, 10);
}

function maintenance_closeDeleteModal() {
  const modal = document.getElementById("deleteModal");
  if (!modal) return;
  modal.classList.add("opacity-0");
  const transformDiv = modal.querySelector("div.transform");
  if (transformDiv) {
    transformDiv.classList.remove("scale-100");
    transformDiv.classList.add("scale-95");
  }
  setTimeout(() => {
    modal.classList.add("hidden");
  }, 300);
}

// --- VERIFICACIÓN PERIÓDICA PARA EXPULSAR USUARIOS ---
let maintenanceCheckInterval = null;

// --- SISTEMA DE EXPULSIÓN CON AVISO PREVIO ---
let warningShown = false;
let countdownInterval = null;

function startMaintenanceWatcher() {
    maintenanceCheckInterval = setInterval(async () => {
        try {
            const res = await fetch('/api/admin/check-maintenance');

            // Sesión expirada — redirigir al login
            if (res.status === 401) {
                clearInterval(maintenanceCheckInterval);
                clearInterval(countdownInterval);
                window.location.href = '/login';
                return;
            }

            if (!res.ok) return; // otro error HTTP, ignorar silenciosamente

            const data = await res.json();
            if (!data.success) return;

            if (data.maintenance_starting_soon && !warningShown) {
                warningShown = true;
                const minutesLeft = Math.ceil(data.seconds_until_start / 60);
                showMaintenanceWarning(minutesLeft);
            }

            if (data.maintenance_active && !data.can_stay_logged) {
                clearInterval(maintenanceCheckInterval);
                clearInterval(countdownInterval);
                createForceLogoutModal();
            }

        } catch (e) {
            // Solo loguear si no es error de sesión (que ya está manejado arriba)
            console.warn('Error verificando mantenimiento:', e.message);
        }
    }, 10000);
}

function showMaintenanceWarning(minutesLeft) {
    // Crear banner de aviso
    const banner = document.createElement('div');
    banner.id = 'maintenance-warning';
    banner.className = 'fixed top-0 left-0 right-0 bg-yellow-500 text-white text-center py-3 px-4 z-50 shadow-lg';
    banner.innerHTML = `
        <div class="flex items-center justify-center gap-3">
            <i class="fas fa-exclamation-triangle"></i>
            <span id="warning-text"> Mantenimiento programado en ${minutesLeft} minutos. Guarda tu trabajo.</span>
        </div>
    `;
    document.body.prepend(banner);
    
    // Actualizar contador
    let secondsLeft = minutesLeft * 60;
    countdownInterval = setInterval(() => {
        secondsLeft--;
        const mins = Math.floor(secondsLeft / 60);
        const secs = secondsLeft % 60;
        const text = document.getElementById('warning-text');
        if (text) {
            text.textContent = ` Mantenimiento en ${mins}:${secs.toString().padStart(2, '0')}. Guarda tu trabajo.`;
        }
    }, 1000);
}

function createForceLogoutModal() {
    const modal = document.createElement('div');
    modal.className = 'fixed inset-0 z-[100] flex items-center justify-center bg-gray-900 bg-opacity-90 backdrop-blur-sm';
    modal.innerHTML = `
        <div class="bg-white rounded-2xl shadow-2xl p-8 max-w-md text-center">
            <div class="mb-6">
                <i class="fas fa-tools text-6xl text-orange-500 animate-bounce"></i>
            </div>
            <h2 class="text-2xl font-bold text-gray-800 mb-4">Mantenimiento en Curso</h2>
            <p class="text-gray-600 mb-6">
                El sistema está actualmente en mantenimiento programado. 
                Serás redirigido al inicio de sesión en <span id="countdown">5</span> segundos...
            </p>
            <button onclick="window.location.href='/logout'" 
                class="bg-orange-500 hover:bg-orange-600 text-white font-bold py-3 px-8 rounded-xl transition">
                Salir Ahora
            </button>
        </div>
    `;
    document.body.appendChild(modal);
    
    // Countdown de 5 segundos antes de expulsar
    let count = 5;
    const countdownEl = document.getElementById('countdown');
    const timer = setInterval(() => {
        count--;
        if (countdownEl) countdownEl.textContent = count;
        if (count <= 0) {
            clearInterval(timer);
            window.location.href = '/logout';
        }
    }, 1000);
}

// Iniciar al cargar
document.addEventListener('DOMContentLoaded', startMaintenanceWatcher);