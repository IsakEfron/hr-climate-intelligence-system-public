# app.py
# =================================================================
# CANELS — Sistema de Gestión Psicosocial
# Versión con seguridad completa + documentación Swagger/OpenAPI (Flasgger)
# =================================================================

from flask import (
    Flask, render_template, request, jsonify,
    send_file, send_from_directory, redirect, url_for, session
)
from config import Config
from db import get_db_connection
from datetime import datetime
import os
import hmac
import pandas as pd
import io

from utils.admin_logic import (
    create_backup, restore_backup, reset_data_only,
    process_excel_import, get_or_create_period
)
from utils.report_generator import generate_word_report
from utils.password_security import PasswordValidator, PasswordGenerator, validate_new_password

from flask_login import (
    LoginManager, UserMixin,
    login_user, login_required, logout_user, current_user
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from security import init_security, configure_logging, limiter
from flasgger import Swagger


# =================================================================
# 1. INICIALIZACIÓN DE LA APP
# =================================================================
app = Flask(__name__)
app.config.from_object(Config)

# Seguridad primero - antes de registrar cualquier ruta
init_security(app)
configure_logging(app)

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('logs', exist_ok=True)

# -----------------------------------------------------------------
# Configuración Swagger / OpenAPI
# -----------------------------------------------------------------
app.config['SWAGGER'] = {
    'title': 'API REST — Sistema CANELS',
    'uiversion': 3,
    'description': '''
Sistema de Gestión de Encuestas de Clima Laboral desarrollado con Flask 3.0.

**Autenticación:**  
Todas las rutas protegidas requieren una sesión activa iniciada mediante POST /login.
La sesión se gestiona con Flask-Login y se transmite via cookie HttpOnly.
Cada petición AJAX debe incluir el header `X-CSRFToken` con el token del meta tag.

**Roles disponibles:**
- `superadmin` — Control total del sistema
- `admin` — Gestión de datos, importación y reportes
- `analista` — Visualización avanzada y generación de reportes
- `consulta` — Solo lectura básica

**Base URL local:** `http://<ip-servidor>:5000`  
**Documentación interactiva:** `/apidocs`
    ''',
    'version': '2.0.0',
    'contact': {
        'name': 'Gael Isak Alvarado García',
    },
    'tags': [
        {'name': 'Autenticación',    'description': 'Login, logout y registro de usuarios'},
        {'name': 'Dashboard',        'description': 'KPIs y gráficas del panel principal'},
        {'name': 'Analítica',        'description': 'Búsqueda filtrada y exportación Excel'},
        {'name': 'Gráficos',         'description': 'Generación de gráficos por categoría'},
        {'name': 'Reportes',         'description': 'Reporte ejecutivo en Word'},
        {'name': 'Encuestas',        'description': 'Gestión de periodos de encuesta'},
        {'name': 'Preguntas',        'description': 'CRUD de preguntas por periodo'},
        {'name': 'Población',        'description': 'Registro de población objetivo por planta'},
        {'name': 'Usuarios',         'description': 'Gestión de cuentas (solo superadmin)'},
        {'name': 'Administración',   'description': 'Importación, backup, restore y reset'},
        {'name': 'Mantenimiento',    'description': 'Programación y control de ventanas de mantenimiento'},
        {'name': 'Auditoría',        'description': 'Bitácora de eventos del sistema'},
        {'name': 'Seguridad',        'description': 'Validación y generación de contraseñas'},
    ]
}

swagger = Swagger(app)


# =================================================================
# 2. FLASK-LOGIN
# =================================================================
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login_page'


@login_manager.unauthorized_handler
def unauthorized():
    if request.path.startswith('/api/') or request.is_json:
        return jsonify({
            'error': 'Sesión expirada',
            'redirect': '/login',
            'session_expired': True
        }), 401
    return redirect(url_for('login_page'))


# =================================================================
# 3. MODELO DE USUARIO
# =================================================================
class User(UserMixin):
    def __init__(self, id, username, nombre, rol):
        self.id       = id
        self.username = username
        self.nombre   = nombre
        self.rol      = rol


@login_manager.user_loader
def load_user(user_id):
    """
    Carga el usuario desde la BD de forma segura.
    Devuelve None en cualquier fallo para que Flask-Login maneje
    la sesión inválida sin causar un crash.
    """
    conn = None
    try:
        conn = get_db_connection()
        if not conn:
            return None
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT * FROM usuarios WHERE id_usuario = %s", (user_id,)
        )
        user_data = cursor.fetchone()
        if user_data:
            return User(
                user_data['id_usuario'],
                user_data['username'],
                user_data['nombre_completo'],
                user_data['rol']
            )
        return None
    except Exception as e:
        app.logger.error("Error en load_user: %s", e)
        return None
    finally:
        if conn:
            conn.close()


# =================================================================
# 4. HELPERS INTERNOS
# =================================================================

def _is_superadmin(user) -> bool:
    """Comprueba si el usuario actual es el superadministrador."""
    return (
        hasattr(user, 'rol') and
        user.rol == 'admin' and
        user.username == os.getenv('SUPERADMIN_USERNAME')
    )


def _require_admin():
    """
    Devuelve una respuesta de error si el usuario no es admin.
    Uso: err = _require_admin(); if err: return err
    """
    if not (hasattr(current_user, 'rol') and current_user.rol == 'admin'):
        return jsonify({'success': False, 'error': 'Acceso denegado. Solo administradores.'}), 403
    return None


def registrar_auditoria(accion: str, detalle: str = "", usuario_override: str = None) -> None:
    """
    Registra un evento en la tabla de auditoría.

    Args:
        accion (str): Código del evento (LOGIN, IMPORTAR_DATOS, RESET_SISTEMA, etc.)
        detalle (str): Descripción detallada del evento.
        usuario_override (str): Permite guardar el username real incluso cuando
            el usuario no está autenticado (ej. intentos de login fallidos).
            Prioridad: override -> usuario autenticado -> 'Sistema/Anonimo'.
    """
    conn = None
    try:
        conn = get_db_connection()
        if not conn:
            app.logger.warning("Auditoría: no se pudo conectar a BD para '%s'", accion)
            return
        cursor = conn.cursor()

        if usuario_override:
            usuario = usuario_override
        elif current_user.is_authenticated:
            usuario = current_user.username
        else:
            usuario = 'Sistema/Anonimo'

        ip = request.remote_addr
        cursor.execute(
            "INSERT INTO auditoria (usuario, accion, detalle, ip_origen) VALUES (%s, %s, %s, %s)",
            (usuario, accion, detalle, ip)
        )
        conn.commit()
    except Exception as e:
        app.logger.error("Error registrando auditoría (%s): %s", accion, e)
    finally:
        if conn:
            conn.close()


def is_maintenance_active() -> bool:
    """Devuelve True si hay un evento de mantenimiento activo ahora mismo."""
    conn = None
    try:
        conn = get_db_connection()
        if not conn:
            return False
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT id FROM mantenimiento "
            "WHERE active = 1 "
            "AND (start IS NULL OR start <= NOW()) "
            "AND (end IS NULL OR end >= NOW()) "
            "ORDER BY id DESC LIMIT 1"
        )
        return cursor.fetchone() is not None
    except Exception as e:
        app.logger.error("Error comprobando mantenimiento: %s", e)
        return False
    finally:
        if conn:
            conn.close()


def check_user_lockout(username: str) -> bool:
    """
    Protección de fuerza bruta por usuario (complementa el rate limit por IP).

    Args:
        username (str): Nombre de usuario a verificar.

    Returns:
        bool: True si la cuenta tiene >= 10 intentos fallidos en los últimos 5 minutos.
    """
    conn = None
    try:
        conn = get_db_connection()
        if not conn:
            return False
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT COUNT(*) AS intentos FROM auditoria "
            "WHERE usuario = %s "
            "AND accion = 'LOGIN_FALLIDO' "
            "AND fecha >= NOW() - INTERVAL 5 MINUTE",
            (username,)
        )
        result = cursor.fetchone()
        return result['intentos'] >= 10
    except Exception as e:
        app.logger.error("Error en check_user_lockout: %s", e)
        return False
    finally:
        if conn:
            conn.close()


def ensure_superadmin_exists() -> bool:
    """
    Crea la cuenta superadmin desde las variables de entorno si no existe en la BD.

    Returns:
        bool: True si el superadmin ya existe o fue creado correctamente.
    """
    username = app.config.get('SUPERADMIN_USERNAME')
    password = app.config.get('SUPERADMIN_PASSWORD')
    if not username or not password:
        app.logger.warning("SUPERADMIN_USERNAME o SUPERADMIN_PASSWORD no configurados.")
        return False

    conn = None
    try:
        conn = get_db_connection()
        if not conn:
            return False
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT id_usuario FROM usuarios WHERE username = %s", (username,)
        )
        if cursor.fetchone():
            return True

        pass_hash = generate_password_hash(password)
        cursor.execute(
            "INSERT INTO usuarios (username, password_hash, nombre_completo, rol) "
            "VALUES (%s, %s, %s, %s)",
            (username, pass_hash, 'Super Administrador', 'admin')
        )
        conn.commit()
        print(f"[CANELS] Superadmin '{username}' creado correctamente.")
        return True
    except Exception as e:
        app.logger.error("Error creando superadmin: %s", e)
        return False
    finally:
        if conn:
            conn.close()


# =================================================================
# 5. MIDDLEWARES (before_request)
# =================================================================

# Rutas públicas: no requieren sesión activa
_PUBLIC_ENDPOINTS = {
    'login_page', 'login_post', 'logout', 'static',
    'validate_password_strength', 'generate_secure_password', 'register_user'
}


@app.before_request
def require_login_for_protected_routes():
    """Bloquea acceso a rutas privadas si no hay sesión activa."""
    if request.endpoint and request.endpoint not in _PUBLIC_ENDPOINTS:
        if not current_user.is_authenticated:
            if request.path.startswith('/api/'):
                return jsonify({'error': 'No autenticado', 'redirect': '/login'}), 401
            return redirect(url_for('login_page'))


@app.before_request
def enforce_maintenance_logout():
    """Fuerza logout a usuarios no-admin cuando hay mantenimiento activo."""
    try:
        if request.path.startswith('/static'):
            return
        if request.endpoint in (
            'login_page', 'login_post', 'logout',
            'admin_maintenance_list', 'admin_maintenance', 'check_maintenance_status'
        ):
            return
        if not (hasattr(current_user, 'is_authenticated') and current_user.is_authenticated):
            return
        if current_user.rol == 'admin':
            return
        if is_maintenance_active():
            logout_user()
            return redirect(url_for('login_page'))
    except Exception as e:
        app.logger.error("Error en enforce_maintenance_logout: %s", e)


@app.before_request
def check_session_timeout():
    """Invalida sesiones que superaron el tiempo máximo de inactividad (default 3600 s)."""
    if not (hasattr(current_user, 'is_authenticated') and current_user.is_authenticated):
        return
    if request.path.startswith('/static') or request.endpoint in ('login_page', 'login_post', 'logout'):
        return

    login_time_str = session.get('_login_time')

    def _expire_session():
        logout_user()
        session.clear()
        if request.path.startswith('/api/') or request.is_json:
            return jsonify({'error': 'Sesión expirada', 'session_expired': True, 'redirect': '/login'}), 401
        return redirect(url_for('login_page'))

    if not login_time_str:
        return _expire_session()

    try:
        login_time = datetime.fromisoformat(login_time_str)
        elapsed    = (datetime.now() - login_time).total_seconds()
        timeout    = app.config.get('SESSION_TIMEOUT_SECONDS', 3600)
        if elapsed > timeout:
            return _expire_session()
    except (ValueError, TypeError):
        return _expire_session()


# =================================================================
# 6. RUTAS — PÁGINAS HTML (no documentadas en Swagger)
# =================================================================

@app.route('/')
def root():
    return redirect(url_for('index') if current_user.is_authenticated else url_for('login_page'))


@app.route('/index.html')
@login_required
def index():
    return render_template('index.html', user_rol=current_user.rol)


@app.route('/analitica.html')
@login_required
def analitica():
    return render_template('analitica.html', user_rol=current_user.rol)


@app.route('/grafico.html')
@login_required
def grafico():
    if current_user.rol not in ('admin', 'analista'):
        return render_template('acceso_bloqueado.html', rol=current_user.rol, pagina='Gráficos')
    return render_template('grafico.html', user_rol=current_user.rol)


@app.route('/update.html')
@login_required
def update_page():
    if current_user.rol != 'admin':
        return render_template('acceso_bloqueado.html', rol=current_user.rol, pagina='Gestión de Preguntas')
    return render_template('update.html', user_rol=current_user.rol)


@app.route('/import_export.html')
@login_required
def import_export():
    if current_user.rol != 'admin':
        return render_template('acceso_bloqueado.html', rol=current_user.rol, pagina='Gestión de Datos')
    return render_template('import_export.html', user_rol=current_user.rol)


@app.route('/maintenance.html')
@login_required
def maintenance_page():
    if not _is_superadmin(current_user):
        return render_template('acceso_bloqueado.html', rol=current_user.rol, pagina='Mantenimiento')
    return render_template('maintenance.html', user_rol=current_user.rol)


# =================================================================
# 7. AUTENTICACIÓN
# =================================================================

@app.route('/login', methods=['GET'])
def login_page():
    """
    Página de inicio de sesión (HTML).
    Si el usuario ya tiene sesión activa redirige al dashboard.
    ---
    tags:
      - Autenticación
    responses:
      200:
        description: HTML de la pantalla de login.
      302:
        description: Redirección a /index.html si ya hay sesión activa.
    """
    if current_user.is_authenticated:
        return redirect('/index.html')
    return render_template('login.html')


