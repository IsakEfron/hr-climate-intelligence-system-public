#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de inicialización para Canels - Sistema de Gestión de Encuestas
Automatiza la configuración inicial del sistema

CÓMO FUNCIONA:
  Al ejecutar con el Python del sistema, el script:
    1. Instala python-dotenv en el sistema (si hace falta)
    2. Crea el entorno virtual
    3. Instala todas las dependencias dentro del venv
    4. Se RE-LANZA a sí mismo usando el Python del venv  <- punto clave
    5. Con las librerías ya disponibles, configura .env, BD y datos iniciales

  El usuario solo necesita ejecutar UNA vez:
      python setup.py
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

# ============================================================================
# DETECCIÓN DE FASE - ¿Estamos en el Python del sistema o en el venv?
# ============================================================================

_PROJECT_ROOT = Path(__file__).parent
_VENV_PATH    = _PROJECT_ROOT / 'venv'
_IS_WINDOWS   = sys.platform.startswith('win')

_VENV_PYTHON = (
    _VENV_PATH / 'Scripts' / 'python.exe' if _IS_WINDOWS
    else _VENV_PATH / 'bin' / 'python'
)

def _running_in_venv() -> bool:
    """True si este intérprete ES el Python del entorno virtual de Canels."""
    try:
        return Path(sys.executable).resolve() == _VENV_PYTHON.resolve()
    except Exception:
        return False

def _in_phase2() -> bool:
    return os.environ.get('CANELS_PHASE2') == '1' or _running_in_venv()


# ============================================================================
# FASE 1 - Python del SISTEMA
# Solo prepara el venv y se relanza. Sin imports de mysql/bcrypt/etc.
# ============================================================================

def _phase1_bootstrap():
    """Prepara el entorno virtual y relanza el script con el Python del venv."""

    def _title(msg):
        print(f"\n{'='*60}\n  {msg}\n{'='*60}")
    def _ok(msg):   print(f"  Correcto  {msg}")
    def _err(msg):  print(f"  Error     {msg}")
    def _info(msg): print(f"  Informacion!  {msg}")

    print("""
    ============================================================
          CANELS - SETUP INICIAL  (Preparando entorno)
      Sistema de Gestion de Encuestas de Satisfaccion
    ============================================================
    """)

    # -- Paso 0: Verificar versión de Python -------------------------─
    _title("1. Verificando version de Python")
    vi = sys.version_info
    if (vi.major, vi.minor) < (3, 7):
        _err(f"Python 3.7+ requerido. Version actual: {vi.major}.{vi.minor}")
        sys.exit(1)
    _ok(f"Python {vi.major}.{vi.minor}.{vi.micro} detectado")

    # -- Paso 1: Asegurar python-dotenv en el sistema -----------------------─
    _title("2. Verificando python-dotenv en el sistema")
    try:
        import dotenv  # noqa: F401
        _ok("python-dotenv ya disponible en el sistema")
    except ImportError:
        _info("Instalando python-dotenv en el sistema...")
        subprocess.check_call(
            [sys.executable, '-m', 'pip', 'install', 'python-dotenv', '--quiet']
        )
        _ok("python-dotenv instalado")

    # -- Paso 2: Crear entorno virtual -------------------------
    _title("3. Creando entorno virtual")
    if _VENV_PATH.exists():
        _ok(f"Entorno virtual '{_VENV_PATH.name}' ya existe")
    else:
        _info(f"Creando entorno virtual en {_VENV_PATH}...")
        try:
            subprocess.check_call([sys.executable, '-m', 'venv', str(_VENV_PATH)])
            _ok("Entorno virtual creado correctamente")
        except subprocess.CalledProcessError as e:
            _err(f"No se pudo crear el entorno virtual: {e}")
            sys.exit(1)

    # -- Paso 3: Instalar dependencias dentro del venv -----------------------
    _title("4. Instalando dependencias en el entorno virtual")
    req_file = _PROJECT_ROOT / 'requirements.txt'
    if not req_file.exists():
        _err("Archivo requirements.txt no encontrado")
        sys.exit(1)

    venv_pip = (
        _VENV_PATH / 'Scripts' / 'pip.exe' if _IS_WINDOWS
        else _VENV_PATH / 'bin' / 'pip'
    )
    _info("Esto puede tardar unos minutos la primera vez...")
    result = subprocess.run(
        [str(venv_pip), 'install', '-r', str(req_file)],
        cwd=str(_PROJECT_ROOT)
    )
    if result.returncode != 0:
        _err("Fallo la instalacion de dependencias.")
        sys.exit(1)
    _ok("Dependencias instaladas correctamente en el entorno virtual")

    # -- Paso 4: Relanzar con el Python del venv -----------------------
    _title("5. Relanzando instalador con el entorno virtual")
    _info(f"Usando: {_VENV_PYTHON}")
    _info("Ahora estan disponibles mysql-connector, bcrypt, etc.\n")

    env = os.environ.copy()
    env['CANELS_PHASE2'] = '1'

    result = subprocess.run(
        [str(_VENV_PYTHON), str(__file__)],
        env=env,
        cwd=str(_PROJECT_ROOT)
    )
    sys.exit(result.returncode)


