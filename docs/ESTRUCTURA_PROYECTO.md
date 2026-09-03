# Estructura del Proyecto — CANELS

Referencia completa de archivos, carpetas y su función en el sistema.

---

## Árbol del Proyecto

```
canels/
│
├── app.py                          # Aplicación Flask — todas las rutas y APIs
├── config.py                       # Configuración centralizada (lee .env)
├── db.py                           # Función get_db_connection()
├── security.py                     # Módulo de seguridad (CSRF, rate limit, headers, sanitización)
├── setup.py                        # Instalador automático del proyecto
│
├── requirements.txt                # Dependencias Python con versiones fijas
├── package.json                    # Dependencias Node.js (Tailwind CSS build)
├── package-lock.json               # Lockfile de npm
│
├── .env                            # Variables de entorno — credenciales (NO incluir en Git)
├── .env.example                    # Plantilla de .env para nuevas instalaciones
├── .gitattributes                  # Configuración de saltos de línea para Git
│
├── iniciar.bat                     # Script de inicio para Windows
├── iniciar.sh                      # Script de inicio para Linux/Mac
├── LICENSE                         # Licencia MIT — Copyright (c) 2026 Gael Alvarado
├── README.md                       # Documentación principal del proyecto
│
├── utils/                          # Módulos Python auxiliares
│   ├── admin_logic.py              # Backup, restore, reset, importación Excel (process_excel_import)
│   ├── import_Excel_SQL.py         # Script standalone de importación (uso directo desde consola)
│   ├── password_security.py        # Validador y generador de contraseñas
│   └── report_generator.py         # Generador de reportes Word (generate_word_report)
│
├── static/                         # Recursos estáticos servidos directamente
│   ├── src/
│   │   └── tailwindcss.css         # Build compilado de Tailwind CSS
│   ├── css/
│   │   └── main.css                # Estilos personalizados adicionales
│   ├── js/
│   │   ├── csrf.js                 # Token CSRF global — debe cargarse antes que cualquier otro JS
│   │   ├── login.js                # Login, registro y validación de contraseña
│   │   ├── grafica_dashboard.js    # Gráficas del dashboard (Chart.js: barras, dona, histórico)
│   │   ├── grafica_page.js         # Página de gráficos avanzados con filtros
│   │   ├── analitica.js            # Búsqueda, filtros y exportación de analítica
│   │   ├── update.js               # Gestión de preguntas y población por planta
│   │   ├── modal_imp.js            # Modal de importación de Excel
│   │   ├── maintenance.js          # Polling de estado de mantenimiento (todas las páginas)
│   │   ├── maintenance_actions.js  # Acciones del panel de mantenimiento (admin)
│   │   ├── notifications.js        # Sistema de notificaciones toast
│   │   └── admin_actions.js        # Acciones administrativas (usuarios, backup, reset)
│   └── img/
│       ├── canels-Logo.png         # Logotipo de CANELS
│       └── canels-icon.png         # Ícono pequeño (favicon y UI)
│
├── templates/                      # Plantillas HTML renderizadas por Flask (Jinja2)
│   ├── login.html                  # Página de login y registro de usuarios
│   ├── index.html                  # Dashboard principal
│   ├── analitica.html              # Módulo de analítica y búsqueda
│   ├── grafico.html                # Gráficos avanzados y generación de reporte Word
│   ├── update.html                 # Gestión de preguntas y población
│   ├── import_export.html          # Importación, backup, restore, reset y usuarios
│   ├── maintenance.html            # Panel de administración de mantenimientos
│   └── acceso_bloqueado.html       # Página de acceso denegado por rol insuficiente
│
├── database/
│   └── schema.sql                  # DDL completo — crea todas las tablas con índices y FKs
│
├── docs/                           # Documentación adicional
│   ├── INSTALACION.md              # Guía de instalación paso a paso
│   ├── ACCESO_RED_LOCAL.md         # Configuración de acceso desde red local
│   ├── COMO_USAR_VENV.md           # Guía de entornos virtuales Python
│   ├── ESTRUCTURA_PROYECTO.md      # Este archivo
│   └── PROPUESTA_PRODUCCION.md     # Despliegue en producción con IIS + Waitress
│
├── uploads/                        # Archivos temporales generados en runtime
│                                   # (backups .sql, reportes .docx, imports temporales)
│                                   # Se crea automáticamente al iniciar
│
└── logs/
    └── security.log                # Log de eventos de seguridad (logins, errores, auditoría)
```

---

## Descripción Detallada por Módulo

### `app.py` — Núcleo de la Aplicación

Contiene todas las rutas Flask organizadas por sección:

| Sección | Rutas |
|---|---|
| Autenticación | `/login` (GET/POST), `/logout`, `/api/register` |
| Páginas HTML | `/`, `/index.html`, `/analitica.html`, `/grafico.html`, `/update.html`, `/import_export.html`, `/maintenance.html` |
| Dashboard | `/api/dashboard`, `/api/grafico/historico` |
| Analítica | `/api/analitica/options`, `/api/analitica/search`, `/api/analitica/excel` |
| Gráficos | `/api/grafico/generar` |
| Reporte | `/api/reporte/generar` |
| Encuestas | `/api/encuestas` (GET), `/api/encuestas/<id>` (PUT/DELETE) |
| Preguntas | `/api/preguntas` (GET/POST), `/api/preguntas/<id>` (PUT/DELETE) |
| Población | `/api/poblacion` (GET/POST), `/api/poblacion/<id>` (PUT/DELETE) |
| Usuarios | `/api/usuarios` (GET), `/api/usuarios/<id>` (DELETE) |
| Admin | `/api/admin/importar`, `/api/admin/backup`, `/api/admin/restore`, `/api/admin/reset` |
| Mantenimiento | `/api/admin/maintenance` (GET/POST), `/api/admin/maintenance/list`, `/api/admin/maintenance/<id>` (DELETE), `/api/admin/check-maintenance`, `/api/admin/server-status` |
| Auditoría | `/api/admin/auditoria` (GET), `/api/admin/auditoria/<id>` (DELETE/PUT), `/api/admin/auditoria/excel` |
| Contraseñas | `/api/validate-password`, `/api/generate-password` |

