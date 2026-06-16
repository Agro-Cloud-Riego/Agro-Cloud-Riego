from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, Response
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import sqlite3
import os
import io
import csv
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = 'agroriego_secreto_marcelocarabajal'
DATABASE = 'agroriego_stock.db'

# --- CONFIGURACIÓN DE LOGIN ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, id):
        self.id = id

usuarios_sistema = {"marcelo": "agro2026"}

@login_manager.user_loader
def load_user(user_id):
    if user_id in usuarios_sistema:
        return User(user_id)
    return None

# --- CONFIGURACIÓN DE BASE DE DATOS ---
def conectar_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def inicializar_db():
    conn = conectar_db()
    cursor = conn.cursor()
    
    # Tabla de Inventario
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS inventario (
            parte TEXT PRIMARY KEY,
            motor TEXT,
            categoria TEXT,
            item TEXT,
            ubicacion TEXT,
            minimo INTEGER,
            actual INTEGER
        )
    ''')
    
    # Tabla de Historial de Movimientos de Repuestos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS movimientos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo TEXT,
            parte TEXT,
            cantidad INTEGER,
            destino_origen TEXT,
            responsable TEXT,
            fecha TEXT
        )
    ''')

    # Tabla de Órdenes de Trabajo
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ordenes_trabajo (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tarea TEXT,
            responsable TEXT,
            prioridad TEXT,
            equipo_id TEXT,
            estado TEXT,
            fecha TEXT,
            repuesto_asociado TEXT DEFAULT NULL,
            horas_registro REAL DEFAULT NULL,
            motor_id TEXT DEFAULT NULL
        )
    ''')

    # Tabla Histórica de Riego (Estructura base)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS registro_riego (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            equipo_id TEXT,
            lamina_mm REAL,
            horas_operadas REAL,
            presion_bar REAL DEFAULT 0.0,
            posicion_grados INTEGER DEFAULT 0,
            estado_operacion TEXT DEFAULT 'MARCHA',
            fecha TEXT
        )
    ''')

    # --- CONTROL DE EVOLUCIÓN: Agregar columna lamina_programada si no existe ---
    cursor.execute("PRAGMA table_info(registro_riego)")
    columnas = [info['name'] for info in cursor.fetchall()]
    if 'lamina_programada' not in columnas:
        cursor.execute("ALTER TABLE registro_riego ADD COLUMN lamina_programada REAL DEFAULT 0.0")

    # Tabla de Alertas de Falla del Sistema
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS alertas_sistema (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            equipo_id TEXT,
            tipo_falla TEXT,
            descripcion TEXT,
            estado TEXT,
            fecha_hora TEXT
        )
    ''')
    
    # Tabla: Estado de Telemetría en Tiempo Real de las Placas Hardware
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS telemetria_equipos (
            equipo_id TEXT PRIMARY KEY,
            latitud REAL,
            longitud REAL,
            presion_terminal REAL,
            posicion_actual INTEGER DEFAULT 0,
            rssi TEXT,
            ultima_actualizacion TEXT
        )
    ''')
    
    # Tabla de Monitoreo de Motores Físicos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS control_services (
            motor_id TEXT PRIMARY KEY,
            motor_modelo TEXT,
            equipo_asignado TEXT,
            horas_actuales REAL,
            ultimo_service REAL,
            frecuencia_hs INTEGER DEFAULT 300
        )
    ''')
    
    # Ubicaciones iniciales (Joaquín V. González)
    cursor.execute("INSERT OR IGNORE INTO telemetria_equipos VALUES ('PIVOT-LOTE-A2', -25.1794, -63.8632, 2.4, 340, '-98 dBm', 'Nunca')")
    cursor.execute("INSERT OR IGNORE INTO telemetria_equipos VALUES ('FRONTAL-F22', -25.1750, -63.8500, 3.2, 180, '-85 dBm', 'Nunca')")

    # Inyección de datos simulados
    cursor.execute("SELECT COUNT(*) FROM registro_riego")
    if cursor.fetchone()[0] == 0:
        datos_demo = [
            ('PIVOT-LOTE-A2', 10.5, 4.0,  2.4, 310, 'MARCHA',   '2026-06-15 08:00', 10.5),
            ('PIVOT-LOTE-A2', 12.0, 8.5,  2.3, 325, 'MARCHA',   '2026-06-15 14:00', 12.0),
            ('PIVOT-LOTE-A2', 12.5, 12.0, 2.4, 340, 'MARCHA',   '2026-06-15 20:00', 12.5),
            ('PIVOT-LOTE-A2', 11.0, 16.5, 1.8, 355, 'MARCHA',   '2026-06-16 02:00', 12.0),
            ('PIVOT-LOTE-A2', 0.0,  2.5,  0.0, 355, 'FALLA',    '2026-06-16 04:30', 0.0),
            ('PIVOT-LOTE-A2', 0.0,  6.0,  0.0, 355, 'PARADO',   '2026-06-16 10:30', 0.0),
        ]
        cursor.executemany('''
            INSERT INTO registro_riego (equipo_id, lamina_mm, horas_operadas, presion_bar, posicion_grados, estado_operacion, fecha, lamina_programada)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', datos_demo)

    # Cargar repuestos base
    repuestos_iniciales = [
        ("1R-0739", "Caterpillar", "Filtros", "Filtro de Aceite", "Estante A1", 2, 5),
        ("1R-0770", "Caterpillar", "Filtros", "Filtro Combustible / Trampa Agua", "Estante A1", 2, 1),
        ("106-3969", "Caterpillar", "Filtros", "Filtro Aire Primario", "Estante A2", 1, 2),
        ("504074043", "Iveco T5/T8", "Filtros", "Filtro de Aceite", "Estante B1", 3, 4),
        ("504107584", "Iveco T5/T8", "Filtros", "Filtro de Combustible", "Estante B1", 2, 2),
        ("504013423", "Iveco T5/T8", "Correas", "Correa Poly-V", "Estante B2", 2, 1),
        ("1174416", "Deutz 1013", "Filtros", "Filtro de Aceite", "Estante C1", 4, 6),
        ("1174423", "Deutz 1013", "Filtros", "Filtro de Combustible", "Estante C1", 3, 3),
        ("4272819", "Deutz 1013", "Repuestos", "Bomba de Pre-alimentación", "Caja Herramientas", 1, 0),
        ("Poliuretano", "Varios", "Bombas", "Goma de Acoplamiento", "Estante D1", 2, 3),
        ("Carburo Silicio", "Varios", "Bombas", "Sello Mecánico Cornell", "Estante D1", 2, 1)
    ]
    cursor.executemany('''
        INSERT OR IGNORE INTO inventario (parte, motor, categoria, item, ubicacion, minimo, actual)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', repuestos_iniciales)

    motores_iniciales = [
        ("INV-001", "Iveco T8", "Pivot A2", 601.1, 351.1, 300),
        ("INV-002", "Iveco T8", "Pivot B2", 1414.8, 1118.0, 300),
        ("INV-005", "Deutz 1013", "Frontal F22", 120.0, 0.0, 300)
    ]
    cursor.executemany('''
        INSERT OR IGNORE INTO control_services (motor_id, motor_modelo, equipo_asignado, horas_actuales, ultimo_service, frecuencia_hs)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', motores_iniciales)

    conn.commit()
    conn.close()

# --- ENLACE DIRECTO DESCARGA EXCEL/CSV DEL CICLO DE TRABAJO ---
@app.route('/descargar-datos-ciclo/<equipo_id>')
@login_required
def descargar_datos_ciclo(equipo_id):
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT fecha, horas_operadas, presion_bar, posicion_grados, lamina_mm, lamina_programada, estado_operacion 
        FROM registro_riego 
        WHERE equipo_id = ? 
        ORDER BY fecha ASC
    ''', (equipo_id,))
    filas = cursor.fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    
    writer.writerow(['Fecha / Timeline', 'Horas Parciales (hs)', 'Presion en Barra (Bar)', 'Posicion Angular (°)', 'Lamina Aplicada (mm)', 'Lamina Programada (mm)', 'Estado de Operacion'])
    for f in filas:
        writer.writerow([f['fecha'], f['horas_operadas'], f['presion_bar'], f['posicion_grados'], f['lamina_mm'], f['lamina_programada'], f['estado_operacion']])
    
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-disposition": f"attachment; filename=Historico_Ciclo_{equipo_id}_{datetime.now().strftime('%Y%m%d')}.csv"}
    )

@app.route('/api/telemetria', methods=['POST'])
def recibir_telemetria():
    data = request.get_json()
    if not data or 'equipo_id' not in data:
        return jsonify({"status": "error", "message": "Datos incompletos"}), 400
        
    equipo_id = data.get('equipo_id')
    lat = data.get('latitud')
    lng = data.get('longitud')
    presion = data.get('presion_terminal')
    posicion = data.get('posicion_actual', 0)
    rssi = data.get('rssi', '-90 dBm')
    fecha_gps = (datetime.utcnow() - timedelta(hours=3)).strftime('%d/%m/%Y a las %I:%M %p')
    
    conn = conectar_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO telemetria_equipos (equipo_id, latitud, longitud, presion_terminal, posicion_actual, rssi, ultima_actualizacion)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(equipo_id) DO UPDATE SET
            latitud=excluded.latitud,
            longitud=excluded.longitud,
            presion_terminal=excluded.presion_terminal,
            posicion_actual=excluded.posicion_actual,
            rssi=excluded.rssi,
            ultima_actualizacion=excluded.ultima_actualizacion
    ''', (equipo_id, lat, lng, presion, posicion, rssi, fecha_gps))
    
    if presion and float(presion) < 1.5:
        cursor.execute("SELECT COUNT(*) FROM alertas_sistema WHERE equipo_id = ? AND tipo_falla = 'Baja Presión Inalámbrica' AND estado = 'ACTIVA'", (equipo_id,))
        if cursor.fetchone()[0] == 0:
            cursor.execute('''
                INSERT INTO alertas_sistema (equipo_id, tipo_falla, descripcion, estado, fecha_hora)
                VALUES (?, 'Baja Presión Inalámbrica', ?, 'ACTIVA', ?)
            ''', (equipo_id, f"Presión crítica detectada por hardware LoRa: {presion} Bar", (datetime.utcnow() - timedelta(hours=3)).strftime('%Y-%m-%d %H:%M:%S')))
            
    conn.commit()
    conn.close()
    return jsonify({"status": "ok", "message": "Telemetría integrada correctamente"}), 200

