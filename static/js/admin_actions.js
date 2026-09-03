// static/js/admin_actions.js
// Requiere: csrf.js cargado ANTES en el template
let deleteAction = null;
let targetId = null;
let targetUserId = null;

document.addEventListener('DOMContentLoaded', loadPeriods);

async function loadPeriods() {
    const select = document.getElementById('periodoSelect');
    if (!select) return;
    try {
        const res = await fetch('/api/encuestas');
        const data = await res.json();
        select.innerHTML = '<option value="">-- Seleccionar --</option>';
        data.forEach(p => {
            select.innerHTML += `<option value="${p.id_encuesta}">${p.nombre}</option>`;
        });
        if (data.length > 0) select.selectedIndex = 1;
        renderPeriodsTable(data);
    } catch (e) {
        console.error("Error cargando periodos:", e);
        select.innerHTML = '<option value="">Error cargando datos</option>';
    }
}

function renderPeriodsTable(data) {
    const tbody = document.getElementById('periodsTableBody');
    if (!tbody) return;
    tbody.innerHTML = '';
    if (data.length === 0) {
        tbody.innerHTML = '<tr><td colspan="3" class="p-4 text-center text-gray-400">No hay periodos registrados</td></tr>';
        return;
    }
    data.forEach(p => {
        const row = `
            <tr class="hover:bg-gray-50 group transition border-b border-gray-100">
                <td class="p-3 font-mono text-xs text-gray-500 text-center">${p.id_encuesta}</td>
                <td class="p-3">
                    <input type="text" id="name-${p.id_encuesta}" value="${p.nombre}"
                        class="w-full bg-transparent border-b border-transparent hover:border-gray-300 focus:border-blue-500 focus:bg-white px-2 py-1 outline-none transition text-sm text-gray-700"
                        onchange="updatePeriodName(${p.id_encuesta})">
                </td>
                <td class="p-3 text-center">
                    <button onclick="prepareDeletePeriod(${p.id_encuesta})"
                        class="text-red-400 hover:text-red-600 p-2 rounded-full hover:bg-red-50 transition" title="Eliminar Periodo">
                        <i class="fas fa-trash-alt"></i>
                    </button>
                </td>
            </tr>`;
        tbody.innerHTML += row;
    });
}

