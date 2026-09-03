// static/js/csrf.js
// ---------------------------------------------------------------
// Utilidad global de CSRF - incluir ANTES de cualquier otro JS
// en todos los templates que hagan fetch POST / PUT / DELETE.
// ---------------------------------------------------------------

/**
 * Obtiene el token CSRF del meta tag del documento.
 * Requiere que el <head> contenga:
 *   <meta name="csrf-token" content="{{ csrf_token() }}">
 */
function getCsrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    if (!meta) {
        console.warn('[CSRF] meta[name="csrf-token"] no encontrado. Verifica el template.');
        return '';
    }
    return meta.getAttribute('content');
}

/**
 * Wrapper de fetch que agrega el header X-CSRFToken
 * automáticamente en métodos que lo requieren (POST, PUT, DELETE, PATCH).
 * Úsado igual que fetch() normal.
 *
 * Ejemplo:
 *   const res = await csrfFetch('/api/admin/reset', {
 *       method: 'POST',
 *       headers: { 'Content-Type': 'application/json' },
 *       body: JSON.stringify({ key: '...' })
 *   });
 */
async function csrfFetch(url, options = {}) {
    const method = (options.method || 'GET').toUpperCase();
    const needsCsrf = ['POST', 'PUT', 'DELETE', 'PATCH'].includes(method);

    if (needsCsrf) {
        options.headers = options.headers || {};
        options.headers['X-CSRFToken'] = getCsrfToken();
    }

    return fetch(url, options);
}