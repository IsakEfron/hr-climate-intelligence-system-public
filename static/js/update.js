// static/js/update.js
// Requiere: csrf.js cargado ANTES en el template
let editingId = null;
let deleteTargetId = null;

document.addEventListener('DOMContentLoaded', () => {
    loadGlobalPeriods();
});

async function loadGlobalPeriods() {
    const select = document.getElementById("globalPeriodo");
    try {
        const res = await fetch('/api/encuestas');
        const data = await res.json();
        select.innerHTML = '<option value="">Todos los periodos</option>';
        data.forEach(p => { select.innerHTML += `<option value="${p.id_encuesta}">${p.nombre}</option>`; });
        if (data.length > 0) {
            select.value = data[data.length - 1].id_encuesta;
            fetchQuestions();
            loadPoblacion();
        }
    } catch (e) { console.error("Error cargando periodos:", e); }
}

async function fetchQuestions() {
    const tbody = document.getElementById('questionsTableBody');
    const periodoId = document.getElementById('globalPeriodo').value;
    const url = periodoId ? `/api/preguntas?periodo_id=${periodoId}` : '/api/preguntas';
    try {
        const res = await fetch(url);
        const questions = await res.json();
        tbody.innerHTML = '';
        if (questions.length === 0) {
            tbody.innerHTML = `<tr><td colspan="6" class="text-center p-8 text-gray-400">No hay preguntas registradas en este periodo.</td></tr>`;
            return;
        }
        questions.forEach(q => {
            const tipoColor = q.tipo === 'escala' ? 'bg-blue-100 text-blue-700' : 'bg-purple-100 text-purple-700';
            tbody.innerHTML += `
                <tr class="border-b hover:bg-blue-50 transition">
                    <td class="p-4 text-center font-bold text-gray-600">${q.numero}</td>
                    <td class="p-4">${q.texto}</td>
                    <td class="p-4">
                        <span class="inline-block px-2 py-1 rounded text-xs font-bold ${tipoColor}">${q.tipo}</span>
                    </td>
                    <td class="p-4 text-gray-600 text-xs">${q.categoria || '-'}</td>
                    <td class="p-4 text-center text-xs text-gray-500">${q.periodo_nombre || '-'}</td>
                    <td class="p-4 text-center">
                        <button onclick="openEditModal(${q.id_pregunta}, ${q.numero}, '${q.tipo}', '${(q.categoria || '').replace(/'/g, "\\'")}', '${(q.texto || '').replace(/'/g, "\\'").replace(/\n/g, "\\n")}')"
                            class="bg-blue-500 hover:bg-blue-600 text-white font-bold py-1 px-3 rounded text-xs transition">
                            <i class="fas fa-edit"></i>
                        </button>
                        <button onclick="openDeleteModal(${q.id_pregunta})"
                            class="bg-red-500 hover:bg-red-600 text-white font-bold py-1 px-3 rounded text-xs transition mt-2">
                            <i class="fas fa-trash"></i>
                        </button>
                    </td>
                </tr>`;
        });
    } catch (e) { console.error('Error:', e); tbody.innerHTML = '<tr><td colspan="6" class="text-center p-4 text-red-500">Error al cargar preguntas.</td></tr>'; }
}

function openAddModal() {
    editingId = null;
    document.getElementById('modalTitle').textContent = 'Agregar Pregunta';
    document.getElementById('questionForm').reset();
    document.getElementById('formModal').classList.remove('hidden');
}

function openEditModal(id, numero, tipo, categoria, texto) {
    editingId = id;
    document.getElementById('modalTitle').textContent = 'Editar Pregunta';
    document.getElementById('inputId').value = numero;
    document.getElementById('inputType').value = tipo;
    document.getElementById('inputCategory').value = categoria;
    document.getElementById('inputText').value = texto.replace(/\\n/g, '\n');
    document.getElementById('formModal').classList.remove('hidden');
}

function closeFormModal() { document.getElementById('formModal').classList.add('hidden'); }