async function updatePeriodName(id) {
    const input = document.getElementById(`name-${id}`);
    const newName = input.value;
    try {
        const res = await csrfFetch(`/api/encuestas/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ nombre: newName })
        });
        if (res.ok) {
            input.classList.add('text-green-600', 'font-bold');
            setTimeout(() => input.classList.remove('text-green-600', 'font-bold'), 1000);
        } else {
            alert("Error al actualizar nombre");
        }
    } catch (e) { console.error(e); }
}

// --- MODALES ---
function openPeriodsModal() {
    loadPeriods();
    const modal = document.getElementById('periodsModal');
    modal.classList.remove('hidden');
    setTimeout(() => {
        modal.classList.remove('opacity-0');
        modal.querySelector('div.relative').classList.remove('scale-95');
    }, 10);
}

function closePeriodsModal() {
    const modal = document.getElementById('periodsModal');
    modal.classList.add('opacity-0');
    modal.querySelector('div.relative').classList.add('scale-95');
    setTimeout(() => modal.classList.add('hidden'), 300);
    loadPeriods();
}

function prepareSystemReset() {
    deleteAction = 'RESET_SYSTEM';
    document.getElementById('deleteTitle').innerText = "¿Reiniciar TODO?";
    document.getElementById('deleteMsg').innerHTML = "Se borrarán <b>TODAS</b> las encuestas, empleados y respuestas.<br>El sistema quedará vacío.";
    openDeleteModal();
}

function prepareDeletePeriod(id) {
    if (!id) { console.error("ID inválido para borrar"); return; }
    deleteAction = 'DELETE_PERIOD';
    targetId = id;
    document.getElementById('deleteTitle').innerText = "¿Eliminar Periodo?";
    document.getElementById('deleteMsg').innerText = "Se eliminará este periodo y TODOS sus datos asociados.";
    openDeleteModal();
}

function openDeleteModal() {
    const modal = document.getElementById('deleteModal');
    modal.classList.remove('hidden');
    setTimeout(() => modal.classList.remove('opacity-0'), 10);
}

function closeDeleteModal() {
    const modal = document.getElementById('deleteModal');
    modal.classList.add('opacity-0');
    setTimeout(() => {
        modal.classList.add('hidden');
        deleteAction = null;
        targetId = null;
    }, 300);
}

async function executeDelete() {
    if (deleteAction === 'DELETE_USER') {
        await confirmDeleteUser();
    } else if (deleteAction === 'RESET_SYSTEM') {
        await confirmResetSystem();
    } else if (deleteAction === 'DELETE_PERIOD') {
        await confirmDeletePeriod();
    }
    closeDeleteModal();
}

async function confirmResetSystem() {
    try {
        const key = prompt('Ingresa la clave maestra para reiniciar el sistema:');
        if (!key) { alert('Operación cancelada'); return; }
        const res = await csrfFetch('/api/admin/reset', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ master_key: key })
        });
        const data = await res.json();
        if (res.status === 403) { alert('Clave maestra inválida o no tienes permisos.'); return; }
        if (data.success) { alert("Sistema reiniciado completamente."); location.reload(); }
        else { alert("Error: " + (data.message || 'No fue posible reiniciar')); }
    } catch (e) { alert("Error de conexión"); }
}

async function confirmDeletePeriod() {
    if (!targetId) return;
    try {
        const res = await csrfFetch(`/api/encuestas/${targetId}`, { method: 'DELETE' });
        const data = await res.json();
        if (data.success) { loadPeriods(); }
        else { alert("Error: " + (data.error || "No se pudo eliminar")); }
    } catch (e) { alert("Error de conexión"); }
}

// --- UI TOGGLES ---
function toggleNewPeriodInput() {
    const check = document.getElementById('checkNewPeriod');
    const select = document.getElementById('periodoSelect');
    const inputDiv = document.getElementById('newPeriodContainer');
    const inputName = document.getElementById('newPeriodName');
    if (check.checked) {
        select.disabled = true;
        select.classList.add('opacity-50', 'bg-gray-100');
        inputDiv.classList.remove('hidden');
        inputName.focus();
    } else {
        select.disabled = false;
        select.classList.remove('opacity-50', 'bg-gray-100');
        inputDiv.classList.add('hidden');
    }
}

function updateFileName(input, spanId) {
    const span = document.getElementById(spanId);
    if (input.files.length > 0) {
        span.textContent = input.files[0].name;
        span.classList.add("text-gray-800", "font-medium");
    } else {
        span.textContent = "Seleccionar archivo...";
        span.classList.remove("text-gray-800", "font-medium");
    }
}

async function uploadExcel() {
    const input = document.getElementById('excelInput');
    const file = input.files[0];
    
    // Obtener datos del formulario de periodo
    const isNew = document.getElementById('checkNewPeriod').checked;
    const existingId = document.getElementById('periodoSelect').value;
    const newName = document.getElementById('newPeriodName').value.trim();

    if (!file) {
        alert(" Por favor selecciona un archivo Excel.");
        return;
    }
    alert('Función de importación no disponible.');
}

// --- MANTENIMIENTO ---
async function loadMaintenanceList() {
    const tbody = document.getElementById('maintenanceTableBody');
    if (!tbody) return;
    try {
        const res = await fetch('/api/admin/maintenance/list');
        const data = await res.json();
        if (data.success) { renderMaintenanceTable(data.maintenance); }
        else { tbody.innerHTML = `<tr><td colspan="6" class="p-4 text-center text-red-500">Error: ${data.message}</td></tr>`; }
    } catch (e) {
        console.error('Error cargando mantenimiento:', e);
        tbody.innerHTML = '<tr><td colspan="6" class="p-4 text-center text-red-500">Error cargando datos</td></tr>';
    }
}

async function reserveMaintenance() {
    const categorySelect = document.getElementById('categorySelect');
    const start = document.getElementById('startInput');
    const end = document.getElementById('endInput');
    const notes = document.getElementById('notesInput');

    if (!categorySelect || !categorySelect.value) { alert('Por favor selecciona una categoría.'); return; }
    if (!start || start.value.trim() === '') { alert('Por favor ingresa fecha y hora de inicio.'); return; }
    if (!end || end.value.trim() === '') { alert('Por favor ingresa fecha y hora de fin.'); return; }

    const startDate = new Date(start.value);
    const endDate = new Date(end.value);
    if (endDate <= startDate) { alert('La fecha/hora de fin debe ser posterior a la de inicio.'); return; }

    const convertToLocal = (s) => {
        const d = new Date(s);
        return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')} ${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}:00`;
    };

    const categoryText = categorySelect.options[categorySelect.selectedIndex].text;
    const notesText = notes ? notes.value.trim() : '';
    const formattedNotes = notesText ? `${categoryText} - ${notesText}` : categoryText;

    const payload = { active: 1, start: convertToLocal(start.value), end: convertToLocal(end.value), notas: formattedNotes };

    try {
        const res = await csrfFetch('/api/admin/maintenance', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (data.success) {
            alert('Evento de mantenimiento programado.');
            if (categorySelect) categorySelect.selectedIndex = 0;
            if (notes) notes.value = '';
            if (start) start.value = '';
            if (end) end.value = '';
            loadMaintenanceList();
            checkResetAvailability();
        } else {
            alert('Error: ' + (data.message || 'No se pudo programar'));
        }
    } catch (e) { console.error(e); alert('Error al programar mantenimiento'); }
}

function renderMaintenanceTable(rows) {
    const tbody = document.getElementById('maintenanceTableBody');
    if (!tbody) return;
    const table = tbody.closest('table');
    const headerCells = table ? table.querySelectorAll('thead th') : [];
    const hasRolColumn = headerCells.length === 6;

    tbody.innerHTML = '';
    if (!rows || rows.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" class="p-6 text-center text-gray-400">No hay eventos programados</td></tr>';
        return;
    }

    rows.forEach(r => {
        try {
            const parseLocalDate = (dateStr) => {
                if (!dateStr) return null;
                const parts = dateStr.split(' ');
                if (parts.length !== 2) return null;
                const d = new Date(`${parts[0]}T${parts[1]}`);
                return isNaN(d.getTime()) ? null : d;
            };
            const startDate = r.start ? parseLocalDate(r.start) : null;
            const endDate = r.end ? parseLocalDate(r.end) : null;
            const now = new Date();
            const start = startDate ? startDate.toLocaleString('es-MX') : '—';
            const end = endDate ? endDate.toLocaleString('es-MX') : '—';

            let status = 'Desconocido', statusLabel = 'bg-gray-100 text-gray-700', statusIcon = 'fa-question-circle';
            if (r.active === 0) { status = 'Cancelado'; statusLabel = 'bg-gray-100 text-gray-500'; statusIcon = 'fa-ban'; }
            else if (!startDate) { status = 'Sin programar'; statusLabel = 'bg-yellow-100 text-yellow-700'; statusIcon = 'fa-exclamation-triangle'; }
            else if (now < startDate) { status = 'Programado'; statusLabel = 'bg-blue-100 text-blue-700'; statusIcon = 'fa-clock'; }
            else if (now >= startDate && (!endDate || now <= endDate)) { status = 'En Curso'; statusLabel = 'bg-orange-100 text-orange-700 animate-pulse'; statusIcon = 'fa-wrench'; }
            else if (endDate && now > endDate) { status = 'Finalizado'; statusLabel = 'bg-green-100 text-green-700'; statusIcon = 'fa-check-circle'; }

            let showCancelButton = false, showDeleteButton = false;
            if (r.active === 0 || !startDate || (endDate && now > endDate)) { showDeleteButton = true; }
            else if (now < startDate) { showCancelButton = true; showDeleteButton = true; }
            else if (now >= startDate && (!endDate || now <= endDate)) { showCancelButton = true; }

            const parts = (r.notas || '').split(' - ');
            const categoria = parts[0] || 'Mantenimiento General';
            const detalles = parts.slice(1).join(' - ') || '';

            const row = document.createElement('tr');
            row.className = 'hover:bg-gray-50 transition';
            const actionsHtml = `
                <div class="flex justify-center gap-2">
                    ${showCancelButton ? `<button onclick="cancelMaintenance(${r.id})" class="text-blue-500 hover:text-blue-700 p-1 hover:bg-blue-50 rounded transition" title="Cancelar"><i class="fas fa-times-circle"></i></button>` : ''}
                    ${showDeleteButton ? `<button onclick="deleteMaintenance(${r.id}, ${r.active})" class="text-red-500 hover:text-red-700 p-1 hover:bg-red-50 rounded transition" title="Eliminar"><i class="fas fa-trash"></i></button>` : ''}
                </div>`;

            if (hasRolColumn) {
                row.innerHTML = `
                    <td class="p-4 font-bold text-gray-600">${r.created_by || 'Sistema'}</td>
                    <td class="p-4"><div class="font-medium text-gray-900">${categoria}</div>${detalles ? `<div class="text-xs text-gray-500">${detalles}</div>` : ''}</td>
                    <td class="p-4"><div class="font-bold text-gray-800">${start}</div><div class="text-xs text-gray-500">Hasta: ${end}</div></td>
                    <td class="p-4 text-gray-500 text-xs italic">${r.notas || 'Sin notas'}</td>
                    <td class="p-4 text-center"><span class="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium ${statusLabel}"><i class="fas ${statusIcon}"></i> ${status}</span></td>
                    <td class="p-4 text-center">${actionsHtml}</td>`;
            } else {
                row.innerHTML = `
                    <td class="p-4"><div class="font-medium text-gray-900">${categoria}</div>${detalles ? `<div class="text-xs text-gray-500">${detalles}</div>` : ''}</td>
                    <td class="p-4"><div class="font-bold text-gray-800">${start}</div><div class="text-xs text-gray-500">Hasta: ${end}</div></td>
                    <td class="p-4 text-gray-500 text-xs italic">${r.notas || 'Sin notas'}</td>
                    <td class="p-4 text-center"><span class="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium ${statusLabel}"><i class="fas ${statusIcon}"></i> ${status}</span></td>
                    <td class="p-4 text-center">${actionsHtml}</td>`;
            }
            tbody.appendChild(row);
        } catch (rowError) { console.error('Error renderizando fila:', rowError, r); }
    });
}

async function cancelMaintenance(id) {
    if (!confirm('¿Confirmar cancelar este evento de mantenimiento?')) return;
    try {
        const res = await csrfFetch(`/api/admin/maintenance/${id}`, { method: 'DELETE' });
        const data = await res.json();
        if (data.success) { alert('Mantenimiento cancelado'); loadMaintenanceList(); checkResetAvailability(); }
        else { alert('Error: ' + (data.message || 'No se pudo cancelar')); }
    } catch (e) { console.error(e); alert('Error al cancelar mantenimiento'); }
}

async function deleteMaintenance(id, active) {
    if (!confirm('¿Eliminar este evento de mantenimiento?')) return;
    try {
        const res = await csrfFetch(`/api/admin/maintenance/${id}`, {
            method: 'DELETE',
            headers: { 'X-Delete-Force': 'true' }
        });
        const data = await res.json().catch(() => ({ success: false, message: 'Respuesta inválida' }));
        if (res.status === 400) { alert('Error: ' + (data.message || 'No se puede eliminar este evento')); return; }
        if (data.success) { alert('Evento de mantenimiento eliminado'); loadMaintenanceList(); checkResetAvailability(); }
        else { alert('Error: ' + (data.message || 'No se pudo eliminar')); }
    } catch (e) { console.error(e); alert('Error al eliminar mantenimiento'); }
}

function parseMaintenanceDate(raw) {
    try {
        if (!raw) return null;
        let s = String(raw).trim();
        if (/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}(:\d{2})?$/.test(s)) s = s.replace(' ', 'T');
        if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(s)) s = s + ':00';
        const d = new Date(s);
        return isNaN(d.getTime()) ? null : d;
    } catch (e) { return null; }
}