@app.route('/login', methods=['POST'])
@limiter.limit("5 per minute", error_message="Demasiados intentos. Espera 1 minuto.")
def login_post():
    """
    Procesar inicio de sesión.
    Valida credenciales, comprueba mantenimiento activo y crea la sesión.
    El rate limit se aplica SOLO al POST para no bloquear cargas de página (GET).
    ---
    tags:
      - Autenticación
    consumes:
      - multipart/form-data
    parameters:
      - in: formData
        name: usuario
        type: string
        required: true
        description: Nombre de usuario.
        example: superadmin
      - in: formData
        name: password
        type: string
        required: true
        description: Contraseña del usuario.
        example: "MiPassword2024!"
    responses:
      200:
        description: Login exitoso o credenciales inválidas.
        schema:
          type: object
          properties:
            success:
              type: boolean
              example: true
            redirect:
              type: string
              example: /index.html
            message:
              type: string
              example: "Usuario o contraseña incorrectos."
      400:
        description: Campos vacíos.
        schema:
          type: object
          properties:
            success:
              type: boolean
              example: false
            message:
              type: string
              example: "Credenciales incompletas."
      429:
        description: Cuenta bloqueada por intentos fallidos o rate limit de IP.
        schema:
          type: object
          properties:
            success:
              type: boolean
              example: false
            message:
              type: string
              example: "Cuenta bloqueada temporalmente. Intenta en 5 minutos."
      503:
        description: Base de datos no disponible.
    """
    if current_user.is_authenticated:
        return jsonify({'success': True, 'redirect': '/index.html'})

    username = request.form.get('usuario', '').strip()
    password = request.form.get('password', '')

    if not username or not password:
        return jsonify({'success': False, 'message': 'Credenciales incompletas.'}), 400

    if check_user_lockout(username):
        registrar_auditoria(
            'LOGIN_BLOQUEADO',
            f"Cuenta '{username}' bloqueada temporalmente por exceso de intentos.",
            usuario_override=username
        )
        return jsonify({
            'success': False,
            'message': 'Cuenta bloqueada temporalmente. Intenta en 5 minutos.'
        }), 429

    conn = None
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Error de conexión. Intenta más tarde.'}), 503

        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM usuarios WHERE username = %s", (username,))
        user_data = cursor.fetchone()

    except Exception as e:
        app.logger.error("Error en login_post (BD): %s", e)
        return jsonify({'success': False, 'message': 'Error interno. Intenta más tarde.'}), 500
    finally:
        if conn:
            conn.close()

    # Siempre ejecutamos check_password_hash aunque user_data sea None
    # para evitar timing attacks por enumeración de usuarios.
    dummy_hash     = generate_password_hash("dummy_para_timing")
    stored_hash    = user_data['password_hash'] if user_data else dummy_hash
    credentials_ok = user_data and check_password_hash(stored_hash, password)

    if not credentials_ok:
        registrar_auditoria(
            'LOGIN_FALLIDO',
            f"Intento fallido para usuario '{username}'",
            usuario_override=username
        )
        return jsonify({'success': False, 'message': 'Usuario o contraseña incorrectos.'})

    if is_maintenance_active() and user_data.get('username') != app.config.get('SUPERADMIN_USERNAME'):
        return jsonify({'success': False, 'message': 'Sistema en mantenimiento. Intenta más tarde.'})

    user = User(
        user_data['id_usuario'],
        user_data['username'],
        user_data['nombre_completo'],
        user_data['rol']
    )
    login_user(user)
    session.permanent = True
    session['_login_time'] = datetime.now().isoformat()
    registrar_auditoria('LOGIN', f"Usuario '{username}' inició sesión")

    return jsonify({'success': True, 'redirect': '/index.html'})


@app.route('/logout')
@login_required
def logout():
    """
    Cerrar sesión.
    Invalida la sesión activa y redirige al login. Registra el evento en auditoría.
    ---
    tags:
      - Autenticación
    responses:
      302:
        description: Redirección a /login.
    """
    registrar_auditoria('LOGOUT', f"Usuario '{current_user.username}' cerró sesión")
    logout_user()
    session.clear()
    return redirect('/login')


# =================================================================
# 8. REGISTRO DE USUARIO
# =================================================================

@app.route('/api/register', methods=['POST'])
@limiter.limit("5 per minute")
def register_user():
    """
    Crear nueva cuenta de usuario.
    Requiere el token maestro (MASTER_KEY) para evitar registros no autorizados.
    ---
    tags:
      - Autenticación
    consumes:
      - multipart/form-data
    parameters:
      - in: formData
        name: usuario
        type: string
        required: true
        description: Nombre de usuario único (sin espacios).
        example: analista_rh
      - in: formData
        name: password
        type: string
        required: true
        description: Contraseña (puntuación mínima 60/100 en el validador interno).
        example: "MiPassword2024!"
      - in: formData
        name: nombre
        type: string
        required: true
        description: Nombre completo del usuario.
        example: "María González López"
      - in: formData
        name: rol
        type: string
        required: true
        description: "Rol asignado: consulta | analista | admin."
        enum: [consulta, analista, admin]
        example: analista
      - in: formData
        name: token
        type: string
        required: true
        description: Clave maestra definida en MASTER_KEY del archivo .env.
        example: "clave-maestra-2026"
    responses:
      200:
        description: Usuario creado o error de validación.
        schema:
          type: object
          properties:
            success:
              type: boolean
              example: true
            message:
              type: string
              example: "Usuario creado exitosamente. Ahora inicia sesión."
      400:
        description: Faltan campos obligatorios o rol inválido.
      403:
        description: Token maestro incorrecto.
      503:
        description: Base de datos no disponible.
    """
    if current_user.is_authenticated:
        return jsonify({'success': False, 'message': 'Ya hay una sesión activa.'})

    username = request.form.get('usuario', '').strip()
    password = request.form.get('password', '')
    nombre   = request.form.get('nombre', '').strip()
    rol      = request.form.get('rol', '').strip()
    token    = request.form.get('token', '')

    master_key = app.config.get('MASTER_KEY', '')
    if not token or not hmac.compare_digest(token.encode(), master_key.encode()):
        registrar_auditoria('REGISTRO_TOKEN_INVALIDO', f"Intento con token inválido para '{username}'")
        return jsonify({'success': False, 'message': 'Token de autorización inválido.'}), 403

    if not all([username, password, nombre, rol]):
        return jsonify({'success': False, 'message': 'Faltan datos obligatorios.'}), 400

    roles_permitidos = {'consulta', 'analista', 'admin'}
    if rol not in roles_permitidos:
        return jsonify({'success': False, 'message': 'Rol inválido.'}), 400

    is_valid, validation_message = validate_new_password(password, min_score=60)
    if not is_valid:
        return jsonify({'success': False, 'message': f'Contraseña insegura. {validation_message}'})

    conn = None
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Error de conexión.'}), 503
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT id_usuario FROM usuarios WHERE username = %s", (username,))
        if cursor.fetchone():
            return jsonify({'success': False, 'message': 'Ese nombre de usuario ya existe.'})

        pass_hash = generate_password_hash(password)
        cursor.execute(
            "INSERT INTO usuarios (username, password_hash, nombre_completo, rol) VALUES (%s, %s, %s, %s)",
            (username, pass_hash, nombre, rol)
        )
        conn.commit()

    except Exception as e:
        app.logger.error("Error en register_user: %s", e)
        return jsonify({'success': False, 'message': 'Error interno del servidor.'}), 500
    finally:
        if conn:
            conn.close()

    registrar_auditoria('REGISTRO_USUARIO', f"Usuario '{username}' (rol: {rol}) registrado")
    return jsonify({'success': True, 'message': 'Usuario creado exitosamente. Ahora inicia sesión.'})


# =================================================================
# 9. ENCUESTAS / PERIODOS
# =================================================================

