// grafica_dashboard.js
let chartSatisfaccionInstance = null;
let chartDistribucionInstance = null;
let chartHistoricoInstance = null;

document.addEventListener('DOMContentLoaded', async function() {
    await loadGlobalPeriods(); 
    loadDashboardData();       
    cargarGraficoHistorico();
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
        if(data.length > 0) select.value = data[0].id_encuesta; 
    } catch(e) { console.error(e); }
}

async function loadDashboardData() {
    const select = document.getElementById('globalPeriodo');
    const periodId = select ? select.value : '';
    
    try {
        const response = await fetch(`/api/dashboard?periodo_id=${periodId}`);
        const data = await response.json();

        // KPIs
        animateValue("kpi-plantas", 0, data.kpis.plantas, 1000);
        animateValue("kpi-empleados", 0, data.kpis.empleados, 1500);
        animateValue("kpi-areas", 0, data.kpis.areas, 1000);
        const kpiSat = document.getElementById('kpi-satisfaccion');
        const kpiSatPorcentaje = document.getElementById('kpi-satisfaccion-porcentaje');
        if(kpiSat) {
            kpiSat.textContent = parseFloat(data.kpis.satisfaccion).toFixed(2);
            if(kpiSatPorcentaje && data.kpis.satisfaccion_porcentaje) {
                kpiSatPorcentaje.textContent = `(${parseFloat(data.kpis.satisfaccion_porcentaje).toFixed(2)}%)`;
            }
        }

        // Población por planta
        if (data.poblacion_plantas) {
            renderPoblacionPlanta(data.poblacion_plantas);
        }

        Chart.defaults.font.family = 'Inter';
        Chart.defaults.color = '#64748b';

        // --- Plugin: Etiquetas encima de barras ---
        const barLabelPlugin = {
            id: 'barLabelPlugin',
            afterDatasetsDraw(chart) {
                const { ctx } = chart;
                chart.data.datasets.forEach((dataset, i) => {
                    const meta = chart.getDatasetMeta(i);
                    meta.data.forEach((bar, index) => {
                        const value = dataset.data[index];
                        if (value !== null && value !== undefined) {
                            ctx.save();
                            ctx.font = 'bold 11px Inter';
                            ctx.fillStyle = '#1e306e';
                            ctx.textAlign = 'center';
                            ctx.textBaseline = 'bottom';
                            // Promedio arriba
                            ctx.fillText(value.toFixed(2), bar.x, bar.y - 18);
                            // Porcentaje abajo
                            const porcentaje = ((value / 7) * 100).toFixed(2) + '%';
                            ctx.fillText(porcentaje, bar.x, bar.y - 6);
                            ctx.restore();
                        }
                    });
                });
            }
        };

        // --- Plugin: Total en centro de dona ---
        const doughnutCenterPlugin = {
            id: 'doughnutCenterText',
            beforeDraw(chart) {
                if (chart.config.type !== 'doughnut') return;
                const { ctx, width, height } = chart;
                const dataset = chart.data.datasets[0];
                if (!dataset || !dataset.data) return;
                const total = dataset.data.reduce((sum, val) => sum + (val || 0), 0);
                ctx.save();
                ctx.font = 'bold 28px Inter';
                ctx.fillStyle = '#1e306e';
                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                const centerX = (chart.chartArea.left + chart.chartArea.right) / 2;
                const centerY = (chart.chartArea.top + chart.chartArea.bottom) / 2;
                ctx.fillText(total.toLocaleString(), centerX, centerY - 10);
                ctx.font = '12px Inter';
                ctx.fillStyle = '#64748b';
                ctx.fillText('Total', centerX, centerY + 16);
                ctx.restore();
            }
        };

        // --- GRÁFICA DE BARRAS ---
        const ctxBar = document.getElementById("chartSatisfaccion").getContext("2d");
        if (chartSatisfaccionInstance) chartSatisfaccionInstance.destroy();
        const existingBar = Chart.getChart("chartSatisfaccion");
        if(existingBar) existingBar.destroy();

        chartSatisfaccionInstance = new Chart(ctxBar, {
            type: "bar",
            data: {
                labels: data.graficas.barras.map(item => item.nombre),
                datasets: [{
                    label: "Promedio",
                    data: data.graficas.barras.map(item => item.promedio),
                    backgroundColor: '#1e306e', 
                    borderRadius: 6,
                    barPercentage: 0.5,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                layout: { padding: { top: 25 } },
                plugins: { 
                    legend: { display: false },
                    tooltip: {
                        backgroundColor: '#1e306e',
                        titleColor: '#fff',
                        bodyColor: '#e0f2fe',
                        padding: 12,
                        borderRadius: 8,
                        callbacks: {
                            label: function(context) {
                                const promedio = context.raw.toFixed(2);
                                const porcentaje = ((context.raw / 7) * 100).toFixed(2) + '%';
                                return [`Promedio: ${promedio}`, `Porcentaje: ${porcentaje}`];
                            }
                        }
                    }   
                },
                scales: {
                    y: { beginAtZero: true, max: 7, grid: { borderDash: [5, 5], color: '#e2e8f0' } },
                    x: { grid: { display: false } }
                }
            },
            plugins: [barLabelPlugin]
        });

        // --- GRÁFICA DE DONA ---
        const ctxPie = document.getElementById("chartDistribucion").getContext("2d");
        if (chartDistribucionInstance) chartDistribucionInstance.destroy();
        const existingPie = Chart.getChart("chartDistribucion");
        if(existingPie) existingPie.destroy();

        chartDistribucionInstance = new Chart(ctxPie, {
            type: "doughnut",
            data: {
                labels: data.graficas.pastel.map(item => item.nombre),
                datasets: [{
                    data: data.graficas.pastel.map(item => item.total),
                    backgroundColor: ["#1e306e", "#2563eb", "#3b82f6", "#60a5fa", "#93c5fd", "#bfdbfe"],
                    borderWidth: 0,
                    hoverOffset: 4
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '65%',
                plugins: {
                    legend: { position: "right", labels: { usePointStyle: true } },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                const pct = ((context.raw / total) * 100).toFixed(1);
                                return `${context.label}: ${context.raw} (${pct}%)`;
                            }
                        }
                    }
                }
            },
            plugins: [doughnutCenterPlugin]
        });

    } catch (error) {
        console.error("Error cargando dashboard:", error);
    }
}

// --- Población por planta (nuevo panel) ---
function renderPoblacionPlanta(plantas) {
    const container = document.getElementById('poblacionPlantaGrid');
    if (!container) return;
    
    if (!plantas || plantas.length === 0) {
        container.innerHTML = '<p class="text-gray-400 text-sm text-center col-span-full py-4">Sin datos de población registrados para este periodo.</p>';
        return;
    }

    const colors = ['bg-blue-900', 'bg-blue-700', 'bg-blue-600', 'bg-indigo-600', 'bg-indigo-500', 'bg-purple-600'];
    const icons = ['fa-industry', 'fa-warehouse', 'fa-building', 'fa-star', 'fa-crown', 'fa-bolt'];
    
    container.innerHTML = plantas.map((p, i) => `
        <div class="flex items-center gap-3 bg-white rounded-xl p-4 shadow-sm border border-gray-100 hover:shadow-md transition">
            <div class="${colors[i % colors.length]} text-white rounded-lg p-3 flex items-center justify-center w-11 h-11">
                <i class="fas ${icons[i % icons.length]} text-sm"></i>
            </div>
            <div class="flex-1 min-w-0">
                <p class="text-xs text-gray-500 font-semibold uppercase tracking-wide truncate">${p.nombre}</p>
                <div class="flex items-baseline gap-2">
                    <span class="text-xl font-bold text-gray-800">${p.num_poblacion != null ? p.num_poblacion.toLocaleString() : '—'}</span>
                    <span class="text-xs text-gray-400">/ población</span>
                </div>
                <p class="text-xs text-gray-500">${p.empleados_encuestados || 0} encuestados</p>
            </div>
        </div>
    `).join('');
}

function animateValue(id, start, end, duration) {
    const obj = document.getElementById(id);
    if (!obj) return;
    let startTimestamp = null;
    const step = (timestamp) => {
        if (!startTimestamp) startTimestamp = timestamp;
        const progress = Math.min((timestamp - startTimestamp) / duration, 1);
        obj.innerHTML = Math.floor(progress * (end - start) + start);
        if (progress < 1) window.requestAnimationFrame(step);
        else obj.innerHTML = end;
    };
    window.requestAnimationFrame(step);
}

// --- Gráfico Histórico con etiquetas de puntos ---
async function cargarGraficoHistorico() {
    const ctx = document.getElementById('historicalChart');
    if (!ctx) return;

    try {
        const res = await fetch('/api/grafico/historico');
        const data = await res.json();

        // Plugin: etiquetas en cada punto de la línea
        const linePointLabelPlugin = {
            id: 'linePointLabel',
            afterDatasetsDraw(chart) {
                const { ctx } = chart;
                chart.data.datasets.forEach((dataset, i) => {
                    const meta = chart.getDatasetMeta(i);
                    meta.data.forEach((point, index) => {
                        const value = dataset.data[index];
                        if (value !== null && value !== undefined) {
                            ctx.save();
                            ctx.font = 'bold 11px Inter';
                            ctx.fillStyle = '#1e306e';
                            ctx.textAlign = 'center';
                            ctx.textBaseline = 'bottom';
                            ctx.fillText(value + '%', point.x, point.y - 12);
                            ctx.restore();
                        }
                    });
                });
            }
        };

        if (chartHistoricoInstance) chartHistoricoInstance.destroy();
        const existing = Chart.getChart("historicalChart");
        if (existing) existing.destroy();

        chartHistoricoInstance = new Chart(ctx, {
            type: 'line',
            data: {
                labels: data.labels,
                datasets: [{
                    label: 'Satisfacción Global (%)',
                    data: data.data,
                    borderColor: '#1E306E',
                    backgroundColor: (context) => {
                        const ct = context.chart.ctx;
                        const gradient = ct.createLinearGradient(0, 0, 0, 300);
                        gradient.addColorStop(0, 'rgba(30, 48, 110, 0.2)');
                        gradient.addColorStop(1, 'rgba(30, 48, 110, 0)');
                        return gradient;
                    },
                    borderWidth: 3,
                    pointBackgroundColor: '#FFFFFF',
                    pointBorderColor: '#EAB308',
                    pointBorderWidth: 2,
                    pointRadius: 6,
                    pointHoverRadius: 8,
                    fill: true,
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                layout: { padding: { top: 25 } },
                plugins: {
                    legend: { display: true, position: 'top', align: 'end' },
                    tooltip: {
                        mode: 'index',
                        intersect: false,
                        backgroundColor: '#1e306e',
                        titleColor: '#fff',
                        bodyColor: '#e0f2fe',
                        padding: 12,
                        borderRadius: 8,
                        callbacks: {
                            label: function(context) {
                                const porcentaje = context.raw;
                                const raw = data.raw_data ? data.raw_data[context.dataIndex] : null;
                                if(raw) return `Promedio: ${raw.toFixed(4)} (${porcentaje}%)`;
                                return `${porcentaje}% de Satisfacción`;
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true, max: 100,
                        grid: { borderDash: [5, 5], color: '#f3f4f6' },
                        ticks: { callback: function(value) { return value + "%" } }
                    },
                    x: { grid: { display: false } }
                },
                interaction: { mode: 'nearest', axis: 'x', intersect: false }
            },
            plugins: [linePointLabelPlugin]
        });

    } catch (error) {
        console.error("Error cargando histórico:", error);
    }
}

// --- Descargar gráfico como PNG ---
function downloadChart(canvasId, filename) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    
    // Crear canvas temporal con fondo blanco
    const tempCanvas = document.createElement('canvas');
    tempCanvas.width = canvas.width;
    tempCanvas.height = canvas.height;
    const tempCtx = tempCanvas.getContext('2d');
    tempCtx.fillStyle = '#FFFFFF';
    tempCtx.fillRect(0, 0, tempCanvas.width, tempCanvas.height);
    tempCtx.drawImage(canvas, 0, 0);
    
    const link = document.createElement('a');
    link.download = filename || 'grafico.png';
    link.href = tempCanvas.toDataURL('image/png');
    link.click();
}