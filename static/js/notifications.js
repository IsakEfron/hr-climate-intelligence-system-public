// ==========================================
// SISTEMA DE NOTIFICACIONES DE MANTENIMIENTO
// ==========================================

let notificationCheckInterval = null;
let notificationPanelOpen = false;
let notificationBackoffMs = 30000;  // Intervalo base: 30 segundos
const NOTIFICATION_MAX_BACKOFF = 120000;  // Máximo: 2 minutos

// --- INICIALIZAR SISTEMA ---
document.addEventListener('DOMContentLoaded', () => {
    loadNotifications();
    startNotificationChecker();
});

// --- TOGGLE PANEL ---
function toggleNotifications() {
    const panel = document.getElementById('notificationPanel');
    notificationPanelOpen = !notificationPanelOpen;
    
    if (notificationPanelOpen) {
        panel.classList.remove('hidden');
        setTimeout(() => {
            panel.style.transform = 'translateY(0)';
            panel.style.opacity = '1';
        }, 10);
        loadNotifications(); // Recargar al abrir
    } else {
        panel.style.transform = 'translateY(-20px)';
        panel.style.opacity = '0';
        setTimeout(() => panel.classList.add('hidden'), 300);
    }
}

// Cerrar al hacer click fuera
document.addEventListener('click', (e) => {
    const panel = document.getElementById('notificationPanel');
    const btn = document.getElementById('notificationBtn');
    
    if (notificationPanelOpen && 
        !panel.contains(e.target) && 
        !btn.contains(e.target)) {
        toggleNotifications();
    }
});

// --- CARGAR NOTIFICACIONES ---
async function loadNotifications() {
    try {
        const res = await fetch('/api/maintenance/upcoming');
        
        if (res.status === 401) {
            // Sesión expirada — redirigir silenciosamente
            clearInterval(notificationCheckInterval);
            window.location.href = '/login';
            return;
        }

        // ===============================================================
        // FIX 429: Si recibimos 429 (rate limit), no mostrar error
        //          al usuario. Solo hacer backoff silencioso.
        // ===============================================================
        if (res.status === 429) {
            console.warn('[Notificaciones] Rate limit alcanzado, reintentando más tarde...');
            // Incrementar backoff para no saturar
            notificationBackoffMs = Math.min(notificationBackoffMs * 2, NOTIFICATION_MAX_BACKOFF);
            restartNotificationChecker();
            return;
        }

        if (!res.ok) {
            // Solo mostrar error si el panel está abierto
            if (notificationPanelOpen) {
                showNotificationError('Error al cargar notificaciones');
            }
            return;
        }
        
        const data = await res.json();
        
        if (!data.success) {
            if (notificationPanelOpen) {
                showNotificationError('Error al cargar notificaciones');
            }
            return;
        }
        
        // Éxito: resetear backoff al valor normal
        notificationBackoffMs = 30000;
        
        const maintenance = data.maintenance || [];
        
        // Filtrar solo eventos activos y futuros
        const now = new Date();
        const activeEvents = maintenance.filter(m => {
            if (m.active !== 1) return false;
            
            // Si tiene fecha de fin y ya pasó, no mostrar
            if (m.end) {
                const endDate = parseLocalDate(m.end);
                if (endDate && now > endDate) return false;
            }
            
            return true;
        });
        
        // Actualizar badge
        updateNotificationBadge(activeEvents.length);
        
        // Renderizar contenido
        renderNotifications(activeEvents);
        
    } catch (e) {
        console.warn('Error cargando notificaciones:', e.message);
        // No mostrar error en UI para errores de red silenciosos
    }
}

// --- ACTUALIZAR BADGE ---
function updateNotificationBadge(count) {
    const badge = document.getElementById('notificationBadge');
    const btn = document.getElementById('notificationBtn');
    if (!badge || !btn) return;
    
    if (count > 0) {
        badge.textContent = count > 9 ? '9+' : count;
        badge.classList.remove('hidden');
        
        // Efecto de pulso si hay notificaciones
        btn.classList.add('animate-pulse');
        
        // Agregar clase de alerta para icono rojo
        const icon = btn.querySelector('i');
        if (icon) {
            icon.classList.add('text-red-500');
            icon.classList.remove('text-white');
        }
    } else {
        badge.classList.add('hidden');
        btn.classList.remove('animate-pulse');
        const icon = btn.querySelector('i');
        if (icon) {
            icon.classList.remove('text-red-500');
            icon.classList.add('text-white');
        }
    }
}

// --- RENDERIZAR NOTIFICACIONES ---
function renderNotifications(events) {
    const container = document.getElementById('notificationContent');
    if (!container) return;
    
    if (events.length === 0) {
        container.innerHTML = `
            <div class="flex flex-col items-center justify-center py-12 text-gray-400">
                <i class="fas fa-check-circle text-5xl mb-3 text-green-400"></i>
                <p class="font-semibold text-gray-600">Sin mantenimientos programados</p>
                <p class="text-sm mt-1">El sistema está disponible</p>
            </div>
        `;
        return;
    }
    
    container.innerHTML = events.map(event => createNotificationCard(event)).join('');
}