@app.route('/api/encuestas', methods=['GET'])
@login_required
def get_encuestas():
    """
    Listar todos los periodos de encuesta.
    Devuelve la lista completa ordenada del más reciente al más antiguo.
    ---
    tags:
      - Encuestas
    responses:
      200:
        description: Lista de periodos obtenida exitosamente.
        schema:
          type: array
          items:
            type: object
            properties:
              id_encuesta:
                type: integer
                example: 2
              nombre:
                type: string
                example: "Q1 2026"
      500:
        description: Error interno del servidor.
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id_encuesta, nombre FROM encuestas ORDER BY id_encuesta DESC")
        return jsonify(cursor.fetchall())
    except Exception as e:
        app.logger.error("Error en get_encuestas: %s", e)
        return jsonify({'error': 'Error interno'}), 500
    finally:
        if conn:
            conn.close()


@app.route('/api/encuestas/<int:encuesta_id>', methods=['PUT', 'DELETE'])
@login_required
def mod_encuesta(encuesta_id):
    """
    Renombrar (PUT) o eliminar en cascada (DELETE) un periodo de encuesta.
    Requiere rol admin o superadmin.
    ---
    tags:
      - Encuestas
    parameters:
      - in: path
        name: encuesta_id
        type: integer
        required: true
        description: ID del periodo a modificar o eliminar.
        example: 2
      - in: body
        name: body
        description: Nuevo nombre del periodo (solo PUT).
        schema:
          type: object
          properties:
            nombre:
              type: string
              example: "Q1 2026 — Revisado"
    responses:
      200:
        description: Operación completada.
        schema:
          type: object
          properties:
            success:
              type: boolean
              example: true
            message:
              type: string
              example: "Nombre actualizado"
      400:
        description: Nombre vacío (PUT).
      403:
        description: Rol insuficiente.
      500:
        description: Error interno.
    """
    err = _require_admin()
    if err:
        return err

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        if request.method == 'PUT':
            nuevo_nombre = (request.json or {}).get('nombre', '').strip()
            if not nuevo_nombre:
                return jsonify({'success': False, 'error': 'El nombre no puede estar vacío.'}), 400
            cursor.execute(
                "UPDATE encuestas SET nombre = %s WHERE id_encuesta = %s",
                (nuevo_nombre, encuesta_id)
            )
            conn.commit()
            registrar_auditoria('EDITAR_PERIODO', f"Periodo {encuesta_id} renombrado a '{nuevo_nombre}'")
            return jsonify({'success': True, 'message': 'Nombre actualizado'})

        # DELETE — elimina en cascada: respuestas -> empleados sin respuestas -> preguntas -> encuesta
        cursor.execute("""
            DELETE FROM respuestas
            WHERE id_pregunta IN (
                SELECT id_pregunta FROM preguntas WHERE id_encuesta = %s
            )
        """, (encuesta_id,))
        cursor.execute("""
            DELETE FROM empleados
            WHERE id_empleado NOT IN (SELECT DISTINCT id_empleado FROM respuestas WHERE id_empleado IS NOT NULL)
        """)
        cursor.execute("DELETE FROM preguntas WHERE id_encuesta = %s", (encuesta_id,))
        cursor.execute("DELETE FROM encuestas WHERE id_encuesta = %s", (encuesta_id,))
        conn.commit()
        registrar_auditoria('ELIMINAR_PERIODO', f"Periodo {encuesta_id} eliminado")
        return jsonify({'success': True, 'message': 'Periodo eliminado'})

    except Exception as e:
        if conn:
            conn.rollback()
        app.logger.error("Error en mod_encuesta: %s", e)
        return jsonify({'success': False, 'error': 'Error interno'}), 500
    finally:
        if conn:
            conn.close()


# =================================================================
# 10. USUARIOS (solo superadmin)
# =================================================================

@app.route('/api/usuarios', methods=['GET'])
@login_required
def get_usuarios():
    """
    Listar todos los usuarios del sistema.
    Solo accesible por el superadministrador.
    ---
    tags:
      - Usuarios
    responses:
      200:
        description: Lista de usuarios obtenida exitosamente.
        schema:
          type: array
          items:
            type: object
            properties:
              id_usuario:
                type: integer
                example: 1
              usuario:
                type: string
                example: analista_rh
              nombre:
                type: string
                example: "María González"
              rol:
                type: string
                example: analista
              is_superadmin:
                type: boolean
                example: false
      403:
        description: Solo el superadministrador puede acceder a este endpoint.
    """
    if not _is_superadmin(current_user):
        return jsonify({'success': False, 'error': 'Solo el superadministrador puede gestionar usuarios'}), 403

    conn = None
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Error de conexión a BD'}), 500
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT id_usuario, username, nombre_completo, rol FROM usuarios ORDER BY id_usuario DESC"
        )
        data = cursor.fetchall()
        superadmin_username = os.getenv('SUPERADMIN_USERNAME')
        for user in data:
            user['usuario']       = user.pop('username')
            user['nombre']        = user.pop('nombre_completo')
            user['is_superadmin'] = (user['usuario'] == superadmin_username)
        return jsonify(data)
    except Exception as e:
        app.logger.error("Error en get_usuarios: %s", e)
        return jsonify({'success': False, 'error': 'Error interno'}), 500
    finally:
        if conn:
            conn.close()


@app.route('/api/usuarios/<int:user_id>', methods=['DELETE'])
@login_required
def delete_usuario(user_id):
    """
    Eliminar un usuario del sistema.
    Solo el superadministrador puede eliminar cuentas.
    No puede eliminar al propio superadmin ni a la cuenta activa.
    ---
    tags:
      - Usuarios
    parameters:
      - in: path
        name: user_id
        type: integer
        required: true
        description: ID del usuario a eliminar.
        example: 5
    responses:
      200:
        description: Usuario eliminado correctamente.
        schema:
          type: object
          properties:
            success:
              type: boolean
              example: true
            message:
              type: string
              example: "Usuario 'analista_rh' eliminado"
      400:
        description: Intento de eliminar al superadmin o a la cuenta propia.
      403:
        description: Solo el superadministrador puede realizar esta acción.
      404:
        description: Usuario no encontrado.
      500:
        description: Error interno.
    """
    if not _is_superadmin(current_user):
        return jsonify({'success': False, 'error': 'Solo el superadministrador puede eliminar usuarios'}), 403

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT id_usuario, username FROM usuarios WHERE id_usuario = %s", (user_id,)
        )
        usuario = cursor.fetchone()

        if not usuario:
            return jsonify({'success': False, 'error': 'Usuario no encontrado'}), 404
        if usuario['username'] == os.getenv('SUPERADMIN_USERNAME'):
            return jsonify({'success': False, 'error': 'No se puede eliminar al superadministrador'}), 400
        if current_user.id == user_id:
            return jsonify({'success': False, 'error': 'No puedes eliminar tu propia cuenta'}), 400

        cursor.execute("DELETE FROM usuarios WHERE id_usuario = %s", (user_id,))
        conn.commit()
        registrar_auditoria(
            'ELIMINAR_USUARIO',
            f"Usuario '{usuario['username']}' (ID: {user_id}) eliminado por {current_user.username}"
        )
        return jsonify({'success': True, 'message': f"Usuario '{usuario['username']}' eliminado"})

    except Exception as e:
        if conn:
            conn.rollback()
        app.logger.error("Error en delete_usuario: %s", e)
        return jsonify({'success': False, 'error': 'Error interno'}), 500
    finally:
        if conn:
            conn.close()


# =================================================================
# 11. DASHBOARD
# =================================================================

@app.route('/api/dashboard')
@login_required
def dashboard_data():
    """
    Datos completos del panel principal.
    Calcula KPIs, promedios de satisfacción y distribución por planta.
    La relación empleado-periodo se obtiene via respuestas -> preguntas -> encuestas
    (sin columna id_encuesta en la tabla empleados).
    ---
    tags:
      - Dashboard
    parameters:
      - in: query
        name: periodo_id
        type: integer
        required: false
        description: ID del periodo a consultar. Si se omite, devuelve datos globales.
        example: 2
    responses:
      200:
        description: Datos del dashboard obtenidos correctamente.
        schema:
          type: object
          properties:
            kpis:
              type: object
              properties:
                plantas:
                  type: integer
                  example: 6
                  description: Total de plantas registradas.
                empleados:
                  type: integer
                  example: 385
                  description: Colaboradores con respuestas en el periodo seleccionado.
                areas:
                  type: integer
                  example: 9
                  description: Total de áreas registradas.
                satisfaccion:
                  type: number
                  format: float
                  example: 5.08
                  description: Promedio general de satisfacción en escala 1-7.
                satisfaccion_porcentaje:
                  type: number
                  format: float
                  example: 72.57
                  description: Satisfacción convertida a porcentaje (÷7 × 100).
            graficas:
              type: object
              properties:
                barras:
                  type: array
                  items:
                    type: object
                    properties:
                      nombre:
                        type: string
                        example: CANELS
                      promedio:
                        type: number
                        example: 5.04
                pastel:
                  type: array
                  items:
                    type: object
                    properties:
                      nombre:
                        type: string
                        example: CANELS
                      total:
                        type: integer
                        example: 120
            poblacion_plantas:
              type: array
              items:
                type: object
                properties:
                  nombre:
                    type: string
                    example: CANELS
                  num_poblacion:
                    type: integer
                    example: 150
                    nullable: true
                  empleados_encuestados:
                    type: integer
                    example: 120
      500:
        description: Error interno o fallo de conexión a BD.
    """
    periodo_id = request.args.get('periodo_id')
    conn = None
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'DB Error'}), 500
        cursor = conn.cursor(dictionary=True)

        has_periodo = bool(periodo_id and periodo_id not in ('null', ''))
        params_enc  = [periodo_id] if has_periodo else []

        _sub = """
            AND e.id_empleado IN (
                SELECT DISTINCT r2.id_empleado
                FROM respuestas r2
                JOIN preguntas pr2 ON r2.id_pregunta = pr2.id_pregunta
                WHERE pr2.id_encuesta = %s
            )
        """ if has_periodo else ""

        cursor.execute("SELECT COUNT(*) AS t FROM plantas")
        t_plantas = cursor.fetchone()['t']

        cursor.execute(
            f"SELECT COUNT(DISTINCT e.id_empleado) AS t FROM empleados e WHERE 1=1 {_sub}",
            tuple(params_enc)
        )
        t_emp = cursor.fetchone()['t']

        cursor.execute("SELECT COUNT(*) AS t FROM areas")
        t_areas = cursor.fetchone()['t']

        q_prom = f"""
            SELECT e.id_empleado, AVG(r.valor) AS prom_emp
            FROM respuestas r
            JOIN empleados e ON r.id_empleado = e.id_empleado
            WHERE r.valor > 0 {_sub}
            GROUP BY e.id_empleado
            HAVING COUNT(r.id_respuesta) > 0
        """
        cursor.execute(q_prom, tuple(params_enc))
        promedios_emp = cursor.fetchall()

        if promedios_emp:
            prom_general    = sum(float(p['prom_emp']) for p in promedios_emp) / len(promedios_emp)
            prom            = round(prom_general, 10)
            prom_porcentaje = round((prom_general / 7.0) * 100, 10)
        else:
            prom = prom_porcentaje = 0

        q_barras = f"""
            SELECT p.nombre, e.id_empleado, AVG(r.valor) AS prom_emp
            FROM respuestas r
            JOIN empleados e ON r.id_empleado = e.id_empleado
            JOIN plantas p   ON e.id_planta   = p.id_planta
            WHERE r.valor > 0 {_sub}
            GROUP BY p.id_planta, e.id_empleado
            HAVING COUNT(r.id_respuesta) > 0
        """
        cursor.execute(q_barras, tuple(params_enc))
        plantas_dict = {}
        for row in cursor.fetchall():
            plantas_dict.setdefault(row['nombre'], []).append(float(row['prom_emp']))

        barras = sorted(
            [{'nombre': k, 'promedio': round(sum(v) / len(v), 2)} for k, v in plantas_dict.items()],
            key=lambda x: x['nombre']
        )

        q_pastel = f"""
            SELECT p.nombre, COUNT(DISTINCT e.id_empleado) AS total
            FROM empleados e
            JOIN plantas p ON e.id_planta = p.id_planta
            WHERE 1=1 {_sub}
            GROUP BY p.id_planta
        """
        cursor.execute(q_pastel, tuple(params_enc))
        pastel = cursor.fetchall()

        poblacion_plantas = []
        try:
            if has_periodo:
                cursor.execute("""
                    SELECT pl.nombre,
                           pob.num_poblacion,
                           COUNT(DISTINCT emp_sub.id_empleado) AS empleados_encuestados
                    FROM plantas pl
                    LEFT JOIN poblacion pob
                           ON pl.id_planta = pob.id_planta AND pob.id_encuesta = %s
                    LEFT JOIN empleados emp_sub
                           ON pl.id_planta = emp_sub.id_planta
                          AND emp_sub.id_empleado IN (
                              SELECT DISTINCT r2.id_empleado
                              FROM respuestas r2
                              JOIN preguntas pr2 ON r2.id_pregunta = pr2.id_pregunta
                              WHERE pr2.id_encuesta = %s
                          )
                    GROUP BY pl.id_planta, pl.nombre, pob.num_poblacion
                    ORDER BY pl.nombre
                """, (periodo_id, periodo_id))
            else:
                cursor.execute("""
                    SELECT pl.nombre, NULL AS num_poblacion,
                           COUNT(DISTINCT e.id_empleado) AS empleados_encuestados
                    FROM plantas pl
                    LEFT JOIN empleados e ON pl.id_planta = e.id_planta
                    GROUP BY pl.id_planta, pl.nombre ORDER BY pl.nombre
                """)
            poblacion_plantas = cursor.fetchall()
            for pp in poblacion_plantas:
                pp['num_poblacion']         = int(pp['num_poblacion']) if pp.get('num_poblacion') else None
                pp['empleados_encuestados'] = int(pp.get('empleados_encuestados', 0))
        except Exception as e:
            app.logger.warning("Error consultando poblacion: %s", e)

        return jsonify({
            'kpis': {
                'plantas': t_plantas, 'empleados': t_emp,
                'areas': t_areas, 'satisfaccion': prom,
                'satisfaccion_porcentaje': prom_porcentaje
            },
            'graficas': {'barras': barras, 'pastel': pastel},
            'poblacion_plantas': poblacion_plantas
        })

    except Exception as e:
        app.logger.error("Error en dashboard_data: %s", e)
        return jsonify({'error': 'Error interno'}), 500
    finally:
        if conn:
            conn.close()


# =================================================================
# 12. GRÁFICO HISTÓRICO
# =================================================================

@app.route('/api/grafico/historico', methods=['GET'])
@login_required
def grafico_historico():
    """
    Evolución histórica de satisfacción por periodo.
    Calcula el promedio de promedios individuales por encuesta.
    El JOIN se realiza via respuestas -> preguntas -> encuestas.
    ---
    tags:
      - Gráficos
    responses:
      200:
        description: Datos históricos obtenidos correctamente.
        schema:
          type: object
          properties:
            labels:
              type: array
              items:
                type: string
              example: ["Encuesta Inicial", "Q1 2026"]
              description: Nombres de los periodos en orden cronológico.
            data:
              type: array
              items:
                type: number
              example: [68.45, 72.57]
              description: Porcentajes de satisfacción por periodo (÷7 × 100).
            raw_data:
              type: array
              items:
                type: number
              example: [4.79, 5.08]
              description: Promedios en escala 1-7 para referencia.
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT en.id_encuesta, en.nombre AS periodo,
                   r.id_empleado, AVG(r.valor) AS prom_emp
            FROM respuestas r
            JOIN preguntas pr ON r.id_pregunta  = pr.id_pregunta
            JOIN encuestas en ON pr.id_encuesta = en.id_encuesta
            WHERE r.valor > 0
            GROUP BY en.id_encuesta, r.id_empleado
            HAVING COUNT(r.id_respuesta) > 0
            ORDER BY en.id_encuesta ASC
        """)
        periodos_dict = {}
        for row in cursor.fetchall():
            periodos_dict.setdefault(row['periodo'], []).append(float(row['prom_emp']))

        labels, values, values_raw = [], [], []
        for periodo, vals in periodos_dict.items():
            prom = sum(vals) / len(vals)
            labels.append(periodo)
            values.append(round((prom / 7.0) * 100, 2))
            values_raw.append(round(prom, 4))

        return jsonify({'labels': labels, 'data': values, 'raw_data': values_raw})

    except Exception as e:
        app.logger.error("Error en grafico_historico: %s", e)
        return jsonify({'labels': [], 'data': [], 'raw_data': []})
    finally:
        if conn:
            conn.close()


# =================================================================
# 13. ANALÍTICA
# =================================================================

@app.route('/api/analitica/options')
@login_required
def get_analytics_options():
    """
    Opciones disponibles para los filtros de analítica.
    Devuelve plantas, áreas y categorías de preguntas para poblar los selectores.
    ---
    tags:
      - Analítica
    parameters:
      - in: query
        name: periodo_id
        type: integer
        required: false
        description: Si se proporciona, filtra las categorías al periodo indicado.
        example: 2
    responses:
      200:
        description: Opciones obtenidas correctamente.
        schema:
          type: object
          properties:
            plantas:
              type: array
              items:
                type: object
                properties:
                  id_planta:
                    type: integer
                    example: 1
                  nombre:
                    type: string
                    example: CANELS
            areas:
              type: array
              items:
                type: object
                properties:
                  id_area:
                    type: integer
                    example: 1
                  nombre:
                    type: string
                    example: "Recursos Humanos"
                  id_planta:
                    type: integer
                    example: 1
            categorias:
              type: array
              items:
                type: string
              example: ["Condiciones Físicas", "Jefatura Directa", "Liderazgo"]
      500:
        description: Error interno.
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        periodo_id = request.args.get('periodo_id')

        cursor.execute("SELECT id_planta, nombre FROM plantas ORDER BY nombre")
        plantas = cursor.fetchall()
        cursor.execute("SELECT id_area, nombre, id_planta FROM areas ORDER BY nombre")
        areas = cursor.fetchall()

        if periodo_id:
            cursor.execute(
                "SELECT DISTINCT categoria FROM preguntas "
                "WHERE categoria IS NOT NULL AND id_encuesta = %s ORDER BY categoria",
                (periodo_id,)
            )
        else:
            cursor.execute(
                "SELECT DISTINCT categoria FROM preguntas WHERE categoria IS NOT NULL ORDER BY categoria"
            )
        categorias = [r['categoria'] for r in cursor.fetchall()]
        return jsonify({'plantas': plantas, 'areas': areas, 'categorias': categorias})
    except Exception as e:
        app.logger.error("Error en get_analytics_options: %s", e)
        return jsonify({'error': 'Error interno'}), 500
    finally:
        if conn:
            conn.close()