async function handleFormSubmit(e) {
    e.preventDefault();
    const periodoId = document.getElementById('globalPeriodo').value;
    const payload = {
        numero: parseFloat(document.getElementById('inputId').value),
        tipo: document.getElementById('inputType').value,
        categoria: document.getElementById('inputCategory').value,
        texto: document.getElementById('inputText').value,
        periodo_id: periodoId ? parseInt(periodoId) : null
    };

    const url = editingId ? `/api/preguntas/${editingId}` : '/api/preguntas';
    const method = editingId ? 'PUT' : 'POST';

    try {
        const res = await csrfFetch(url, {
            method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (data.success) { closeFormModal(); fetchQuestions(); }
        else { alert('Error: ' + (data.error || 'No se pudo guardar')); }
    } catch (err) { console.error(err); alert('Error de conexión'); }
}

function openDeleteModal(id) {
    deleteTargetId = id;
    document.getElementById('deleteModal').classList.remove('hidden');
}

function closeDeleteModal() {
    deleteTargetId = null;
    document.getElementById('deleteModal').classList.add('hidden');
}

async function confirmDelete() {
    if (!deleteTargetId) return;
    try {
        const res = await csrfFetch(`/api/preguntas/${deleteTargetId}`, { method: 'DELETE' });
        const data = await res.json();
        if (data.success) { closeDeleteModal(); fetchQuestions(); }
        else { alert('Error: ' + (data.error || 'No se pudo eliminar')); }
    } catch (err) { console.error(err); alert('Error de conexión'); }
}

// =====================================================================
// SECCIÓN: Gestión de Población por Planta
// =====================================================================

async function loadPoblacion() {
    const tbody = document.getElementById('poblacionTableBody');
    if (!tbody) return;
    const periodoId = document.getElementById('globalPeriodo').value;
    if (!periodoId) {
        tbody.innerHTML = '<tr><td colspan="4" class="text-center p-6 text-gray-400">Selecciona un periodo para ver la población.</td></tr>';
        return;
    }

    try {
        const res = await fetch(`/api/poblacion?periodo_id=${periodoId}`);
        const data = await res.json();
        tbody.innerHTML = '';

        if (!data || data.length === 0) {
            tbody.innerHTML = '<tr><td colspan="4" class="text-center p-6 text-gray-400">No hay datos de población. Usa el formulario para agregar.</td></tr>';
            return;
        }

        data.forEach(p => {
            tbody.innerHTML += `
                <tr class="border-b hover:bg-indigo-50 transition" id="pob-row-${p.id_poblacion}">
                    <td class="p-3 font-bold text-gray-700">${p.planta_nombre}</td>
                    <td class="p-3 text-center">
                        <input type="number" id="pob-val-${p.id_poblacion}" value="${p.num_poblacion}" min="0"
                            class="w-24 text-center bg-transparent border-b border-transparent hover:border-gray-300 focus:border-indigo-500 focus:bg-white px-2 py-1 outline-none transition text-sm font-bold text-gray-800"
                            onchange="updatePoblacion(${p.id_poblacion})">
                    </td>
                    <td class="p-3 text-center text-sm text-gray-500">${p.empleados_encuestados || 0}</td>
                    <td class="p-3 text-center">
                        <button onclick="deletePoblacion(${p.id_poblacion})"
                            class="text-red-400 hover:text-red-600 p-1.5 rounded-full hover:bg-red-50 transition" title="Eliminar">
                            <i class="fas fa-trash-alt text-xs"></i>
                        </button>
                    </td>
                </tr>`;
        });
    } catch (e) {
        console.error('Error cargando población:', e);
        tbody.innerHTML = '<tr><td colspan="4" class="text-center p-4 text-red-500">Error al cargar datos.</td></tr>';
    }
}

async function addPoblacion() {
    const periodoId = document.getElementById('globalPeriodo').value;
    const plantaId = document.getElementById('poblacionPlantaSelect').value;
    const numPob = document.getElementById('poblacionNumInput').value;

    if (!periodoId) { alert('Selecciona un periodo primero.'); return; }
    if (!plantaId) { alert('Selecciona una planta.'); return; }
    if (!numPob || parseInt(numPob) < 0) { alert('Ingresa un número válido de población.'); return; }

    try {
        const res = await csrfFetch('/api/poblacion', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                id_encuesta: parseInt(periodoId),
                id_planta: parseInt(plantaId),
                num_poblacion: parseInt(numPob)
            })
        });
        const data = await res.json();
        if (data.success) {
            document.getElementById('poblacionNumInput').value = '';
            document.getElementById('poblacionPlantaSelect').selectedIndex = 0;
            loadPoblacion();
        } else {
            alert('Error: ' + (data.error || data.message || 'No se pudo guardar'));
        }
    } catch (e) { console.error(e); alert('Error de conexión'); }
}

