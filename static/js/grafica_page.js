// static/js/grafica_page.js
let chartInstance = null;
let allAreasData = [];
let allCategoriesData = [];
let selectedChartCategories = [];
let chartRequestId = 0; // ID para cancelar llamadas obsoletas

document.addEventListener('DOMContentLoaded', async () => {
    initChart();                   // 1° Crear el chart ANTES de todo
    await loadGlobalPeriods();     // 2° Cargar periodos
    await loadChartOptions();      // 3° Cargar opciones + generar gráfico
});

async function loadGlobalPeriods() {
    const select = document.getElementById('globalPeriodo');
    if(!select) return;

    try {
        const res = await fetch('/api/encuestas');
        const data = await res.json();
        
        select.innerHTML = '';
        data.forEach(p => {
            select.innerHTML += `<option value="${p.id_encuesta}">${p.nombre}</option>`;
        });

        if(data.length > 0) {
            select.value = data[0].id_encuesta; 
        }
        
        // NO agregar addEventListener aquí - el HTML ya tiene onchange="loadChartOptions()"
        
    } catch(e) {
        console.error("Error cargando periodos:", e);
    }
}

async function loadChartOptions() {
    try {
        const periodoId = document.getElementById('globalPeriodo')?.value;
        const url = periodoId 
            ? `/api/analitica/options?periodo_id=${periodoId}`
            : '/api/analitica/options';
        
        const res = await fetch(url);
        const data = await res.json();

        const selPlanta = document.getElementById('chartPlanta');
        if (selPlanta) {
          selPlanta.innerHTML = '<option value="">-- Seleccionar Centro de Trabajo --</option>';
          data.plantas.forEach((p) => {
            selPlanta.innerHTML += `<option value="${p.nombre}" data-id="${p.id_planta}">${p.nombre}</option>`;
          });
        }

        allAreasData = data.areas;
        allCategoriesData = data.categorias;
        
        // Siempre resetear al cambiar periodo - mostrar TODAS las categorías por defecto
        selectedChartCategories = [];
        
        await generarGrafico();

    } catch (error) {
        console.error("Error opciones:", error);
    }
}

function filterChartAreas() {
    const selPlanta = document.getElementById('chartPlanta');
    const selArea = document.getElementById('chartArea');
    const selectedOption = selPlanta.options[selPlanta.selectedIndex];
    const plantaId = selectedOption.getAttribute('data-id');

    selArea.innerHTML = '<option value="">Áreas (Todas)</option>';
    selArea.disabled = true;

    if (plantaId) {
        const areas = allAreasData.filter(a => a.id_planta == plantaId);
        areas.forEach(a => {
            selArea.innerHTML += `<option value="${a.nombre}">${a.nombre}</option>`;
        });
        selArea.disabled = false;
    }
}

function initChart() {
    const canvas = document.getElementById('chartCondiciones');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    
    const dataLabelPlugin = {
        id: 'dataLabelPlugin',
        afterDatasetsDraw(chart) {
            const { ctx } = chart;
            chart.data.datasets.forEach((dataset, i) => {
                const meta = chart.getDatasetMeta(i);
                meta.data.forEach((bar, index) => {
                    const value = dataset.data[index];
                    if (value !== null && value !== undefined) {
                        ctx.font = 'bold 12px Inter';
                        ctx.fillStyle = '#1e306e'; 
                        ctx.textAlign = 'left';
                        ctx.textBaseline = 'middle';
                        ctx.fillText(value + '%', bar.x + 8, bar.y);
                    }
                });
            });
        }
    };

    chartInstance = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: [],
            datasets: [{
                label: 'Satisfacción',
                data: [],
                backgroundColor: [], 
                borderRadius: 6,
                barPercentage: 0.65,
                categoryPercentage: 0.8
            }]
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            plugins: { 
                legend: { display: false }, 
                tooltip: { 
                    enabled: true,
                    backgroundColor: '#1e306e', 
                    titleColor: '#ffffff',
                    bodyColor: '#e0f2fe',
                    padding: 12,
                    cornerRadius: 8,
                    titleFont: { family: 'Inter', size: 14, weight: 'bold' },
                    bodyFont: { family: 'Inter', size: 13 },
                    callbacks: {
                        label: function(context) {
                            return context.raw + '% de Satisfacción';
                        }
                    }
                } 
            },
            layout: { padding: { right: 60, left: 0 } },
            scales: {
                x: { 
                    min: 0, 
                    max: 100,
                    grid: { color: '#e5e7eb', borderDash: [5, 5] }, 
                    ticks: { 
                        font: { family: 'Inter', weight: '600' }, 
                        color: '#64748b',
                        callback: function(value) { return value + "%" }
                    }
                },
                y: { 
                    grid: { display: false }, 
                    ticks: { 
                        font: { family: 'Inter', weight: '600', size: 12 }, 
                        color: '#1e306e', 
                        autoSkip: false 
                    } 
                }
            }
        },
        plugins: [dataLabelPlugin]
    });
}