// --- CREAR TARJETA DE NOTIFICACIÓN ---
function createNotificationCard(event) {
    const startDate = event.start ? parseLocalDate(event.start) : null;
    const endDate = event.end ? parseLocalDate(event.end) : null;
    const now = new Date();
    
    // Determinar estado
    let statusClass = 'bg-blue-100 text-blue-800';
    let statusIcon = 'fa-clock';
    let statusText = 'Programado';
    
    if (startDate && now >= startDate) {
        if (!endDate || now <= endDate) {
            statusClass = 'bg-orange-100 text-orange-800';
            statusIcon = 'fa-wrench';
            statusText = 'En Curso';
        }
    }
    
    // Parsear categoría y notas
    const parts = (event.notas || '').split(' - ');
    const categoria = parts[0] || 'Mantenimiento General';
    const detalles = parts.slice(1).join(' - ') || 'Sin detalles adicionales';
    
    // Formatear fechas
    const startFormatted = startDate ? formatDateTime(startDate) : 'No especificado';
    const endFormatted = endDate ? formatDateTime(endDate) : 'No especificado';
    
    // Calcular tiempo restante
    let timeRemaining = '';
    if (startDate && now < startDate) {
        const diff = startDate - now;
        const days = Math.floor(diff / (1000 * 60 * 60 * 24));
        const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
        const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
        
        if (days > 0) {
            timeRemaining = `En ${days}d ${hours}h`;
        } else if (hours > 0) {
            timeRemaining = `En ${hours}h ${minutes}m`;
        } else {
            timeRemaining = `En ${minutes} minutos`;
        }
    }
    
    return `
        <div class="bg-white border border-gray-200 rounded-xl p-4 mb-3 hover:shadow-md transition">
            <!-- Header -->
            <div class="flex justify-between items-start mb-3">
                <div class="flex items-center gap-2">
                    <div class="bg-gradient-to-br from-primary to-blue-600 text-white rounded-lg p-2">
                        <i class="fas ${statusIcon}"></i>
                    </div>
                    <div>
                        <h4 class="font-bold text-gray-800">${categoria}</h4>
                        <p class="text-xs text-gray-500">Por: ${event.created_by || 'Sistema'}</p>
                    </div>
                </div>
                <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold ${statusClass}">
                    ${statusText}
                </span>
            </div>
            
            <!-- Detalles -->
            <p class="text-sm text-gray-600 mb-3 italic">${detalles}</p>
            
            <!-- Fechas -->
            <div class="bg-gray-50 rounded-lg p-3 space-y-2">
                <div class="flex items-center gap-2 text-sm">
                    <i class="fas fa-play text-green-600 w-4"></i>
                    <span class="text-gray-600">Inicio:</span>
                    <span class="font-semibold text-gray-800">${startFormatted}</span>
                </div>
                <div class="flex items-center gap-2 text-sm">
                    <i class="fas fa-stop text-red-600 w-4"></i>
                    <span class="text-gray-600">Fin:</span>
                    <span class="font-semibold text-gray-800">${endFormatted}</span>
                </div>
            </div>
            
            ${timeRemaining ? `
                <div class="mt-3 bg-yellow-50 border border-yellow-200 rounded-lg p-2 text-center">
                    <span class="text-sm font-bold text-yellow-800">
                        <i class="fas fa-hourglass-half mr-1"></i>${timeRemaining}
                    </span>
                </div>
            ` : ''}
        </div>
    `;
}

// --- HELPER: PARSEAR FECHA LOCAL ---
function parseLocalDate(dateStr) {
    if (!dateStr) return null;
    const parts = dateStr.split(' ');
    if (parts.length !== 2) return null;
    const localDateString = `${parts[0]}T${parts[1]}`;
    const date = new Date(localDateString);
    return isNaN(date.getTime()) ? null : date;
}

// --- HELPER: FORMATEAR FECHA ---
function formatDateTime(date) {
    return date.toLocaleString('es-MX', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

// --- MOSTRAR ERROR ---
function showNotificationError(message) {
    const container = document.getElementById('notificationContent');
    if (!container) return;
    
    container.innerHTML = `
        <div class="flex flex-col items-center justify-center py-12 text-red-400">
            <i class="fas fa-exclamation-triangle text-5xl mb-3"></i>
            <p class="font-semibold">${message}</p>
        </div>
    `;
}

// --- VERIFICACIÓN PERIÓDICA ---
function startNotificationChecker() {
    // Recargar notificaciones cada 30 segundos (con backoff dinámico)
    notificationCheckInterval = setInterval(() => {
        if (!notificationPanelOpen) {
            // Solo actualizar badge si el panel está cerrado
            loadNotifications();
        }
    }, notificationBackoffMs);
}

// Reiniciar el checker con nuevo intervalo (para backoff)
function restartNotificationChecker() {
    if (notificationCheckInterval) {
        clearInterval(notificationCheckInterval);
    }
    notificationCheckInterval = setInterval(() => {
        if (!notificationPanelOpen) {
            loadNotifications();
        }
    }, notificationBackoffMs);
}

// Limpiar intervalo al salir de la página
window.addEventListener('beforeunload', () => {
    if (notificationCheckInterval) {
        clearInterval(notificationCheckInterval);
    }
});