async function updatePoblacion(id) {
    const input = document.getElementById(`pob-val-${id}`);
    if (!input) return;
    const val = parseInt(input.value);
    if (isNaN(val) || val < 0) { alert('Valor inválido'); return; }

    try {
        const res = await csrfFetch(`/api/poblacion/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ num_poblacion: val })
        });
        const data = await res.json();
        if (data.success) {
            input.classList.add('text-green-600');
            setTimeout(() => input.classList.remove('text-green-600'), 1000);
        } else {
            alert('Error: ' + (data.error || 'No se pudo actualizar'));
        }
    } catch (e) { console.error(e); alert('Error de conexión'); }
}

async function deletePoblacion(id) {
    if (!confirm('¿Eliminar este registro de población?')) return;
    try {
        const res = await csrfFetch(`/api/poblacion/${id}`, { method: 'DELETE' });
        const data = await res.json();
        if (data.success) { loadPoblacion(); }
        else { alert('Error: ' + (data.error || 'No se pudo eliminar')); }
    } catch (e) { console.error(e); alert('Error de conexión'); }
}

async function loadPlantasForPoblacion() {
    const select = document.getElementById('poblacionPlantaSelect');
    if (!select) return;
    try {
        const res = await fetch('/api/analitica/options');
        const data = await res.json();
        select.innerHTML = '<option value="">-- Seleccionar Centro de Trabajo --</option>';
        data.plantas.forEach(p => {
            select.innerHTML += `<option value="${p.id_planta}">${p.nombre}</option>`;
        });
    } catch (e) { console.error(e); }
}

// Cargar plantas al iniciar
document.addEventListener('DOMContentLoaded', () => {
    loadPlantasForPoblacion();
});

// =====================================================================
// IMPORTAR CATEGORÍAS DESDE ARCHIVO JSON
// =====================================================================

async function importarCategoriasJSON(input) {
    const file = input.files[0];
    if (!file) return;

    const periodoId = document.getElementById('globalPeriodo').value;
    if (!periodoId) {
        alert('Selecciona un periodo antes de importar categorías.');
        input.value = '';
        return;
    }

    const status = document.getElementById('jsonImportStatus');

    // Leer el archivo
    let categorias;
    try {
        const text = await file.text();
        categorias = JSON.parse(text);
    } catch (e) {
        alert('El archivo no es un JSON válido.');
        input.value = '';
        return;
    }

    // Validar estructura mínima
    if (typeof categorias !== 'object' || Array.isArray(categorias)) {
        alert('El JSON debe tener el formato { "numero": "categoria", ... }');
        input.value = '';
        return;
    }

    status.textContent = 'Importando...';
    status.classList.remove('hidden', 'text-red-500', 'text-green-600');
    status.classList.add('text-gray-500');

    try {
        const res = await csrfFetch('/api/preguntas/importar-categorias', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ periodo_id: parseInt(periodoId), categorias })
        });

        const data = await res.json();

        if (data.success) {
            status.textContent = `/ ${data.actualizadas} categorías aplicadas`;
            status.classList.remove('text-gray-500', 'text-red-500');
            status.classList.add('text-green-600');

            if (data.no_encontradas && data.no_encontradas.length > 0) {
                console.warn('Preguntas no encontradas:', data.no_encontradas);
                status.textContent += ` (${data.no_encontradas.length} sin coincidencia: ${data.no_encontradas.join(', ')})`;
            }

            // Recargar tabla para ver los cambios
            fetchQuestions();
        } else {
            status.textContent = 'X ' + (data.error || 'Error al importar');
            status.classList.remove('text-gray-500', 'text-green-600');
            status.classList.add('text-red-500');
        }
    } catch (e) {
        console.error(e);
        status.textContent = 'X Error de conexión';
        status.classList.add('text-red-500');
    }

    // Limpiar el input para permitir re-subir el mismo archivo
    input.value = '';

    // Ocultar el mensaje después de 5 segundos
    setTimeout(() => status.classList.add('hidden'), 5000);
}