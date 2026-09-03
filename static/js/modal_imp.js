// static/js/modal_imp.js
// ====================================================================
// FIX: La versión anterior tenía recursión infinita porque
//      uploadExcel() verificaba window.uploadExcel que era ella misma.
//      Ahora solo delega a MaintenanceCore directamente.
// ====================================================================

async function uploadExcel() {
    // Delegar a la implementación centralizada si está disponible
    if (window.MaintenanceCore && typeof window.MaintenanceCore.uploadExcel === 'function') {
        return await window.MaintenanceCore.uploadExcel();
    }

    // Fallback mínimo: informar al usuario
    alert('Función de importación no disponible en esta página.');
}