@app.route('/', methods=['GET', 'POST'])
@login_required
def index():
    conn = conectar_db()
    cursor = conn.cursor()

    id_solicitado = request.args.get('equipo', 'PIVOT-LOTE-A2')
    if id_solicitado not in ['PIVOT-LOTE-A2', 'FRONTAL-F22']: 
        id_solicitado = "PIVOT-LOTE-A2"
    
    # Manejo de Formularios
    if request.method == 'POST' and request.form.get('form_tipo') == 'nuevo_riego':
        equipo_id = request.form.get('equipo_id')
        lamina = float(request.form.get('lamina_mm', 0))
        horas = float(request.form.get('horas_operadas', 0))
        presion_ingresada = float(request.form.get('presion_bar', 2.2))
        posicion_ingresada = int(request.form.get('posicion_grados', 0))
        estado_ingresado = request.form.get('estado_operacion', 'MARCHA')
        fecha_riego = request.form.get('fecha_riego')
        
        # Guardar Lámina Programada del Formulario Operativo
        lamina_prog = request.form.get('lamina_programada')
        lamina_prog_val = float(lamina_prog) if lamina_prog else 0.0
        
        # Inserción con el nuevo parámetro de lámina objetivo/programada
        cursor.execute('''
            INSERT INTO registro_riego (equipo_id, lamina_mm, horas_operadas, presion_bar, posicion_grados, estado_operacion, fecha, lamina_programada) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (equipo_id, lamina, horas, presion_ingresada, posicion_ingresada, estado_ingresado, fecha_riego, lamina_prog_val))
        
        mapa_equipos = {"PIVOT-LOTE-A2": "Pivot A2", "FRONTAL-F22": "Frontal F22"}
        nombre_mapeado = mapa_equipos.get(equipo_id, "")
        if nombre_mapeado and estado_ingresado == 'MARCHA':
            cursor.execute("UPDATE control_services SET horas_actuales = horas_actuales + ? WHERE equipo_asignado = ?", (horas, nombre_mapeado))
        
        conn.commit()
        return redirect(url_for('index', equipo=equipo_id))

    # CONSULTA TELEMETRÍA REAL
    cursor.execute("SELECT * FROM telemetria_equipos WHERE equipo_id = ?", (id_solicitado,))
    tel_db = cursor.fetchone()

    if tel_db and tel_db['ultima_actualizacion'] != 'Nunca':
        estado_calculado = "MARCHA"
        presion_calculada = f"{tel_db['presion_terminal']} Bar" if tel_db['presion_terminal'] else "0.0 Bar"
        posicion_calculada = f"GPS: {tel_db['latitud']}, {tel_db['longitud']}"
        angulo_actual = f"{tel_db['posicion_actual']}°"
        lectura_texto = tel_db['ultima_actualizacion']
        rssi_val = tel_db['rssi'] if tel_db['rssi'] else "0 dBm"
        lat_val = tel_db['latitud'] if tel_db['latitud'] else -25.1794
        lng_val = tel_db['longitud'] if tel_db['longitud'] else -63.8632
    else:
        estado_calculado = "DESCONECTADO"
        presion_calculada = "0.0 Bar"
        posicion_calculada = "Sin Coordenadas GPS"
        angulo_actual = "0°"
        lectura_texto = "Nunca (Hardware no enlazado)"
        rssi_val = "0 dBm"
        lat_val = -25.1794 if id_solicitado == "PIVOT-LOTE-A2" else -25.1750
        lng_val = -63.8632 if id_solicitado == "PIVOT-LOTE-A2" else -63.8500

    # CÁLCULOS SUMATORIOS DE LAS TARJETAS (KPIs)
    cursor.execute("SELECT SUM(horas_operadas) as hs_r FROM registro_riego WHERE equipo_id = ? AND estado_operacion = 'MARCHA'", (id_solicitado,))
    calc_riego = cursor.fetchone()['hs_r'] or 0.0
    
    cursor.execute("SELECT SUM(horas_operadas) as hs_f FROM registro_riego WHERE equipo_id = ? AND estado_operacion = 'FALLA'", (id_solicitado,))
    calc_falla = cursor.fetchone()['hs_f'] or 0.0
    
    cursor.execute("SELECT SUM(horas_operadas) as hs_m FROM registro_riego WHERE equipo_id = ? AND estado_operacion = 'MOVIMIENTO'", (id_solicitado,))
    calc_mov = cursor.fetchone()['hs_m'] or 0.0

    cursor.execute("SELECT SUM(horas_operadas) as hs_p FROM registro_riego WHERE equipo_id = ? AND estado_operacion = 'PARADO'", (id_solicitado,))
    calc_parado = cursor.fetchone()['hs_p'] or 0.0
    
    # Calcular Lámina Acumulada
    cursor.execute("SELECT SUM(lamina_mm) as mm_tot FROM registro_riego WHERE equipo_id = ?", (id_solicitado,))
    total_acumulado_mm = cursor.fetchone()['mm_tot'] or 0.0

    equipos_riego = {
        "PIVOT-LOTE-A2": {
            "id": "PIVOT-LOTE-A2", "nombre_corto": "Lote A2", "tipo": "Pivot Central", "lote": "Lote A2 (156 Ha)",
            "posicion": posicion_calculada, "caudal": "115.000 L/h" if estado_calculado == "MARCHA" else "0 L/h", 
            "estado": estado_calculado, "presion": presion_calculada, "posicion_tramo": angulo_actual, "senal": rssi_val,
            "ultima_lectura": lectura_texto, "lat": lat_val, "lng": lng_val,
            "hs_riego": round(calc_riego, 1), "hs_falla": round(calc_falla, 1), "hs_movimiento": round(calc_mov, 1), "hs_parado": round(calc_parado, 1)
        },
        "FRONTAL-F22": {
            "id": "FRONTAL-F22", "nombre_corto": "Frontal F22", "tipo": "Avance Frontal Lineal", "lote": "Cuadro Norte (210 Ha)",
            "posicion": posicion_calculada, "caudal": "120.000 L/h" if estado_calculado == "MARCHA" else "0 L/h", 
            "estado": estado_calculado, "presion": presion_calculada, "posicion_tramo": angulo_actual, "senal": rssi_val,
            "ultima_lectura": lectura_texto, "lat": lat_val, "lng": lng_val,
            "hs_riego": round(calc_riego, 1), "hs_falla": round(calc_falla, 1), "hs_movimiento": round(calc_mov, 1), "hs_parado": round(calc_parado, 1)
        }
    }
    
    data_render = equipos_riego[id_solicitado]

    # RECUPERAR LÍNEAS COMPLETAS PARA PASAR AL GRAFICO
    cursor.execute("SELECT fecha, horas_operadas, presion_bar, posicion_grados, lamina_mm FROM registro_riego WHERE equipo_id = ? ORDER BY fecha ASC LIMIT 15", (id_solicitado,))
    registros_db = cursor.fetchall()
    
    eje_x_fechas = [r['fecha'] for r in registros_db]
    datos_y_horas = [r['horas_operadas'] for r in registros_db]
    datos_y_presion = [r['presion_bar'] for r in registros_db]
    datos_y_posicion = [r['posicion_grados'] for r in registros_db]
    datos_y_lamina = [r['lamina_mm'] for r in registros_db]

    cursor.execute("SELECT * FROM ordenes_trabajo WHERE estado = 'PENDIENTE' AND equipo_id = ? ORDER BY id DESC", (id_solicitado,))
    ot_reales = cursor.fetchall()
    
    cursor.execute("SELECT * FROM alertas_sistema WHERE estado = 'ACTIVA' ORDER BY id DESC")
    alertas_activas = cursor.fetchall()

    cursor.execute("SELECT parte, item, motor FROM inventario WHERE actual > 0")
    repuestos_taller = cursor.fetchall()

    conn.close()
    
    return render_template('dashboard.html', 
                           data=data_render, 
                           todos_equipos=equipos_riego, 
                           ot=ot_reales, 
                           user=current_user,
                           fechas_riego=eje_x_fechas,
                           horas_riego=datos_y_horas,
                           presiones_linea=datos_y_presion,
                           posiciones_linea=datos_y_posicion,
                           laminas_riego=datos_y_lamina,
                           alertas=alertas_activas,
                           repuestos=repuestos_taller,
                           total_acumulado_mm=round(total_acumulado_mm, 1))

# --- FIN DEL CONTENIDO DE LA APP ---
@app.route('/finalizar-ot/<int:ot_id>')
@login_required
def finalizar_ot(ot_id):
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("SELECT equipo_id, repuesto_asociado, tarea, responsable FROM ordenes_trabajo WHERE id = ?", (ot_id,))
    ot = cursor.fetchone()
    if ot:
        equipo_id = ot['equipo_id']
        repuesto = ot['repuesto_asociado']
        if repuesto:
            cursor.execute("SELECT actual FROM inventario WHERE parte = ?", (repuesto,))
            inv = cursor.fetchone()
            if inv and inv['actual'] > 0:
                cursor.execute("UPDATE inventario SET actual = ? WHERE parte = ?", (inv['actual'] - 1, repuesto))
                fecha_mov = (datetime.utcnow() - timedelta(hours=3)).strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute('''
                    INSERT INTO movimientos (tipo, parte, cantidad, destino_origen, responsable, fecha) 
                    VALUES ('salida', ?, 1, ?, ?, ?)
                ''', (repuesto, f"Uso en OT #{ot_id} ({equipo_id})", ot['responsable'], fecha_mov))
        cursor.execute("UPDATE ordenes_trabajo SET estado = 'COMPLETADA' WHERE id = ?", (ot_id,))
        conn.commit()
    conn.close()
    return redirect(url_for('index', equipo=equipo_id if ot else 'PIVOT-LOTE-A2'))

@app.route('/desactivar-alerta/<int:alerta_id>')
@login_required
def desactivar_alerta(alerta_id):
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("SELECT equipo_id FROM alertas_sistema WHERE id = ?", (alerta_id,))
    fila = cursor.fetchone()
    equipo_id = fila['equipo_id'] if fila else 'PIVOT-LOTE-A2'
    cursor.execute("UPDATE alertas_sistema SET estado = 'SOLUCIONADA' WHERE id = ?", (alerta_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('index', equipo=equipo_id))

@app.route('/stock', methods=['GET', 'POST'])
@login_required
def stock():
    conn = conectar_db()
    cursor = conn.cursor()
    if request.method == 'POST':
        form_origen = request.form.get('form_origen')
        if form_origen == 'alta_articulo':
            parte = request.form.get('parte').strip()
            item = request.form.get('item').strip()
            categoria = request.form.get('categoria')
            motor_equipo = request.form.get('motor_equipo').strip()
            ubicacion = request.form.get('ubicacion').strip()
            minimo = int(request.form.get('minimo', 0))
            actual = int(request.form.get('actual', 0))
            if parte and item:
                cursor.execute('''
                    INSERT OR IGNORE INTO inventario (parte, motor, category, item, ubicacion, minimo, actual)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (parte, motor_equipo, categoria, item, ubicacion, minimo, actual))
                conn.commit()
                if actual > 0:
                    fecha_local = (datetime.utcnow() - timedelta(hours=3)).strftime('%Y-%m-%d %H:%M:%S')
                    cursor.execute('''
                        INSERT INTO movimientos (tipo, parte, cantidad, destino_origen, responsable, fecha)
                        VALUES ('entrada', ?, ?, 'Carga Inicial de Sistema', 'Marcelo Daniel', ?)
                    ''', (parte, actual, fecha_local))
                    conn.commit()
            return redirect(url_for('stock'))
        elif form_origen == 'movimiento_stock':
            tipo_accion = request.form.get('accion') 
            nro_parte = request.form.get('part')
            amount = int(request.form.get('quantity', 0))
            responsable = request.form.get('responsable')
            destino_origen = request.form.get('destino_origen')
            fecha_local = (datetime.utcnow() - timedelta(hours=3)).strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute("SELECT actual FROM inventario WHERE parte = ?", (nro_parte,))
            fila = cursor.fetchone()
            if fila and amount > 0:
                stock_actual = fila['actual']
                if tipo_accion == 'entrada':
                    cursor.execute("UPDATE inventario SET actual = ? WHERE parte = ?", (stock_actual + amount, nro_parte))
                    cursor.execute("INSERT INTO movimientos (tipo, parte, cantidad, destino_origen, responsable, fecha) VALUES ('entrada', ?, ?, ?, ?, ?)", (nro_parte, amount, destino_origen, responsable, fecha_local))
                elif tipo_accion == 'salida' and stock_actual >= amount:
                    cursor.execute("UPDATE inventario SET actual = ? WHERE parte = ?", (stock_actual - amount, nro_parte))
                    cursor.execute("INSERT INTO movimientos (tipo, parte, cantidad, destino_origen, responsable, fecha) VALUES ('salida', ?, ?, ?, ?, ?)", (nro_parte, amount, destino_origen, responsable, fecha_local))
                conn.commit()
            return redirect(url_for('stock'))

    cursor.execute("SELECT * FROM inventario ORDER BY categoria ASC, item ASC")
    lista_inventario = cursor.fetchall()
    cursor.execute("SELECT m.*, i.item, i.motor FROM movimientos m JOIN inventario i ON m.parte = i.parte WHERE m.tipo = 'entrada' ORDER BY m.id DESC LIMIT 10")
    entradas = cursor.fetchall()
    cursor.execute("SELECT m.*, i.item, i.motor FROM movimientos m JOIN inventario i ON m.parte = i.parte WHERE m.tipo = 'salida' ORDER BY m.id DESC LIMIT 10")
    salidas = cursor.fetchall()
    conn.close()
    return render_template('stock.html', stock=lista_inventario, entries=entradas, exits=salidas, user=current_user)

