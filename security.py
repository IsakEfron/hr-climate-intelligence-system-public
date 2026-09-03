# security.py
# Módulo centralizado de seguridad para CANELS

import re
import html
import logging
from functools import wraps
from flask import request, jsonify, session, g
from flask_wtf.csrf import CSRFProtect, CSRFError
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_limiter.errors import RateLimitExceeded

# --- Instancias Globales ---
csrf = CSRFProtect()
limiter = Limiter(
    key_func=get_remote_address,
    # ======================================================================
    # Los límites anteriores (200/day, 50/hour) eran demasiado
    # restrictivos para una app con múltiples endpoints de polling
    # (check-maintenance cada 5s, notifications cada 30s, etc).
    # Con 50/hour el límite se agota en ~2 minutos de uso normal.
    # ======================================================================
    default_limits=["5000 per day", "500 per hour"],
    storage_uri="memory://"
)

security_logger = logging.getLogger("canels.security")

# --- Inicialización ---
def init_security(app):
    csrf.init_app(app)
    limiter.init_app(app)

    app.config.setdefault("SESSION_COOKIE_HTTPONLY", True)
    app.config.setdefault("SESSION_COOKIE_SECURE", not app.debug)
    app.config.setdefault("SESSION_COOKIE_SAMESITE", "Lax")

    @app.errorhandler(CSRFError)
    def handle_csrf_error(e):
        security_logger.warning(
            "CSRF error | ip=%s | path=%s | msg=%s",
            request.remote_addr, request.path, e.description
        )
        if request.is_json or request.path.startswith("/api/"):
            return jsonify({"success": False, "error": "Token CSRF inválido o expirado."}), 400
        return (
            "<h2>Error CSRF</h2><p>Token inválido. "
            "<a href='/'>Volver al inicio</a></p>",
            400,
        )
    @app.errorhandler(RateLimitExceeded)
    def handle_rate_limit_exceeded(e):
        return jsonify({
            'success': False,
            'message': str(e.description)   # usa el error_message= del decorador
        }), 429

    @app.after_request
    def set_security_headers(response):
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers.pop('X-Powered-By', None)
        response.headers.pop('Server', None)

        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' "
            "https://cdn.tailwindcss.com "
            "https://cdnjs.cloudflare.com "
            "https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' "
            "https://cdnjs.cloudflare.com "
            "https://fonts.googleapis.com; "
            "font-src 'self' "
            "https://fonts.gstatic.com "
            "https://cdnjs.cloudflare.com; "
            "img-src 'self' data:; "
            "connect-src 'self' https://cdn.jsdelivr.net;"
        )

        if not app.debug:
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )
        return response

    security_logger.info("Módulo de seguridad CANELS inicializado correctamente.")
    return app


# --- Rate Limiting ---
def limit_login(f):
    @wraps(f)
    @limiter.limit("5 per minute", error_message="Demasiados intentos. Espera 1 minuto.")
    def decorated(*args, **kwargs):
        return f(*args, **kwargs)
    return decorated


def limit_api(f):
    @wraps(f)
    @limiter.limit("30 per minute")
    def decorated(*args, **kwargs):
        return f(*args, **kwargs)
    return decorated


# --- Sanitización ---
_DANGEROUS_PATTERNS = re.compile(
    r"(<script[\s\S]*?>[\s\S]*?</script>|"
    r"javascript\s*:|"
    r"on\w+\s*=|"
    r"<\s*iframe|"
    r"<\s*object|"
    r"<\s*embed|"
    r"union\s+select|"
    r"--\s*$|"
    r";\s*drop\s+table)",
    re.IGNORECASE,
)


def sanitize_input(value: str, max_length: int = 500) -> str:
    if not isinstance(value, str):
        value = str(value)
    value = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", value)
    if _DANGEROUS_PATTERNS.search(value):
        raise ValueError("Input contiene contenido no permitido.")
    value = html.escape(value, quote=True)
    return value[:max_length]


def sanitize_dict(data: dict, field_limits: dict = None) -> dict:
    field_limits = field_limits or {}
    sanitized = {}
    for key, value in data.items():
        if isinstance(value, str):
            limit = field_limits.get(key, 500)
            sanitized[key] = sanitize_input(value, max_length=limit)
        else:
            sanitized[key] = value
    return sanitized


# --- Logging ---
def log_login_attempt(username: str, success: bool, db_conn=None):
    status = "EXITOSO" if success else "FALLIDO"
    ip = request.remote_addr
    ua = request.headers.get("User-Agent", "desconocido")[:200]
    security_logger.info("LOGIN %s | usuario=%s | ip=%s | ua=%s", status, username, ip, ua)

    if db_conn:
        try:
            cursor = db_conn.cursor()
            cursor.execute(
                "INSERT INTO auditoria (usuario, accion, detalle, ip_address, fecha) "
                "VALUES (%s, %s, %s, %s, NOW())",
                (username, f"LOGIN_{status}", f"IP: {ip} | UA: {ua[:100]}", ip),
            )
            db_conn.commit()
        except Exception as exc:
            security_logger.error("Error al guardar auditoría: %s", exc)
        finally:
            cursor.close()


def log_security_event(event: str, detail: str, user: str = "anónimo"):
    security_logger.warning(
        "SECURITY_EVENT | evento=%s | usuario=%s | ip=%s | detalle=%s",
        event, user, request.remote_addr, detail
    )


def configure_logging(app):
    log_level = logging.DEBUG if app.debug else logging.INFO
    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    ch = logging.StreamHandler()
    ch.setFormatter(formatter)

    try:
        fh = logging.FileHandler("logs/security.log", encoding="utf-8")
        fh.setFormatter(formatter)
        fh.setLevel(logging.WARNING)
        security_logger.addHandler(fh)
    except OSError:
        pass

    security_logger.addHandler(ch)
    security_logger.setLevel(log_level)
    app.logger.addHandler(ch)
    app.logger.setLevel(log_level)