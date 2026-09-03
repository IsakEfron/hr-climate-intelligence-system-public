# Guía de Instalación — CANELS

Guía completa para instalar CANELS desde cero en Windows o Linux.

---

## Requisitos Previos

Antes de instalar, verifica que tienes lo siguiente:

| Requisito | Versión mínima | Verificar |
|---|---|---|
| Python | 3.9+ (probado en 3.12.10) | `python --version` |
| MySQL | 8.0+ (probado en 8.0.45) | `mysql --version` |
| Espacio en disco | ~400 MB | — |
| RAM | 1 GB mínimo, 2 GB recomendado | — |

### Instalar Python

Descargar desde https://www.python.org/downloads/  
Durante la instalación en Windows, marcar **"Add Python to PATH"**.

### Instalar MySQL

Descargar MySQL Community Server desde https://dev.mysql.com/downloads/mysql/  
Alternativamente, puedes usar XAMPP (https://www.apachefriends.org/) que incluye MySQL.

---

## Instalación Automática (Recomendado)

El instalador `setup.py` automatiza todo: entorno virtual, dependencias, base de datos, esquema y datos iniciales. Solo necesitas ejecutarlo una vez.

### Paso 1 — Obtener el proyecto

```bash
git clone https://github.com/IsakEfron/Canels_SI_ACL.git
cd canels
```

O descarga el ZIP desde GitHub y extráelo.

### Paso 2 — Ejecutar el instalador

```powershell
python setup.py    # Windows
python3 setup.py   # Linux/Mac
```

El instalador realiza automáticamente:
- Crea el entorno virtual (`venv/`)
- Instala todas las dependencias de `requirements.txt`
- Genera el archivo `.env` desde `.env.example`
- Crea la base de datos si no existe
- Importa el esquema desde `database/schema.sql`
- Carga las plantas iniciales: CANELS, CEDIS, CORPORATIVO, GANA, LA VICTORIA, ULTRA

### Paso 3 — Configurar `.env`

Abre el archivo `.env` que se generó y edita las credenciales con tus datos reales:

```env
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=tu_contraseña_mysql
DB_NAME=canels_db
SECRET_KEY=<generar_con_comando_abajo>
MASTER_KEY=clave_maestra_segura
SUPERADMIN_USERNAME=superadmin
SUPERADMIN_PASSWORD=contraseña_segura
MYSQL_BIN_PATH="C:\Program Files\MySQL\MySQL Server 8.0\bin"
SERVER_HOST=0.0.0.0
SERVER_PORT=5000
DEBUG_MODE=true
```

Generar una `SECRET_KEY` segura:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### Paso 4 — Iniciar CANELS

```bash
iniciar.bat    # Windows (doble clic o desde terminal)
./iniciar.sh   # Linux/Mac
```

Accede en el navegador: **http://localhost:5000**

> Si el instalador falla al conectar a MySQL, verifica que el servicio esté activo y que las credenciales en `.env` sean correctas, luego vuelve a ejecutar `python setup.py`.

---

## Instalación Manual

Sigue esta ruta si prefieres control total del proceso o si el instalador automático no está disponible. Aquí debes realizar a mano todo lo que `setup.py` haría automáticamente.

### 1. Crear entorno virtual

```bash
python -m venv venv
```

### 2. Activar el entorno

```powershell
venv\Scripts\activate       # Windows PowerShell
venv\Scripts\activate.bat   # Windows CMD
source venv/bin/activate    # Linux/Mac
```

### 3. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 4. Configurar `.env`

```bash
copy .env.example .env      # Windows
cp .env.example .env        # Linux/Mac
```

Edita el archivo `.env` con tus credenciales (ver estructura en el Paso 3 de instalación automática).

### 5. Crear la base de datos e importar el esquema

Conecta a MySQL y crea la base de datos:

```sql
CREATE DATABASE canels_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

Importa el esquema desde la terminal del proyecto:

```bash
mysql -u root -p canels_db < database/schema.sql
```

### 6. Insertar las plantas iniciales

A diferencia de `setup.py`, en la instalación manual debes insertar las plantas tú mismo. Conéctate a MySQL y ejecuta:

```sql
USE canels_db;

INSERT INTO plantas (nombre) VALUES
  ('CANELS'),
  ('CEDIS'),
  ('CORPORATIVO'),
  ('GANA'),
  ('LA VICTORIA'),
  ('ULTRA');
```

> Si tu organización tiene nombres de planta diferentes, ajusta estos valores. Los nombres deben coincidir exactamente con los que aparecen en los archivos Excel exportados de Google Forms (distingue mayúsculas y espacios).

### 7. Ejecutar la aplicación

```bash
python app.py
```

---

## Verificación de la Instalación

**Entorno y dependencias:**
```bash
python --version    # Debe mostrar 3.9+
pip list            # Debe listar Flask, pandas, mysql-connector-python, etc.
```

**Base de datos:**
```sql
USE canels_db;
SHOW TABLES;                  -- Debe listar todas las tablas del esquema
SELECT nombre FROM plantas;   -- Debe mostrar las 6 plantas
```

**Aplicación:**
1. Ejecutar `python app.py` o el script de inicio
2. Abrir http://localhost:5000
3. Debe aparecer la página de login
4. Iniciar sesión con las credenciales del SuperAdmin definidas en `.env`

---

## Solución de Problemas

**"python no se reconoce como comando"**  
Python no está en el PATH. Reinstálalo marcando "Add Python to PATH" o usa la ruta completa.

**"No module named 'flask'"**  
El entorno virtual no está activo. Actívalo primero y reinstala:
```bash
venv\Scripts\activate
pip install -r requirements.txt
```

**"MySQL Connection refused"**  
Verifica que el servicio MySQL esté corriendo, que las credenciales en `.env` sean correctas y que la base de datos `canels_db` exista.

**"Port 5000 already in use"**  
Cambia `SERVER_PORT` en `.env` a otro valor como `5001`.

**"venv no se activa" en PowerShell**
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

**Error en `schema.sql` al importar**  
Elimina la BD y recréala antes de importar:
```sql
DROP DATABASE IF EXISTS canels_db;
CREATE DATABASE canels_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

**El dashboard muestra "0 empleados" tras importar**  
El nombre de la planta en el Excel no coincide con el registrado en la BD. Verifica `SELECT nombre FROM plantas;` y compáralo con la columna "Planta:" del Excel. La comparación es exacta (mayúsculas y espacios cuentan).

---

## Próximos Pasos

Una vez instalado:

1. Acceder a http://localhost:5000 con las credenciales del SuperAdmin
2. Ir a **Importación** y cargar el primer Excel exportado de Google Forms
3. Verificar que el dashboard muestra los datos importados correctamente
4. Crear usuarios adicionales (Admin, Analista, Consulta) desde la sección de usuarios

Para acceso desde otras PCs en la red -> ver [ACCESO_RED_LOCAL.md](ACCESO_RED_LOCAL.md)  
Para despliegue en servidor de producción -> ver [PROPUESTA_PRODUCCION.md](PROPUESTA_PRODUCCION.md)