async function generarGrafico() {
    if (!chartInstance) {
        console.warn("Chart no inicializado aún");
        return;
    }
    const thisRequestId = ++chartRequestId;

    try {
        const modal = document.getElementById('chartModal');
        if (modal && !modal.classList.contains('hidden')) {
            const checkboxes = document.querySelectorAll('#chartCategoriesContainer .chart-category-checkbox:checked');
            selectedChartCategories = Array.from(checkboxes).map(cb => cb.value);
            closeChartModal();
        }

        const elCatPrincipal = document.getElementById('chartCategoria');
        const catPrincipal = elCatPrincipal ? elCatPrincipal.value : "";
        const titleEl = document.getElementById('chartTitle');

        let catsToSend = [];
        if (catPrincipal !== "") {
            catsToSend = [catPrincipal];
            if(titleEl) titleEl.textContent = catPrincipal;
        } else {
            if (selectedChartCategories.length === 0) {
                // Enviar vacío para que el backend NO filtre por categoría
                // (mostrará todas, incluso las que tienen categoria NULL)
                catsToSend = [];
                if(titleEl) titleEl.textContent = "Resultados Generales (Todas las categorías)";
            } else {
                catsToSend = selectedChartCategories;
                if(titleEl) titleEl.textContent = "Resultados Seleccionados";
            }
        }

        const periodoVal = document.getElementById('globalPeriodo') ? document.getElementById('globalPeriodo').value : "";

        const filters = {
            periodo: periodoVal,
            genero: document.getElementById('chartGenero') ? document.getElementById('chartGenero').value : "",
            planta: document.getElementById('chartPlanta') ? document.getElementById('chartPlanta').value : "",
            area: document.getElementById('chartArea') ? document.getElementById('chartArea').value : "",
            antiguedad: document.getElementById('chartAntiguedad') ? document.getElementById('chartAntiguedad').value : "",
            categories: catsToSend 
        };

        const res = await csrfFetch('/api/grafico/generar', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(filters)
        });
        
        const data = await res.json();
        // Si hubo otro cambio de periodo mientras esperábamos, ignorar esta respuesta
        if (thisRequestId !== chartRequestId) return;
        
        if (data.error) { 
            console.error(data.error); 
            return; 
        }

        // --- Filtrar labels nulos (periodos sin categorías asignadas) ---
        const cleanLabels = [];
        const cleanData = [];
        for (let i = 0; i < data.labels.length; i++) {
            if (data.labels[i] !== null && data.labels[i] !== undefined && data.labels[i] !== '') {
                cleanLabels.push(data.labels[i]);
                cleanData.push(data.data[i]);
            }
        }

        // Si no hay datos, limpiar el chart completamente
        if (cleanLabels.length === 0) {
            chartInstance.data.labels = [];
            chartInstance.data.datasets[0].data = [];
            chartInstance.data.datasets[0].backgroundColor = [];
            chartInstance.update();
            if(titleEl) titleEl.textContent = "Sin categorías asignadas para este periodo";
            return;
        }

        const ctx = chartInstance.ctx;
        const backgrounds = cleanData.map(val => {
            if (val >= 78.5) return createGradient(ctx, '#1e306e', '#2563eb'); 
            if (val >= 57.1) return createGradient(ctx, '#3b82f6', '#60a5fa'); 
            return createGradient(ctx, '#64748b', '#94a3b8'); 
        });

        chartInstance.data.labels = cleanLabels;
        chartInstance.data.datasets[0].data = cleanData;
        chartInstance.data.datasets[0].backgroundColor = backgrounds;
        
        const container = document.querySelector('.relative.h-80');
        if (container) {
            const height = Math.max(350, cleanLabels.length * 45); 
            container.style.height = `${height}px`;
        }
       
        chartInstance.resize();
        chartInstance.update();

    } catch (error) {
        console.error("Error graficando:", error);
    }
}

function createGradient(ctx, colorStart, colorEnd) {
    const gradient = ctx.createLinearGradient(0, 0, 400, 0);
    gradient.addColorStop(0, colorStart);
    gradient.addColorStop(1, colorEnd);
    return gradient;
}

const modalElement = document.getElementById('chartModal'); 

