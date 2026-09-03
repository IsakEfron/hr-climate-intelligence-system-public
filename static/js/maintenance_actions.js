// static/js/maintenance_actions.js
// Requiere: csrf.js cargado ANTES en el template

let _maintenanceIsActive = false; // Cache del estado de mantenimiento

document.addEventListener('DOMContentLoaded', () => {
    loadMaintenanceList();
    loadServerStatus();
    checkMaintenanceStatus();
    loadPeriodsForMaintenance();
});

// --- Lista de Mantenimientos -------------------------
async function loadMaintenanceList() {
    const tbody = document.getElementById('maintenanceTableBody');
    if (!tbody) return;
    try {
        const res = await fetch('/api/admin/maintenance/list');
        const data = await res.json();
        if (!data.success) {
            tbody.innerHTML = `<tr><td colspan="6" class="p-4 text-center text-red-500">Error: ${data.message}</td></tr>`;
            return;
        }
        renderMaintenanceTable(data.maintenance);
    } catch (e) {
        tbody.innerHTML = '<tr><td colspan="6" class="p-4 text-center text-red-500">Error cargando datos</td></tr>';
    }
}

function renderMaintenanceTable(rows) {
    const tbody = document.getElementById('maintenanceTableBody');
    if (!tbody) return;
    tbody.innerHTML = '';
    if (!rows || rows.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" class="p-6 text-center text-gray-400">No hay eventos programados</td></tr>';
        return;
    }

    rows.forEach(r => {
        const parseLocalDate = (s) => {
            if (!s) return null;
            const p = s.split(' ');
            if (p.length !== 2) return null;
            const d = new Date(`${p[0]}T${p[1]}`);
            return isNaN(d.getTime()) ? null : d;
        };
        const startDate = parseLocalDate(r.start);
        const endDate = r.end ? parseLocalDate(r.end) : null;
        const now = new Date();
        const start = startDate ? startDate.toLocaleString('es-MX') : '—';
        const end   = endDate   ? endDate.toLocaleString('es-MX')   : '—';

        let status = 'Desconocido', statusLabel = 'bg-gray-100 text-gray-700', statusIcon = 'fa-question-circle';
        if (r.active === 0) { status = 'Cancelado'; statusLabel = 'bg-gray-100 text-gray-500'; statusIcon = 'fa-ban'; }
        else if (!startDate) { status = 'Sin programar'; statusLabel = 'bg-yellow-100 text-yellow-700'; statusIcon = 'fa-exclamation-triangle'; }
        else if (now < startDate) { status = 'Programado'; statusLabel = 'bg-blue-100 text-blue-700'; statusIcon = 'fa-clock'; }
        else if (now >= startDate && (!endDate || now <= endDate)) { status = 'En Curso'; statusLabel = 'bg-orange-100 text-orange-700 animate-pulse'; statusIcon = 'fa-wrench'; }
        else if (endDate && now > endDate) { status = 'Finalizado'; statusLabel = 'bg-green-100 text-green-700'; statusIcon = 'fa-check-circle'; }

        let showCancel = false, showDelete = false;
        if (r.active === 0 || !startDate || (endDate && now > endDate)) { showDelete = true; }
        else if (now < startDate) { showCancel = true; showDelete = true; }
        else if (now >= startDate && (!endDate || now <= endDate)) { showCancel = true; }

        const parts = (r.notas || '').split(' - ');
        const categoria = parts[0] || 'Mantenimiento General';
        const detalles  = parts.slice(1).join(' - ') || '';

        const actionsHtml = `
            <div class="flex justify-center gap-2">
                ${showCancel ? `<button onclick="cancelMaintenance(${r.id})" class="text-blue-500 hover:text-blue-700 p-1 hover:bg-blue-50 rounded transition" title="Cancelar"><i class="fas fa-times-circle"></i></button>` : ''}
                ${showDelete ? `<button onclick="deleteMaintenance(${r.id})" class="text-red-500 hover:text-red-700 p-1 hover:bg-red-50 rounded transition" title="Eliminar"><i class="fas fa-trash"></i></button>` : ''}
            </div>`;

        tbody.innerHTML += `
            <tr class="hover:bg-gray-50 transition">
                <td class="p-4 font-bold text-gray-600">${r.created_by || 'Sistema'}</td>
                <td class="p-4">
                    <div class="font-medium text-gray-900">${categoria}</div>
                    ${detalles ? `<div class="text-xs text-gray-500">${detalles}</div>` : ''}
                </td>
                <td class="p-4">
                    <div class="font-bold text-gray-800">${start}</div>
                    <div class="text-xs text-gray-500">Hasta: ${end}</div>
                </td>
                <td class="p-4 text-gray-500 text-xs italic">${r.notas || 'Sin notas'}</td>
                <td class="p-4 text-center">
                    <span class="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium ${statusLabel}">
                        <i class="fas ${statusIcon}"></i> ${status}
                    </span>
                </td>
                <td class="p-4 text-center">${actionsHtml}</td>
            </tr>`;
    });
}

