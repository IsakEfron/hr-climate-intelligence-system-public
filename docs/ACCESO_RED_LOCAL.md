# Acceso en Red Local — CANELS

Guía para acceder a CANELS desde otras computadoras en la misma red.

---

## ¿Qué es el Acceso en Red Local?

Cuando ejecutas CANELS en una PC, otras computadoras conectadas al mismo WiFi o cable de red pueden acceder al sistema sin necesidad de Internet.

```
Red de la oficina:
  PC Servidor  (192.168.1.100) — Ejecuta CANELS
  PC Analista  (192.168.1.101) — Accede desde el navegador
  Tablet RRHH  (192.168.1.102) — Accede desde el navegador
  Todos en el mismo WiFi corporativo
```

| Tipo de acceso | URL | Desde dónde |
|---|---|---|
| Local | `http://localhost:5000` | La misma PC que ejecuta CANELS |
| Red local | `http://192.168.1.100:5000` | Otras PCs en la misma red |
| Internet | Requiere configuración especial | Desde cualquier lugar |

---

## Requisitos

- CANELS corriendo en la PC servidor
- Otras PCs conectadas al mismo WiFi o cable LAN
- No se necesita conexión a Internet

---

## Paso 1 — Verificar la configuración de CANELS

Abre el archivo `.env` y asegúrate de que `SERVER_HOST` sea `0.0.0.0`:

```env
SERVER_HOST=0.0.0.0
SERVER_PORT=5000
```

Con `0.0.0.0` el servidor escucha en todas las interfaces de red, no solo en localhost.

Al iniciar CANELS deberías ver en la terminal:

```
* Running on http://0.0.0.0:5000
* Running on http://192.168.1.100:5000
```

Si solo ves `http://127.0.0.1:5000`, el servidor no es accesible desde otras PCs.

---

## Paso 2 — Encontrar la IP de tu PC

### Windows

Abre PowerShell o CMD y ejecuta:

```powershell
ipconfig
```

Busca la sección de tu adaptador activo (WiFi o Ethernet) y anota el valor de **Dirección IPv4**:

```
Adaptador de LAN inalámbrica Wi-Fi:
   Dirección IPv4. . . . . . . . . : 192.168.1.100
```

La IP generalmente comienza con `192.168.x.x` o `10.x.x.x`.

### Linux

```bash
ip addr show
# o
hostname -I
```

---

## Paso 3 — Acceder desde otra PC

Desde cualquier computadora en la misma red:

1. Abre un navegador (Chrome, Firefox, Edge, Brave, Safari)
2. Escribe la URL: `http://192.168.1.100:5000` (reemplaza con tu IP real)
3. Deberías ver la página de login de CANELS

---

## Solución de Problemas

### No puedo acceder desde otra PC

**Verificación 1 — Mismo WiFi**

Ambas PCs deben estar en la misma red. Desde la PC servidor prueba hacer ping a la otra PC:

```powershell
ping 192.168.1.101
```

Si responde, están en la misma red. Si no, verifica la conexión WiFi.

**Verificación 2 — Firewall de Windows**

El Firewall de Windows puede estar bloqueando el puerto 5000. Ejecuta esto en PowerShell como Administrador en la PC servidor:

```powershell
netsh advfirewall firewall add rule name="CANELS Puerto 5000" dir=in action=allow protocol=tcp localport=5000
```

O manualmente:
1. Busca "Firewall de Windows Defender" en el menú Inicio
2. Clic en "Permitir una aplicación o característica"
3. Busca Python y marca las casillas "Privada" y "Pública"

**Verificación 3 — URL correcta**

-  Correcto: `http://192.168.1.100:5000`
-  Incorrecto: `https://192.168.1.100:5000` (HTTPS sin certificado)
-  Incorrecto: `192.168.1.100:5000` (sin `http://`)

### El puerto 5000 está ocupado por otra aplicación

Cambia el puerto en `.env`:

```env
SERVER_PORT=5001
```

Y accede con: `http://192.168.1.100:5001`

---

## Compartir el acceso con el equipo

Si quieres que otros accedan, comparte la URL por correo o chat interno:

> Para acceder a CANELS desde tu navegador, entra a:
> **http://192.168.1.100:5000**
> Asegúrate de estar conectado al WiFi de la oficina.

---

## Seguridad en Red Local

- Usa contraseñas fuertes en cada cuenta de CANELS
- No expongas CANELS a Internet sin HTTPS configurado
- Si necesitas acceso desde fuera de la oficina, usa una VPN corporativa
- Para producción consulta `docs/PROPUESTA_PRODUCCION.md`