# ============================================================================
# FASE 2 - Python del VENV (todas las librerías disponibles)
# ============================================================================

class CanelsSetup:
    def __init__(self):
        self.project_root = _PROJECT_ROOT
        self.env_file     = self.project_root / '.env'
        self.env_example  = self.project_root / '.env.example'
        self.venv_path    = _VENV_PATH
        self.is_windows   = _IS_WINDOWS
        self.venv_python  = _VENV_PYTHON
        self.venv_pip     = (
            self.venv_path / 'Scripts' / 'pip.exe' if self.is_windows
            else self.venv_path / 'bin' / 'pip'
        )

    # -- Utilidades de impresion -------------------------

    def print_header(self, message):
        print(f"\n{'='*60}\n  {message}\n{'='*60}")

    def print_success(self, message):
        print(f"Correcto {message}")

    def print_error(self, message):
        print(f"Error {message}")

    def print_info(self, message):
        print(f"Informacion! {message}")

    def print_warning(self, message):
        print(f"Advertencia  {message}")

    # -- Paso 1: Verificar Python -------------------------

    def check_python_version(self):
        self.print_header("1. Verificando version de Python")
        vi = sys.version_info
        if (vi.major, vi.minor) >= (3, 7):
            self.print_success(
                f"Python {vi.major}.{vi.minor}.{vi.micro} "
                f"(entorno virtual activo)"
            )
            return True
        self.print_error(
            f"Python 3.7+ requerido. Version actual: {vi.major}.{vi.minor}"
        )
        return False

    # -- Paso 2: Entorno virtual -------------------------

    def create_virtual_env(self):
        self.print_header("2. Verificando entorno virtual")
        if self.venv_path.exists():
            self.print_success(f"Entorno virtual '{self.venv_path.name}' listo")
            return True
        try:
            subprocess.check_call([sys.executable, '-m', 'venv', str(self.venv_path)])
            self.print_success("Entorno virtual creado")
            return True
        except subprocess.CalledProcessError as e:
            self.print_error(f"Error creando entorno virtual: {e}")
            return False

    # -- Paso 3: Archivo .env -----------------------

    def create_env_file(self):
        self.print_header("3. Configurando archivo de entorno (.env)")

        if self.env_file.exists():
            self.print_info("Archivo .env ya existe")
            return True

        if not self.env_example.exists():
            self.print_error("Archivo .env.example no encontrado")
            return False

        try:
            shutil.copy(str(self.env_example), str(self.env_file))
            self.print_success("Archivo .env creado desde .env.example")
            self.print_warning(
                "IMPORTANTE: Edita el archivo .env con tus credenciales reales"
            )
            return True
        except Exception as e:
            self.print_error(f"Error creando .env: {e}")
            return False

    # -- Paso 4: Verificar dependencias -------------------------

    def install_dependencies(self):
        self.print_header("4. Verificando dependencias")
        try:
            import mysql.connector  # noqa: F401
            import bcrypt            # noqa: F401
            self.print_success(
                "Todas las dependencias disponibles en el entorno virtual"
            )
            return True
        except ImportError as e:
            self.print_error(f"Dependencia faltante: {e}")
            self.print_info("Intentando instalar desde requirements.txt...")
            req = self.project_root / 'requirements.txt'
            if not req.exists():
                self.print_error("requirements.txt no encontrado")
                return False
            result = subprocess.run(
                [str(self.venv_pip), 'install', '-r', str(req)],
                cwd=str(self.project_root)
            )
            return result.returncode == 0

    # -- Paso 5: Base de datos -------------------------

    def check_database_connection(self):
        self.print_header("5. Creando/Verificando Base de Datos")

        from dotenv import load_dotenv
        load_dotenv(str(self.env_file))

        try:
            import mysql.connector

            db_host     = os.getenv('DB_HOST', 'localhost')
            db_user     = os.getenv('DB_USER', 'root')
            db_password = os.getenv('DB_PASSWORD', '')
            db_name     = os.getenv('DB_NAME', 'canels_db')

            self.print_info(f"Conectando a {db_host}...")

            conn = mysql.connector.connect(
                host=db_host,
                user=db_user,
                password=db_password,
                connection_timeout=10
            )

            if not conn.is_connected():
                self.print_error("No se pudo establecer conexion")
                return False

            self.print_success(
                f"Conectado a MySQL Server version {conn.get_server_info()}"
            )
            cursor = conn.cursor()

            # Crear BD si no existe
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{db_name}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
            self.print_success(f"Base de datos '{db_name}' lista")
            cursor.execute(f"USE `{db_name}`")
            self.print_success(f"Usando base de datos: {db_name}")

            # Importar schema si existe
            schema_file = self.project_root / 'database' / 'schema.sql'
            if schema_file.exists():
                self.print_info("Importando estructura de base de datos...")
                with open(schema_file, 'r', encoding='utf-8') as f:
                    sql_content = f.read()

                for statement in sql_content.split(';'):
                    stmt = statement.strip()
                    if stmt:
                        try:
                            cursor.execute(stmt)
                        except mysql.connector.Error as e:
                            if ('already exists' not in str(e)
                                    and 'unknown table' not in str(e).lower()):
                                pass
                conn.commit()
                self.print_success("Estructura de base de datos importada")
            else:
                self.print_warning(
                    f"Archivo schema.sql no encontrado en {schema_file}"
                )

            cursor.execute(
                "SELECT COUNT(*) FROM information_schema.TABLES "
                "WHERE TABLE_SCHEMA = %s",
                (db_name,)
            )
            table_count = cursor.fetchone()[0]
            self.print_success(f"Tablas en la BD: {table_count}")

            cursor.close()
            conn.close()
            return True

        except Exception as e:
            self.print_error(f"Error con la base de datos: {e}")
            self.print_warning("Asegurate de que:")
            self.print_warning("  1. MySQL este corriendo")
            self.print_warning("  2. Las credenciales en .env sean correctas")
            self.print_warning(
                "  3. El usuario de MySQL tenga permiso para crear bases de datos"
            )
            return False

    # -- Paso 6: Datos iniciales -------------------------

    def load_initial_data(self):
        self.print_header("6. Cargando plantas iniciales")

        try:
            import mysql.connector
        except ImportError:
            self.print_warning(
                "mysql.connector no disponible, saltando carga de plantas"
            )
            return True

        plantas_iniciales = [
            "CANELS", "CEDIS", "CORPORATIVO",
            "GANA", "LA VICTORIA", "ULTRA"
        ]

        try:
            from dotenv import load_dotenv
            load_dotenv(str(self.env_file))

            conn = mysql.connector.connect(
                host=os.getenv('DB_HOST', 'localhost'),
                user=os.getenv('DB_USER', 'root'),
                password=os.getenv('DB_PASSWORD', ''),
                database=os.getenv('DB_NAME', 'canels_db'),
                connection_timeout=10
            )
            cursor = conn.cursor()

            plantas_insertadas = 0
            for planta in plantas_iniciales:
                try:
                    cursor.execute(
                        "INSERT INTO plantas (nombre) VALUES (%s)", (planta,)
                    )
                    plantas_insertadas += 1
                except mysql.connector.Error:
                    pass  # Ya existe, continuar

            conn.commit()

            if plantas_insertadas > 0:
                self.print_success(f"Plantas cargadas: {plantas_insertadas}")
            else:
                self.print_info("Todas las plantas ya existian")

            cursor.close()
            conn.close()
            return True

        except Exception as e:
            self.print_warning(f"No se pudieron cargar plantas: {e}")
            return True  # No es critico

    # -- Instrucciones finales -------------------------

    def print_next_steps(self):
        self.print_header("Instalacion completada")

        activate  = (
            r"venv\Scripts\activate" if self.is_windows
            else "source venv/bin/activate"
        )
        start_cmd = "iniciar.bat" if self.is_windows else "./iniciar.sh"

        print(f"""
PROXIMOS PASOS:

1. CONFIGURAR ARCHIVO .env:
   - Abre el archivo .env
   - Actualiza tus credenciales reales:
     * DB_PASSWORD: Tu contrasena de MySQL
     * SECRET_KEY: Algo unico (opcional)
     * MASTER_KEY: Para crear usuarios

2. INICIAR SERVIDOR:

   Windows: Doble clic en iniciar.bat
   Linux/Mac: ./iniciar.sh

   O manualmente:
   $ {activate}
   $ python app.py

3. ACCEDER:
   - Abre: http://localhost:5000
   - Crea tu primer usuario
   - Login y comienza a usar

4. IMPORTAR DATOS (opcional):
   - Como Admin: DATOS -> Importar Excel
   - Sube tu archivo con empleados y respuestas
   - El sistema los asignara a las plantas existentes

PLANTAS CARGADAS:
   CANELS, CEDIS, CORPORATIVO, GANA, LA VICTORIA, ULTRA

Para cambiar plantas:
  Lee: PLANTAS_REFERENCIA.txt
  O: Seccion 7 en INSTALACION.txt

Lee INSTALACION.txt para mas detalles.
        """)

    # -- Orquestador principal -------------------------

    def run(self):
        print("""
    ============================================================
          CANELS - SETUP INICIAL  (Configurando sistema)
      Sistema de Gestion de Encuestas de Satisfaccion
    ============================================================
        """)

        steps = [
            ("Verificacion de Python",      self.check_python_version),
            ("Verificacion del venv",        self.create_virtual_env),
            ("Creacion de .env",             self.create_env_file),
            ("Verificacion de dependencias", self.install_dependencies),
            ("Verificacion de BD",           self.check_database_connection),
            ("Carga de datos iniciales",     self.load_initial_data),
        ]

        passed = 0
        failed = 0

        for name, step_fn in steps:
            try:
                if step_fn():
                    passed += 1
                else:
                    failed += 1
            except Exception as e:
                self.print_error(f"Excepcion en '{name}': {e}")
                failed += 1

        print(f"\n{'='*60}")
        print(f"Verificaciones: {passed} OK, {failed} errores")
        print(f"{'='*60}")

        if failed == 0:
            self.print_next_steps()
            return True
        else:
            self.print_error("Hay problemas que resolver antes de continuar")
            return False


# ============================================================================
# PUNTO DE ENTRADA
# ============================================================================

if __name__ == '__main__':
    if _in_phase2():
        # Ya estamos en el venv: ejecutar la configuracion completa
        setup = CanelsSetup()
        success = setup.run()
        sys.exit(0 if success else 1)
    else:
        # Estamos en el Python del sistema: preparar venv y relanzar
        _phase1_bootstrap()