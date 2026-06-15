from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import sqlite3
import os
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
            amount INTEGER, -- Nota: mapeado internamente a cantidad en tus formularios
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
            repuesto_asociado TEXT DEFAULT NULL
        )
    ''')

    # Tabla Histórica de Riego
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS registro_riego (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            equipo_id TEXT,
            lamina_mm REAL,
            horas_operadas REAL,
            fecha TEXT
        )
    ''')

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
    
    # NUEVA TABLA: Estado de Telemetría en Tiempo Real de las Placas Hardware
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS telemetria_equipos (
            equipo_id TEXT PRIMARY KEY,
            latitud REAL,
            longitud REAL,
            presion_terminal REAL,
            rssi TEXT,
            ultima_actualizacion TEXT
        )
    ''')
    
    # CORRECCIÓN DE UBICACIÓN REAL: Se cargan tus coordenadas en formato decimal para Joaquín V. González
    cursor.execute("INSERT OR IGNORE INTO telemetria_equipos VALUES ('PIVOT-LOTE-A2', -25.1794, -63.8632, 2.4, '-98 dBm', 'Nunca')")
    cursor.execute("INSERT OR IGNORE INTO telemetria_equipos VALUES ('FRONTAL-F22', -25.1750, -63.8500, 3.2, '-85 dBm', 'Nunca')")

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
        ("1182313", "Deutz 1013 Powers", "Filtros", "Filtro Aire Reforzado", "Estante C2", 2, 2),
        ("Poliuretano", "Varios", "Bombas", "Goma de Acoplamiento", "Estante D1", 2, 3),
        ("Carburo Silicio", "Varios", "Bombas", "Sello Mecánico Cornell", "Estante D1", 2, 1)
    ]
    cursor.executemany('''
        INSERT OR IGNORE INTO inventario (parte, motor, categoria, item, ubicacion, minimo, actual)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', repuestos_iniciales)

    conn.commit()
    conn.close()

# --- ENTRADA DE DATOS DESDE LA PLACA HELTEC (API GATEWAY) ---
@app.route('/api/telemetria', methods=['POST'])
def recibir_telemetria():
    """
    Ruta para recibir datos mediante POST HTTP desde el Gateway LoRa.
    No interfiere con el uso de la web.
    """
    data = request.get_json()
    if not data or 'equipo_id' not in data:
        return jsonify({"status": "error", "message": "Datos incompletos"}), 400
        
    equipo_id = data.get('equipo_id')
    lat = data.get('latitud')
    lng = data.get('longitud')
    presion = data.get('presion_terminal')
    rssi = data.get('rssi', '-90 dBm')
    fecha_gps = (datetime.utcnow() - timedelta(hours=3)).strftime('%d/%m/%Y a las %I:%M %p')
    
    conn = conectar_db()
    cursor = conn.cursor()
    
    # Actualizar tabla de telemetría en tiempo real
    cursor.execute('''
        INSERT INTO telemetria_equipos (equipo_id, latitud, longitud, presion_terminal, rssi, ultima_actualizacion)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(equipo_id) DO UPDATE SET
            latitud=excluded.latitud,
            longitud=excluded.longitud,
            presion_terminal=excluded.presion_terminal,
            rssi=excluded.rssi,
            ultima_actualizacion=excluded.ultima_actualizacion
    ''', (equipo_id, lat, lng, presion, rssi, fecha_gps))
    
    # Alerta automática preventiva si la presión baja de 1.5 Bar
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


