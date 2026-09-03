# Sistema de Clima Laboral

![Version](https://img.shields.io/badge/version-2.1.0-blue.svg)
![Python](https://img.shields.io/badge/python-3.12.10-brightgreen.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Status](https://img.shields.io/badge/status-production-success.svg)

**Plataforma profesional para la gestión integral, importación, análisis y visualización de encuestas de clima laboral con reportes avanzados y control administrativo seguro.**

---

## Tabla de Contenidos

- [Descripción General](#descripción-general)
- [Características Principales](#características-principales)
- [Requisitos del Sistema](#requisitos-del-sistema)
- [Instalación Rápida](#instalación-rápida)
- [Estructura del Proyecto](#estructura-del-proyecto)
- [Documentación](#documentación)
- [Funciones Principales](#funciones-principales)
- [Roles y Permisos](#roles-y-permisos)
- [Licencias y Atribuciones](#licencias-y-atribuciones)
- [Seguridad](#seguridad)
- [Soporte y FAQ](#soporte-y-faq)

---

## Descripción General

**CANELS** es el sistema interno de clima laboral de **Canel's**, desarrollado para capturar, procesar, analizar y reportar el nivel de satisfacción de los colaboradores a través de encuestas periódicas aplicadas en todas las plantas y áreas de la organización.

El sistema centraliza todo el ciclo de vida de las encuestas de clima laboral: desde la importación masiva de respuestas recolectadas en Google Forms hasta la generación de reportes ejecutivos en Word y Excel, pasando por dashboards interactivos con filtros por planta, área, género y antigüedad.

Diseñado para:
- **RRHH y áreas de Bienestar** que necesitan analizar el clima laboral por planta y categoría
- **Administradores** que requieren control total del sistema y gestión de usuarios
- **Analistas** que necesitan explorar y exportar datos para análisis adicionales
- **Usuarios de consulta** que requieren acceso seguro y controlado a los resultados

---

## Características Principales

### Gestión de Encuestas
- Importación masiva de respuestas desde archivos Excel exportados de Google Forms
- Detección automática de preguntas y categorías al importar
- Gestión de periodos de encuesta (crear, renombrar, eliminar)
- Gestión de preguntas por periodo (crear, editar, eliminar)
- Almacenamiento seguro en base de datos MySQL

### Autenticación y Control de Acceso
- Sistema de login con sesiones cifradas (Flask-Login)
- Cuatro niveles de acceso: SuperAdministrador, Administrador, Analista y Consulta
- Rate limiting y protección contra fuerza bruta por IP y por usuario
- Modo de mantenimiento con expulsión automática de usuarios no autorizados
- Expiración automática de sesión por inactividad (1 hora)

### Análisis y Visualización
- Dashboard interactivo con estadísticas en tiempo real
- KPIs de plantas, empleados encuestados y áreas
- Gráfico de barras por planta, gráfico de dona por distribución y evolución histórica
- Análisis detallado por categoría, planta, área, género y antigüedad
- Comparativas temporales entre periodos

### Generación de Reportes
- Exportación de análisis en Excel con formato profesional
- Reportes ejecutivos en Word con top/bottom 3 categorías
- Backup completo de la base de datos en formato SQL
- Descarga de datos filtrados para análisis externo

### Seguridad
- Protección CSRF en todos los formularios y peticiones AJAX
- Sanitización de inputs y prevención de SQL Injection (prepared statements)
- Headers de seguridad HTTP (CSP, HSTS, X-Frame-Options, etc.)
- Registro de auditoría de todos los eventos críticos
- Bloqueo temporal por intentos fallidos de login

---

## Requisitos del Sistema

| Componente | Mínimo | Probado y Recomendado | Notas |
|---|---|---|---|
| **Python** | 3.9 | **3.12.10** | Versión en producción verificada |
| **MySQL** | 8.0 | **8.0.45** | Versión en producción verificada |
| **RAM** | 1 GB | **2 GB** | 2 GB para rendimiento óptimo |
| **Espacio en Disco** | 400 MB | 1 GB | El proyecto ocupa ~389 MB sin BD |
| **Sistema Operativo** | Windows 10+, Ubuntu 20.04+ | **Windows 10/11** | Probado en Windows; compatible con Linux |
| **Navegadores** | Chrome, Firefox, Edge, Brave, Safari | Versiones actuales | Soporte completo para móviles y tablets |

---

## Instalación Rápida

### Opción 1: Instalador Automático (Recomendado)

```bash
# 1. Clonar o descargar el repositorio
git clone https://github.com/tu-usuario/canels.git
cd canels

# 2. Ejecutar instalador
python setup.py

# 3. Configurar credenciales en .env

# 4. Iniciar servidor
iniciar.bat      # Windows
./iniciar.sh     # Linux/Mac
```

**Acceso:** http://localhost:5000

### Opción 2: Instalación Manual

```bash
# 1. Crear entorno virtual
python -m venv venv

# 2. Activar
venv\Scripts\activate       # Windows
source venv/bin/activate    # Linux/Mac

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Configurar variables de entorno
copy .env.example .env      # Windows
cp .env.example .env        # Linux/Mac
# Editar .env con tus credenciales

# 5. Crear la base de datos (ejecutar database/schema.sql en MySQL)

# 6. Iniciar
python app.py
```

### Variables de Entorno Requeridas (`.env`)

```env
DB_HOST=localhost
DB_USER=tu_usuario
DB_PASSWORD=tu_contraseña
DB_NAME=canels_db

# Generar con: python -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY=<64_caracteres_aleatorios>
MASTER_KEY=<clave_maestra_segura>

SUPERADMIN_USERNAME=superadmin
SUPERADMIN_PASSWORD=<contraseña_segura>

MYSQL_BIN_PATH="C:\Program Files\MySQL\MySQL Server 8.0\bin"

SERVER_HOST=0.0.0.0
SERVER_PORT=5000
DEBUG_MODE=false
HTTPS_ENABLED=false
```

---

## Estructura del Proyecto

```
canels/
│
├── app.py                          # Aplicación Flask — rutas y APIs
├── config.py                       # Configuración centralizada
├── db.py                           # Conexión a la base de datos
├── security.py                     # Módulo de seguridad (CSRF, rate limit, sanitización)
├── setup.py                        # Instalador automático
├── requirements.txt                # Dependencias Python
├── package.json                    # Dependencias Node.js (Tailwind build)
├── .env                            # Variables de entorno (NO incluir en Git)
├── .env.example                    # Plantilla de variables de entorno
├── .gitattributes                  # Configuración de Git
├── iniciar.bat                     # Script de inicio para Windows
├── iniciar.sh                      # Script de inicio para Linux/Mac
├── LICENSE                         # Licencia MIT
├── README.md                       # Este archivo
│
├── utils/                          # Módulos auxiliares Python
│   ├── admin_logic.py              # Backup, restore, reset, importación Excel
│   ├── import_Excel_SQL.py         # Script standalone de importación
│   ├── password_security.py        # Validador y generador de contraseñas
│   └── report_generator.py         # Generador de reportes Word
│
├── static/                         # Recursos estáticos
│   ├── src/
│   │   └── tailwindcss.css         # Build de Tailwind CSS
│   ├── css/
│   │   └── main.css                # Estilos personalizados
│   ├── js/
│   │   ├── csrf.js                 # Utilidad global CSRF (incluir antes que cualquier JS)
│   │   ├── login.js                # Lógica de login y registro
│   │   ├── grafica_dashboard.js    # Gráficas del dashboard (Chart.js)
│   │   ├── grafica_page.js         # Página de gráficos avanzados
│   │   ├── analitica.js            # Módulo de analítica y búsqueda
│   │   ├── update.js               # Gestión de preguntas y población
│   │   ├── modal_imp.js            # Modal de importación
│   │   ├── maintenance.js          # Monitoreo de mantenimiento (polling)
│   │   ├── maintenance_actions.js  # Acciones del panel de mantenimiento
│   │   ├── notifications.js        # Sistema de notificaciones
│   │   └── admin_actions.js        # Acciones administrativas
│   └── img/
│       ├── canels-Logo.png
│       └── canels-icon.png
│
├── templates/                      # Plantillas HTML (Jinja2)
│   ├── login.html                  # Página de login y registro
│   ├── index.html                  # Dashboard principal
│   ├── analitica.html              # Módulo de analítica
│   ├── grafico.html                # Gráficos avanzados y reporte Word
│   ├── update.html                 # Gestión de preguntas y población
│   ├── import_export.html          # Importación, backup, usuarios
│   ├── maintenance.html            # Panel de mantenimiento
│   └── acceso_bloqueado.html       # Página de acceso denegado
│
├── database/
│   └── schema.sql                  # Estructura de la base de datos
│
├── docs/                           # Documentación adicional
│   ├── INSTALACION.md
│   ├── ACCESO_RED_LOCAL.md
│   ├── COMO_USAR_VENV.md
│   ├── ESTRUCTURA_PROYECTO.md
│   └── PROPUESTA_PRODUCCION.md     # Despliegue con IIS + Waitress
│
├── uploads/                        # Archivos temporales (backups, imports, reportes)
└── logs/
    └── security.log                # Log de eventos de seguridad
```

---

## Documentación

| Documento | Para Quién |
|---|---|
| **docs/INSTALACION.md** | Usuarios nuevos — guía paso a paso |
| **docs/ACCESO_RED_LOCAL.md** | Acceso desde otras PCs en la red local |
| **docs/COMO_USAR_VENV.md** | Desarrolladores — entornos virtuales Python |
| **docs/DIAGRAMA_DESPLIEGUE.pdf** | Despliegue en servidor Windows con IIS |
| **docs/ESTRUCTURA_PROYECTO.md** | Referencia completa de archivos y carpetas |

---

## Funciones Principales

### Dashboard (`index.html`)
- KPIs en tiempo real: plantas, empleados encuestados, áreas y satisfacción promedio
- Gráfico de barras por planta, gráfico de dona por distribución y evolución histórica
- Panel de población por planta (encuestados vs. total registrado)
- Selector de periodo de encuesta

### Analítica (`analitica.html`)
- Búsqueda con filtros por planta, área, género, antigüedad y nómina
- Visualización de puntajes por categoría por colaborador
- Filtro por nivel de puntaje con operadores (>, <, =, >=, <=)
- Exportación del resultado filtrado a Excel

### Gráficos (`grafico.html`)
- Gráfico de barras horizontal por categoría con filtros múltiples
- Generación de reporte Word ejecutivo con gráfica y top/bottom 3 categorías

### Gestión de Preguntas (`update.html`)
- Alta, edición y eliminación de preguntas por periodo
- Gestión de población por planta (número de colaboradores objetivo)
- Visualización del esquema importado automáticamente

### Importación y Administración (`import_export.html`)
- Importación de Excel desde Google Forms con detección automática de columnas
- Backup del esquema SQL completo
- Restauración de base de datos desde archivo SQL
- Reinicio de datos protegido con clave maestra
- Gestión de usuarios (crear, consultar, eliminar)

### Mantenimiento (`maintenance.html`)
- Programación de ventanas de mantenimiento con fecha/hora de inicio y fin
- Cancelación de mantenimientos activos
- Historial de eventos y estado del servidor

---

## Roles y Permisos

| Función | SuperAdmin | Admin | Analista | Consulta |
|---|---|---|---|---|
| Ver Dashboard | / | / | / | / |
| Ver Gráficos | / | / | / | X |
| Ver Analítica | / | / | / | / |
| Exportar Excel | / | / | / | X |
| Generar Reporte Word | / | / | / | X |
| Backup y Restore | / | / | X | X |
| Gestionar Preguntas | / | / | X | X |
| Importar Datos | / | X | X | X |
| Gestionar Usuarios | / | X | X | X |
| Panel de Mantenimiento | / | X | X | X |

---

## Licencias y Atribuciones

### Licencia del Proyecto: MIT

```
MIT License
Copyright (c) 2026 Gael Alvarado
```

Ver archivo [LICENSE](LICENSE) para el texto completo.

### Dependencias Backend

| Paquete | Licencia | Uso |
|---|---|---|
| Flask | BSD-3-Clause | Framework web principal |
| Flask-Login | MIT | Autenticación y sesiones |
| Flask-WTF | BSD-3-Clause | Protección CSRF |
| Flask-Limiter | MIT | Rate limiting |
| mysql-connector-python | GPL-2.0 + FOSS Exception | Conexión a MySQL |
| pandas | BSD-3-Clause | Procesamiento de Excel |
| openpyxl | MIT | Lectura de archivos Excel |
| xlsxwriter | BSD-2-Clause | Generación de Excel |
| python-docx | MIT | Generación de reportes Word |
| python-dotenv | BSD-3-Clause | Variables de entorno |
| Werkzeug | BSD-3-Clause | Utilidades WSGI y seguridad |
| Waitress | ZPL-2.1 | Servidor WSGI de producción |

> **Nota sobre mysql-connector-python:** Incluye excepción FOSS que permite su uso sin modificaciones en proyectos bajo cualquier licencia. Ver: https://www.mysql.com/about/legal/licensing/foss-exception/

### Dependencias Frontend

| Librería | Licencia | Uso |
|---|---|---|
| Tailwind CSS | MIT | Framework de estilos |
| Chart.js | MIT | Gráficos interactivos |
| Font Awesome 6 | CC BY 4.0 | Iconografía — requiere atribución |
| Google Fonts — Inter | OFL-1.1 | Tipografía principal |

**Atribución requerida:** Icons by [Font Awesome](https://fontawesome.com) (CC BY 4.0)

---

## Seguridad

| Medida | Implementación |
|---|---|
| CSRF | Tokens en formularios + header `X-CSRFToken` en AJAX (`csrf.js`) |
| Rate Limiting | 5/min login, 5/min registro, 30/min APIs (Flask-Limiter) |
| Fuerza bruta | Bloqueo por usuario: 10 intentos fallidos en 5 min |
| SQL Injection | Prepared statements en todas las queries |
| XSS | Auto-escape Jinja2 + sanitización de inputs + CSP headers |
| Headers HTTP | X-Frame-Options, X-Content-Type-Options, Referrer-Policy, CSP, HSTS |
| Sesiones | HttpOnly, SameSite=Lax, expiración a 1 hora de inactividad |
| Contraseñas | Hash con Werkzeug (bcrypt), validación de fortaleza en registro |
| Auditoría | Log de login, logout, importaciones, backups y acciones críticas |

### Checklist antes de producción

- [ ] `DEBUG_MODE=false` en `.env`
- [ ] `SECRET_KEY` generada con `python -c "import secrets; print(secrets.token_hex(32))"`
- [ ] `MASTER_KEY` cambiada del valor por defecto
- [ ] Contraseña del SuperAdmin cambiada
- [ ] `.env` en `.gitignore`
- [ ] `HTTPS_ENABLED=true` una vez configurado el certificado SSL
- [ ] Usuario de MySQL con permisos mínimos solo sobre `canels_db`

Ver [docs/PROPUESTA_PRODUCCION.md](docs/PROPUESTA_PRODUCCION.md) para la guía de despliegue con IIS + Waitress en Windows Server.

---

## Soporte y FAQ

**¿Cómo cambio la contraseña de un usuario?**
Elimina el usuario desde `import_export.html` y créalo nuevamente con la nueva contraseña.

**¿Cómo accedo desde otra computadora en la red?**
Consulta [docs/ACCESO_RED_LOCAL.md](docs/ACCESO_RED_LOCAL.md). Asegúrate de que `SERVER_HOST=0.0.0.0` en `.env` y accede con la IP de tu máquina.

**¿El puerto 5000 está en uso?**
Cambia `SERVER_PORT` en el archivo `.env`.

**¿Error de conexión a MySQL?**
Verifica que el servicio MySQL esté activo y que las credenciales en `.env` sean correctas.

**¿Qué formato debe tener el Excel para importar?**
El Excel debe ser la exportación directa de Google Forms. El sistema detecta automáticamente las columnas de preguntas numeradas (`1.`, `2.`, etc.), la planta, el área y los datos del colaborador.

**¿Por qué la importación muestra "0 registros"?**
Verifica que los nombres de las plantas en el Excel coincidan exactamente con los registrados en la base de datos (distingue mayúsculas y espacios).

**¿Soporta PostgreSQL?**
No. Solo MySQL 8.0+.

---

<div align="center">

**CANELS v2.1.0** &nbsp;|&nbsp; © 2026 Gael Alvarado &nbsp;|&nbsp; MIT License

Sistema de Clima Laboral &nbsp;|&nbsp; Uso Interno — Canel's

</div>