@app.route('/mantenimiento')
@login_required
def mantenimiento():
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("SELECT motor_id, motor_modelo, equipo_asignado FROM control_services ORDER BY motor_id ASC")
    motores_disponibles = cursor.fetchall()
    conn.close()
    return render_template('mantenimiento.html', motores=motores_disponibles)

@app.route('/guardar_mantenimiento', methods=['POST'])
@login_required
def guardar_mantenimiento():
    fecha = request.form.get('fecha')
    responsable = request.form.get('responsable')
    motor_seleccionado = request.form.get('motor_id')
    nuevo_motor_id = request.form.get('nuevo_motor_id', '').strip()
    nuevo_motor_modelo = request.form.get('nuevo_motor_modelo', '').strip()
    equipo_seleccionado = request.form.get('equipo_asignado')
    nuevo_equipo_manual = request.form.get('nuevo_equipo_manual', '').strip()
    
    if equipo_seleccionado == 'MANUAL' and nuevo_equipo_manual:
        equipo_asignado = nuevo_equipo_manual
    else:
        equipo_asignado = equipo_seleccionado
        
    horas_registro = float(request.form.get('horas', 0))
    filtro_aceite = request.form.get('filtro_aceite', '').strip()
    filtro_combustible = request.form.get('filtro_combustible', '').strip()
    filtro_aire = request.form.get('filtro_aire', '').strip()
    aceite_motor = request.form.get('aceite_motor', '').strip()
    reparacion_embrague = "SÍ" if request.form.get('embrague') else "NO"
    reparacion_ferodo = "SÍ" if request.form.get('ferodo') else "NO"
    observaciones = request.form.get('observaciones', '').strip()
    
    conn = conectar_db()
    cursor = conn.cursor()
    
    if motor_seleccionado == 'NUEVO' and nuevo_motor_id and nuevo_motor_modelo:
        cursor.execute('''
            INSERT OR REPLACE INTO control_services (motor_id, motor_modelo, equipo_asignado, horas_actuales, ultimo_service, frecuencia_hs)
            VALUES (?, ?, ?, ?, ?, 300)
        ''', (nuevo_motor_id, nuevo_motor_modelo, equipo_asignado, horas_registro, horas_registro))
        motor_final_id = nuevo_motor_id
        motor_final_modelo = nuevo_motor_modelo
    else:
        cursor.execute("SELECT motor_modelo FROM control_services WHERE motor_id = ?", (motor_seleccionado,))
        res_m = cursor.fetchone()
        motor_final_id = motor_seleccionado
        motor_final_modelo = res_m['motor_modelo'] if res_m else "Desconocido"
        cursor.execute('''
            UPDATE control_services 
            SET equipo_asignado = ?, horas_actuales = ?, ultimo_service = ? 
            WHERE motor_id = ?
        ''', (equipo_asignado, horas_registro, horas_registro, motor_final_id))

    detalles_reparacion = []
    if reparacion_embrague == "SÍ": detalles_reparacion.append("Reparación de Embrague")
    if reparacion_ferodo == "SÍ": detalles_reparacion.append("Recambio de Ferodo")
    
    str_reparaciones = ", ".join(detalles_reparacion) if detalles_reparacion else "Mantenimiento Preventivo Regular"
    tarea_desc = f"Motor: {motor_final_modelo} ({motor_final_id}) en {equipo_asignado}. Labor: {str_reparaciones}. Novedades: {observaciones}"
    repuestos_detallados = f"F.Aceite: {filtro_aceite} | F.Comb: {filtro_combustible} | Aceite: {aceite_motor}"
    
    cursor.execute('''
        INSERT INTO ordenes_trabajo (tarea, responsable, prioridad, equipo_id, estado, fecha, repuesto_asociado, horas_registro, motor_id)
        VALUES (?, ?, 'ALTA', ?, 'COMPLETADA', ?, ?, ?, ?)
    ''', (tarea_desc, responsable, equipo_asignado, fecha, repuestos_detallados, horas_registro, motor_final_id))
    
    repuestos_a_descontar = [filtro_aceite, filtro_aire]
    if " / " in filtro_combustible:
        repuestos_a_descontar.extend(filtro_combustible.split(" / "))
    else:
        repuestos_a_descontar.append(filtro_combustible)
        
    for parte_id in repuestos_a_descontar:
        parte_id = parte_id.replace("Cod.", "").strip()
        if parte_id:
            cursor.execute("SELECT actual FROM inventario WHERE parte = ?", (parte_id,))
            inv_fila = cursor.fetchone()
            if inv_fila and inv_fila['actual'] > 0:
                nuevo_stock = inv_fila['actual'] - 1
                cursor.execute("UPDATE inventario SET actual = ? WHERE parte = ?", (nuevo_stock, parte_id))
                cursor.execute('''
                    INSERT INTO movimientos (tipo, parte, cantidad, destino_origen, responsable, fecha)
                    VALUES ('salida', ?, 1, ?, ?, ?)
                ''', (parte_id, f"Service Motor {motor_final_id}", responsable, fecha + " 00:00:00"))

    conn.commit()
    conn.close()
    return redirect(url_for('reportes'))