async function checkResetAvailability() {
    try {
        const res = await fetch('/api/admin/maintenance/list');
        const data = await res.json();
        const btn = document.getElementById('btnResetSystem');
        if (!btn) return;
        if (!data.success) { btn.disabled = true; return; }

        const now = new Date();
        let enabled = false;
        for (const r of data.maintenance) {
            if (!r.start) continue;
            const parseLocalDate = (s) => {
                if (!s) return null;
                const p = s.split(' ');
                if (p.length !== 2) return null;
                const d = new Date(`${p[0]}T${p[1]}`);
                return isNaN(d.getTime()) ? null : d;
            };
            const start = parseLocalDate(r.start);
            const end = r.end ? parseLocalDate(r.end) : null;
            if (!start) continue;
            if (r.active == 1 && now >= start && (!end || now <= end)) { enabled = true; break; }
        }
        btn.disabled = !enabled;
    } catch (e) { console.error('Error verificando disponibilidad reset:', e); }
    setTimeout(checkResetAvailability, 5000);
}

async function loadServerStatus() {
    if (window && window.MaintenanceCore && typeof window.MaintenanceCore.loadServerStatus === 'function') {
        return await window.MaintenanceCore.loadServerStatus();
    }
    try {
        const res = await fetch('/api/admin/server-status');
        const data = await res.json();
        if (!data.success) { updateServerStatusUI('Error', 'bg-red-100 text-red-700', 'Error'); return; }
        updateServerStatusUI(data.db_status, data.db_status_class, data.last_maintenance_text);
    } catch (e) { updateServerStatusUI('Error de conexión', 'bg-red-100 text-red-700', 'Error'); }
}