function openChartModal() {
    if(!modalElement) return;
    modalElement.classList.remove('hidden');
    renderChartModal(); 
    const content = modalElement.querySelector('div');
    setTimeout(() => { 
        content.classList.remove('scale-95', 'opacity-0'); 
        content.classList.add('scale-100', 'opacity-100'); 
    }, 10);
}

function closeChartModal() {
    if(!modalElement) return;
    const content = modalElement.querySelector('div');
    content.classList.remove('scale-100', 'opacity-100');
    content.classList.add('scale-95', 'opacity-0');
    setTimeout(() => { modalElement.classList.add('hidden'); }, 150);
}

function renderChartModal() {
    const container = document.getElementById('chartCategoriesContainer');
    if(!container) return;
    container.innerHTML = `
        <label class="flex items-center space-x-3 p-3 bg-blue-50 rounded-lg cursor-pointer border border-blue-200 mb-3">
            <input type="checkbox" id="selectAllChart" class="form-checkbox h-5 w-5 text-blue-900 rounded border-gray-300 focus:ring-blue-800">
            <span class="text-blue-700 text-sm font-bold select-none">Seleccionar Todas</span>
        </label>
    `;
    allCategoriesData.forEach(cat => {
        const isChecked = selectedChartCategories.includes(cat) ? 'checked' : '';
        container.innerHTML += `
            <label class="flex items-center space-x-3 p-3 hover:bg-blue-50 rounded-lg cursor-pointer border border-gray-100 hover:border-blue-200 transition-colors">
                <input type="checkbox" value="${cat}" ${isChecked} class="form-checkbox h-5 w-5 text-blue-900 rounded border-gray-300 focus:ring-blue-800 chart-category-checkbox">
                <span class="text-gray-700 text-sm font-medium select-none">${cat}</span>
            </label>
        `;
    });

    const selectAllCheckbox = document.getElementById('selectAllChart');
    const categoryCheckboxes = document.querySelectorAll('.chart-category-checkbox');
    if (selectAllCheckbox) {
        selectAllCheckbox.addEventListener('change', function() {
            categoryCheckboxes.forEach(cb => {
                cb.checked = this.checked;
            });
        });
    }

    categoryCheckboxes.forEach(cb => {
        cb.addEventListener('change', function() {
            const allChecked = Array.from(categoryCheckboxes).every(c => c.checked);
            const noneChecked = Array.from(categoryCheckboxes).every(c => !c.checked);
            if (selectAllCheckbox) {
                selectAllCheckbox.checked = allChecked;
                selectAllCheckbox.indeterminate = !allChecked && !noneChecked;
            }
        });
    });
}

async function descargarReporteWord() {
    const btn = document.querySelector('button[onclick="descargarReporteWord()"]');
    if(btn) btn.innerText = "Generando...";

    const chartImage = chartInstance.toBase64Image();
    const periodoVal = document.getElementById('globalPeriodo').value;
    const selPlanta = document.getElementById('chartPlanta');
    
    let plantaText = "Todas";
    if (selPlanta.selectedIndex !== -1) {
        plantaText = selPlanta.options[selPlanta.selectedIndex].text;
        if(plantaText.includes("--")) plantaText = "Todas";
    }

    const generoVal = document.getElementById('chartGenero').value || "Todos";
    const antiguedadEl = document.getElementById('chartAntiguedad');
    const antiguedadVal = antiguedadEl.options[antiguedadEl.selectedIndex].text;
    const areaEl = document.getElementById('chartArea');
    let areaVal = "Todas";
    if (!areaEl.disabled && areaEl.value !== "") {
        areaVal = areaEl.value;
    }

    const payload = {
        image: chartImage,
        periodo: periodoVal,
        planta: plantaText,
        genero: generoVal,
        antiguedad: antiguedadVal,
        area: areaVal
    };

    try {
        const res = await csrfFetch('/api/reporte/generar', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (res.ok) {
            const blob = await res.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;

            const contentDisposition = res.headers.get('Content-Disposition');
            let filename = `Reporte_${plantaText}.docx`;
            
            if (contentDisposition) {
                const filenameMatch = contentDisposition.match(/filename="?([^"]+)"?/);
                if (filenameMatch && filenameMatch.length === 2) {
                    filename = filenameMatch[1];
                }
            }
            a.download = filename;
            
            document.body.appendChild(a);
            a.click();
            a.remove();
        } else {
            const err = await res.json();
            alert("Error: " + (err.error || "Desconocido"));
        }
    } catch (error) {
        console.error(error);
        alert("Error de conexión.");
    } finally {
        if(btn) btn.innerHTML = '<i class="fas fa-file-word mr-2"></i> Generar Word'; 
    }
}