@app.route('/api/analitica/search', methods=['POST'])
@login_required
def search_analytics():
    """
    Búsqueda filtrada de colaboradores y sus puntajes por categoría.
    Los operadores matemáticos se extraen ANTES de sanitize_dict() para
    evitar que el escapado HTML convierta '>' en '&gt;'.
    Los operadores se validan contra una whitelist estricta: { =, >, <, >=, <= }.
    ---
    tags:
      - Analítica
    consumes:
      - application/json
    parameters:
      - in: body
        name: body
        description: Filtros de búsqueda (todos opcionales).
        schema:
          type: object
          properties:
            periodo:
              type: string
              description: ID del periodo de encuesta.
              example: "2"
            nomina:
              type: string
              description: Número de nómina (búsqueda parcial LIKE).
              example: "00123"
            genero:
              type: string
              description: "Masculino | Femenino"
              example: Femenino
            planta:
              type: string
              description: Nombre exacto de la planta.
              example: CANELS
            area:
              type: string
              description: Nombre exacto del área.
              example: Producción
            antiguedad:
              type: string
              description: "1 (< 1 año) | 1-5 (1 a 5 años) | 5+ (> 5 años)"
              example: "5+"
            score_category:
              type: string
              description: Categoría para el filtro de puntuación.
              example: Liderazgo
            score_operator:
              type: string
              description: "Operador de comparación: = | > | < | >= | <="
              example: "<"
            score_value:
              type: string
              description: Valor numérico de comparación (escala 1-7).
              example: "4"
    responses:
      200:
        description: Array de empleados con sus puntajes por categoría.
        schema:
          type: array
          items:
            type: object
            properties:
              id_empleado:
                type: integer
                example: 1
              nomina:
                type: string
                example: "00123"
              nombre:
                type: string
                example: Juan
              apellido_paterno:
                type: string
                example: García
              genero:
                type: string
                example: Masculino
              antiguedad:
                type: string
                example: "3 años"
              planta:
                type: string
                example: CANELS
              area:
                type: string
                example: Producción
              scores:
                type: object
                description: "{ <categoria>: promedio_float | texto_string }"
                example:
                  Liderazgo: 3.8
                  "Condiciones Físicas": 4.5
                  Comentarios: "La comunicación ha mejorado este año."
      400:
        description: Valor de puntuación inválido (no numérico).
      500:
        description: Error interno.
    """
    conn = None
    try:
        from security import sanitize_dict

        raw_json = request.json or {}

        raw_score_op  = str(raw_json.get('score_operator', '')).strip()
        raw_score_cat = str(raw_json.get('score_category', '')).strip()
        raw_score_val = str(raw_json.get('score_value', '')).strip()

        f = sanitize_dict(raw_json, field_limits={'nomina': 20, 'planta': 100})

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        query = """
            SELECT e.id_empleado, e.nomina, e.nombre, e.apellido_paterno,
                   e.genero, e.antiguedad, p.nombre AS planta, a.nombre AS area
            FROM empleados e
            JOIN plantas p ON e.id_planta = p.id_planta
            JOIN areas a   ON e.id_area   = a.id_area
            WHERE 1=1
        """
        params = []

        if f.get('periodo') and str(f['periodo']).strip():
            query += """
                AND e.id_empleado IN (
                    SELECT DISTINCT r2.id_empleado
                    FROM respuestas r2
                    JOIN preguntas pr2 ON r2.id_pregunta = pr2.id_pregunta
                    WHERE pr2.id_encuesta = %s
                )
            """
            params.append(f['periodo'])
        if f.get('nomina') and str(f['nomina']).strip():
            query += " AND e.nomina LIKE %s"; params.append(f"%{f['nomina']}%")
        if f.get('genero'):
            if f['genero'] in ('F', 'Femenino'):
                query += " AND (e.genero LIKE 'Fem%' OR e.genero = 'F')"
            elif f['genero'] in ('M', 'Masculino'):
                query += " AND (e.genero LIKE 'Masc%' OR e.genero = 'M')"
            else:
                query += " AND e.genero = %s"; params.append(f['genero'])
        if f.get('planta'): query += " AND p.nombre = %s"; params.append(f['planta'])
        if f.get('area'):   query += " AND a.nombre = %s"; params.append(f['area'])

        val_ant = f.get('antiguedad')
        if val_ant == '1':     query += " AND e.meses_antiguedad < 12"
        elif val_ant == '1-5': query += " AND e.meses_antiguedad BETWEEN 12 AND 60"
        elif val_ant == '5+':  query += " AND e.meses_antiguedad > 60"

        allowed_ops = {'=', '>', '<', '>=', '<='}
        if raw_score_cat and raw_score_op in allowed_ops and raw_score_val:
            try:
                numeric_val = float(raw_score_val)
            except (ValueError, TypeError):
                return jsonify({'error': 'Valor de puntuación inválido'}), 400
            query += f"""
                AND e.id_empleado IN (
                    SELECT r.id_empleado
                    FROM respuestas r
                    JOIN preguntas pr ON r.id_pregunta = pr.id_pregunta
                    WHERE pr.categoria = %s
                    GROUP BY r.id_empleado
                    HAVING AVG(r.valor) {raw_score_op} %s
                )
            """
            params += [raw_score_cat, numeric_val]

        cursor.execute(query, tuple(params))
        empleados = cursor.fetchall()

        if not empleados:
            return jsonify([])

        ids            = [e['id_empleado'] for e in empleados]
        format_strings = ','.join(['%s'] * len(ids))
        emp_map        = {e['id_empleado']: e for e in empleados}
        for e in empleados:
            e['scores'] = {}

        cursor.execute(
            f"SELECT r.id_empleado, pr.categoria, AVG(r.valor) AS score "
            f"FROM respuestas r JOIN preguntas pr ON r.id_pregunta = pr.id_pregunta "
            f"WHERE r.id_empleado IN ({format_strings}) AND r.valor > 0 "
            f"GROUP BY r.id_empleado, pr.categoria",
            tuple(ids)
        )
        for s in cursor.fetchall():
            if s['score'] is not None:
                emp_map[s['id_empleado']]['scores'][s['categoria']] = round(float(s['score']), 1)

        cursor.execute(
            f"SELECT r.id_empleado, pr.categoria, r.texto "
            f"FROM respuestas r JOIN preguntas pr ON r.id_pregunta = pr.id_pregunta "
            f"WHERE r.id_empleado IN ({format_strings}) AND pr.tipo = 'abierta' AND r.texto IS NOT NULL",
            tuple(ids)
        )
        for t in cursor.fetchall():
            emp_map[t['id_empleado']]['scores'][t['categoria']] = t['texto']

        return jsonify(empleados)

    except Exception as e:
        app.logger.error("Error en search_analytics: %s", e)
        return jsonify({'error': 'Error interno'}), 500
    finally:
        if conn:
            conn.close()


@app.route('/api/analitica/excel', methods=['POST'])
@login_required
def exportar_analitica_excel():
    """
    Exportar analítica filtrada a Excel.
    Genera un archivo .xlsx con dos hojas: Resumen Analítico y Base de Datos (Filtrada).
    El rol consulta no puede exportar y recibe 403.
    ---
    tags:
      - Analítica
    consumes:
      - application/json
    parameters:
      - in: body
        name: body
        description: Filtros para la exportación (mismos que en /api/analitica/search).
        schema:
          type: object
          properties:
            periodo:
              type: string
              example: "2"
            genero:
              type: string
              example: Femenino
            planta:
              type: string
              example: CANELS
            area:
              type: string
              example: Producción
            antiguedad:
              type: string
              example: "5+"
    responses:
      200:
        description: Archivo Excel descargable con dos hojas.
        headers:
          Content-Disposition:
            description: Nombre del archivo generado.
            type: string
            example: 'attachment; filename="Analitica_Canels_20260321_1130.xlsx"'
      400:
        description: No hay colaboradores con los filtros aplicados.
      403:
        description: El rol Consulta no puede exportar datos.
      500:
        description: Error interno.
    """
    if hasattr(current_user, 'rol') and current_user.rol == 'consulta':
        return jsonify({'success': False, 'error': 'Acceso denegado. El rol Consulta no puede exportar datos.'}), 403

    conn = None
    try:
        f      = request.json or {}
        conn   = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        query_base = """
            SELECT e.nomina, e.nombre, e.genero, e.antiguedad,
                   p.nombre AS planta, a.nombre AS area, e.id_empleado, e.meses_antiguedad
            FROM empleados e
            JOIN plantas p ON e.id_planta = p.id_planta
            JOIN areas a   ON e.id_area   = a.id_area
            WHERE 1=1
        """
        params = []
        if f.get('periodo'):
            query_base += """
                AND e.id_empleado IN (
                    SELECT DISTINCT r2.id_empleado
                    FROM respuestas r2
                    JOIN preguntas pr2 ON r2.id_pregunta = pr2.id_pregunta
                    WHERE pr2.id_encuesta = %s
                )
            """
            params.append(f['periodo'])
        if f.get('nomina'):  query_base += " AND e.nomina LIKE %s";   params.append(f"%{f['nomina']}%")
        if f.get('genero'):  query_base += " AND e.genero = %s";      params.append(f['genero'])
        if f.get('planta'):  query_base += " AND p.nombre = %s";      params.append(f['planta'])
        if f.get('area'):    query_base += " AND a.nombre = %s";      params.append(f['area'])

        val_ant = f.get('antiguedad')
        if val_ant == '1':     query_base += " AND e.meses_antiguedad < 12"
        elif val_ant == '1-5': query_base += " AND e.meses_antiguedad BETWEEN 12 AND 60"
        elif val_ant == '5+':  query_base += " AND e.meses_antiguedad > 60"

        cursor.execute(query_base, tuple(params))
        empleados = cursor.fetchall()
        if not empleados:
            return jsonify({'error': 'No hay datos con estos filtros'}), 400

        df_emp        = pd.DataFrame(empleados)
        ids_empleados = df_emp['id_empleado'].tolist()
        df_resp       = pd.DataFrame()
        if ids_empleados:
            fmt_ids = ','.join(['%s'] * len(ids_empleados))
            cursor.execute(
                f"SELECT r.id_empleado, pr.categoria, r.valor "
                f"FROM respuestas r JOIN preguntas pr ON r.id_pregunta = pr.id_pregunta "
                f"WHERE r.id_empleado IN ({fmt_ids}) AND r.valor > 0",
                tuple(ids_empleados)
            )
            df_resp = pd.DataFrame(cursor.fetchall())

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            wb  = writer.book
            hdr = wb.add_format({'bold': True, 'font_size': 12, 'bg_color': '#1E306E', 'font_color': 'white', 'border': 1})
            ttl = wb.add_format({'bold': True, 'font_size': 14, 'font_color': '#1E306E'})
            cel = wb.add_format({'border': 1})

            ws = wb.add_worksheet('Resumen Analítico')
            writer.sheets['Resumen Analítico'] = ws

            resumen_planta          = df_emp['planta'].value_counts().reset_index()
            resumen_planta.columns  = ['Planta', 'Total Personas']
            resumen_genero          = df_emp['genero'].value_counts().reset_index()
            resumen_genero.columns  = ['Género', 'Total']

            if not df_resp.empty:
                prom_cat = df_resp.groupby('categoria')['valor'].mean().reset_index()
                prom_cat['valor']          = prom_cat['valor'].apply(lambda x: round(x, 2))
                prom_cat['Porcentaje (%)'] = prom_cat['valor'].apply(lambda x: round((x / 7) * 100, 2))
                prom_cat.columns           = ['Categoría', 'Promedio (1-7)', 'Porcentaje (%)']
                prom_cat                   = prom_cat.sort_values('Porcentaje (%)', ascending=False)
            else:
                prom_cat = pd.DataFrame(columns=['Categoría', 'Promedio (1-7)', 'Porcentaje (%)'])

            ws.write(0, 0, "REPORTE ESTADÍSTICO DE SATISFACCIÓN", ttl)
            ws.write(2, 0, "TOTAL EMPLEADOS FILTRADOS:", hdr)
            ws.write(2, 1, len(df_emp), cel)

            row = 5
            ws.write(row, 0, "DESGLOSE POR PLANTA", ttl)
            resumen_planta.to_excel(writer, sheet_name='Resumen Analítico', startrow=row + 1, index=False)
            ws.write(row, 4, "DESGLOSE POR GÉNERO", ttl)
            resumen_genero.to_excel(writer, sheet_name='Resumen Analítico', startrow=row + 1, startcol=4, index=False)

            row += max(len(resumen_planta), len(resumen_genero)) + 5
            ws.write(row, 0, "PROMEDIOS POR CATEGORÍA", ttl)
            prom_cat.to_excel(writer, sheet_name='Resumen Analítico', startrow=row + 1, index=False)

            df_emp[['nomina', 'nombre', 'genero', 'planta', 'area', 'antiguedad']].to_excel(
                writer, sheet_name='Base de Datos (Filtrada)', index=False
            )

        output.seek(0)
        return send_file(
            output, as_attachment=True,
            download_name=f"Analitica_Canels_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    except Exception as e:
        app.logger.error("Error en exportar_analitica_excel: %s", e)
        return jsonify({'error': 'Error interno'}), 500
    finally:
        if conn:
            conn.close()


# =================================================================
# 14. GRÁFICO
# =================================================================

@app.route('/api/grafico/generar', methods=['POST'])
@login_required
def generar_grafico():
    """
    Generar datos para gráfico de barras por categoría.
    Aplica filtros de género, planta, área, antigüedad y categorías específicas.
    Los resultados se ordenan de mayor a menor promedio.
    ---
    tags:
      - Gráficos
    consumes:
      - application/json
    parameters:
      - in: body
        name: body
        description: Filtros para el gráfico (todos opcionales).
        schema:
          type: object
          properties:
            periodo:
              type: integer
              description: ID del periodo a graficar.
              example: 2
            genero:
              type: string
              description: "Masculino | Femenino"
              example: Femenino
            planta:
              type: string
              description: Nombre exacto de la planta.
              example: CANELS
            area:
              type: string
              description: Nombre exacto del área.
              example: Producción
            antiguedad:
              type: string
              description: "1 | 1-5 | 5+"
              example: "1-5"
            categories:
              type: array
              items:
                type: string
              description: Lista de categorías a incluir (vacío = todas).
              example: ["Liderazgo", "Condiciones Físicas"]
    responses:
      200:
        description: Datos del gráfico generados correctamente.
        schema:
          type: object
          properties:
            labels:
              type: array
              items:
                type: string
              example: ["Liderazgo", "Condiciones Físicas"]
              description: Categorías ordenadas de mayor a menor promedio.
            data:
              type: array
              items:
                type: number
              example: [78.5, 64.3]
              description: Porcentajes de satisfacción por categoría.
            raw_data:
              type: array
              items:
                type: number
              example: [5.5, 4.5]
              description: Promedios en escala 1-7.
      500:
        description: Error interno.
    """
    conn = None
    try:
        f      = request.json or {}
        conn   = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        query = """
            SELECT pr.categoria, e.id_empleado, AVG(r.valor) AS prom_emp
            FROM respuestas r
            JOIN empleados e  ON r.id_empleado  = e.id_empleado
            JOIN plantas p    ON e.id_planta    = p.id_planta
            LEFT JOIN areas a ON e.id_area      = a.id_area
            JOIN preguntas pr ON r.id_pregunta  = pr.id_pregunta
            WHERE r.valor > 0
        """
        params = []

        if f.get('periodo'):
            query += """
                AND e.id_empleado IN (
                    SELECT DISTINCT r2.id_empleado
                    FROM respuestas r2
                    JOIN preguntas pr2 ON r2.id_pregunta = pr2.id_pregunta
                    WHERE pr2.id_encuesta = %s
                )
            """
            params.append(f['periodo'])
        if f.get('genero'):
            if f['genero'] in ('F', 'Femenino'):
                query += " AND (e.genero LIKE 'Fem%' OR e.genero = 'F')"
            else:
                query += " AND e.genero = %s"; params.append(f['genero'])
        if f.get('planta'): query += " AND p.nombre = %s"; params.append(f['planta'])
        if f.get('area'):   query += " AND a.nombre = %s"; params.append(f['area'])

        val_ant = f.get('antiguedad')
        if val_ant == '1':     query += " AND e.meses_antiguedad < 12"
        elif val_ant == '1-5': query += " AND e.meses_antiguedad BETWEEN 12 AND 60"
        elif val_ant == '5+':  query += " AND e.meses_antiguedad > 60"

        cats = f.get('categories', [])
        if cats:
            query += f" AND pr.categoria IN ({','.join(['%s'] * len(cats))})"
            params.extend(cats)

        query += " GROUP BY pr.categoria, e.id_empleado"
        cursor.execute(query, tuple(params))

        categorias_dict = {}
        for row in cursor.fetchall():
            categorias_dict.setdefault(row['categoria'], []).append(float(row['prom_emp']))

        resultado = sorted(
            [
                {
                    'categoria': cat,
                    'promedio': (prom := sum(vals) / len(vals)),
                    'porcentaje': round((prom / 7.0) * 100, 2)
                }
                for cat, vals in categorias_dict.items()
            ],
            key=lambda x: x['promedio'],
            reverse=True
        )

        return jsonify({
            'labels':   [r['categoria']  for r in resultado],
            'data':     [r['porcentaje'] for r in resultado],
            'raw_data': [r['promedio']   for r in resultado]
        })

    except Exception as e:
        app.logger.error("Error en generar_grafico: %s", e)
        return jsonify({'error': 'Error interno'}), 500
    finally:
        if conn:
            conn.close()


# =================================================================
# 15. ADMIN: IMPORTAR / BACKUP / RESTORE / RESET
# =================================================================

@app.route('/api/admin/importar', methods=['POST'])
@login_required
def admin_importar():
    """
    Importar respuestas de encuesta desde un archivo Excel.
    Solo se aceptan archivos .xlsx. Si el periodo ya existe con el nombre indicado,
    se reutiliza en lugar de crear uno nuevo (evita duplicados).
    ---
    tags:
      - Administración
    consumes:
      - multipart/form-data
    parameters:
      - in: formData
        name: file
        type: file
        required: true
        description: Archivo Excel (.xlsx) generado desde Google Forms.
      - in: formData
        name: survey_id
        type: string
        required: false
        description: ID de un periodo existente al que agregar los datos.
        example: "2"
      - in: formData
        name: new_survey_name
        type: string
        required: false
        description: Nombre del nuevo periodo a crear (ignorado si survey_id está presente).
        example: "Q2 2026"
    responses:
      200:
        description: Importación procesada. El campo success indica si fue exitosa.
        schema:
          type: object
          properties:
            success:
              type: boolean
              example: true
            message:
              type: string
              example: "250 empleados importados correctamente."
            errors:
              type: array
              items:
                type: string
              example: ["Fila 5: valor fuera de rango", "Fila 12: nómina vacía"]
      400:
        description: Archivo no recibido o extensión no permitida.
      403:
        description: Rol insuficiente (se requiere admin o superadmin).
    """
    err = _require_admin()
    if err:
        return err

    if 'file' not in request.files:
        return jsonify({'error': 'No se recibió archivo'}), 400

    file = request.files['file']
    if not file.filename or not Config.allowed_file(file.filename):
        return jsonify({'error': 'Solo se permiten archivos .xlsx'}), 400

    survey_id = request.form.get('survey_id')
    new_name  = request.form.get('new_survey_name', '').strip()

    final_id = None
    if new_name:
        conn = None
        try:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute(
                    "SELECT id_encuesta FROM encuestas WHERE nombre = %s", (new_name,)
                )
                existing = cursor.fetchone()
                if existing:
                    final_id = existing['id_encuesta']
        except Exception as e:
            app.logger.error("Error buscando periodo existente: %s", e)
        finally:
            if conn:
                conn.close()

    if not final_id:
        final_id = get_or_create_period(survey_id, new_name)

    if not final_id:
        return jsonify({'success': False, 'error': 'Error al obtener/crear periodo'})

    filepath  = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(file.filename))
    file.save(filepath)
    resultado = process_excel_import(filepath, final_id)

    accion = 'IMPORTAR_DATOS' if resultado.get('success') else 'ERROR_IMPORTACION'
    registrar_auditoria(accion, f"Archivo: {file.filename}, Periodo ID: {final_id}")
    return jsonify(resultado)


