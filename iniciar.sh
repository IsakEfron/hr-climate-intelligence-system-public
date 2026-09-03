#!/bin/bash
# Script de inicio rápido para Canels - Linux/Mac
# Activa el entorno virtual y ejecuta la aplicación

clear
cat << "EOF"

============================================================
          CANELS - Sistema de Encuestas
     Iniciando servidor de desarrollo...
============================================================

EOF

# Verificar que existe el entorno virtual
if [ ! -d "venv" ]; then
    echo "Error: Entorno virtual no encontrado"
    echo ""
    echo "Ejecuta primero: python3 setup.py"
    echo ""
    exit 1
fi

# Verificar que .env existe
if [ ! -f ".env" ]; then
    echo "Error: Archivo .env no encontrado"
    echo ""
    echo "Ejecuta primero: python3 setup.py"
    echo ""
    exit 1
fi

# Activar entorno virtual
echo "Activando entorno virtual..."
source venv/bin/activate

if [ $? -ne 0 ]; then
    echo "Error al activar el entorno virtual"
    exit 1
fi

echo ""
echo "Iniciando servidor..."
echo ""
echo "URL Local:     http://localhost:5000"
echo "Red Local:     http://<tu-ip>:5000"
echo ""
echo "Para obtener tu IP: ifconfig | grep inet"
echo "Para detener: Presiona Ctrl+C"
echo ""

python app.py