// --- Reservar Mantenimiento -------------------------
async function reserveMaintenance() {
    const btn = document.getElementById('btnReserve');
    const originalText = btn ? btn.innerHTML : '';
    if (btn) { btn.disabled = true; btn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i> Reservando...'; }

    const categorySelect = document.getElementById('categorySelect');
    const start  = document.getElementById('startInput');
    const end    = document.getElementById('endInput');
    const notes  = document.getElementById('notesInput');

    if (!categorySelect || !categorySelect.value) { showToast('Por favor selecciona una categoría.', 'error'); if (btn) { btn.disabled = false; btn.innerHTML = originalText; } return; }
    if (!start || !start.value.trim()) { showToast('Por favor ingresa fecha y hora de inicio.', 'error'); if (btn) { btn.disabled = false; btn.innerHTML = originalText; } return; }
    if (!end   || !end.value.trim())   { showToast('Por favor ingresa fecha y hora de fin.',    'error'); if (btn) { btn.disabled = false; btn.innerHTML = originalText; } return; }

    const startDate = new Date(start.value);
    const endDate   = new Date(end.value);
    if (endDate <= startDate) { showToast('La fecha/hora de fin debe ser posterior al inicio.', 'error'); if (btn) { btn.disabled = false; btn.innerHTML = originalText; } return; }

    const toLocalStr = (s) => {
        const d = new Date(s);
        return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')} ${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}:00`;
    };

    const catText    = categorySelect.options[categorySelect.selectedIndex].text;
    const notesText  = notes ? notes.value.trim() : '';
    const notasFinal = notesText ? `${catText} - ${notesText}` : catText;

    try {
        const res = await csrfFetch('/api/admin/maintenance', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ active: 1, start: toLocalStr(start.value), end: toLocalStr(end.value), notas: notasFinal })
        });
        const data = await res.json();
        if (data.success) {
            showToast('Mantenimiento programado correctamente.', 'success');
            if (categorySelect) categorySelect.selectedIndex = 0;
            if (notes)  notes.value  = '';
            if (start)  start.value  = '';
            if (end)    end.value    = '';
            loadMaintenanceList();
            checkMaintenanceStatus();
        } else {
            showToast('Error: ' + (data.message || 'No se pudo programar'), 'error');
        }
    } catch (e) { showToast('Error al programar mantenimiento', 'error'); console.error(e); }
    finally { if (btn) { btn.disabled = false; btn.innerHTML = originalText; } }
}

// --- Cancelar / Eliminar Mantenimiento ---
async function cancelMaintenance(id) {
    if (!confirm('¿Confirmar cancelar este evento?')) return;
    try {
        const res = await csrfFetch(`/api/admin/maintenance/${id}`, { method: 'DELETE' });
        const data = await res.json();
        if (data.success) { showToast('Mantenimiento cancelado.', 'success'); loadMaintenanceList(); checkMaintenanceStatus(); }
        else { showToast('Error: ' + (data.message || 'No se pudo cancelar'), 'error'); }
    } catch (e) { showToast('Error de conexión', 'error'); console.error(e); }
}