function updateServerStatusUI(dbStatus, dbStatusClass, lastMaintenanceText) {
    const dbStatusEl = document.getElementById('dbStatus');
    const lastMaintenanceEl = document.getElementById('lastMaintenance');
    if (dbStatusEl) {
        dbStatusEl.className = `text-xs px-2 py-1 rounded font-bold ${dbStatusClass}`;
        dbStatusEl.innerHTML = `<i class="fas ${dbStatus === 'Conectada' ? 'fa-check-circle' : 'fa-times-circle'}"></i> ${dbStatus}`;
    }
    if (lastMaintenanceEl) lastMaintenanceEl.textContent = lastMaintenanceText;
}

function refreshServerStatus() {
    const btn = event.target;
    const icon = btn.querySelector('i');
    icon.classList.add('fa-spin');
    loadServerStatus().finally(() => { setTimeout(() => icon.classList.remove('fa-spin'), 500); });
}

document.addEventListener('DOMContentLoaded', () => {
    try {
        loadMaintenanceList();
        loadServerStatus();
        checkResetAvailability();
        loadPeriodsForMaintenance();
    } catch (e) { console.error('Error inicializando:', e); }
});

function downloadBackup() { window.location.href = '/api/admin/backup'; }

async function confirmReset() {
    try {
        const input = document.getElementById('masterKeyInput');
        let key = input && input.value ? input.value.trim() : null;
        if (!key) { key = prompt('Ingresa la clave maestra para reiniciar el sistema:'); }
        if (!key) { alert('Operación cancelada'); closeDeleteModal(); return; }

        const res = await csrfFetch('/api/admin/reset', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ master_key: key })
        });
        if (res.status === 403) {
            alert('Clave maestra inválida o no tienes permisos.');
            if (input) input.value = '';
            closeDeleteModal();
            return;
        }
        const data = await res.json();
        if (data.success) { alert(data.message || 'Sistema reiniciado completamente.'); closeDeleteModal(); location.reload(); }
        else { alert('Error: ' + (data.message || 'No fue posible reiniciar')); if (input) input.value = ''; closeDeleteModal(); }
    } catch (e) { console.error(e); alert('Error de conexión: ' + e.message); closeDeleteModal(); }
}