# --- SALIDA DE DATOS EN TIEMPO REAL PARA EL MAPA (API STATUS) ---
@app.route('/api/status', methods=['GET'])
@login_required
def obtener_status_tiempo_real():
    """
    Ruta que consulta el mapa mediante AJAX para actualizar la posición
    del marcador y las métricas en pantalla sin recargar la página.
    """
    equipo_id = request.args.get('equipo')
    if not equipo_id:
        return jsonify({"status": "error", "message": "Falta equipo_id"}), 400

    conn = conectar_db()
    cursor = conn.cursor()
    
    # Buscamos los datos dinámicos actualizados por el hardware Heltec
    cursor.execute("SELECT * FROM telemetria_equipos WHERE equipo_id = ?", (equipo_id,))
    fila = cursor.fetchone()
    conn.close()

    if fila:
        # Estado dinámico según esté o no reportando
        estado_motor = "MARCHA" if fila['ultima_actualizacion'] != "Nunca" else "DESCONECTADO"
        
        return jsonify({
            "latitud": fila['latitud'],
            "longitud": fila['longitud'],
            "presion": str(fila['presion_terminal']),
            "caudal": "115.000 L/h" if equipo_id == "PIVOT-LOTE-A2" else "120.000 L/h",
            "estado": estado_motor,
            "ultima_lectura": fila['ultima_actualizacion'],
            "senal": fila['rssi']
        }), 200
    
    return jsonify({"status": "error", "message": "Equipo no encontrado"}), 404


# --- PANEL CENTRAL ---
@app.route('/', methods=['GET', 'POST'])
@login_required
def index():
    conn = conectar_db()
    cursor = conn.cursor()

    if request.method == 'POST' and request.form.get('form_tipo') == 'nueva_ot':
        tarea = request.form.get('tarea')
        responsable = request.form.get('responsable')
        prioridad = request.form.get('prioridad')
        equipo_id = request.form.get('equipo_id')
        repuesto = request.form.get('repuesto_asociado')
        if repuesto == "": repuesto = None
        
        fecha_actual = (datetime.utcnow() - timedelta(hours=3)).strftime('%Y-%m-%d')
        cursor.execute('''
            INSERT INTO ordenes_trabajo (tarea, responsable, prioridad, equipo_id, estado, fecha, repuesto_asociado) 
            VALUES (?, ?, ?, ?, 'PENDIENTE', ?, ?)
        ''', (tarea, responsable, prioridad, equipo_id, fecha_actual, repuesto))
        conn.commit()
        return redirect(url_for('index', equipo=equipo_id))

    if request.method == 'POST' and request.form.get('form_tipo') == 'nuevo_riego':
        equipo_id = request.form.get('equipo_id')
        lamina = float(request.form.get('lamina_mm', 0))
        horas = float(request.form.get('horas_operadas', 0))
        fecha_riego = request.form.get('fecha_riego')
        cursor.execute("INSERT INTO registro_riego (equipo_id, lamina_mm, horas_operadas, fecha) VALUES (?, ?, ?, ?)", (equipo_id, lamina, horas, fecha_riego))
        conn.commit()
        return redirect(url_for('index', equipo=equipo_id))

    if request.method == 'POST' and request.form.get('form_tipo') == 'nueva_alerta':
        equipo_id = request.form.get('equipo_id')
        tipo = request.form.get('tipo_falla')
        desc = request.form.get('descripcion')
        fechahora = (datetime.utcnow() - timedelta(hours=3)).strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute("INSERT INTO alertas_sistema (equipo_id, tipo_falla, descripcion, estado, fecha_hora) VALUES (?, ?, ?, 'ACTIVA', ?)", (equipo_id, tipo, desc, fechahora))
        conn.commit()
        return redirect(url_for('index', equipo=equipo_id))

    # Estructura de equipos estáticos
    equipos_riego = {
        "PIVOT-LOTE-A2": {
            "id": "PIVOT-LOTE-A2", "nombre_corto": "Lote A2", "tipo": "Pivot Central", "lote": "Lote A2 (156 Ha)",
            "posicion": "Calculando...", "caudal": "115.000 L/h", "estado": "MARCHA",
            "hs_riego": 47.7, "hs_falla": 0.0, "hs_movimiento": 0.0, "hs_parado": 14.6
        },
        "FRONTAL-F22": {
            "id": "FRONTAL-F22", "nombre_corto": "Frontal F22", "tipo": "Avance Frontal Lineal", "lote": "Cuadro Norte (210 Ha)",
            "posicion": "Tramo Fijo", "caudal": "120.000 L/h", "estado": "MARCHA",
            "hs_riego": 72.3, "hs_falla": 1.1, "hs_movimiento": 5.4, "hs_parado": 8.2
        }
    }
    
    id_solicitado = request.args.get('equipo', 'PIVOT-LOTE-A2')
    if id_solicitado not in equipos_riego: id_solicitado = "PIVOT-LOTE-A2"
    
    # Cruzar con los datos dinámicos de telemetría de la base de datos
    cursor.execute("SELECT * FROM telemetria_equipos WHERE equipo_id = ?", (id_solicitado,))
    tel_db = cursor.fetchone()
    
    data_render = equipos_riego[id_solicitado]
    if tel_db:
        data_render["presion"] = f"{tel_db['presion_terminal']} Bar"
        data_render["senal"] = tel_db["rssi"]
        data_render["lat"] = tel_db["latitud"]
        data_render["lng"] = tel_db["longitud"]
        data_render["ultima_lectura"] = tel_db["ultima_actualizacion"]
        data_render["posicion"] = f"GPS: {tel_db['latitud']}, {tel_db['longitud']}"

    cursor.execute("SELECT * FROM ordenes_trabajo WHERE estado = 'PENDIENTE' AND equipo_id = ? ORDER BY id DESC", (id_solicitado,))
    ot_reales = cursor.fetchall()
    
    cursor.execute("SELECT fecha, lamina_mm, horas_operadas FROM registro_riego WHERE equipo_id = ? ORDER BY fecha ASC LIMIT 10", (id_solicitado,))
    registros_db = cursor.fetchall()
    
    eje_x_fechas = [r['fecha'] for r in registros_db]
    datos_y_lamina = [r['lamina_mm'] for r in registros_db]
    datos_y_horas = [r['horas_operadas'] for r in registros_db]
    
    cursor.execute("SELECT SUM(lamina_mm) as total FROM registro_riego WHERE equipo_id = ?", (id_solicitado,))
    total_mm = cursor.fetchone()['total'] or 0.0

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
                           laminas_riego=datos_y_lamina,
                           horas_riego=datos_y_horas,
                           total_acumulado_mm=round(total_mm, 1),
                           alertas=alertas_activas,
                           repuestos=repuestos_taller)