@app.route('/reportes')
@login_required
def reportes():
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM registro_riego ORDER BY fecha DESC")
    historico_riegos = cursor.fetchall()
    cursor.execute("SELECT * FROM ordenes_trabajo WHERE estado = 'COMPLETADA' ORDER BY fecha DESC")
    historico_ots = cursor.fetchall()
    cursor.execute("SELECT equipo_id, SUM(lamina_mm) as mm_totales, SUM(horas_operadas) as hs_totales, COUNT(id) as vueltas FROM registro_riego GROUP BY equipo_id")
    resum_equipos = cursor.fetchall()
    cursor.execute("SELECT *, (ultimo_service + frecuencia_hs) AS proximo_service, ((ultimo_service + frecuencia_hs) - horas_actuales) AS horas_restantes FROM control_services")
    motores_crudo = cursor.fetchall()
    
    motores_monitoreo = []
    for m in motores_crudo:
        hs_restantes = m['horas_restantes']
        if hs_restantes <= 0:
            estado_servicio = "VENCIDO"
            color_clase = "danger"
        elif hs_restantes <= 25:
            estado_servicio = "CRÍTICO"
            color_clase = "warning"
        else:
            estado_servicio = "AL DÍA"
            color_clase = "success"
            
        motores_monitoreo.append({
            "motor_id": m['motor_id'], "motor_modelo": m['motor_modelo'], "equipo_asignado": m['equipo_asignado'],
            "horas_actuales": round(m['horas_actuales'], 1), "ultimo_service": round(m['ultimo_service'], 1),
            "frecuencia_hs": m['frecuencia_hs'], "proximo_service": round(m['proximo_service'], 1),
            "horas_restantes": round(hs_restantes, 1), "estado": estado_servicio, "color": color_clase
        })
    conn.close()
    return render_template('reportes.html', riegos=historico_riegos, ots=historico_ots, resumen=resum_equipos, motores=motores_monitoreo, user=current_user)

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        usuario = request.form.get('username')
        clave = request.form.get('password')
        if usuario in usuarios_sistema and usuarios_sistema[usuario] == clave:
            user = User(usuario)
            login_user(user)
            return redirect(url_for('index'))
        else:
            error = "Usuario o contraseña incorrectos."
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))

if __name__ == '__main__':
    inicializar_db()
    puerto = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=puerto)