async function deleteMaintenance(id) {
    if (!confirm('¿Eliminar este evento de mantenimiento?')) return;
    try {
        const res = await csrfFetch(`/api/admin/maintenance/${id}`, {
            method: 'DELETE',
            headers: { 'X-Delete-Force': 'true' }
        });
        const data = await res.json().catch(() => ({ success: false, message: 'Respuesta inválida' }));
        if (res.status === 400) { showToast('Error: ' + (data.message || 'No se puede eliminar'), 'error'); return; }
        if (data.success) { showToast('Evento eliminado.', 'success'); loadMaintenanceList(); checkMaintenanceStatus(); }
        else { showToast('Error: ' + (data.message || 'No se pudo eliminar'), 'error'); }
    } catch (e) { showToast('Error de conexión', 'error'); console.error(e); }
}

// --- Acciones Críticas ----------------------------
function prepareSystemReset() {
    const modal = document.getElementById('deleteModal');
    if (!modal) return;
    const masterInput = document.getElementById('masterKeyInput');
    if (masterInput) masterInput.value = '';
    modal.classList.remove('hidden');
    setTimeout(() => {
        modal.classList.remove('opacity-0');
        const whiteDiv = modal.querySelector('div.bg-white');
        if (whiteDiv) whiteDiv.classList.remove('scale-95');
    }, 10);
}

function closeDeleteModal() {
    const modal = document.getElementById('deleteModal');
    if (!modal) return;
    modal.classList.add('opacity-0');
    const whiteDiv = modal.querySelector('div.bg-white');
    if (whiteDiv) whiteDiv.classList.add('scale-95');
    setTimeout(() => modal.classList.add('hidden'), 300);
}

async function confirmReset() {
    const input = document.getElementById('masterKeyInput');
    const key = input ? input.value.trim() : '';
    if (!key) { showToast('Debes ingresar la contraseña maestra.', 'error'); return; }

    const btn = document.getElementById('confirmResetBtn');
    if (btn) { btn.disabled = true; btn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i> Reiniciando...'; }

    try {
        const res = await csrfFetch('/api/admin/reset', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ master_key: key })
        });
        if (res.status === 403) { showToast('Clave maestra inválida o sin permisos.', 'error'); if (input) input.value = ''; if (btn) { btn.disabled = false; btn.innerHTML = 'Sí, Eliminar Todo'; } return; }
        const data = await res.json();
        if (data.success) { showToast(data.message || 'Sistema reiniciado.', 'success'); closeDeleteModal(); setTimeout(() => location.reload(), 2000); }
        else { showToast('Error: ' + (data.message || 'No fue posible reiniciar'), 'error'); if (input) input.value = ''; if (btn) { btn.disabled = false; btn.innerHTML = 'Sí, Eliminar Todo'; } }
    } catch (e) { showToast('Error de conexión', 'error'); if (btn) { btn.disabled = false; btn.innerHTML = 'Sí, Eliminar Todo'; } }
}

// --- Estado del Servidor ----------------------------
async function loadServerStatus() {
    try {
        const res = await fetch('/api/admin/server-status');
        const data = await res.json();
        if (!data.success) { updateStatusUI('Error', 'bg-red-100 text-red-700', 'Error'); return; }
        updateStatusUI(data.db_status, data.db_status_class, data.last_maintenance_text);
    } catch (e) { updateStatusUI('Error de conexión', 'bg-red-100 text-red-700', '—'); }
}

function updateStatusUI(dbStatus, dbStatusClass, lastText) {
    const dbEl   = document.getElementById('dbStatus');
    const lastEl = document.getElementById('lastMaintenance');
    if (dbEl) {
        dbEl.className = `text-xs px-2 py-1 rounded font-bold ${dbStatusClass}`;
        dbEl.innerHTML = `<i class="fas ${dbStatus === 'Conectada' ? 'fa-check-circle' : 'fa-times-circle'}"></i> ${dbStatus}`;
    }
    if (lastEl) lastEl.textContent = lastText;
}

