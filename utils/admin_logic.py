import os
import subprocess
import pandas as pd
import re
from datetime import datetime
from config import Config
from db import get_db_connection

# --- HELPERS BACKUP / RESTORE / RESET ---
def create_backup():
    basedir = os.path.abspath(os.path.dirname(__file__))
    root_dir = os.path.dirname(basedir) 
    upload_dir = os.path.join(root_dir, Config.UPLOAD_FOLDER)
    os.makedirs(upload_dir, exist_ok=True)
    
    filename = f"respaldo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql"
    filepath = os.path.join(upload_dir, filename)

    print(f"--> Intentando guardar respaldo en: {filepath}")
    print(f"--> Ejecutable: {Config.MYSQL_DUMP}")

    cmd = [
        Config.MYSQL_DUMP,
        f"--host={Config.DB_HOST}",
        f"--user={Config.DB_USER}",
        f"--password={Config.DB_PASSWORD}",
        f"--result-file={filepath}",
        Config.DB_NAME
    ]
    
    try:
        process = subprocess.run(cmd, check=False, shell=False, capture_output=True, text=True)

        if process.returncode != 0:
            err_msg = process.stderr
            if "Using a password" in err_msg and os.path.exists(filepath):
                print("Aviso de seguridad ignorado (Backup exitoso).")
            else:
                print(f" Error real en mysqldump: {err_msg}")
                return None
        
        if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
            return filepath
        else:
            print(" El archivo se creó pero está vacío.")
            return None

    except Exception as e:
        print(f" Excepción Python en Backup: {e}")
        return None


def restore_backup(filepath):
    cmd = [Config.MYSQL_EXE, f"-h{Config.DB_HOST}", f"-u{Config.DB_USER}", f"-p{Config.DB_PASSWORD}", Config.DB_NAME]
    try:
        with open(filepath, 'r') as f:
            subprocess.run(cmd, stdin=f, check=False, shell=True)
        return True
    except:
        return False


