// static/js/analitica.js
// Requiere: csrf.js cargado ANTES en el template
let allCategories = [];
let selectedCategories = [];
let currentResults = [];
let allAreasData = [];

document.addEventListener("DOMContentLoaded", async () => {
    await loadGlobalPeriods();
    loadOptions();
});

async function loadGlobalPeriods() {
    const select = document.getElementById("globalPeriodo");
    try {
        const res = await fetch("/api/encuestas");
        const data = await res.json();
        select.innerHTML = '<option value="">Todos los tiempos</option>';
        data.forEach(p => { select.innerHTML += `<option value="${p.id_encuesta}">${p.nombre}</option>`; });
        if (data.length > 0) select.value = data[data.length - 1].id_encuesta;
        select.addEventListener('change', async () => { await loadOptions(); });
    } catch (e) { console.error("Error cargando periodos:", e); }
}

async function loadOptions() {
    try {
        const periodoId = document.getElementById("globalPeriodo").value;
        const url = periodoId ? `/api/analitica/options?periodo_id=${periodoId}` : '/api/analitica/options';
        const res = await fetch(url);
        const data = await res.json();

        const selPlanta = document.getElementById("filterPlanta");
        selPlanta.innerHTML = '<option value="">Centros de Trabajo (Todas)</option>';
        data.plantas.forEach(p => { selPlanta.innerHTML += `<option value="${p.nombre}" data-id="${p.id_planta}">${p.nombre}</option>`; });

        const scoreCatSelect = document.getElementById("scoreCategory");
        if (scoreCatSelect) {
            scoreCatSelect.innerHTML = '<option value="">-- Ninguna Categoría --</option>';
            data.categorias.forEach(cat => { scoreCatSelect.innerHTML += `<option value="${cat}">${cat}</option>`; });
        }

        allAreasData = data.areas;
        allCategories = data.categorias;

        if (allCategories.length > 0) {
            selectedCategories = selectedCategories.filter(cat => allCategories.includes(cat));
            if (selectedCategories.length === 0) selectedCategories = allCategories.slice(0, 3);
        } else {
            selectedCategories = [];
        }

        renderCategoriesModal();
        if (currentResults && currentResults.length > 0) renderTable();
    } catch (error) { console.error("Error cargando opciones:", error); }
}

function filterAreasByPlant() {
    const selPlanta = document.getElementById("filterPlanta");
    const selArea = document.getElementById("filterArea");
    selArea.innerHTML = '<option value="">Áreas (Todas)</option>';
    selArea.disabled = true;
    const selectedOption = selPlanta.options[selPlanta.selectedIndex];
    const plantaId = selectedOption.getAttribute("data-id");
    if (!plantaId) { selArea.innerHTML = '<option value="">Selecciona Planta primero</option>'; return; }
    const areasFiltradas = allAreasData.filter(a => a.id_planta == plantaId);
    areasFiltradas.forEach(a => { selArea.innerHTML += `<option value="${a.nombre}">${a.nombre}</option>`; });
    selArea.disabled = false;
}