@app.route('/api/admin/backup', methods=['GET'])
@login_required
def admin_backup():
    """
    Generar y descargar copia de seguridad SQL.
    Ejecuta mysqldump sobre la base de datos activa y devuelve el archivo.
    ---
    tags:
      - Administración
    responses:
      200:
        description: Archivo SQL de backup descargable.
        headers:
          Content-Disposition:
            description: Nombre del archivo.
            type: string
            example: 'attachment; filename="backup_canels_20260321.sql"'
      403:
        description: Rol insuficiente.
      500:
        description: Error generando el backup en el servidor.
    """
    err = _require_admin()
    if err:
        return err
    try:
        full_path = create_backup()
        if full_path and os.path.exists(full_path):
            registrar_auditoria('GENERAR_RESPALDO', 'Copia de seguridad SQL descargada.')
            full_path = os.path.normpath(full_path)
            return send_from_directory(
                os.path.dirname(full_path),
                os.path.basename(full_path),
                as_attachment=True
            )
        return jsonify({'error': 'Error generando respaldo'}), 500
    except Exception as e:
        app.logger.error("Error en admin_backup: %s", e)
        return jsonify({'error': f'Error interno: {str(e)}'}), 500


@app.route('/api/admin/restore', methods=['POST'])
@login_required
def admin_restore():
    """
    Restaurar base de datos desde archivo SQL de backup.
    ADVERTENCIA: Esta operación elimina TODOS los datos actuales y los reemplaza
    con el contenido del archivo SQL. La operación es irreversible.
    ---
    tags:
      - Administración
    consumes:
      - multipart/form-data
    parameters:
      - in: formData
        name: file
        type: file
        required: true
        description: Archivo .sql generado previamente por el endpoint de backup.
    responses:
      200:
        description: Resultado de la restauración.
        schema:
          type: object
          properties:
            success:
              type: boolean
              example: true
      400:
        description: Archivo no recibido.
      403:
        description: Rol insuficiente.
      500:
        description: Error durante la restauración.
    """
    err = _require_admin()
    if err:
        return err
    file = request.files.get('file')
    if not file:
        return jsonify({'error': 'No se recibió archivo'}), 400
    path  = os.path.join(app.config['UPLOAD_FOLDER'], 'restore.sql')
    file.save(path)
    exito = restore_backup(path)
    registrar_auditoria(
        'RESTAURAR_BACKUP' if exito else 'ERROR_RESTAURACION',
        'Restauración de BD ' + ('exitosa' if exito else 'fallida')
    )
    return jsonify({'success': exito})


@app.route('/api/admin/reset', methods=['POST'])
@login_required
def admin_reset():
    """
    Limpiar todos los datos operativos del sistema.
    Elimina en orden: respuestas, empleados, preguntas, encuestas, población.
    NO elimina usuarios, plantas ni áreas.
    Requiere la clave maestra (MASTER_KEY del .env) como confirmación.
    ADVERTENCIA: Operación completamente irreversible.
    ---
    tags:
      - Administración
    consumes:
      - application/json
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - master_key
          properties:
            master_key:
              type: string
              description: Clave maestra definida en MASTER_KEY del archivo .env.
              example: "clave-maestra-2026"
    responses:
      200:
        description: Sistema reiniciado o error de validación.
        schema:
          type: object
          properties:
            success:
              type: boolean
              example: true
            message:
              type: string
              example: "Sistema reiniciado."
      403:
        description: Clave maestra inválida o rol insuficiente.
      500:
        description: Fallo durante el reinicio.
    """
    err = _require_admin()
    if err:
        return err

    data       = request.get_json() or request.form or {}
    master_key = data.get('master_key', '')

    if not master_key or not hmac.compare_digest(
        master_key.encode(), Config.MASTER_KEY.encode()
    ):
        return jsonify({'success': False, 'message': 'Clave maestra inválida.'}), 403

    exito = reset_data_only()
    registrar_auditoria(
        'RESET_SISTEMA' if exito else 'ERROR_RESET',
        f'Reinicio del sistema por {current_user.username}'
    )
    if exito:
        return jsonify({'success': True, 'message': 'Sistema reiniciado.'})
    return jsonify({'success': False, 'message': 'Fallo al reiniciar.'}), 500


# =================================================================
# 16. MANTENIMIENTO
# =================================================================

