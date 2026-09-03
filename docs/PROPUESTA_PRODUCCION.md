# Propuesta de Despliegue en Producción

**Sistema:** CANELS — Sistema de Clima Laboral  
**Arquitectura propuesta:** IIS + Waitress en Windows Server  
**Autor:** Gael Alvarado  

---

## Arquitectura General

```
Internet / Red Corporativa
        │
        V HTTPS (443)
┌─────────────────────┐
│   IIS Windows Server │  <- Proxy inverso + SSL
│  (URL Rewrite + ARR) │
└─────────┬───────────┘
          │ HTTP interno (localhost:5000)
          V
┌─────────────────────┐
│      Waitress        │  <- Servidor WSGI Python
│   (localhost:5000)   │
└─────────┬───────────┘
          │
          V
┌─────────────────────┐
│    Flask (app.py)    │  <- Lógica de negocio
└─────────┬───────────┘
          │
          V
┌─────────────────────┐
│     MySQL 8.0.45     │  <- Base de datos
└─────────────────────┘
```

**El tráfico externo nunca llega directamente a Flask/Waitress.** IIS actúa como único punto de entrada, aplicando SSL antes de reenviar al backend.

---

## Requisitos de la Plataforma

| Componente | Descripción |
|---|---|
| Sistema Operativo | Windows Server 2019 / 2022 |
| IIS | Rol Web Server (incluido en Windows Server) |
| Módulo ARR | Application Request Routing (descarga gratuita de Microsoft) |
| Módulo URL Rewrite | URL Rewrite Module (descarga gratuita de Microsoft) |
| Python | 3.12.10 instalado en el servidor y agregado al PATH |
| MySQL | 8.0.45 |
| Waitress | `pip install waitress` en el entorno virtual del proyecto |

---

## Paso 1 — Preparar el Entorno Python

### 1.1 Ubicar el proyecto en el servidor

Copiar la carpeta del proyecto a una ruta limpia, por ejemplo:

```
C:\inetpub\canels\
```

### 1.2 Crear entorno virtual y instalar dependencias

Abrir PowerShell como Administrador:

```powershell
cd C:\inetpub\canels
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
pip install waitress
```

### 1.3 Configurar el archivo `.env` de producción

Editar `C:\inetpub\canels\.env`:

```env
DB_HOST=localhost
DB_USER=canels_user
DB_PASSWORD=<contraseña_fuerte>
DB_NAME=canels_db

# Generar con: python -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY=<64_caracteres_aleatorios>
MASTER_KEY=<clave_maestra_segura>

SUPERADMIN_USERNAME=superadmin
SUPERADMIN_PASSWORD=<contraseña_segura>

MYSQL_BIN_PATH="C:\Program Files\MySQL\MySQL Server 8.0\bin"

SERVER_HOST=127.0.0.1
SERVER_PORT=5000
DEBUG_MODE=false
HTTPS_ENABLED=true
```

> `SERVER_HOST=127.0.0.1` — Waitress solo escucha localmente. IIS hace el proxy.

---

## Paso 2 — Configurar Waitress como Servicio Windows

### 2.1 Crear el archivo de inicio WSGI

Crear `C:\inetpub\canels\wsgi_server.py`:

```python
from waitress import serve
from app import app

if __name__ == '__main__':
    serve(
        app,
        host='127.0.0.1',   # Solo escucha local — IIS hace el proxy
        port=5000,
        threads=4,           # Ajustar según núcleos del servidor
        channel_timeout=60
    )
```

### 2.2 Probar manualmente antes de crear el servicio

```powershell
cd C:\inetpub\canels
venv\Scripts\activate
python wsgi_server.py
```

Si no hay errores y se ve `Serving on http://127.0.0.1:5000`, el servidor funciona.

### 2.3 Registrar como Servicio de Windows con NSSM

Descargar NSSM (Non-Sucking Service Manager) desde https://nssm.cc — es gratuito.

Ejecutar en PowerShell como Administrador:

```powershell
# Instalar el servicio
nssm install CANELS_App

# En el asistente configurar:
#   Path:        C:\inetpub\canels\venv\Scripts\python.exe
#   Startup dir: C:\inetpub\canels
#   Arguments:   wsgi_server.py

# Iniciar el servicio
nssm start CANELS_App
```

Verificar que el servicio está corriendo:

```powershell
nssm status CANELS_App
# Esperado: SERVICE_RUNNING
```

El servicio arrancará automáticamente con Windows, incluso después de reinicios.

---

## Paso 3 — Configurar IIS como Proxy Inverso HTTPS

### 3.1 Instalar IIS y módulos requeridos

En **Administrador del servidor → Agregar roles y características**:
- Marcar **Servidor Web (IIS)**
- Dentro de IIS, habilitar **Compresión de contenido dinámico**

Descargar e instalar en orden:
1. **Application Request Routing (ARR):** https://iis.net/downloads/microsoft/application-request-routing
2. **URL Rewrite Module:** https://iis.net/downloads/microsoft/url-rewrite

### 3.2 Habilitar proxy en ARR

1. Abrir **IIS Manager**
2. Seleccionar el nodo raíz del servidor (no un sitio)
3. Doble clic en **Application Request Routing Cache**
4. En el panel derecho: **Server Proxy Settings**
5. Marcar **Enable proxy** → **Apply**

### 3.3 Crear el sitio CANELS en IIS

1. En IIS Manager: **Sitios → Agregar sitio web**
   - Nombre: `CANELS`
   - Ruta física: `C:\inetpub\canels\static` (IIS sirve estáticos desde aquí)
   - Enlace HTTPS: puerto `443`, certificado SSL seleccionado
   - Enlace HTTP: puerto `80` (para redirigir a HTTPS)

### 3.4 Crear el archivo `web.config`