async function realizarBusqueda(tipoBusqueda) {
    const nominaInput = document.getElementById("filterNomina").value.trim();
    if (tipoBusqueda === "nomina" && nominaInput === "") {
        alert("Por favor, ingresa un número de nómina para buscar.");
        return;
    }

    const isAdvancedActive = document.getElementById("enableScoreFilter").checked;
    const catVal = document.getElementById("scoreCategory").value;
    const opVal = document.getElementById("scoreOperator").value;
    const scoreVal = document.getElementById("scoreValue").value;

    if (isAdvancedActive && (!catVal || !opVal || !scoreVal)) {
        alert("Si activas el filtro por puntuación, debes seleccionar Categoría, Operador y Valor.");
        return;
    }

    const filters = {
        periodo: document.getElementById("globalPeriodo").value,
        nomina: nominaInput,
        genero: document.getElementById("filterGenero").value,
        planta: document.getElementById("filterPlanta").value,
        area: document.getElementById("filterArea").value,
        antiguedad: document.getElementById("filterAntiguedad").value,
        score_category: isAdvancedActive ? catVal : "",
        score_operator: isAdvancedActive ? opVal : "",
        score_value: isAdvancedActive ? scoreVal : "",
    };

    if (isAdvancedActive) {
        selectedCategories = [catVal];
    } else {
        const checkboxes = document.querySelectorAll('#categoriesContainer .category-checkbox:checked');
        selectedCategories = checkboxes.length > 0
            ? Array.from(checkboxes).map(cb => cb.value)
            : allCategories.slice(0, 3);
    }

    const tbody = document.getElementById("resultsTableBody");
    tbody.innerHTML = `<tr><td colspan="10" class="text-center py-10"><div class="loader ease-linear rounded-full border-4 border-t-4 border-gray-200 h-12 w-12 mb-4 mx-auto"></div>Buscando...</td></tr>`;

    try {
        const res = await csrfFetch("/api/analitica/search", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(filters),
        });
        if (!res.ok) throw new Error("Error en servidor");
        const data = await res.json();
        currentResults = data;
        document.getElementById("resultCount").textContent = data.length;
        renderTable();
    } catch (error) {
        tbody.innerHTML = `<tr><td colspan="10" class="text-center py-4 text-red-500 font-bold">Error al obtener datos. Intenta de nuevo.</td></tr>`;
        console.error(error);
    }
}

let respuestasAbiertas = {};
let respuestaId = 0;

function renderTable() {
    const theadRow = document.getElementById("tableHeaderRow");
    const tbody = document.getElementById("resultsTableBody");

    let headersHTML = `
        <th class="px-4 py-4 border-b border-blue-700">Nomina</th>
        <th class="px-4 py-4 border-b border-blue-700">Nombre</th>
        <th class="px-4 py-4 border-b border-blue-700">Género</th>
        <th class="px-4 py-4 border-b border-blue-700">Centro de Trabajo</th>
        <th class="px-4 py-4 border-b border-blue-700">Área</th>`;

    selectedCategories.forEach(cat => {
        headersHTML += `<th class="px-4 py-4 border-b border-blue-700 text-center min-w-[140px] border-l border-blue-600 text-xs uppercase tracking-wide">${cat}</th>`;
    });
    theadRow.innerHTML = headersHTML;

    if (!currentResults || currentResults.length === 0) {
        tbody.innerHTML = `<tr><td colspan="${5 + selectedCategories.length}" class="text-center py-8 text-gray-500">No se encontraron resultados.</td></tr>`;
        return;
    }

    respuestasAbiertas = {};
    respuestaId = 0;
    let rowsHTML = "";

    currentResults.forEach(emp => {
        let row = `
            <tr class="hover:bg-blue-50 transition border-b border-gray-100">
                <td class="px-4 py-3 font-bold text-gray-800">${emp.nomina || "-"}</td>
                <td class="px-4 py-3 font-medium text-gray-900">${emp.nombre} ${emp.apellido_paterno || ""}</td>
                <td class="px-4 py-3 text-gray-600">${emp.genero || "-"}</td>
                <td class="px-4 py-3 text-gray-600">${emp.planta || "-"}</td>
                <td class="px-4 py-3 text-gray-500 text-xs">${emp.area || "-"}</td>`;

        selectedCategories.forEach(cat => {
            const val = emp.scores && emp.scores[cat] !== undefined ? emp.scores[cat] : null;
            let badge = `<span class="text-gray-300 font-light">-</span>`;
            if (val !== null) {
                if (typeof val === "number") {
                    let colorClass = "bg-gray-100 text-gray-800";
                    if (val >= 4.0) colorClass = "bg-green-100 text-green-800 border border-green-200";
                    else if (val >= 3.0) colorClass = "bg-yellow-100 text-yellow-800 border border-yellow-200";
                    else colorClass = "bg-red-100 text-red-800 border border-red-200";
                    badge = `<span class="${colorClass} px-2 py-1 rounded-md font-bold text-xs shadow-sm">${val.toFixed(2)}</span>`;
                } else {
                    respuestaId++;
                    respuestasAbiertas[respuestaId] = { categoria: cat, respuesta: val };
                    badge = `<button onclick="mostrarRespuestaCompleta(${respuestaId})" class="text-teal-700 hover:text-teal-900 font-medium text-xs bg-teal-50 hover:bg-teal-100 px-2 py-1 rounded border border-teal-200 transition cursor-pointer max-w-[120px] truncate block"><i class="fas fa-eye mr-1"></i>Ver</button>`;
                }
            }
            row += `<td class="px-4 py-3 text-center border-l border-gray-200">${badge}</td>`;
        });
        row += `</tr>`;
        rowsHTML += row;
    });
    tbody.innerHTML = rowsHTML;
}