@app.route('/api/maintenance/upcoming', methods=['GET'])
@login_required
@limiter.exempt
def maintenance_upcoming():
    """
    Mantenimientos activos y futuros (accesible para todos los roles).
    Usado por notifications.js para actualizar el badge de la campana.
    Devuelve eventos activos cuya fecha de fin no haya pasado aún.
    ---
    tags:
      - Mantenimiento
    responses:
      200:
        description: Lista de mantenimientos próximos o en curso.
        schema:
          type: object
          properties:
            success:
              type: boolean
              example: true
            maintenance:
              type: array
              items:
                type: object
                properties:
                  id:
                    type: integer
                    example: 3
                  active:
                    type: integer
                    example: 1
                  start:
                    type: string
                    example: "2026-03-22 02:00:00"
                  end:
                    type: string
                    example: "2026-03-22 04:00:00"
                  notas:
                    type: string
                    example: "Actualización mensual del sistema"
                  created_by:
                    type: string
                    example: superadmin
                  created_at:
                    type: string
                    example: "2026-03-20 10:30:00"
      500:
        description: Error interno.
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT id, active, start, end, notas, created_by, created_at "
            "FROM mantenimiento "
            "WHERE active = 1 "
            "AND (end IS NULL OR end >= NOW()) "
            "ORDER BY start ASC"
        )
        rows = cursor.fetchall()
        for row in rows:
            for campo in ('start', 'end', 'created_at'):
                if row.get(campo) and hasattr(row[campo], 'strftime'):
                    row[campo] = row[campo].strftime('%Y-%m-%d %H:%M:%S')
        return jsonify({'success': True, 'maintenance': rows})
    except Exception as e:
        app.logger.error("Error en maintenance_upcoming: %s", e)
        return jsonify({'success': False, 'message': 'Error interno'}), 500
    finally:
        if conn:
            conn.close()


@app.route('/api/admin/maintenance', methods=['GET', 'POST'])
@login_required
def admin_maintenance():
    """
    Consultar (GET) o programar (POST) evento de mantenimiento.
    Requiere rol admin o superadmin.
    ---
    tags:
      - Mantenimiento
    consumes:
      - application/json
    parameters:
      - in: body
        name: body
        description: Datos del nuevo evento (solo POST).
        schema:
          type: object
          properties:
            active:
              type: integer
              description: "1 para activar inmediatamente, 0 para programar inactivo."
              example: 1
            start:
              type: string
              description: Fecha y hora de inicio (YYYY-MM-DD HH:MM:SS).
              example: "2026-03-22 02:00:00"
            end:
              type: string
              description: Fecha y hora de fin (YYYY-MM-DD HH:MM:SS).
              example: "2026-03-22 04:00:00"
            notas:
              type: string
              description: Descripción del mantenimiento.
              example: "Actualización mensual de seguridad"
    responses:
      200:
        description: Datos del último mantenimiento (GET) o confirmación de creación (POST).
      403:
        description: Rol insuficiente.
      500:
        description: Error interno.
    """
    err = _require_admin()
    if err:
        return err

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        if request.method == 'GET':
            cursor.execute("SELECT * FROM mantenimiento ORDER BY id DESC LIMIT 1")
            return jsonify({'success': True, 'maintenance': cursor.fetchone()})

        data   = request.form or request.get_json() or {}
        active = int(data.get('active', 0))
        start  = data.get('start') or None
        end    = data.get('end')   or None
        notas  = data.get('notas', '')

        cursor.execute(
            "INSERT INTO mantenimiento (active, start, end, notas, created_by) VALUES (%s, %s, %s, %s, %s)",
            (active, start, end, notas, current_user.username)
        )
        conn.commit()
        registrar_auditoria(
            'MANTENIMIENTO',
            f"active={active} start={start} end={end} por {current_user.username}"
        )
        return jsonify({'success': True, 'message': 'Mantenimiento actualizado'})

    except Exception as e:
        app.logger.error("Error en admin_maintenance: %s", e)
        return jsonify({'success': False, 'message': 'Error interno'}), 500
    finally:
        if conn:
            conn.close()


@app.route('/api/admin/maintenance/list', methods=['GET'])
@login_required
@limiter.exempt
def admin_maintenance_list():
    """
    Lista completa del historial de mantenimientos.
    Solo accesible por admin y superadmin.
    ---
    tags:
      - Mantenimiento
    responses:
      200:
        description: Lista de todos los eventos de mantenimiento registrados.
        schema:
          type: object
          properties:
            success:
              type: boolean
              example: true
            maintenance:
              type: array
              items:
                type: object
      403:
        description: Rol insuficiente.
      500:
        description: Error interno.
    """
    err = _require_admin()
    if err:
        return err
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT id, active, start, end, notas, created_by, created_at "
            "FROM mantenimiento ORDER BY id DESC"
        )
        rows = cursor.fetchall()
        for row in rows:
            for campo in ('start', 'end', 'created_at'):
                if row.get(campo) and hasattr(row[campo], 'strftime'):
                    row[campo] = row[campo].strftime('%Y-%m-%d %H:%M:%S')
        return jsonify({'success': True, 'maintenance': rows})
    except Exception as e:
        app.logger.error("Error en admin_maintenance_list: %s", e)
        return jsonify({'success': False, 'message': 'Error interno'}), 500
    finally:
        if conn:
            conn.close()


@app.route('/api/admin/maintenance/<int:maint_id>', methods=['DELETE'])
@login_required
def admin_maintenance_delete(maint_id):
    """
    Cancelar o eliminar físicamente un evento de mantenimiento.
    Solo el superadministrador puede realizar esta acción.
    Sin el header X-Delete-Force solo se cancela (active=0).
    Con X-Delete-Force: true se elimina físicamente, pero solo si el evento
    está cancelado o ya finalizó.
    ---
    tags:
      - Mantenimiento
    parameters:
      - in: path
        name: maint_id
        type: integer
        required: true
        description: ID del evento de mantenimiento.
        example: 3
      - in: header
        name: X-Delete-Force
        type: string
        required: false
        description: "Si es 'true', elimina físicamente el registro."
        example: "true"
    responses:
      200:
        description: Mantenimiento cancelado o eliminado.
        schema:
          type: object
          properties:
            success:
              type: boolean
              example: true
            message:
              type: string
              example: "Mantenimiento cancelado"
      400:
        description: No se puede eliminar un evento activo o sin fecha de fin.
      403:
        description: Solo el superadministrador puede realizar esta acción.
      404:
        description: Evento no encontrado.
      500:
        description: Error interno.
    """
    if not _is_superadmin(current_user):
        return jsonify({'success': False, 'message': 'Solo el superadministrador puede gestionar mantenimientos'}), 403

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT active, start, end FROM mantenimiento WHERE id = %s", (maint_id,))
        event = cursor.fetchone()
        if not event:
            return jsonify({'success': False, 'message': 'Evento no encontrado'}), 404

        force_delete = request.headers.get('X-Delete-Force') == 'true'
        if force_delete:
            is_cancelled = event['active'] == 0
            end_date     = event['end']
            if not is_cancelled:
                if not end_date:
                    return jsonify({'success': False, 'message': 'No se puede eliminar un evento sin fecha de fin'}), 400
                if end_date > datetime.now():
                    return jsonify({'success': False, 'message': 'Solo se pueden eliminar eventos finalizados o cancelados'}), 400
            cursor.execute("DELETE FROM mantenimiento WHERE id = %s", (maint_id,))
            conn.commit()
            registrar_auditoria('MANTENIMIENTO_DELETE', f'id={maint_id} eliminado por {current_user.username}')
            return jsonify({'success': True, 'message': 'Mantenimiento eliminado'})

        cursor.execute("UPDATE mantenimiento SET active = 0 WHERE id = %s", (maint_id,))
        conn.commit()
        registrar_auditoria('MANTENIMIENTO_CANCEL', f'id={maint_id} cancelado por {current_user.username}')
        return jsonify({'success': True, 'message': 'Mantenimiento cancelado'})

    except Exception as e:
        app.logger.error("Error en admin_maintenance_delete: %s", e)
        return jsonify({'success': False, 'message': 'Error interno'}), 500
    finally:
        if conn:
            conn.close()


@app.route('/api/admin/check-maintenance', methods=['GET'])
@login_required
@limiter.exempt
def check_maintenance_status():
    """
    Verificar estado actual del mantenimiento.
    Usado por maintenance.js cada 10 segundos para detectar mantenimientos
    activos o próximos a iniciar (dentro de 5 minutos).
    ---
    tags:
      - Mantenimiento
    responses:
      200:
        description: Estado de mantenimiento verificado correctamente.
        schema:
          type: object
          properties:
            success:
              type: boolean
              example: true
            maintenance_active:
              type: boolean
              example: false
              description: true si hay un evento activo en este momento.
            maintenance_starting_soon:
              type: boolean
              example: false
              description: true si hay un evento que inicia en menos de 5 minutos.
            seconds_until_start:
              type: integer
              nullable: true
              example: 180
              description: Segundos hasta el inicio (null si no aplica).
            can_stay_logged:
              type: boolean
              example: true
              description: true para superadmin o cuando no hay mantenimiento activo.
            reason:
              type: string
              example: normal
              description: "superadmin | maintenance | normal"
      500:
        description: Error interno.
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT *, TIMESTAMPDIFF(SECOND, NOW(), start) AS seconds_until_start
            FROM mantenimiento
            WHERE active = 1 AND (start IS NULL OR start <= NOW()) AND (end IS NULL OR end >= NOW())
            LIMIT 1
        """)
        maintenance_active = cursor.fetchone()

        cursor.execute("""
            SELECT *, TIMESTAMPDIFF(SECOND, NOW(), start) AS seconds_until_start
            FROM mantenimiento
            WHERE active = 1 AND start > NOW() AND TIMESTAMPDIFF(MINUTE, NOW(), start) <= 5
            LIMIT 1
        """)
        maintenance_soon = cursor.fetchone()

        is_super = _is_superadmin(current_user)
        return jsonify({
            'success': True,
            'maintenance_active':        maintenance_active is not None,
            'maintenance_starting_soon': maintenance_soon is not None,
            'seconds_until_start':       maintenance_soon['seconds_until_start'] if maintenance_soon else None,
            'can_stay_logged':           is_super or not maintenance_active,
            'reason': 'superadmin' if is_super else ('maintenance' if maintenance_active else 'normal')
        })
    except Exception as e:
        app.logger.error("Error en check_maintenance_status: %s", e)
        return jsonify({'success': False, 'message': 'Error interno'}), 500
    finally:
        if conn:
            conn.close()


@app.route('/api/admin/server-status', methods=['GET'])
@login_required
@limiter.exempt
def get_server_status():
    """
    Estado de la base de datos y último mantenimiento completado.
    ---
    tags:
      - Mantenimiento
    responses:
      200:
        description: Estado del servidor obtenido correctamente.
        schema:
          type: object
          properties:
            success:
              type: boolean
              example: true
            db_status:
              type: string
              example: Conectada
              description: "Conectada | Desconectada | Error"
            db_status_class:
              type: string
              example: "bg-green-100 text-green-700"
              description: Clase CSS para colorear el indicador en la interfaz.
            last_maintenance:
              type: object
              nullable: true
              description: Datos del último mantenimiento completado.
            last_maintenance_text:
              type: string
              example: "Hace 2 días"
              description: Tiempo transcurrido en lenguaje natural.
      500:
        description: Error interno.
    """
    conn = None
    try:
        conn = get_db_connection()
        db_ok           = conn is not None
        db_status       = 'Conectada' if db_ok else 'Desconectada'
        db_status_class = 'bg-green-100 text-green-700' if db_ok else 'bg-red-100 text-red-700'

        last_maintenance_text = 'Nunca'
        last_maintenance      = None

        if db_ok:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT created_by, start, end, notas, created_at
                FROM mantenimiento WHERE active = 1 AND end < NOW()
                ORDER BY end DESC LIMIT 1
            """)
            last_maintenance = cursor.fetchone()

            if last_maintenance and last_maintenance.get('end'):
                end_time = last_maintenance['end']
                if isinstance(end_time, str):
                    end_time = datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S')
                diff    = datetime.now() - end_time
                days, hours = diff.days, diff.seconds // 3600
                minutes = (diff.seconds % 3600) // 60
                if days:
                    last_maintenance_text = f'Hace {days} día{"s" if days > 1 else ""}'
                elif hours:
                    last_maintenance_text = f'Hace {hours} hora{"s" if hours > 1 else ""}'
                elif minutes:
                    last_maintenance_text = f'Hace {minutes} minuto{"s" if minutes > 1 else ""}'
                else:
                    last_maintenance_text = 'Hace unos momentos'

        return jsonify({
            'success': True,
            'db_status': db_status,
            'db_status_class': db_status_class,
            'last_maintenance': last_maintenance,
            'last_maintenance_text': last_maintenance_text
        })
    except Exception as e:
        app.logger.error("Error en get_server_status: %s", e)
        return jsonify({
            'success': False, 'db_status': 'Error',
            'db_status_class': 'bg-red-100 text-red-700',
            'last_maintenance': None, 'last_maintenance_text': 'Error al consultar'
        }), 500
    finally:
        if conn:
            conn.close()


# =================================================================
# 17. AUDITORÍA
# =================================================================

@app.route('/api/admin/auditoria', methods=['GET'])
@login_required
def admin_auditoria_list():
    """
    Listar registros de auditoría.
    Devuelve los últimos 1000 eventos ordenados del más reciente al más antiguo.
    ---
    tags:
      - Auditoría
    responses:
      200:
        description: Registros de auditoría obtenidos correctamente.
        schema:
          type: object
          properties:
            success:
              type: boolean
              example: true
            auditoria:
              type: array
              items:
                type: object
                properties:
                  id_log:
                    type: integer
                    example: 78
                  usuario:
                    type: string
                    example: superadmin
                    description: Username del autor del evento (o 'Sistema/Anonimo').
                  accion:
                    type: string
                    example: LOGIN_BLOQUEADO
                    description: Código del evento registrado.
                  detalle:
                    type: string
                    example: "Cuenta 'superadmin' bloqueada temporalmente por exceso de intentos."
                  fecha:
                    type: string
                    example: "2026-03-17 11:44:57"
                  ip_origen:
                    type: string
                    example: "192.168.12.87"
      403:
        description: Rol insuficiente.
      500:
        description: Error interno.
    """
    err = _require_admin()
    if err:
        return err
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT id_log, usuario, accion, detalle, fecha, ip_origen "
            "FROM auditoria ORDER BY fecha DESC LIMIT 1000"
        )
        return jsonify({'success': True, 'auditoria': cursor.fetchall()})
    except Exception as e:
        app.logger.error("Error en admin_auditoria_list: %s", e)
        return jsonify({'success': False, 'message': 'Error interno'}), 500
    finally:
        if conn:
            conn.close()


@app.route('/api/admin/auditoria/<int:log_id>', methods=['DELETE'])
@login_required
def admin_auditoria_delete(log_id):
    """
    Eliminar un registro de la bitácora de auditoría.
    ---
    tags:
      - Auditoría
    parameters:
      - in: path
        name: log_id
        type: integer
        required: true
        description: ID del registro a eliminar.
        example: 78
    responses:
      200:
        description: Registro eliminado correctamente.
      403:
        description: Rol insuficiente.
      500:
        description: Error interno.
    """
    err = _require_admin()
    if err:
        return err
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM auditoria WHERE id_log = %s", (log_id,))
        conn.commit()
        registrar_auditoria('AUDITORIA_DELETE', f'id={log_id} eliminado por {current_user.username}')
        return jsonify({'success': True, 'message': 'Registro eliminado'})
    except Exception as e:
        app.logger.error("Error en admin_auditoria_delete: %s", e)
        return jsonify({'success': False, 'message': 'Error interno'}), 500
    finally:
        if conn:
            conn.close()


@app.route('/api/admin/auditoria/<int:log_id>', methods=['PUT'])
@login_required
def admin_auditoria_edit(log_id):
    """
    Editar el campo detalle de un registro de auditoría.
    ---
    tags:
      - Auditoría
    consumes:
      - application/json
    parameters:
      - in: path
        name: log_id
        type: integer
        required: true
        description: ID del registro a editar.
        example: 78
      - in: body
        name: body
        required: true
        schema:
          type: object
          properties:
            detalle:
              type: string
              description: Nuevo texto del campo detalle.
              example: "Detalle corregido manualmente."
    responses:
      200:
        description: Registro actualizado correctamente.
      403:
        description: Rol insuficiente.
      500:
        description: Error interno.
    """
    err = _require_admin()
    if err:
        return err
    conn = None
    try:
        detalle = (request.get_json() or {}).get('detalle', '')
        conn    = get_db_connection()
        cursor  = conn.cursor()
        cursor.execute("UPDATE auditoria SET detalle = %s WHERE id_log = %s", (detalle, log_id))
        conn.commit()
        registrar_auditoria('AUDITORIA_EDIT', f'id={log_id} editado por {current_user.username}')
        return jsonify({'success': True, 'message': 'Registro actualizado'})
    except Exception as e:
        app.logger.error("Error en admin_auditoria_edit: %s", e)
        return jsonify({'success': False, 'message': 'Error interno'}), 500
    finally:
        if conn:
            conn.close()