async function refreshServerStatus() {
    const btn = event.target.closest('button');
    const icon = btn ? btn.querySelector('i') : null;
    if (icon) icon.classList.add('fa-spin');
    await loadServerStatus();
    setTimeout(() => { if (icon) icon.classList.remove('fa-spin'); }, 500);
}

// --- Toggle Nuevo Periodo (Checkbox) ---
function toggleNewPeriodInputMaint() {
    const check = document.getElementById('checkNewPeriodMaint');
    const select = document.getElementById('periodoSelectMaint');
    const inputField = document.getElementById('newPeriodNameMaint');
    if (!check || !select || !inputField) return;

    if (check.checked) {
        select.disabled = true;
        select.classList.add('opacity-50', 'bg-gray-100');
        inputField.classList.remove('hidden');
        inputField.focus();
    } else {
        // Solo habilitar select si mantenimiento está activo
        select.disabled = !_maintenanceIsActive;
        select.classList.remove('opacity-50', 'bg-gray-100');
        inputField.classList.add('hidden');
        inputField.value = '';
    }
}

// --- Chequeo de Estado de Mantenimiento ---
async function checkMaintenanceStatus() {
    try {
        const res = await fetch('/api/admin/check-maintenance');
        const data = await res.json();
        const isActive = data.maintenance_active;
        _maintenanceIsActive = isActive; // Cache global

        const controlIds = ['periodoSelectMaint', 'checkNewPeriodMaint', 'excelInputMaint', 'btnImportData', 'sqlInputMaint', 'btnRestoreBackup', 'btnResetSystem', 'radioAppend', 'radioReplace'];
        controlIds.forEach(id => {
            const el = document.getElementById(id);
            if (!el) return;
            el.disabled = !isActive;
        });

        // Conectar checkbox
        const checkNewPeriod = document.getElementById('checkNewPeriodMaint');
        if (checkNewPeriod) {
            checkNewPeriod.onchange = toggleNewPeriodInputMaint;
        }

        // ==========================================================
        // Actualizar labels de archivo según estado
        // ==========================================================
        const excelLabel = document.getElementById('excelInputLabel');
        const sqlLabel   = document.getElementById('sqlInputLabel');

        if (excelLabel) {
            excelLabel.classList.toggle('cursor-pointer', isActive);
            excelLabel.classList.toggle('cursor-not-allowed', !isActive);
            excelLabel.classList.toggle('opacity-50', !isActive);
            excelLabel.classList.toggle('hover:bg-white', isActive);
            excelLabel.classList.toggle('hover:border-teal-400', isActive);
        }
        if (sqlLabel) {
            sqlLabel.classList.toggle('cursor-pointer', isActive);
            sqlLabel.classList.toggle('cursor-not-allowed', !isActive);
            sqlLabel.classList.toggle('opacity-50', !isActive);
        }

        const fileSpanExcel = document.getElementById('fileNameMaint');
        const fileSpanSQL   = document.getElementById('fileNameSQL');

        // FIX: Cambiar texto según estado - "Sistema bloqueado" vs "Seleccionar archivo..."
        if (fileSpanExcel) {
            const excelInput = document.getElementById('excelInputMaint');
            const hasFile = excelInput && excelInput.files && excelInput.files.length > 0;
            if (!isActive) {
                fileSpanExcel.textContent = 'Sistema bloqueado';
            } else if (!hasFile) {
                fileSpanExcel.textContent = 'Seleccionar archivo Excel...';
            }
        }
        if (fileSpanSQL) {
            const sqlInput = document.getElementById('sqlInputMaint');
            const hasFile = sqlInput && sqlInput.files && sqlInput.files.length > 0;
            if (!isActive) {
                fileSpanSQL.textContent = 'Sistema bloqueado';
            } else if (!hasFile) {
                fileSpanSQL.textContent = 'Seleccionar archivo SQL...';
            }
        }

        if (isActive) {
            const excelInput = document.getElementById('excelInputMaint');
            if (excelInput) {
                excelInput.onchange = () => {
                    const span = document.getElementById('fileNameMaint');
                    if (span && excelInput.files.length > 0) span.textContent = excelInput.files[0].name;
                };
            }
            const sqlInput = document.getElementById('sqlInputMaint');
            if (sqlInput) {
                sqlInput.onchange = () => {
                    const span = document.getElementById('fileNameSQL');
                    if (span && sqlInput.files.length > 0) span.textContent = sqlInput.files[0].name;
                };
            }
        }
    } catch (e) { console.error('Error verificando estado de mantenimiento:', e); }
    setTimeout(checkMaintenanceStatus, 5000);
}

