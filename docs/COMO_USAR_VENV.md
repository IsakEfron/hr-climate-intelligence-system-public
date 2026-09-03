# Cómo Usar Entornos Virtuales (venv)

Guía práctica para crear, activar y gestionar el entorno virtual de CANELS.

---

## ¿Qué es un Entorno Virtual?

Un entorno virtual es una carpeta aislada que contiene una versión de Python y sus paquetes, independiente del resto del sistema. Cada proyecto tiene sus propias dependencias sin afectar a otros proyectos ni al Python global instalado en la máquina.

**Sin venv:** todos los proyectos comparten los mismos paquetes → conflictos de versiones.  
**Con venv:** cada proyecto tiene los suyos → entorno limpio y reproducible.

---

## Crear el Entorno Virtual

Solo se hace una vez por proyecto.

**Windows:**
```powershell
cd C:\ruta\del\proyecto\canels
python -m venv venv
```

**Linux / Mac:**
```bash
cd /ruta/del/proyecto/canels
python3 -m venv venv
```

Esto crea la carpeta `venv/` en la raíz del proyecto.

---

## Activar el Entorno Virtual

Debes activarlo cada vez que abras una nueva terminal.

**Windows (PowerShell):**
```powershell
venv\Scripts\Activate.ps1
```

**Windows (CMD):**
```cmd
venv\Scripts\activate.bat
```

**Linux / Mac:**
```bash
source venv/bin/activate
```

Cuando está activo, el prompt muestra `(venv)` al inicio:
```
(venv) C:\canels>
```

> Si PowerShell da error de permisos:
> ```powershell
> Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
> ```

---

## Instalar las Dependencias

Con el entorno activo, instala todo lo que necesita CANELS:

```bash
pip install -r requirements.txt
```

Verifica que se instaló todo:

```bash
pip list
```

Deberías ver Flask, pandas, mysql-connector-python, python-docx, waitress, entre otros.

---

## Desactivar el Entorno

Cuando termines de trabajar:

```bash
deactivate
```

El prompt vuelve a la normalidad sin `(venv)`.

---

## Comandos de Referencia Rápida

| Tarea | Comando |
|---|---|
| Crear venv | `python -m venv venv` |
| Activar (Windows PowerShell) | `venv\Scripts\Activate.ps1` |
| Activar (Windows CMD) | `venv\Scripts\activate.bat` |
| Activar (Linux/Mac) | `source venv/bin/activate` |
| Desactivar | `deactivate` |
| Instalar dependencias | `pip install -r requirements.txt` |
| Ver paquetes instalados | `pip list` |
| Actualizar un paquete | `pip install --upgrade nombre` |
| Guardar cambios en dependencias | `pip freeze > requirements.txt` |

---

## Solución de Problemas Comunes

**"No module named 'flask'"**
El entorno no está activado. Verifica que el prompt muestre `(venv)` y vuelve a instalar:
```bash
pip install -r requirements.txt
```

**"python no se reconoce como comando"**
Python no está en el PATH. Reinstálalo marcando la opción "Add Python to PATH", o usa la ruta completa:
```powershell
C:\Python312\python.exe -m venv venv
```

**"ModuleNotFoundError" al ejecutar app.py**
Estás ejecutando Python global en lugar del venv. Activa el entorno primero y luego ejecuta.

**"pip" no instala en el lugar correcto**
Usa `python -m pip` en lugar de `pip` directamente:
```bash
python -m pip install -r requirements.txt
```

---

## Buenas Prácticas

- **Nunca incluyas `venv/` en Git.** El archivo `.gitignore` ya lo excluye.
- **Siempre trabaja con el venv activo** — el script `iniciar.bat` / `iniciar.sh` lo hace automáticamente.
- **Usa versiones fijas en `requirements.txt`** (`Flask==3.0.3`, no `Flask`) para garantizar reproducibilidad.
- **Si cambias dependencias**, actualiza `requirements.txt`:
  ```bash
  pip freeze > requirements.txt
  ```

---

## Cómo Recrear el venv desde Cero

Si el entorno virtual se corrompe o necesitas empezar de cero:

```bash
# Eliminar el entorno actual
rmdir /s /q venv        # Windows
rm -rf venv             # Linux/Mac

# Crear uno nuevo
python -m venv venv

# Activar y reinstalar
venv\Scripts\activate   # Windows
pip install -r requirements.txt
```