const modal = document.getElementById("categoryModal");

function openCategoryModal() {
    modal.classList.remove("hidden");
    const content = modal.querySelector("div");
    setTimeout(() => { content.classList.remove("scale-95", "opacity-0"); content.classList.add("scale-100", "opacity-100"); }, 10);
}

function closeCategoryModal() {
    const content = modal.querySelector("div");
    content.classList.remove("scale-100", "opacity-100");
    content.classList.add("scale-95", "opacity-0");
    setTimeout(() => { modal.classList.add("hidden"); }, 150);
}

function renderCategoriesModal() {
    const container = document.getElementById("categoriesContainer");
    container.innerHTML = `
        <label class="flex items-center space-x-3 p-3 bg-teal-50 rounded-lg cursor-pointer border border-teal-200 mb-3">
            <input type="checkbox" id="selectAllCategories" class="form-checkbox h-5 w-5 text-teal-900 rounded border-gray-300 focus:ring-teal-800">
            <span class="text-teal-700 text-sm font-bold select-none">Seleccionar Todas</span>
        </label>
    `;
    allCategories.forEach(cat => {
        const isChecked = selectedCategories.includes(cat) ? "checked" : "";
        container.innerHTML += `
            <label class="flex items-center space-x-3 p-3 hover:bg-gray-100 rounded-lg cursor-pointer transition border border-transparent hover:border-gray-200">
                <input type="checkbox" value="${cat}" ${isChecked} class="form-checkbox h-5 w-5 text-teal-600 rounded focus:ring-teal-500 border-gray-300 transition category-checkbox">
                <span class="text-gray-700 text-sm font-medium select-none">${cat}</span>
            </label>`;
    });

    // Event listener para "Seleccionar Todas"
    const selectAllCheckbox = document.getElementById('selectAllCategories');
    const categoryCheckboxes = document.querySelectorAll('.category-checkbox');
    selectAllCheckbox.addEventListener('change', function() {
        categoryCheckboxes.forEach(cb => {
            cb.checked = this.checked;
        });
    });

    // Si algún checkbox individual cambia, actualizar "Seleccionar Todas"
    categoryCheckboxes.forEach(cb => {
        cb.addEventListener('change', function() {
            const allChecked = Array.from(categoryCheckboxes).every(c => c.checked);
            const noneChecked = Array.from(categoryCheckboxes).every(c => !c.checked);
            selectAllCheckbox.checked = allChecked;
            selectAllCheckbox.indeterminate = !allChecked && !noneChecked;
        });
    });
}

function applyCategories() {
    const checkboxes = document.querySelectorAll('#categoriesContainer .category-checkbox:checked');
    selectedCategories = Array.from(checkboxes).map(cb => cb.value);
    renderTable();
    closeCategoryModal();
}

function toggleScoreFilter() {
    const isChecked = document.getElementById("enableScoreFilter").checked;
    const container = document.getElementById("scoreInputsContainer");
    const box = document.getElementById("advancedFilterBox");
    if (isChecked) {
        container.classList.remove("opacity-50", "pointer-events-none");
        box.classList.remove("bg-blue-50", "border-blue-200");
        box.classList.add("bg-teal-50", "border-teal-200");
    } else {
        container.classList.add("opacity-50", "pointer-events-none");
        box.classList.add("bg-blue-50", "border-blue-200");
        box.classList.remove("bg-teal-50", "border-teal-200");
        document.getElementById("scoreCategory").value = "";
        document.getElementById("scoreOperator").value = "";
        document.getElementById("scoreValue").value = "";
    }
}

