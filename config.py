# config.py
import os
from dotenv import load_dotenv
from datetime import timedelta

load_dotenv()

class Config:
    # -- Base de Datos 
    DB_HOST     = os.getenv('DB_HOST', 'localhost')
    DB_USER     = os.getenv('DB_USER', 'root')
    DB_PASSWORD = os.getenv('DB_PASSWORD', '')
    DB_NAME     = os.getenv('DB_NAME', 'canels_db')

    # -- Seguridad de Sesión
    SECRET_KEY = os.getenv('SECRET_KEY')
    if not SECRET_KEY:
        raise RuntimeError(
            "SECRET_KEY no configurada. Define SECRET_KEY en el archivo  .env"
        )

    SESSION_COOKIE_HTTPONLY  = True
    SESSION_COOKIE_SECURE    = os.getenv('HTTPS_ENABLED', 'false').lower() == 'true'
    SESSION_COOKIE_SAMESITE  = 'Lax'
    SESSION_COOKIE_NAME      = 'canels_session'

    # Timeout en segundos (server-side - no depende del cookie)
    # 72 segundos para pruebas - cambiar a 3600 en producción
    SESSION_TIMEOUT_SECONDS  = 3600

    # -- CSRF 
    WTF_CSRF_ENABLED         = True
    WTF_CSRF_TIME_LIMIT      = 3600

    # -- Producción 
    DEBUG = os.getenv('DEBUG_MODE', 'false').lower() == 'true'
    TESTING = False

    # -- Archivos 
    UPLOAD_FOLDER = 'uploads'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024

    # Y validar tipo MIME en la ruta de importación:
    ALLOWED_EXTENSIONS = {'xlsx'}
    
    @staticmethod
    def allowed_file(filename):
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in Config.ALLOWED_EXTENSIONS

    # -- Clave Maestra 
    MASTER_KEY = os.getenv('MASTER_KEY')
    if not MASTER_KEY:
        raise RuntimeError(
            "MASTER_KEY no configurada. Define MASTER_KEY en el archivo .env"
        )

    # -- SuperAdmin 
    SUPERADMIN_USERNAME = os.getenv('SUPERADMIN_USERNAME', '')
    SUPERADMIN_PASSWORD = os.getenv('SUPERADMIN_PASSWORD', '')

    # -- MySQL (Windows) 
    _bin_path_raw = os.getenv('MYSQL_BIN_PATH', '')
    _bin_path     = _bin_path_raw.replace('"', '').replace("'", '').strip()
    MYSQL_DUMP    = os.path.join(_bin_path, 'mysqldump.exe')
    MYSQL_EXE     = os.path.join(_bin_path, 'mysql.exe')

    # -- Servidor 
    SERVER_HOST = os.getenv('SERVER_HOST', '0.0.0.0')
    SERVER_PORT = int(os.getenv('SERVER_PORT', 5000))