def reset_data_only():
    conn = get_db_connection()
    if not conn: return False
    cursor = conn.cursor()
    try:
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
        cursor.execute("TRUNCATE TABLE respuestas")
        cursor.execute("TRUNCATE TABLE preguntas")
        cursor.execute("TRUNCATE TABLE encuestas")
        cursor.execute("TRUNCATE TABLE empleados")
        cursor.execute("TRUNCATE TABLE poblacion")
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
        conn.commit()
        return True
    except Exception as e:
        print(f"Error Reset: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


def get_or_create_period(periodo_id, nuevo_nombre):
    conn = get_db_connection()
    if not conn: return None
    # ============================================================
    # FIX: Usar buffered=True para evitar "Unread result found"
    # ============================================================
    cursor = conn.cursor(buffered=True)
    final_id = periodo_id
    try:
        if nuevo_nombre and str(nuevo_nombre).strip():
            cursor.execute("INSERT INTO encuestas (nombre, fecha) VALUES (%s, NOW())", (nuevo_nombre.strip(),))
            conn.commit()
            final_id = cursor.lastrowid
        return final_id
    except Exception as e:
        print(f"Error get_or_create_period: {e}")
        return None
    finally:
        cursor.close()
        conn.close()


def calcular_meses_inteligente(texto):
    if pd.isna(texto): return 0
    texto = str(texto).lower().strip()
    
    total_meses = 0
    encontrado = False

    match_anos = re.search(r'(\d+)\s*(?:año|anio)', texto)
    if match_anos:
        total_meses += int(match_anos.group(1)) * 12
        encontrado = True

    match_meses = re.search(r'(\d+)\s*mes', texto)
    if match_meses:
        total_meses += int(match_meses.group(1))
        encontrado = True
        
    match_semanas = re.search(r'(\d+)\s*semana', texto)
    if match_semanas:
        encontrado = True

    match_dias = re.search(r'(\d+)\s*d[ií]a', texto)
    if match_dias:
        encontrado = True

    if encontrado:
        return total_meses

    nums = re.findall(r'\d+', texto)
    if nums:
        val = int(nums[0])
        if val > 100: return 0
        return val
        
    return 0


# --- IMPORTADOR INTELIGENTE (SCHEMA DISCOVERY) ---
def process_excel_import(filepath, survey_id, import_mode='append'):
    conn = get_db_connection()
    if not conn: return {"success": False, "error": "DB Error"}
    
    # ============================================================════
    # Usar buffered=True para evitar "Unread result found"
    # 
    # MySQL Connector Python requiere que TODOS los resultados de una
    # query sean leídos antes de ejecutar otra query en el mismo cursor.
    # Con buffered=True, los resultados se leen automáticamente en memoria
    # después de cada execute(), eliminando el error.
    # ============================================================════
    cursor = conn.cursor(buffered=True)
    log = []
    registros = 0
    
    try:
        if not os.path.exists(filepath):
            return {"success": False, "error": f"Archivo no encontrado: {filepath}"}
        
        # ============================================================
        # MODO REEMPLAZAR: Limpiar datos existentes del periodo
        # Se eliminan respuestas y empleados, pero se conservan las
        # preguntas (esquema) para que el mapeo funcione correctamente.
        # ============================================================
        registros_eliminados = 0
        if import_mode == 'replace':
            print(f"[IMPORT] Modo REEMPLAZAR: limpiando datos del periodo {survey_id}...")

            # Encontrar empleados del periodo vía respuestas -> preguntas
            cursor.execute("""
                SELECT COUNT(DISTINCT r.id_empleado)
                FROM respuestas r
                JOIN preguntas p ON r.id_pregunta = p.id_pregunta
                WHERE p.id_encuesta = %s
            """, (survey_id,))
            count_row = cursor.fetchone()
            registros_eliminados = count_row[0] if count_row else 0

            if registros_eliminados > 0:
                # Borrar respuestas del periodo
                cursor.execute("""
                    DELETE FROM respuestas
                    WHERE id_pregunta IN (
                        SELECT id_pregunta FROM preguntas WHERE id_encuesta = %s
                    )
                """, (survey_id,))

                # Borrar empleados que ya no tienen ninguna respuesta
                cursor.execute("""
                    DELETE FROM empleados
                    WHERE id_empleado NOT IN (
                        SELECT DISTINCT id_empleado FROM respuestas
                        WHERE id_empleado IS NOT NULL
                    )
                """)
                conn.commit()
                print(f"[IMPORT] Eliminados {registros_eliminados} empleados anteriores y sus respuestas.")
            else:
                print(f"[IMPORT] Periodo {survey_id} vacío, nada que limpiar.")

        df = pd.read_excel(filepath)
        # print("[IMPORT COLS]", list(df.columns))
        
        # 1. VERIFICAR SI EL PERIODO YA TIENE PREGUNTAS
        cursor.execute("SELECT count(*) FROM preguntas WHERE id_encuesta = %s", (survey_id,))
        row = cursor.fetchone()
        tiene_preguntas = row[0] > 0 if row else False
        
        columnas_mapeadas = {}

        # 2. ANÁLISIS DE COLUMNAS (Detectar Preguntas)
        cols_potenciales = []
        
        for col in df.columns:
            col_str = str(col).strip()
            match = re.match(r"^(\d+(?:\.\d+)?)\.?(.*)", col_str)
            
            if match:
                num = float(match.group(1))
                texto = match.group(2).strip()
                if not texto: texto = col_str
                
                sample = df[col].dropna()
                
                valores_numericos = 0
                valores_texto = 0
                valores_likert = 0
                
                for s in sample:
                    val_str = str(s).strip()
                    try:
                        val_num = float(val_str)
                        valores_numericos += 1
                        if val_num == int(val_num) and 1 <= val_num <= 7:
                            valores_likert += 1
                    except ValueError:
                        valores_texto += 1
                
                total_valores = valores_numericos + valores_texto
                pct_numericos = (valores_numericos / total_valores * 100) if total_valores > 0 else 0
                pct_likert = (valores_likert / total_valores * 100) if total_valores > 0 else 0
                
                es_numerica = (pct_numericos > 70 and pct_likert > 50)
                
                print(f"[IMPORT DEBUG] Pregunta {num}: {pct_numericos:.1f}% números, {pct_likert:.1f}% Likert -> {'ESCALA' if es_numerica else 'ABIERTA'}")
                
                cat_temporal = f"Categoría {int(num)}" if num.is_integer() else f"Categoría {num}"
                
                cols_potenciales.append({
                    'col': col,
                    'numero': num,
                    'texto': texto,
                    'tipo': 'escala' if es_numerica else 'abierta',
                    'categoria': cat_temporal 
                })

        col_comentarios = next((c for c in df.columns if "basado en sus respuestas" in str(c).lower() or "comentario" in str(c).lower()), None)

        # 3. CREACIÓN DE ESQUEMA (Si es periodo nuevo)
        if not tiene_preguntas:
            print(f"--- Creando esquema automático para Encuesta ID {survey_id} ---")
            for p in cols_potenciales:
                cursor.execute("""
                    INSERT INTO preguntas (id_encuesta, numero, texto, categoria, tipo)
                    VALUES (%s, %s, %s, %s, %s)
                """, (survey_id, p['numero'], p['texto'], p['categoria'], p['tipo']))
                p_id = cursor.lastrowid
                columnas_mapeadas[p['col']] = {'id': p_id, 'tipo': p['tipo']}
            
            if col_comentarios and col_comentarios not in columnas_mapeadas:
                cursor.execute(
                    "INSERT INTO preguntas (id_encuesta, numero, texto, categoria, tipo) VALUES (%s, 99.9, 'Comentarios Finales', 'Comentarios', 'abierta')",
                    (survey_id,)
                )
                columnas_mapeadas[col_comentarios] = {'id': cursor.lastrowid, 'tipo': 'abierta'}
            
            # ============================================================
            # FIX: Commit después de crear el esquema para que los IDs
            #      sean visibles en las queries posteriores
            # ============================================================
            conn.commit()
        
        else:
            print(f"--- Usando esquema existente para Encuesta ID {survey_id} ---")
            for p in cols_potenciales:
                cursor.execute(
                    "SELECT id_pregunta, tipo FROM preguntas WHERE id_encuesta=%s AND numero=%s",
                    (survey_id, p['numero'])
                )
                res = cursor.fetchone()
                if res:
                    id_pregunta_existente = res[0]
                    tipo_antiguo = res[1]
                    
                    if tipo_antiguo != p['tipo']:
                        print(f"[IMPORT DEBUG] Actualizando Pregunta {p['numero']}: '{tipo_antiguo}' -> '{p['tipo']}'")
                        cursor.execute("UPDATE preguntas SET tipo=%s WHERE id_pregunta=%s", (p['tipo'], id_pregunta_existente))
                    
                    columnas_mapeadas[p['col']] = {'id': id_pregunta_existente, 'tipo': p['tipo']}
            
            if col_comentarios:
                cursor.execute(
                    "SELECT id_pregunta, tipo FROM preguntas WHERE id_encuesta=%s AND (categoria='Comentarios' OR numero=99.9)",
                    (survey_id,)
                )
                res = cursor.fetchone()
                if res:
                    columnas_mapeadas[col_comentarios] = {'id': res[0], 'tipo': res[1]}
            
            conn.commit()

        # 4. IMPORTACIÓN DE DATOS
        area_cols = [c for c in df.columns if 'Selecciona el área' in str(c)]
        nombre_completo_col = next(
            (c for c in df.columns if 'nombre completo' in str(c).lower()),
            None
        )

        for index, row in df.iterrows():
            try:
                # 1. Planta
                planta_raw = str(row.get('Planta:', '')).strip()
                if not planta_raw or planta_raw == 'nan': 
                    log.append(f"Fila {index}: planta vacía — fila omitida")    
                    continue
                    
                cursor.execute("SELECT id_planta FROM plantas WHERE nombre = %s", (planta_raw,))
                res = cursor.fetchone()
                if not res: 
                    continue 
                id_planta = res[0]

                if not id_planta:
                    log.append(f"Fila {index}: planta '{planta_raw}' no reconocida — fila omitida")
                    continue

                # 2. Área
                area_raw = ""
                for c in area_cols:
                    v = row.get(c)
                    if pd.notna(v) and str(v).strip():
                        area_raw = str(v).strip()
                        break
                
                if not area_raw:
                    area_raw = "Sin Especificar"
                
                cursor.execute("SELECT id_area FROM areas WHERE nombre=%s AND id_planta=%s", (area_raw, id_planta))
                res_a = cursor.fetchone()
                if res_a: 
                    id_area = res_a[0]
                else:
                    cursor.execute("INSERT INTO areas (nombre, id_planta) VALUES (%s,%s)", (area_raw, id_planta))
                    id_area = cursor.lastrowid
                    log.append(f"Área nueva creada: '{area_raw}' (planta ID {id_planta}) — verificar si es correcta")

                # 3. Empleado
                antiguedad = str(row.get('¿Cuánto tiempo lleva formando parte de la empresa?', ''))
                meses = calcular_meses_inteligente(antiguedad)

                if nombre_completo_col:
                    val_nc = row.get(nombre_completo_col)
                    tiene_nombre_completo = pd.notna(val_nc) and str(val_nc).strip()
                else:
                    tiene_nombre_completo = False

                if tiene_nombre_completo:
                    nombre_val     = str(row.get(nombre_completo_col, '')).strip()
                    ap_paterno_val = None
                    ap_materno_val = None
                else:
                    # Leer cada campo y convertir NaN -> None explícitamente
                    val_nombre = row.get('Nombre:')
                    val_pat    = row.get('Apellido Paterno:')
                    val_mat    = row.get('Apellido Materno:')

                    nombre_val     = str(val_nombre).strip() if pd.notna(val_nombre) else None
                    ap_paterno_val = str(val_pat).strip()    if pd.notna(val_pat)    else None
                    ap_materno_val = str(val_mat).strip()    if pd.notna(val_mat)    else None

                # Si no hay ningún nombre, no tiene sentido insertar la fila
                if not nombre_val:
                    log.append(f"Fila {index}: sin nombre — fila omitida")
                    continue

                cursor.execute("""
                    INSERT INTO empleados (nomina, nombre, apellido_paterno, apellido_materno,
                                        genero, antiguedad, meses_antiguedad, id_planta, id_area)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    row.get('Nómina:'), nombre_val, ap_paterno_val, ap_materno_val,
                    row.get('Género'), antiguedad, meses, id_planta, id_area
                ))
                id_emp = cursor.lastrowid

                # 4. Respuestas
                for col_excel, config in columnas_mapeadas.items():
                    val = row.get(col_excel)
                    if pd.notna(val):
                        val_str = str(val).strip()
                        if val_str:
                            if config['tipo'] == 'escala':
                                try:
                                    val_num = int(float(val_str))
                                    cursor.execute(
                                        "INSERT INTO respuestas (id_empleado, id_pregunta, valor) VALUES (%s,%s,%s)",
                                        (id_emp, config['id'], val_num)
                                    )
                                except Exception: 
                                    pass
                            else:
                                try:
                                    cursor.execute(
                                        "INSERT INTO respuestas (id_empleado, id_pregunta, texto) VALUES (%s,%s,%s)",
                                        (id_emp, config['id'], val_str)
                                    )
                                except Exception:
                                    pass
                
                registros += 1

                # Commit cada 50 registros para no perder todo si falla
                if registros % 50 == 0:
                    conn.commit()
                    print(f"[IMPORT] {registros} empleados procesados...")

            except Exception as ex:
                log.append(f"Fila {index}: {ex}")

        conn.commit()

        modo_texto = "reemplazados" if import_mode == 'replace' else "agregados"
        msg = f"Importados {registros} registros ({modo_texto})."
        if import_mode == 'replace' and registros_eliminados > 0:
            msg += f" Se eliminaron {registros_eliminados} registros anteriores."

        print(f"[IMPORT] {msg}")
        return {"success": True, "message": msg, "log": log}
    
    except Exception as e:
        print(f"CRITICAL: {e}")
        try:
            conn.rollback()
        except:
            pass
        return {"success": False, "error": str(e)}
    finally:
        try:
            cursor.close()
        except:
            pass
        try:
            conn.close()
        except:
            pass