### `security.py` — Módulo de Seguridad

Inicializado al arrancar la app antes de registrar cualquier ruta:

- `init_security(app)` — configura CSRF (Flask-WTF), rate limiter (Flask-Limiter) y headers HTTP de seguridad
- `configure_logging(app)` — configura el logger de Flask hacia `logs/security.log`
- `sanitize_dict()` — sanitiza diccionarios de entrada (escapa HTML, limita longitud de campos)
- `limiter` — instancia de Flask-Limiter importada en rutas que requieren rate limit

### `utils/admin_logic.py` — Lógica Administrativa

| Función | Descripción |
|---|---|
| `create_backup()` | Ejecuta `mysqldump` y devuelve la ruta del archivo `.sql` generado |
| `restore_backup(filepath)` | Restaura una BD desde un archivo `.sql` |
| `reset_data_only()` | Trunca tablas de datos (respuestas, preguntas, encuestas, empleados, población) |
| `get_or_create_period(id, nombre)` | Crea una nueva encuesta o devuelve el ID de una existente |
| `calcular_meses_inteligente(texto)` | Convierte texto de antigüedad ("5 años 3 meses") a número de meses |
| `process_excel_import(filepath, survey_id)` | Importación completa: detecta columnas, crea esquema, inserta empleados y respuestas |

### `utils/report_generator.py`

| Función | Descripción |
|---|---|
| `generate_word_report(data)` | Genera un `.docx` con el resumen ejecutivo de la encuesta |

Recibe un diccionario con: `planta`, `periodo`, `total_trabajadores`, `chart_image` (base64), `top_3`, `bottom_3`, `filtros`.

### `utils/password_security.py`

| Clase / Función | Descripción |
|---|---|
| `PasswordValidator.validate_password(pwd)` | Analiza fortaleza: longitud, caracteres especiales, mayúsculas, números. Devuelve score 0-100 |
| `PasswordGenerator.generate_secure(length)` | Genera contraseña aleatoria segura |
| `PasswordGenerator.generate_memorable()` | Genera contraseña memorable (palabras + números) |
| `validate_new_password(pwd, min_score)` | Wrapper: devuelve `(is_valid, message)` |

### `database/schema.sql`

Crea las siguientes tablas con sus relaciones e índices:

| Tabla | Descripción |
|---|---|
| `plantas` | Plantas de la empresa |
| `areas` | Áreas dentro de cada planta |
| `encuestas` | Periodos de encuesta (nombre + fecha) |
| `empleados` | Colaboradores encuestados (sin FK a encuesta — relación via respuestas) |
| `preguntas` | Preguntas por encuesta con categoría y tipo (escala/abierta) |
| `respuestas` | Respuestas de cada empleado a cada pregunta |
| `poblacion` | Número total de colaboradores por planta y encuesta (para cálculo de cobertura) |
| `usuarios` | Cuentas de acceso al sistema con rol |
| `auditoria` | Registro de eventos del sistema |
| `mantenimiento` | Ventanas de mantenimiento programadas |

---

## Archivos que NO deben incluirse en Git

El archivo `.gitignore` ya excluye:

```
venv/               # Entorno virtual — se recrea con pip install -r requirements.txt
__pycache__/        # Cache de Python
*.pyc               # Bytecode compilado
.env                # Credenciales — NUNCA en repositorio
uploads/            # Archivos temporales de runtime
logs/               # Logs de seguridad
node_modules/       # Dependencias Node.js — se recrea con npm install
```

---

## Flujo de Datos: Importación Excel

```
Google Forms
    │
    V Exportar respuestas
Archivo .xlsx
    │
    V Upload desde import_export.html
/api/admin/importar (app.py)
    │
    V Llama a
process_excel_import() (admin_logic.py)
    │
    ├── Detecta columnas de preguntas (regex "^N\.")
    ├── Clasifica tipo: escala (Likert 1-7) o abierta
    ├── Crea esquema en tabla `preguntas` (si es periodo nuevo)
    ├── Itera filas → inserta empleados en `empleados`
    └── Inserta respuestas en `respuestas`
```

## Flujo de Datos: Dashboard

```
Navegador → GET /api/dashboard?periodo_id=X
    │
    V
dashboard_data() (app.py)
    │
    ├── COUNT empleados via subquery:
    │       respuestas → preguntas → encuestas
    ├── AVG(valor) por empleado → promedio general
    ├── AVG(valor) por planta → gráfico de barras
    ├── COUNT por planta → gráfico de dona
    └── JOIN con `poblacion` → cobertura por planta
    │
    V
JSON → grafica_dashboard.js -> Chart.js -> Gráficas en pantalla
```