function descargarAuditoria() { window.location.href = '/api/admin/auditoria/excel'; }

// --- USUARIOS ---
async function loadUsers() {
    const tbody = document.getElementById('usersTableBody');
    if (!tbody) return;
    try {
        const res = await fetch('/api/usuarios');
        if (res.status === 403) {
            const data = await res.json();
            tbody.innerHTML = `<tr><td colspan="5" class="p-4 text-center text-red-500">${data.error || 'No tienes permisos'}</td></tr>`;
            return;
        }
        const data = await res.json();
        tbody.innerHTML = '';
        if (data.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" class="p-4 text-center text-gray-400">No hay usuarios registrados</td></tr>';
            return;
        }
        data.forEach(u => {
            let rolColor = 'bg-gray-100 text-gray-700';
            if (u.rol === 'admin') rolColor = 'bg-red-100 text-red-700';
            else if (u.rol === 'analista') rolColor = 'bg-blue-100 text-blue-700';
            else if (u.rol === 'consulta') rolColor = 'bg-green-100 text-green-700';
            const superadminBadge = u.is_superadmin ? '<span class="ml-2 px-2 py-0.5 bg-yellow-100 text-yellow-800 text-xs font-bold rounded-full border border-yellow-300"><i class="fas fa-crown"></i> SUPER</span>' : '';
            const deleteButton = u.is_superadmin
                ? '<span class="text-gray-300 text-xs italic">Protegido</span>'
                : `<button onclick="prepareDeleteUser(${u.id_usuario}, '${u.usuario}')" class="text-red-400 hover:text-red-600 p-2 rounded-full hover:bg-red-50 transition"><i class="fas fa-trash-alt"></i></button>`;
            tbody.innerHTML += `
                <tr class="hover:bg-gray-50 group transition border-b border-gray-100">
                    <td class="p-3 font-mono text-xs text-gray-500 text-center">${u.id_usuario}</td>
                    <td class="p-3 font-bold text-gray-800">${u.usuario}${superadminBadge}</td>
                    <td class="p-3 text-gray-700">${u.nombre}</td>
                    <td class="p-3"><span class="px-3 py-1 rounded-full text-xs font-bold ${rolColor}">${u.rol.charAt(0).toUpperCase() + u.rol.slice(1)}</span></td>
                    <td class="p-3 text-center">${deleteButton}</td>
                </tr>`;
        });
    } catch (e) {
        console.error("Error cargando usuarios:", e);
        tbody.innerHTML = '<tr><td colspan="5" class="p-4 text-center text-red-500">Error al cargar usuarios</td></tr>';
    }
}