// --- Periodos (Modal Mantenimiento) ---
async function loadPeriodsForMaintenance() {
    const select = document.getElementById('periodoSelectMaint');
    if (!select) return;
    try {
        const res = await fetch('/api/encuestas');
        const data = await res.json();
        select.innerHTML = '<option value="">-- Seleccionar --</option>';
        data.forEach(p => { select.innerHTML += `<option value="${p.id_encuesta}">${p.nombre}</option>`; });
        if (data.length > 0) select.selectedIndex = 1;
    } catch (e) { select.innerHTML = '<option value="">Error</option>'; }
}

function openPeriodsModalMaint() {
    loadPeriodsTableMaint();
    const modal = document.getElementById('periodsModalMaint');
    if (!modal) return;
    modal.classList.remove('hidden');
    setTimeout(() => {
        modal.classList.remove('opacity-0');
        modal.querySelector('div.bg-white').classList.remove('scale-95');
    }, 10);
}

function closePeriodsModalMaint() {
    const modal = document.getElementById('periodsModalMaint');
    if (!modal) return;
    modal.classList.add('opacity-0');
    modal.querySelector('div.bg-white').classList.add('scale-95');
    setTimeout(() => modal.classList.add('hidden'), 300);
    loadPeriodsForMaintenance();
}

async function loadPeriodsTableMaint() {
    const tbody = document.getElementById('periodsTableBodyMaint');
    if (!tbody) return;
    try {
        const res = await fetch('/api/encuestas');
        const data = await res.json();
        tbody.innerHTML = '';
        if (data.length === 0) {
            tbody.innerHTML = '<tr><td colspan="3" class="p-4 text-center text-gray-400">No hay periodos</td></tr>';
            return;
        }
        data.forEach(p => {
            // ==========================================================
            // Solo mostrar botón eliminar si mantenimiento activo
            // ==========================================================
            const deleteBtn = _maintenanceIsActive
                ? `<button onclick="deletePeriodMaint(${p.id_encuesta})"
                    class="text-red-400 hover:text-red-600 p-2 rounded-full hover:bg-red-50 transition" title="Eliminar">
                    <i class="fas fa-trash-alt"></i>
                  </button>`
                : `<span class="text-gray-300 text-xs italic" title="Requiere mantenimiento activo">
                    <i class="fas fa-lock"></i>
                  </span>`;

            tbody.innerHTML += `
                <tr class="hover:bg-gray-50 border-b border-gray-100">
                    <td class="p-3 font-mono text-xs text-gray-500 text-center">${p.id_encuesta}</td>
                    <td class="p-3">
                        <input type="text" id="maint-period-name-${p.id_encuesta}" value="${p.nombre}"
                            class="w-full bg-transparent border-b border-transparent hover:border-gray-300 focus:border-teal-500 focus:bg-white px-2 py-1 outline-none transition text-sm text-gray-700"
                            onchange="updatePeriodNameMaint(${p.id_encuesta})">
                    </td>
                    <td class="p-3 text-center">${deleteBtn}</td>
                </tr>`;
        });
    } catch (e) { tbody.innerHTML = '<tr><td colspan="3" class="p-4 text-center text-red-400">Error cargando</td></tr>'; }
}