@app.route('/api/admin/auditoria/excel', methods=['GET'])
@login_required
def descargar_auditoria_excel():
    """
    Descargar la bitácora completa de auditoría en formato Excel.
    ---
    tags:
      - Auditoría
    responses:
      200:
        description: Archivo Excel de auditoría descargable.
        headers:
          Content-Disposition:
            description: Nombre del archivo.
            type: string
            example: 'attachment; filename="Auditoria_Canels_20260321.xlsx"'
      403:
        description: Rol insuficiente.
      404:
        description: No hay registros de auditoría.
      500:
        description: Error interno.
    """
    err = _require_admin()
    if err:
        return err
    conn = None
    try:
        conn    = get_db_connection()
        cursor  = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM auditoria ORDER BY fecha DESC")
        logs = cursor.fetchall()
        if not logs:
            return jsonify({'error': 'No hay registros de auditoría'}), 404

        df     = pd.DataFrame(logs)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='Bitácora de Eventos', index=False)
            wb  = writer.book
            ws  = writer.sheets['Bitácora de Eventos']
            fmt = wb.add_format({'bold': True, 'bg_color': '#D9E1F2', 'border': 1})
            for col_num, col_name in enumerate(df.columns.values):
                ws.write(0, col_num, col_name, fmt)
                ws.set_column(col_num, col_num, 20)
        output.seek(0)
        return send_file(
            output, as_attachment=True,
            download_name=f"Auditoria_Canels_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    except Exception as e:
        app.logger.error("Error en descargar_auditoria_excel: %s", e)
        return jsonify({'error': 'Error interno'}), 500
    finally:
        if conn:
            conn.close()


# =================================================================
# 18. PREGUNTAS
# =================================================================

@app.route('/api/preguntas', methods=['GET', 'POST'])
@login_required
def gestionar_preguntas():
    """
    Listar (GET) o crear (POST) preguntas de encuesta.
    La lectura está disponible para todos los roles.
    La creación requiere rol admin o superadmin.
    ---
    tags:
      - Preguntas
    parameters:
      - in: query
        name: periodo_id
        type: integer
        required: false
        description: Filtra las preguntas al periodo indicado (GET).
        example: 2
      - in: body
        name: body
        description: Datos de la nueva pregunta (POST).
        schema:
          type: object
          required:
            - texto
            - periodo_id
          properties:
            texto:
              type: string
              description: Enunciado de la pregunta.
              example: "¿Qué tan satisfecho estás con tu ambiente de trabajo?"
            tipo:
              type: string
              description: "Tipo de respuesta: escala | abierta (default: escala)."
              example: escala
            categoria:
              type: string
              description: Categoría temática de la pregunta.
              example: "Condiciones Físicas"
            periodo_id:
              type: integer
              description: ID del periodo al que pertenece.
              example: 2
            numero:
              type: number
              description: Número de orden (se auto-asigna si se omite).
              example: 5
    responses:
      200:
        description: Lista de preguntas (GET) o confirmación de creación (POST).
      400:
        description: Falta el ID del periodo o el texto de la pregunta.
      403:
        description: Rol insuficiente (POST).
      500:
        description: Error interno.
    """
    if request.method == 'POST':
        err = _require_admin()
        if err:
            return err

    conn = None
    try:
        conn   = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        if request.method == 'GET':
            periodo_id = request.args.get('periodo_id')
            query = """
                SELECT p.id_pregunta, p.numero, p.texto, p.tipo, p.categoria,
                       e.nombre AS periodo_nombre, p.id_encuesta
                FROM preguntas p
                JOIN encuestas e ON p.id_encuesta = e.id_encuesta
            """
            params = []
            if periodo_id:
                query += " WHERE p.id_encuesta = %s"; params.append(periodo_id)
            query += " ORDER BY p.numero ASC"
            cursor.execute(query, tuple(params))
            return jsonify(cursor.fetchall())

        d         = request.json or {}
        texto     = d.get('texto', '').strip()
        tipo      = d.get('tipo', d.get('type', 'escala'))
        categoria = d.get('categoria', d.get('category', ''))
        id_enc    = d.get('periodo_id', d.get('id_encuesta'))
        num       = d.get('numero')

        if not id_enc:
            return jsonify({'success': False, 'error': 'Falta el ID del periodo'}), 400
        if not texto:
            return jsonify({'success': False, 'error': 'El texto es obligatorio'}), 400
        if not num:
            cursor.execute(
                "SELECT COALESCE(MAX(numero), 0) + 1 AS n FROM preguntas WHERE id_encuesta = %s",
                (id_enc,)
            )
            num = cursor.fetchone()['n']

        cursor.execute(
            "INSERT INTO preguntas (texto, tipo, categoria, numero, id_encuesta) VALUES (%s, %s, %s, %s, %s)",
            (texto, tipo, categoria, num, id_enc)
        )
        conn.commit()
        return jsonify({'success': True, 'message': 'Pregunta creada'})

    except Exception as e:
        app.logger.error("Error en gestionar_preguntas: %s", e)
        return jsonify({'success': False, 'error': 'Error interno'}), 500
    finally:
        if conn:
            conn.close()


@app.route('/api/preguntas/<int:preg_id>', methods=['DELETE', 'PUT'])
@login_required
def mod_preg(preg_id):
    """
    Editar (PUT) o eliminar (DELETE) una pregunta existente.
    El DELETE elimina también todas las respuestas asociadas.
    El PUT desplaza automáticamente los números de orden si hay conflicto.
    ---
    tags:
      - Preguntas
    parameters:
      - in: path
        name: preg_id
        type: integer
        required: true
        description: ID de la pregunta a modificar o eliminar.
        example: 15
      - in: body
        name: body
        description: Nuevos datos de la pregunta (PUT).
        schema:
          type: object
          properties:
            texto:
              type: string
              example: "Texto actualizado de la pregunta"
            categoria:
              type: string
              example: Liderazgo
            tipo:
              type: string
              example: escala
            numero:
              type: number
              example: 3
    responses:
      200:
        description: Operación completada correctamente.
      400:
        description: Número de pregunta inválido o texto vacío.
      403:
        description: Rol insuficiente.
      404:
        description: Pregunta no encontrada.
      500:
        description: Error interno.
    """
    err = _require_admin()
    if err:
        return err

    conn = None
    try:
        conn   = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        if request.method == 'PUT':
            d           = request.json or {}
            nuevo_texto = d.get('texto', '').strip()
            nueva_cat   = d.get('categoria', d.get('category', ''))
            nuevo_tipo  = d.get('tipo', d.get('type', 'escala'))
            try:
                new_num = float(d.get('numero', 0))
            except (ValueError, TypeError):
                return jsonify({'success': False, 'error': 'Número de pregunta inválido'}), 400

            if not nuevo_texto:
                return jsonify({'success': False, 'error': 'El texto es obligatorio'}), 400

            cursor.execute("SELECT id_encuesta FROM preguntas WHERE id_pregunta = %s", (preg_id,))
            pregunta_actual = cursor.fetchone()
            if not pregunta_actual:
                return jsonify({'success': False, 'error': 'Pregunta no encontrada'}), 404

            id_encuesta = pregunta_actual['id_encuesta']
            cursor.execute(
                "SELECT id_pregunta FROM preguntas WHERE numero = %s AND id_pregunta != %s AND id_encuesta = %s",
                (new_num, preg_id, id_encuesta)
            )
            if cursor.fetchone():
                cursor.execute(
                    "UPDATE preguntas SET numero = numero + 1 WHERE numero >= %s AND id_encuesta = %s",
                    (new_num, id_encuesta)
                )
            cursor.execute(
                "UPDATE preguntas SET texto = %s, categoria = %s, tipo = %s, numero = %s WHERE id_pregunta = %s",
                (nuevo_texto, nueva_cat, nuevo_tipo, new_num, preg_id)
            )
            conn.commit()
            return jsonify({'success': True, 'message': 'Pregunta actualizada'})

        # DELETE
        cursor.execute("DELETE FROM respuestas WHERE id_pregunta = %s", (preg_id,))
        cursor.execute("DELETE FROM preguntas  WHERE id_pregunta = %s", (preg_id,))
        conn.commit()
        return jsonify({'success': True, 'message': 'Pregunta eliminada'})

    except Exception as e:
        if conn:
            conn.rollback()
        app.logger.error("Error en mod_preg: %s", e)
        return jsonify({'success': False, 'error': 'Error interno'}), 500
    finally:
        if conn:
            conn.close()

@app.route('/api/preguntas/importar-categorias', methods=['POST'])
@login_required
def importar_categorias_json():
    """
    Importar categorías desde archivo JSON.
    Recibe un objeto con pares número-categoría y actualiza las preguntas
    del periodo indicado cuyo número coincida con las claves del JSON.
    Las preguntas sin coincidencia se reportan en el campo no_encontradas.
    ---
    tags:
      - Preguntas
    consumes:
      - application/json
    parameters:
      - in: body
        name: body
        required: true
        description: Periodo objetivo y mapa de categorías a aplicar.
        schema:
          type: object
          required:
            - periodo_id
            - categorias
          properties:
            periodo_id:
              type: integer
              description: ID del periodo cuyas preguntas se actualizarán.
              example: 2
            categorias:
              type: object
              description: >
                Objeto donde cada clave es el número de pregunta (string)
                y el valor es el nombre de la categoría a asignar.
              example:
                "1": "Condiciones físicas del puesto"
                "2": "Autonomía para realizar el trabajo"
                "5": "Jefe inmediato"
    responses:
      200:
        description: Categorías aplicadas correctamente.
        schema:
          type: object
          properties:
            success:
              type: boolean
              example: true
            actualizadas:
              type: integer
              example: 24
              description: Número de preguntas que recibieron una categoría.
            no_encontradas:
              type: array
              items:
                type: string
              example: ["27", "28"]
              description: >
                Números del JSON que no coincidieron con ninguna pregunta
                del periodo. Puede ocurrir si el JSON tiene más entradas
                que preguntas registradas.
            message:
              type: string
              example: "24 categorías aplicadas correctamente."
      400:
        description: Falta el periodo_id o el JSON de categorías está vacío.
        schema:
          type: object
          properties:
            success:
              type: boolean
              example: false
            error:
              type: string
              example: "Falta el periodo_id"
      403:
        description: Rol insuficiente (se requiere admin o superadmin).
      500:
        description: Error interno del servidor.
    """
    err = _require_admin()
    if err:
        return err

    data       = request.json or {}
    periodo_id = data.get('periodo_id')
    categorias = data.get('categorias', {})

    if not periodo_id:
        return jsonify({'success': False, 'error': 'Falta el periodo_id'}), 400
    if not categorias:
        return jsonify({'success': False, 'error': 'El JSON de categorías está vacío'}), 400

    conn = None
    try:
        conn   = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        actualizadas   = 0
        no_encontradas = []

        for numero_str, categoria in categorias.items():
            try:
                numero = float(numero_str)
            except ValueError:
                continue

            cursor.execute(
                "UPDATE preguntas SET categoria = %s "
                "WHERE id_encuesta = %s AND numero = %s",
                (categoria.strip(), periodo_id, numero)
            )
            if cursor.rowcount > 0:
                actualizadas += cursor.rowcount
            else:
                no_encontradas.append(numero_str)

        conn.commit()
        registrar_auditoria(
            'IMPORTAR_CATEGORIAS',
            f"Periodo {periodo_id}: {actualizadas} preguntas actualizadas desde JSON"
        )

        return jsonify({
            'success':        True,
            'actualizadas':   actualizadas,
            'no_encontradas': no_encontradas,
            'message':        f'{actualizadas} categorías aplicadas correctamente.'
        })

    except Exception as e:
        if conn:
            conn.rollback()
        app.logger.error("Error en importar_categorias_json: %s", e)
        return jsonify({'success': False, 'error': 'Error interno'}), 500
    finally:
        if conn:
            conn.close()

# =================================================================
# 19. POBLACIÓN
# =================================================================

@app.route('/api/poblacion', methods=['GET', 'POST'])
@login_required
def gestionar_poblacion():
    """
    Consultar (GET) o registrar/actualizar (POST) la población objetivo por planta.
    El POST hace upsert: si ya existe el registro para planta+periodo, lo actualiza.
    ---
    tags:
      - Población
    parameters:
      - in: query
        name: periodo_id
        type: integer
        required: true
        description: ID del periodo a consultar (GET).
        example: 2
      - in: body
        name: body
        description: Datos de población (POST).
        schema:
          type: object
          required:
            - id_encuesta
            - id_planta
          properties:
            id_encuesta:
              type: integer
              description: ID del periodo.
              example: 2
            id_planta:
              type: integer
              description: ID de la planta.
              example: 1
            num_poblacion:
              type: integer
              description: Total de colaboradores objetivo en esa planta.
              example: 150
    responses:
      200:
        description: Datos de población o confirmación de operación.
      400:
        description: Faltan campos obligatorios.
      403:
        description: Rol insuficiente (POST).
      500:
        description: Error interno.
    """
    if request.method == 'POST':
        err = _require_admin()
        if err:
            return err

    conn = None
    try:
        conn   = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        if request.method == 'GET':
            periodo_id = request.args.get('periodo_id')
            if not periodo_id:
                return jsonify([])
            cursor.execute("""
                SELECT p.id_poblacion, p.num_poblacion, p.id_encuesta, p.id_planta,
                    pl.nombre AS planta_nombre,
                    (SELECT COUNT(DISTINCT e2.id_empleado)
                        FROM empleados e2
                        WHERE e2.id_planta = p.id_planta
                        AND e2.id_empleado IN (
                            SELECT DISTINCT r2.id_empleado
                            FROM respuestas r2
                            JOIN preguntas pr2 ON r2.id_pregunta = pr2.id_pregunta
                            WHERE pr2.id_encuesta = p.id_encuesta
                        )
                    ) AS empleados_encuestados
                FROM poblacion p
                JOIN plantas pl ON p.id_planta = pl.id_planta
                WHERE p.id_encuesta = %s ORDER BY pl.nombre
            """, (periodo_id,))
            return jsonify(cursor.fetchall())

        d             = request.json or {}
        id_encuesta   = d.get('id_encuesta')
        id_planta     = d.get('id_planta')
        num_poblacion = d.get('num_poblacion', 0)
        if not id_encuesta or not id_planta:
            return jsonify({'success': False, 'error': 'Faltan datos obligatorios'}), 400

        cursor.execute(
            "SELECT id_poblacion FROM poblacion WHERE id_encuesta = %s AND id_planta = %s",
            (id_encuesta, id_planta)
        )
        existing = cursor.fetchone()
        if existing:
            cursor.execute(
                "UPDATE poblacion SET num_poblacion = %s WHERE id_poblacion = %s",
                (num_poblacion, existing['id_poblacion'])
            )
            conn.commit()
            return jsonify({'success': True, 'message': 'Población actualizada', 'id': existing['id_poblacion']})

        cursor.execute(
            "INSERT INTO poblacion (num_poblacion, id_encuesta, id_planta) VALUES (%s, %s, %s)",
            (num_poblacion, id_encuesta, id_planta)
        )
        conn.commit()
        return jsonify({'success': True, 'message': 'Población registrada', 'id': cursor.lastrowid})

    except Exception as e:
        if conn:
            conn.rollback()
        app.logger.error("Error en gestionar_poblacion: %s", e)
        return jsonify({'success': False, 'error': 'Error interno'}), 500
    finally:
        if conn:
            conn.close()


@app.route('/api/poblacion/<int:pob_id>', methods=['PUT', 'DELETE'])
@login_required
def mod_poblacion(pob_id):
    """
    Editar (PUT) o eliminar (DELETE) un registro de población por ID.
    ---
    tags:
      - Población
    parameters:
      - in: path
        name: pob_id
        type: integer
        required: true
        description: ID del registro de población.
        example: 3
      - in: body
        name: body
        description: Nuevo valor de población (PUT).
        schema:
          type: object
          properties:
            num_poblacion:
              type: integer
              example: 175
    responses:
      200:
        description: Operación completada correctamente.
      403:
        description: Rol insuficiente.
      500:
        description: Error interno.
    """
    err = _require_admin()
    if err:
        return err
    conn = None
    try:
        conn   = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        if request.method == 'PUT':
            num = (request.json or {}).get('num_poblacion', 0)
            cursor.execute("UPDATE poblacion SET num_poblacion = %s WHERE id_poblacion = %s", (num, pob_id))
            conn.commit()
            return jsonify({'success': True, 'message': 'Población actualizada'})
        cursor.execute("DELETE FROM poblacion WHERE id_poblacion = %s", (pob_id,))
        conn.commit()
        return jsonify({'success': True, 'message': 'Registro eliminado'})
    except Exception as e:
        if conn:
            conn.rollback()
        app.logger.error("Error en mod_poblacion: %s", e)
        return jsonify({'success': False, 'error': 'Error interno'}), 500
    finally:
        if conn:
            conn.close()


# =================================================================
# 20. REPORTE WORD
# =================================================================

@app.route('/api/reporte/generar', methods=['POST'])
@login_required
def generar_reporte_word():
    """
    Generar reporte ejecutivo en formato Word (.docx).
    Incluye la gráfica de barras actual, el top 3 y bottom 3 de categorías
    y el conteo total de colaboradores con los filtros aplicados.
    El rol consulta no puede exportar reportes y recibe 403.
    ---
    tags:
      - Reportes
    consumes:
      - application/json
    parameters:
      - in: body
        name: body
        description: Configuración del reporte (todos los campos son opcionales).
        schema:
          type: object
          properties:
            periodo:
              type: integer
              description: ID del periodo a reportar.
              example: 2
            planta:
              type: string
              description: Nombre de la planta o GENERAL para todas.
              example: CANELS
            image:
              type: string
              description: Imagen de la gráfica en base64 (data:image/png;base64,...).
              example: "data:image/png;base64,iVBORw0KGgo..."
            genero:
              type: string
              description: Filtro de género.
              example: Femenino
            antiguedad:
              type: string
              description: "Filtro de antigüedad: 1 | 1-5 | 5+"
              example: "5+"
            area:
              type: string
              description: Nombre exacto del área.
              example: Producción
    responses:
      200:
        description: Archivo Word descargable.
        headers:
          Content-Disposition:
            description: Nombre del archivo generado.
            type: string
            example: 'attachment; filename="Reporte_CANELS_20260321_113045.docx"'
      403:
        description: El rol Consulta no puede exportar reportes.
      500:
        description: Error interno.
    """
    if hasattr(current_user, 'rol') and current_user.rol == 'consulta':
        return jsonify({'success': False, 'error': 'Acceso denegado. El rol Consulta no puede exportar reportes.'}), 403

    conn = None
    try:
        data          = request.json or {}
        periodo_id    = data.get('periodo')
        planta_nombre = data.get('planta') or "GENERAL"
        chart_image   = data.get('image')
        genero        = data.get('genero')
        antiguedad    = data.get('antiguedad')
        area          = data.get('area')

        conn   = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        base_query = """
            FROM respuestas r
            JOIN empleados e  ON r.id_empleado  = e.id_empleado
            JOIN plantas p    ON e.id_planta    = p.id_planta
            LEFT JOIN areas a ON e.id_area      = a.id_area
            JOIN preguntas pr ON r.id_pregunta  = pr.id_pregunta
            WHERE r.valor > 0
        """
        params = []

        if periodo_id:
            base_query += """
                AND e.id_empleado IN (
                    SELECT DISTINCT r2.id_empleado
                    FROM respuestas r2
                    JOIN preguntas pr2 ON r2.id_pregunta = pr2.id_pregunta
                    WHERE pr2.id_encuesta = %s
                )
            """
            params.append(periodo_id)
        if planta_nombre not in ('Todas', 'GENERAL'):
            base_query += " AND p.nombre = %s"; params.append(planta_nombre)
        if genero and genero not in ('Todos', 'Género (Todos)'):
            if genero in ('F', 'Femenino'):
                base_query += " AND (e.genero LIKE 'Fem%' OR e.genero = 'F')"
            elif genero in ('M', 'Masculino'):
                base_query += " AND (e.genero LIKE 'Masc%' OR e.genero = 'M')"
            else:
                base_query += " AND e.genero = %s"; params.append(genero)
        if area and area not in ('Todas', 'Áreas (Todas)'):
            base_query += " AND a.nombre = %s"; params.append(area)
        if antiguedad and antiguedad not in ('Todas', 'Antigüedad (Todas)'):
            if 'Menos' in antiguedad or antiguedad == '1':
                base_query += " AND e.meses_antiguedad < 12"
            elif '1 a 5' in antiguedad or antiguedad == '1-5':
                base_query += " AND e.meses_antiguedad BETWEEN 12 AND 60"
            elif 'Más de 5' in antiguedad or antiguedad == '5+':
                base_query += " AND e.meses_antiguedad > 60"

        cursor.execute(f"SELECT COUNT(DISTINCT e.id_empleado) AS total {base_query}", tuple(params))
        total_trabajadores = cursor.fetchone()['total']

        cursor.execute(
            f"SELECT pr.categoria, AVG(r.valor) AS promedio {base_query} "
            f"AND pr.categoria IS NOT NULL GROUP BY pr.categoria ORDER BY promedio DESC",
            tuple(params)
        )
        processed_data = [
            (r['categoria'], round((float(r['promedio']) / 7.0) * 100, 1))
            for r in cursor.fetchall()
        ]
        top_3    = processed_data[:3]
        bottom_3 = sorted(processed_data[-3:], key=lambda x: x[1])

        periodo_txt = "Todos los tiempos"
        if periodo_id:
            cursor.execute("SELECT nombre FROM encuestas WHERE id_encuesta = %s", (periodo_id,))
            res_p = cursor.fetchone()
            if res_p:
                periodo_txt = res_p['nombre']

        file_stream = generate_word_report({
            'planta': planta_nombre, 'periodo': periodo_txt,
            'total_trabajadores': total_trabajadores,
            'chart_image': chart_image,
            'top_3': top_3, 'bottom_3': bottom_3,
            'filtros': {
                'genero':     genero     or 'Todos',
                'antiguedad': antiguedad or 'Todas',
                'area':       area       or 'Todas'
            }
        })
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return send_file(
            file_stream, as_attachment=True,
            download_name=f"Reporte_{planta_nombre}_{timestamp}.docx",
            mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )
    except Exception as e:
        app.logger.error("Error en generar_reporte_word: %s", e)
        return jsonify({'error': 'Error interno'}), 500
    finally:
        if conn:
            conn.close()


# =================================================================
# 21. VALIDACIÓN Y GENERACIÓN DE CONTRASEÑAS (rutas públicas)
# =================================================================

@app.route('/api/validate-password', methods=['POST'])
@limiter.limit("30 per minute")
def validate_password_strength():
    """
    Evaluar la fortaleza de una contraseña en tiempo real.
    No requiere sesión activa. Se usa en el formulario de registro
    para dar retroalimentación inmediata al usuario mientras escribe.
    ---
    tags:
      - Seguridad
    consumes:
      - application/json
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - password
          properties:
            password:
              type: string
              description: Contraseña a evaluar.
              example: "MiPassword2024!"
    responses:
      200:
        description: Resultado de la evaluación.
        schema:
          type: object
          properties:
            is_valid:
              type: boolean
              example: true
              description: true si la puntuación supera 60/100.
            score:
              type: integer
              example: 85
              description: Puntuación de 0 a 100.
            strength:
              type: string
              example: Fuerte
              description: "Muy Débil | Débil | Media | Fuerte | Muy Fuerte"
            issues:
              type: array
              items:
                type: string
              example: []
              description: Lista de problemas detectados en la contraseña.
            suggestions:
              type: array
              items:
                type: string
              example: ["Muy buena contraseña"]
              description: Sugerencias para mejorar.
            complexity:
              type: integer
              example: 4
              description: Número de tipos de caracteres utilizados (0-4).
      500:
        description: Error interno.
    """
    try:
        data     = request.get_json() or {}
        password = data.get('password', '')
        if not password:
            return jsonify({'is_valid': False, 'score': 0, 'strength': 'Muy Débil', 'message': 'Ingresa una contraseña'})
        result = PasswordValidator.validate_password(password)
        return jsonify({
            'is_valid':    result['is_valid'],
            'score':       result['score'],
            'strength':    result['strength'],
            'issues':      result['issues'],
            'suggestions': result['suggestions'],
            'complexity':  result['complexity']
        })
    except Exception as e:
        app.logger.error("Error en validate_password_strength: %s", e)
        return jsonify({'error': 'Error interno'}), 500


@app.route('/api/generate-password', methods=['GET'])
@limiter.limit("20 per minute")
def generate_secure_password():
    """
    Generar una contraseña segura de forma automática.
    No requiere sesión activa. Se usa en el formulario de registro
    para que el usuario pueda obtener una contraseña válida con un clic.
    ---
    tags:
      - Seguridad
    parameters:
      - in: query
        name: type
        type: string
        required: false
        description: "Tipo de contraseña: secure (16 caracteres, default) | memorable (fácil de recordar)"
        enum: [secure, memorable]
        example: secure
    responses:
      200:
        description: Contraseña generada con su evaluación de fortaleza.
        schema:
          type: object
          properties:
            password:
              type: string
              example: "K7#mP9@xL2&qW5nR"
            score:
              type: integer
              example: 92
            strength:
              type: string
              example: "Muy Fuerte"
            is_valid:
              type: boolean
              example: true
      500:
        description: Error interno.
    """
    try:
        type_pwd = request.args.get('type', 'secure')
        password = (
            PasswordGenerator.generate_memorable()
            if type_pwd == 'memorable'
            else PasswordGenerator.generate_secure(16)
        )
        result = PasswordValidator.validate_password(password)
        return jsonify({
            'password': password,
            'score':    result['score'],
            'strength': result['strength'],
            'is_valid': result['is_valid']
        })
    except Exception as e:
        app.logger.error("Error en generate_secure_password: %s", e)
        return jsonify({'error': 'Error interno'}), 500


# =================================================================
# 22. PUNTO DE ENTRADA
# =================================================================

if __name__ == '__main__':
    load_dotenv()
    try:
        ensure_superadmin_exists()
    except Exception as e:
        print(f"[CANELS] Aviso: Error al asegurar superadmin: {e}")

    server_host = os.getenv('SERVER_HOST', '0.0.0.0')
    server_port = int(os.getenv('SERVER_PORT', 5000))
    debug_mode  = os.getenv('DEBUG_MODE', 'False').lower() == 'true'

    print("\n" + "=" * 60)
    print("  CANELS — Sistema de Encuestas de Satisfacción")
    print("=" * 60)
    print(f"  -> Local:    http://localhost:{server_port}")
    print(f"  -> Swagger:  http://localhost:{server_port}/apidocs")
    print(f"  -> Debug:    {'ON (desarrollo)' if debug_mode else 'OFF (producción)'}")
    print("=" * 60 + "\n")

    app.run(debug=debug_mode, host=server_host, port=server_port, use_reloader=debug_mode)