Crear `C:\inetpub\canels\web.config`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<configuration>
  <system.webServer>
    <rewrite>
      <rules>

        <!-- Regla 1: Redirigir HTTP a HTTPS -->
        <rule name="HTTP to HTTPS" stopProcessing="true">
          <match url="(.*)" />
          <conditions>
            <add input="{HTTPS}" pattern="^OFF$" />
          </conditions>
          <action type="Redirect"
                  url="https://{HTTP_HOST}/{R:1}"
                  redirectType="Permanent" />
        </rule>

        <!-- Regla 2: Proxy inverso a Waitress en localhost:5000 -->
        <rule name="Proxy to Waitress" stopProcessing="true">
          <match url="(.*)" />
          <action type="Rewrite"
                  url="http://127.0.0.1:5000/{R:1}" />
        </rule>

      </rules>
    </rewrite>

    <!-- Ocultar versión de IIS en cabecera Server -->
    <security>
      <requestFiltering removeServerHeader="true" />
    </security>

  </system.webServer>
</configuration>
```

---

## Paso 4 — Certificado SSL

### Opción A: Certificado interno (AD CS) — Red interna / intranet

Si la organización tiene Active Directory Certificate Services:

1. **MMC → Certificados → Solicitar nuevo certificado**
2. Seleccionar plantilla **Web Server**
3. Especificar el nombre del servidor (CN)
4. En IIS Manager: **Certificados de servidor → Completar solicitud de certificado**
5. Asignar el certificado al sitio CANELS en el enlace HTTPS

Esta opción no tiene costo adicional y es la más adecuada para uso en intranet corporativa.

### Opción B: Let's Encrypt con win-acme — Servidor con dominio público

Descargar **wacs.exe** desde https://github.com/win-acme/win-acme

```powershell
.\wacs.exe --target iis --siteid 1 --installation iis
```

win-acme configura la renovación automática como Tarea Programada de Windows.

### Opción C: Certificado comercial (DigiCert, Sectigo, etc.)

1. Generar CSR desde IIS Manager → Certificados de servidor
2. Enviar el CSR a la CA comercial
3. Importar el `.pfx` recibido en IIS
4. Asignar al sitio CANELS

---

## Paso 5 — Reforzar TLS con IIS Crypto

Descargar **IIS Crypto** (gratuito) desde https://nartac.com/Products/IISCrypto:

1. Ejecutar IIS Crypto como Administrador
2. Seleccionar plantilla **Best Practices** → **Apply**
3. Esto deshabilita SSL 3.0, TLS 1.0 y TLS 1.1
4. Habilita solo TLS 1.2 y TLS 1.3
5. **Reiniciar el servidor** para que los cambios tomen efecto

---

## Paso 6 — Activar HSTS y `SESSION_COOKIE_SECURE`

Una vez que HTTPS esté operativo, editar `.env`:

```env
HTTPS_ENABLED=true
```

Esto activa automáticamente en `security.py`:
- `SESSION_COOKIE_SECURE = True` — la cookie de sesión solo viaja por HTTPS
- Header `Strict-Transport-Security: max-age=31536000; includeSubDomains`

Opcionalmente, agregar HSTS también desde IIS:
1. IIS Manager → Sitio CANELS → **Encabezados de respuesta HTTP**
2. Agregar encabezado personalizado:
   - Nombre: `Strict-Transport-Security`
   - Valor: `max-age=31536000; includeSubDomains`

---

## Paso 7 — MySQL: Usuario con Permisos Mínimos

En producción, **no usar `root`**. Crear un usuario dedicado para CANELS:

```sql
-- Conectar a MySQL como root
CREATE USER 'canels_user'@'localhost' IDENTIFIED BY 'contraseña_fuerte';

-- Otorgar solo los permisos necesarios sobre la BD de CANELS
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, DROP, INDEX, ALTER
  ON canels_db.* TO 'canels_user'@'localhost';

FLUSH PRIVILEGES;
```

Actualizar `.env`:
```env
DB_USER=canels_user
DB_PASSWORD=contraseña_fuerte
```

---

## Flujo de Tráfico Completo

| Paso | Origen | Destino | Puerto | Protocolo |
|---|---|---|---|---|
| 1 | Cliente (navegador) | Firewall corporativo | 443 / 80 | HTTPS / HTTP |
| 2 | Firewall | IIS Windows Server | 443 | HTTPS — TLS 1.2/1.3 |
| 3 | IIS (URL Rewrite + ARR) | Waitress (Flask) | 5000 | HTTP — solo localhost |
| 4 | Flask | MySQL | 3306 | TCP — solo red interna |

---

## Verificación Final

Probar desde un navegador externo:

1. Acceder a `http://tudominio.com` → debe redirigir a `https://`
2. Verificar que el candado SSL aparece en el navegador
3. Iniciar sesión y comprobar que el dashboard carga correctamente
4. Hacer una importación de prueba para verificar que la BD funciona
5. Verificar headers de seguridad en https://securityheaders.com

---

## Notas Importantes

**¿Por qué IIS y no Nginx?**
La infraestructura de Canel's ya corre en Windows Server con IIS. Usar IIS evita introducir un servidor adicional (Linux + Nginx) y se integra con los certificados y políticas de Active Directory existentes.

**¿Por qué Waitress y no Gunicorn?**
Gunicorn no funciona en Windows. Waitress es el servidor WSGI de producción recomendado para Windows con Python/Flask — es estable, no requiere compiladores y tiene buen soporte de concurrencia.

**¿Múltiples workers con Waitress?**
Waitress usa un modelo de hilos (`threads=4`), no procesos. Flask-Limiter con `storage_uri="memory://"` funciona correctamente en este modelo, a diferencia de Gunicorn con múltiples procesos donde se necesitaría Redis.