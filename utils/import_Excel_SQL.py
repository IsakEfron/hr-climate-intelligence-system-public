# utils/import_Excel_SQL.py
import pandas as pd
import mysql.connector
import unicodedata
import difflib
import os
import csv
import re
import sys
from dotenv import load_dotenv
load_dotenv()

# Configuración de codificación para consola
sys.stdout.reconfigure(encoding='utf-8')

# Configuración
AUTO_CREATE_AREAS = False
FUZZY_CUTOFF = 0.85 
UNMATCHED_LOG = 'unmatched_areas.csv'
FILENAME = "../Encuesta de satisfacción laboral.xlsx"

# --- FUNCIÓN NUEVA: Calcular meses de antigüedad ---
def calcular_meses(texto):
    """Convierte texto como '5 años', '1 mes' a número entero de meses"""
    if pd.isna(texto):
        return None
    
    texto = str(texto).lower().strip()
    
    # Buscar el primer número en el texto
    numeros = re.findall(r'\d+', texto)
    if not numeros:
        return 0 # No se encontró número
        
    cantidad = int(numeros[0])
    
    if 'año' in texto:
        return cantidad * 12
    elif 'mes' in texto:
        return cantidad
    elif 'semana' in texto:
        # Semanas a meses (aprox)
        return max(0, cantidad // 4)
    elif 'dia' in texto or 'día' in texto:
        return 0 # Menos de un mes
    
    return cantidad # Por defecto asumimos meses si no hay unidad, o ajusta según necesites

conn = mysql.connector.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    user=os.getenv('DB_USER', 'root'),
    password=os.getenv('DB_PASSWORD', ''),
    database=os.getenv('DB_NAME', 'canels_db')
)
cursor = conn.cursor()

print(f" Leyendo archivo: {FILENAME}")
df = pd.read_excel(FILENAME)

# ... (Bloque de detección de columnas igual al anterior) ...
area_cols = [c for c in df.columns if 'Selecciona el área' in str(c)]
question_map = {}
for col in df.columns:
    match = re.match(r"^(\d+)\.", str(col).strip())
    if match:
        question_map[int(match.group(1))] = col

open_q_col = None
for col in df.columns:
    if "Basado en sus respuestas" in str(col):
        open_q_col = col; break

if not os.path.exists(UNMATCHED_LOG):
    with open(UNMATCHED_LOG, 'w', newline='', encoding='utf-8') as f:
        csv.writer(f).writerow(['fila', 'planta', 'area_raw', 'area_clean', 'match', 'ratio'])

# PROCESAMIENTO
for index, row in df.iterrows():
    try:
        # 1. PLANTA
        planta_raw = row.get('Planta:')
        if pd.isna(planta_raw): continue
        planta_excel = str(planta_raw).strip()

        cursor.execute("SELECT id_planta FROM plantas WHERE nombre = %s", (planta_excel,))
        planta = cursor.fetchone()
        if not planta:
            print(f" Fila {index+2}: Planta '{planta_excel}' desconocida")
            continue
        id_planta = planta[0]

        # 2. ÁREA (Lógica de limpieza)
        area_raw = None
        for col in area_cols:
            val = row.get(col)
            if pd.notna(val) and str(val).strip() != '':
                area_raw = str(val).strip(); break
        
        id_area = None
        if area_raw:
            # Limpieza
            s = area_raw
            s = re.sub(rf"(?i)\bplanta\s+{re.escape(planta_excel)}\b", "", s)
            s = re.sub(rf"(?i)\b{re.escape(planta_excel)}\b", "", s)
            s = re.sub(r"(?i)\ben planta\b", "", s)
            s = re.sub(r"[-–—:]", " ", s)
            area_clean = ' '.join(s.split()).strip()

            def _norm(txt):
                return ''.join(c for c in unicodedata.normalize('NFKD', str(txt).lower()) 
                               if not unicodedata.category(c).startswith('M'))

            cursor.execute("SELECT id_area FROM areas WHERE nombre = %s AND id_planta = %s", (area_clean, id_planta))
            res = cursor.fetchone()
            if res:
                id_area = res[0]
            else:
                # Fuzzy
                cursor.execute("SELECT id_area, nombre FROM areas WHERE id_planta = %s", (id_planta,))
                areas_bd = cursor.fetchall()
                best_match, best_ratio = None, 0
                norm_target = _norm(area_clean)
                
                for aid, aname in areas_bd:
                    r = difflib.SequenceMatcher(None, norm_target, _norm(aname)).ratio()
                    if r > best_ratio: best_ratio = r; best_match = (aid, aname)
                
                if best_match and best_ratio >= FUZZY_CUTOFF:
                    id_area = best_match[0]
                    print(f" Fila {index+2}: Fuzzy '{area_clean}' -> '{best_match[1]}'")
                elif AUTO_CREATE_AREAS:
                    cursor.execute("INSERT INTO areas (nombre, id_planta) VALUES (%s, %s)", (area_clean, id_planta))
                    conn.commit(); id_area = cursor.lastrowid
                else:
                    with open(UNMATCHED_LOG, 'a', newline='', encoding='utf-8') as f:
                        csv.writer(f).writerow([index+2, planta_excel, area_raw, area_clean, best_match[1] if best_match else '', best_ratio])

        # 3. EMPLEADO (Con cálculo de antigüedad)
        antiguedad_texto = row.get('¿Cuánto tiempo lleva formando parte de la empresa?')
        meses_calc = calcular_meses(antiguedad_texto) # <--- AQUÍ SE CALCULA

        cursor.execute("""
            INSERT INTO empleados
            (nomina, nombre, apellido_paterno, apellido_materno, genero, antiguedad, meses_antiguedad, id_planta, id_area)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            row.get('Nómina:'), row.get('Nombre:'), row.get('Apellido Paterno:'), row.get('Apellido Materno:'),
            row.get('Género'), antiguedad_texto, meses_calc, id_planta, id_area
        ))
        id_empleado = cursor.lastrowid

        # 4. RESPUESTAS
        for i in range(1, 27):
            col = question_map.get(i)
            if col:
                val = row.get(col)
                if pd.isna(val): val = None
                cursor.execute("INSERT INTO respuestas (id_empleado, id_pregunta, valor) VALUES (%s,%s,%s)", (id_empleado, i, val))

        if open_q_col:
            val = row.get(open_q_col)
            if pd.notna(val) and str(val).strip():
                cursor.execute("INSERT INTO respuestas (id_empleado, id_pregunta, texto) VALUES (%s,27,%s)", (id_empleado, str(val)))

        if index % 10 == 0: conn.commit(); print(f"Correcto {index+1} registros...")

    except Exception as e:
        print(f" Error en fila {index+2}: {e}")

conn.commit()
cursor.close()
conn.close()
print(" Importación finalizada")