async function descargarExcelAnalitico() {
    const btn = document.querySelector('button[onclick="descargarExcelAnalitico()"]');
    const originalContent = btn.innerHTML;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Generando...';
    btn.disabled = true;
    btn.classList.add('opacity-75', 'cursor-not-allowed');

    const filters = {
        periodo: document.getElementById("globalPeriodo").value,
        nomina: document.getElementById("filterNomina").value.trim(),
        genero: document.getElementById("filterGenero").value,
        planta: document.getElementById("filterPlanta").value,
        area: document.getElementById("filterArea").value,
        antiguedad: document.getElementById("filterAntiguedad").value
    };

    try {
        const res = await csrfFetch('/api/analitica/excel', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(filters)
        });
        if (res.ok) {
            const blob = await res.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            const cd = res.headers.get('Content-Disposition');
            let filename = 'Analitica_Canels.xlsx';
            if (cd) { const m = cd.match(/filename="?([^"]+)"?/); if (m && m[1]) filename = m[1]; }
            a.download = filename;
            document.body.appendChild(a); a.click(); a.remove();
        } else {
            const err = await res.json();
            alert("Error: " + (err.error || "No se pudo generar el Excel"));
        }
    } catch (error) { console.error(error); alert("Error de conexión al generar Excel."); }
    finally {
        btn.innerHTML = originalContent;
        btn.disabled = false;
        btn.classList.remove('opacity-75', 'cursor-not-allowed');
    }
}

function mostrarRespuestaCompleta(id) {
    const datos = respuestasAbiertas[id];
    if (!datos) { alert("Error: No se pudo encontrar la respuesta."); return; }
    const { categoria, respuesta } = datos;
    const modalEl = document.createElement('div');
    modalEl.className = 'fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50 backdrop-blur-sm';
    modalEl.id = `modal-respuesta-${id}`;
    modalEl.innerHTML = `
        <div class="bg-white rounded-xl shadow-2xl p-6 w-full max-w-2xl mx-4">
            <div class="flex justify-between items-center mb-4">
                <h3 class="text-xl font-bold text-gray-800"><i class="fas fa-comment text-teal-600 mr-2"></i>${categoria}</h3>
                <button onclick="document.getElementById('modal-respuesta-${id}').remove()" class="text-gray-400 hover:text-red-500 text-2xl"><i class="fas fa-times"></i></button>
            </div>
            <div class="bg-teal-50 border-l-4 border-teal-500 p-4 rounded-lg mb-4 max-h-96 overflow-y-auto">
                <p class="text-gray-800 text-sm leading-relaxed whitespace-pre-wrap break-words">${respuesta || 'Sin respuesta'}</p>
            </div>
            <div class="flex justify-end gap-3">
                <button onclick="document.getElementById('modal-respuesta-${id}').remove()" class="px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 font-bold">Cerrar</button>
                <button id="btn-copiar-${id}" onclick="copiarRespuesta(${id})" class="px-4 py-2 bg-teal-600 text-white rounded-lg hover:bg-teal-700 font-bold flex items-center gap-2"><i class="fas fa-copy"></i> Copiar</button>
            </div>
        </div>`;
    document.body.appendChild(modalEl);
}

function copiarRespuesta(id) {
    const datos = respuestasAbiertas[id];
    if (!datos) { alert("Error: No se pudo encontrar la respuesta."); return; }
    const btnCopiar = document.getElementById(`btn-copiar-${id}`);
    const textarea = document.createElement('textarea');
    textarea.value = datos.respuesta;
    textarea.style.position = 'fixed'; textarea.style.opacity = '0';
    document.body.appendChild(textarea);
    try {
        textarea.select(); textarea.setSelectionRange(0, 99999);
        document.execCommand('copy');
        const originalHTML = btnCopiar.innerHTML;
        btnCopiar.innerHTML = '<i class="fas fa-check text-green-200"></i> ¡Copiado!';
        btnCopiar.classList.replace('bg-teal-600', 'bg-green-600');
        setTimeout(() => { btnCopiar.innerHTML = originalHTML; btnCopiar.classList.replace('bg-green-600', 'bg-teal-600'); }, 2000);
    } catch (error) { alert('Error: No se pudo copiar el texto.'); }
    finally { document.body.removeChild(textarea); }
}