# --- ACCIONES RÁPIDAS ---
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

# --- PANEL STOCK ---
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
                    INSERT OR IGNORE INTO inventario (parte, motor, categoria, item, ubicacion, minimo, actual)
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
    return render_template('stock.html', stock=lista_inventario, entradas=entradas, salidas=salidas, user=current_user)

# --- REPORTE GENERAL ---
@app.route('/reportes')
@login_required
def reportes():
    conn = conectar_db()
    cursor = conn.cursor()
    
    # Asegurar que se use el orden correcto de fechas para los reportes
    cursor.execute("SELECT * FROM registro_riego ORDER BY fecha DESC")
    historico_riegos = cursor.fetchall()
    
    cursor.execute("SELECT * FROM ordenes_trabajo WHERE estado = 'COMPLETADA' ORDER BY fecha DESC")
    historico_ots = cursor.fetchall()
    
    cursor.execute("SELECT equipo_id, SUM(lamina_mm) as mm_totales, SUM(horas_operadas) as hs_totales, COUNT(id) as vueltas FROM registro_riego GROUP BY equipo_id")
    resumen_equipos = cursor.fetchall()
    
    conn.close()
    return render_template('reportes.html', 
                           riegos=historico_riegos, 
                           ots=historico_ots, 
                           resumen=resumen_equipos, 
                           user=current_user)

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
        else: error = "Usuario o contraseña incorrectos."
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))

if __name__ == '__main__':
    inicializar_db()
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