async function updatePeriodNameMaint(id) {
    const input = document.getElementById(`maint-period-name-${id}`);
    if (!input) return;
    try {
        const res = await csrfFetch(`/api/encuestas/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ nombre: input.value })
        });
        if (res.ok) { showToast('Periodo actualizado', 'success'); }
        else { showToast('Error actualizando periodo', 'error'); }
    } catch (e) { showToast('Error de conexión', 'error'); }
}

async function deletePeriodMaint(id) {
    // ==========================================================
    // FIX: Bloquear eliminación si no hay mantenimiento activo
    // ==========================================================
    if (!_maintenanceIsActive) {
        showToast('Solo puedes eliminar periodos durante mantenimiento activo.', 'error');
        return;
    }
    if (!confirm('¿Eliminar este periodo y todos sus datos?')) return;
    try {
        const res = await csrfFetch(`/api/encuestas/${id}`, { method: 'DELETE' });
        const data = await res.json();
        if (data.success) { showToast('Periodo eliminado.', 'success'); loadPeriodsTableMaint(); loadPeriodsForMaintenance(); }
        else { showToast('Error: ' + (data.error || 'No se pudo eliminar'), 'error'); }
    } catch (e) { showToast('Error de conexión', 'error'); }
}

// --- Upload Excel (Importar Datos) ---
// ======================================================================
// Endpoint correcto /api/admin/importar, mejor UX con progreso,
// prevención de doble click, campos correctos del FormData
// ======================================================================
async function uploadExcelMaint() {
    const fileInput = document.getElementById('excelInputMaint');
    const file = fileInput ? fileInput.files[0] : null;
    const periodo = document.getElementById('periodoSelectMaint').value;
    const checkNew   = document.getElementById('checkNewPeriodMaint');
    const newPeriodo = document.getElementById('newPeriodNameMaint');
    const isNew = checkNew && checkNew.checked;
    const newNombre = newPeriodo ? newPeriodo.value.trim() : '';

    if (!file) { showToast('Selecciona un archivo Excel primero.', 'error'); return; }
    if (!isNew && !periodo) { showToast('Selecciona un periodo o crea uno nuevo.', 'error'); return; }
    if (isNew && !newNombre) { showToast('Escribe el nombre del nuevo periodo.', 'error'); return; }

    // Leer el modo de importación (Agregar / Reemplazar)
    const importModeRadio = document.querySelector('input[name="importMode"]:checked');
    const importMode = importModeRadio ? importModeRadio.value : 'append';

    // Confirmación extra si el modo es "replace"
    if (importMode === 'replace' && !isNew) {
        const confirmReplace = confirm(
            'Modo REEMPLAZAR seleccionado.\n\n' +
            'Se eliminarán TODOS los empleados y respuestas del periodo seleccionado ' +
            'antes de importar los nuevos datos.\n\n' +
            'Las preguntas (categorías) se conservarán.\n\n' +
            '¿Deseas continuar?'
        );
        if (!confirmReplace) return;
    }

    const formData = new FormData();
    formData.append('file', file);
    formData.append('survey_id', isNew ? '' : periodo);
    formData.append('new_survey_name', isNew ? newNombre : '');
    formData.append('import_mode', importMode);

    const btn = document.getElementById('btnImportData');

    const originalText = btn ? btn.innerHTML : '';
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i> Importando... (esto puede tardar)';
    }

    // Mostrar barra de progreso visual
    showImportProgress(file.name);

    try {
        const res = await csrfFetch('/api/admin/importar', { method: 'POST', body: formData });
        const data = await res.json();

        hideImportProgress();

        if (data.success) {
            showToast('✓ ' + (data.message || 'Datos importados correctamente'), 'success');
            // Limpiar formulario
            fileInput.value = '';
            const fileSpan = document.getElementById('fileNameMaint');
            if (fileSpan) fileSpan.textContent = 'Seleccionar archivo Excel...';
            if (checkNew) { checkNew.checked = false; toggleNewPeriodInputMaint(); }
            loadPeriodsForMaintenance();
        } else {
            showToast('Error: ' + (data.message || data.error || 'Error en importación'), 'error');
        }
    } catch (e) {
        hideImportProgress();
        showToast('Error de conexión al importar', 'error');
        console.error(e);
    } finally {
        if (btn) { btn.disabled = false; btn.innerHTML = originalText; }
    }
}

// --- Barra de progreso para importación ---
function showImportProgress(filename) {
    let bar = document.getElementById('importProgressBar');
    if (bar) bar.remove();

    bar = document.createElement('div');
    bar.id = 'importProgressBar';
    bar.className = 'fixed bottom-20 right-4 z-50 bg-white rounded-xl shadow-2xl border border-teal-200 p-4 w-80';
    bar.innerHTML = `
        <div class="flex items-center gap-3 mb-2">
            <i class="fas fa-file-excel text-green-600 text-xl"></i>
            <div class="flex-1 min-w-0">
                <p class="text-sm font-bold text-gray-800 truncate">${filename}</p>
                <p class="text-xs text-gray-500">Procesando datos...</p>
            </div>
        </div>
        <div class="w-full bg-gray-200 rounded-full h-2">
            <div class="bg-teal-500 h-2 rounded-full animate-pulse" style="width: 100%"></div>
        </div>
        <p class="text-xs text-gray-400 mt-1 text-center">Esto puede tardar según el tamaño del archivo</p>
    `;
    document.body.appendChild(bar);
}

function hideImportProgress() {
    const bar = document.getElementById('importProgressBar');
    if (bar) {
        bar.style.opacity = '0';
        setTimeout(() => bar.remove(), 300);
    }
}

// --- Upload SQL (Restaurar) -------------------------
async function uploadSQLMaint() {
    const file = document.getElementById('sqlInputMaint').files[0];
    if (!file) { showToast('Selecciona un archivo SQL primero.', 'error'); return; }
    if (!confirm('¿Restaurar la base de datos? Esta acción reemplazará TODOS los datos actuales.')) return;

    const formData = new FormData();
    formData.append('file', file);
    const btn = document.getElementById('btnRestoreBackup');
    const originalText = btn ? btn.innerHTML : '';
    if (btn) { btn.disabled = true; btn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i> Restaurando...'; }

    try {
        const res = await csrfFetch('/api/admin/restore', { method: 'POST', body: formData });
        const data = await res.json();
        if (data.success) { showToast('✓ Base de datos restaurada correctamente.', 'success'); setTimeout(() => location.reload(), 2000); }
        else { showToast('Error: ' + (data.message || 'Error en restauración'), 'error'); }
    } catch (e) { showToast('Error de conexión', 'error'); console.error(e); }
    finally { if (btn) { btn.disabled = false; btn.innerHTML = originalText; } }
}

// --- Toast ----------------------------
function showToast(message, type = 'info') {
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        container.className = 'fixed bottom-4 right-4 z-50 flex flex-col gap-2';
        document.body.appendChild(container);
    }
    const colors = { success: 'bg-green-600', error: 'bg-red-600', info: 'bg-blue-600', warning: 'bg-yellow-500' };
    const icons  = { success: 'fa-check-circle', error: 'fa-times-circle', info: 'fa-info-circle', warning: 'fa-exclamation-triangle' };
    const toast  = document.createElement('div');
    toast.className = `${colors[type] || 'bg-gray-700'} text-white px-5 py-3 rounded-lg shadow-lg flex items-center gap-3 transition-all duration-300 max-w-sm`;
    toast.innerHTML = `<i class="fas ${icons[type] || 'fa-bell'} text-lg"></i><p class="text-sm font-medium">${message}</p>`;
    container.appendChild(toast);
    setTimeout(() => { toast.style.opacity = '0'; setTimeout(() => toast.remove(), 300); }, 4000);
}

// --- Alias global ----------------------------
window.startMaintenanceAction = reserveMaintenance;