function openUsersModal() {
    loadUsers();
    const modal = document.getElementById('usersModal');
    modal.classList.remove('hidden');
    setTimeout(() => {
        modal.classList.remove('opacity-0');
        modal.querySelector('div.relative').classList.remove('scale-95');
    }, 10);
}

function closeUsersModal() {
    const modal = document.getElementById('usersModal');
    modal.classList.add('opacity-0');
    modal.querySelector('div.relative').classList.add('scale-95');
    setTimeout(() => modal.classList.add('hidden'), 300);
}

function prepareDeleteUser(id, username) {
    deleteAction = 'DELETE_USER';
    targetUserId = id;
    document.getElementById('deleteTitle').innerText = "¿Eliminar Usuario?";
    document.getElementById('deleteMsg').innerText = `Se eliminará el usuario "${username}" del sistema.`;
    openDeleteModal();
}

async function confirmDeleteUser() {
    if (!targetUserId) return;
    try {
        const res = await csrfFetch(`/api/usuarios/${targetUserId}`, { method: 'DELETE' });
        const data = await res.json();
        if (res.status === 403 || res.status === 400) { alert("Alerta: " + (data.error || data.message || "No tienes permisos")); return; }
        if (data.success) { alert("Usuario eliminado exitosamente"); loadUsers(); }
        else { alert("Error: " + (data.error || data.message || "Error desconocido")); }
    } catch (e) { console.error(e); alert("Error de conexión: " + e.message); }
}

// --- Periodos para Mantenimiento ---
async function loadPeriodsForMaintenance() {
    const select = document.getElementById('periodoSelectMaint');
    if (!select) return;
    try {
        const res = await fetch('/api/encuestas');
        const data = await res.json();
        select.innerHTML = '<option value="">-- Seleccionar --</option>';
        data.forEach(p => { select.innerHTML += `<option value="${p.id_encuesta}">${p.nombre}</option>`; });
        if (data.length > 0) select.selectedIndex = 1;
    } catch (e) {
        console.error("Error cargando periodos:", e);
        select.innerHTML = '<option value="">Error cargando datos</option>';
    }
}

function toggleNewPeriodInputMaint() {
    const check = document.getElementById('checkNewPeriodMaint');
    const select = document.getElementById('periodoSelectMaint');
    const inputDiv = document.getElementById('newPeriodNameMaint');
    if (!check || !select || !inputDiv) return;
    if (check.checked) {
        select.disabled = true; select.classList.add('opacity-50', 'bg-gray-100');
        inputDiv.classList.remove('hidden'); inputDiv.focus();
    } else {
        select.disabled = false; select.classList.remove('opacity-50', 'bg-gray-100');
        inputDiv.classList.add('hidden');
    }
}

function updateFileNameMaint(input, spanId) {
    const span = document.getElementById(spanId);
    if (!span) return;
    if (input.files.length > 0) {
        span.textContent = input.files[0].name; span.classList.add("text-gray-800", "font-medium");
    } else {
        span.textContent = "Seleccionar archivo..."; span.classList.remove("text-gray-800", "font-medium");
    }
}

async function uploadExcelMaint() {
    if (window && window.MaintenanceCore && typeof window.MaintenanceCore.uploadExcel === 'function') {
        return await window.MaintenanceCore.uploadExcel();
    }
    alert('Función de importación no disponible.');
}

async function uploadSQLMaint() {
    if (window && window.MaintenanceCore && typeof window.MaintenanceCore.uploadSQL === 'function') {
        return await window.MaintenanceCore.uploadSQL();
    }
    alert('Función de restauración no disponible.');
}

function startMaintenance() {
    // Guard: si maintenance_actions.js aún no cargó, esperar
    if (typeof window.startMaintenanceAction === 'function') {
        window.startMaintenanceAction();
    } else {
        console.warn('maintenance_actions.js aún no está listo');
        setTimeout(startMaintenance, 500); // reintentar en 500ms
    }
}

// checkResetAvailability ya definida arriba - reutilizable para botones de mantenimiento
// Se llama también al final del init y cada 5s