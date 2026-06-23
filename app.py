from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, Response
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import sqlite3
import os
import io
import csv
from datetime import datetime, timedelta

app = Flask(__name__)

# --------------------------
# CONFIGURACIÓN SEGURA
# --------------------------
app.secret_key = os.environ.get("SECRET_KEY", "agroriego_secreto_marcelocarabajal")
DATABASE = 'agroriego_stock.db'

# Usar variables de entorno para usuario y contraseña en producción
USUARIO_SISTEMA = os.environ.get("APP_USER", "marcelo")
CLAVE_SISTEMA = os.environ.get("APP_PASS", "agro2026")
usuarios_sistema = {USUARIO_SISTEMA: CLAVE_SISTEMA}

# --------------------------
# GESTIÓN DE INICIO DE SESIÓN
# --------------------------
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message_category = "info"

class User(UserMixin):
    def __init__(self, id):
        self.id = id

@login_manager.user_loader
def load_user(user_id):
    if user_id in usuarios_sistema:
        return User(user_id)
    return None

# --------------------------
# CONEXIÓN A BASE DE DATOS
# --------------------------
def conectar_db():
    conn = sqlite3.connect(DATABASE, timeout=30.0)
    conn.row_factory = sqlite3.Row
    return conn

# --------------------------
# INICIALIZACIÓN DE TABLAS
# --------------------------
def inicializar_db():
    conn = conectar_db()
    cursor = conn.cursor()

    # Tabla de Inventario
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS inventario (
            parte TEXT PRIMARY KEY,
            item TEXT NOT NULL,
            motor TEXT,
            cantidad INTEGER DEFAULT 0,
            pasillo TEXT,
            estante TEXT
        )
    ''')

    # Tabla de Órdenes de Trabajo
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ordenes_trabajo (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            equipo_id TEXT NOT NULL,
            tarea TEXT NOT NULL,
            responsable TEXT NOT NULL,
            prioridad TEXT NOT NULL,
            repuesto_asociado TEXT,
            fecha TEXT NOT NULL,
            estado TEXT DEFAULT 'PENDIENTE'
        )
    ''')

    # Tabla de Registro de Riego - AGREGADO campo duracion_vuelta
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS registro_riego (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            equipo_id TEXT NOT NULL,
            lamina_mm REAL NOT NULL,
            horas_operadas REAL NOT NULL,
            presion_bar REAL,
            posicion_grados INTEGER,
            estado_operacion TEXT,
            fecha TEXT NOT NULL,
            lamina_programada REAL DEFAULT 0.0,
            duracion_vuelta REAL DEFAULT 0.0
        )
    ''')

    # Tabla de Alertas Críticas
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS alertas_criticas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            equipo_id TEXT NOT NULL,
            tipo_falla TEXT NOT NULL,
            descripcion TEXT,
            fecha_hora TEXT NOT NULL,
            activa INTEGER DEFAULT 1
        )
    ''')

    # Tabla de Control de Servicios y Mantenimiento
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS control_services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            equipo_asignado TEXT NOT NULL,
            horas_actuales REAL DEFAULT 0.0,
            horas_proximo_service REAL NOT NULL,
            frecuencia_horas REAL NOT NULL,
            descripcion_tarea TEXT NOT NULL
        )
    ''')

    # Tabla de Telemetría Actual
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS telemetria_actual (
            equipo_id TEXT PRIMARY KEY,
            latitud REAL,
            longitud REAL,
            presion_terminal REAL,
            posicion_actual INTEGER,
            estado_sistema TEXT,
            rssi TEXT,
            ultima_actualizacion TEXT
        )
    ''')

    # Datos iniciales de telemetría si están vacíos
    cursor.execute("SELECT COUNT(*) FROM telemetria_actual")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO telemetria_actual VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                       ("PIVOT-LOTE-A2", -25.1794, -63.8632, 1.8, 145, "MARCHA EN AGUA", "-88 dBm", "Hace 2 min"))
        cursor.execute("INSERT INTO telemetria_actual VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                       ("FRONTAL-F22", -25.1750, -63.8500, 0.0, 0, "PARADO FALTA PRESION", "-94 dBm", "Hace 14 min"))

    # Datos iniciales de servicios si están vacíos
    cursor.execute("SELECT COUNT(*) FROM control_services")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO control_services (equipo_asignado, horas_actuales, horas_proximo_service, frecuencia_horas, descripcion_tarea) VALUES (?, ?, ?, ?, ?)",
                       ("Pivot A2", 214.5, 250.0, 250.0, "Cambio aceite caja reductora central y filtros"))
        cursor.execute("INSERT INTO control_services (equipo_asignado, horas_actuales, horas_proximo_service, frecuencia_horas, descripcion_tarea) VALUES (?, ?, ?, ?, ?)",
                       ("Frontal F22", 480.0, 500.0, 500.0, "Engrase general de cardanes y revisión de alineación"))

    conn.commit()
    conn.close()

inicializar_db()

# --------------------------
# RUTA PRINCIPAL - DASHBOARD
# --------------------------
@app.route('/', methods=['GET', 'POST'])
@login_required
def index():
    conn = conectar_db()
    cursor = conn.cursor()
    equipo_seleccionado = request.args.get('equipo', 'PIVOT-LOTE-A2')

    # Procesar formulario de nueva alerta
    if request.method == 'POST':
        form_tipo = request.form.get('form_tipo')
        eq_id = request.form.get('equipo_id')
        if form_tipo == 'nueva_alerta' and eq_id:
            tipo_falla = request.form.get('tipo_falla', 'Sin especificar')
            desc = request.form.get('descripcion', '')
            ahora = datetime.now().strftime('%d/%m/%Y %H:%M')

            cursor.execute('''
                INSERT INTO alertas_criticas (equipo_id, tipo_falla, descripcion, fecha_hora, activa)
                VALUES (?, ?, ?, ?, 1)
            ''', (eq_id, tipo_falla, desc, ahora))

            cursor.execute('''
                UPDATE telemetria_actual 
                SET estado_sistema = ?, ultima_actualizacion = ?
                WHERE equipo_id = ?
            ''', (f"FALLA: {tipo_falla}", ahora, eq_id))

            conn.commit()
            flash("Alerta de falla registrada correctamente.", "danger")
            return redirect(url_for('index', equipo=eq_id))

    # Obtener datos de telemetría
    cursor.execute("SELECT * FROM telemetria_actual WHERE equipo_id = ?", (equipo_seleccionado,))
    fila = cursor.fetchone()
    data_equipo = {}

    if fila:
        presion = fila['presion_terminal']
        lectura_humana = fila['ultima_actualizacion']
        inactivo = False

        # Detectar si no hay señal hace más de 5 minutos
        try:
            ultima_vez = datetime.strptime(fila['ultima_actualizacion'], '%Y-%m-%d %H:%M:%S')
            if datetime.now() - ultima_vez > timedelta(minutes=5):
                inactivo = True
                lectura_humana = ultima_vez.strftime('%d/%m/%Y %H:%M') + " (Sin señal)"
        except:
            pass

        # Lógica de estado del equipo
        if presion < 0.2:
            estado_final = "⚪ APAGADO (Sin presión)"
            presion_final = 0.0
            caudal_final = "0"
        elif inactivo:
            estado_final = "❌ DETENIDO (Sin comunicación)"
            presion_final = 0.0
            caudal_final = "0"
        else:
            estado_final = fila['estado_sistema']
            presion_final = presion
            caudal_final = "185.000" if "MARCHA" in estado_final.upper() else "0"

        data_equipo = {
            "id": fila['equipo_id'],
            "nombre_corto": "Pivot Lote A2" if fila['equipo_id'] == "PIVOT-LOTE-A2" else "Frontal F22",
            "lote": "Lote A2 - Maíz (156 Ha)" if fila['equipo_id'] == "PIVOT-LOTE-A2" else "Cuadro Norte - Soja (210 Ha)",
            "estado": estado_final,
            "presion": round(presion_final, 2),
            "caudal": caudal_final,
            "posicion_tramo": f"{fila['posicion_actual']}°",
            "ultima_lectura": lectura_humana,
            "senal": fila['rssi'] if not inactivo else "-- dBm",
            "lat": fila['latitud'],
            "lng": fila['longitud']
        }
    else:
        data_equipo = {
            "id": equipo_seleccionado,
            "nombre_corto": equipo_seleccionado,
            "lote": "Lote no registrado",
            "estado": "DESCONOCIDO",
            "presion": 0.0,
            "caudal": "0",
            "posicion_tramo": "0°",
            "ultima_lectura": "Sin datos",
            "senal": "--",
            "lat": -25.1794,
            "lng": -63.8632
        }

    # Datos complementarios para el panel
    cursor.execute("SELECT * FROM alertas_criticas WHERE activa = 1 ORDER BY fecha_hora DESC")
    alertas_activas = cursor.fetchall()

    cursor.execute("SELECT SUM(lamina_mm) as mm_tot FROM registro_riego WHERE equipo_id = ?", (equipo_seleccionado,))
    total_acumulado = cursor.fetchone()['mm_tot'] or 0.0

    cursor.execute("SELECT fecha, lamina_mm, horas_operadas FROM registro_riego WHERE equipo_id = ? ORDER BY id DESC LIMIT 7", (equipo_seleccionado,))
    registros = cursor.fetchall()[::-1]

    conn.close()

    return render_template('dashboard.html',
                           data=data_equipo,
                           alertas=alertas_activas,
                           total_acumulado_mm=round(total_acumulado, 1),
                           fechas_riego=[r['fecha'] for r in registros],
                           laminas_riego=[r['lamina_mm'] for r in registros],
                           horas_riego=[r['horas_operadas'] for r in registros])

# --------------------------
# REGISTRO DE RIEGO
# --------------------------
@app.route('/registrar-riego', methods=['GET', 'POST'])
@login_required
def registrar_riego():
    conn = conectar_db()
    cursor = conn.cursor()
    fecha_hoy = datetime.now().strftime('%Y-%m-%d')

    if request.method == 'POST':
        form_accion = request.form.get('form_accion')

        # Guardar nuevo registro
        if form_accion == 'guardar':
            equipo_id = request.form.get('equipo_id')
            lamina_prog = float(request.form.get('lamina_programada', 0.0))
            lamina_real = float(request.form.get('lamina_mm', 0.0))
            horas = float(request.form.get('horas_operadas', 0.0))
            presion = float(request.form.get('presion_bar', 0.0))
            estado = request.form.get('estado_operacion', 'EN PROCESO')

            cursor.execute('''
                INSERT INTO registro_riego 
                (equipo_id, lamina_mm, horas_operadas, presion_bar, estado_operacion, fecha, lamina_programada)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (equipo_id, lamina_real, horas, presion, estado, fecha_hoy, lamina_prog))
            conn.commit()
            flash("Registro de riego guardado correctamente.", "success")

        # Finalizar registro existente
        elif form_accion == 'finalizar':
            registro_id = request.form.get('registro_id')
            hs_fin = float(request.form.get('hs_fin', 0.0))
            cursor.execute("SELECT horas_operadas FROM registro_riego WHERE id = ?", (registro_id,))
            reg = cursor.fetchone()
            if reg:
                duracion = abs(hs_fin - reg['horas_operadas'])
                cursor.execute('''
                    UPDATE registro_riego 
                    SET duracion_vuelta = ?, estado_operacion = 'COMPLETADO' 
                    WHERE id = ?
                ''', (duracion, registro_id))
                conn.commit()
                flash("Registro marcado como finalizado.", "info")

        return redirect(url_for('registrar_riego'))

    # Cargar datos para mostrar
    cursor.execute("SELECT equipo_id, fecha, lamina_mm, lamina_programada, horas_operadas, presion_bar, estado_operacion FROM registro_riego ORDER BY id DESC LIMIT 15")
    riegos_cargados = cursor.fetchall()

    cursor.execute("SELECT SUM(lamina_mm) as mm_tot FROM registro_riego")
    total_acumulado_mm = cursor.fetchone()['mm_tot'] or 0.0

    equipos_mapa = {
        "PIVOT-LOTE-A2": {"id": "PIVOT-LOTE-A2", "lote": "Lote A2 - Maíz (156 Ha)", "nombre_corto": "Pivot Lote A2"},
        "FRONTAL-F22": {"id": "FRONTAL-F22", "lote": "Cuadro Norte - Soja (210 Ha)", "nombre_corto": "Frontal F22"}
    }

    conn.close()

    return render_template('registrar_riego.html',
                           equipos=equipos_mapa,
                           riegos=riegos_cargados,
                           total_acumulado_mm=round(total_acumulado_mm, 1),
                           fecha_hoy=fecha_hoy,
                           user=current_user)

# --------------------------
# API PARA MAPA
# --------------------------
@app.route('/api/status')
def api_status():
    equipo_id = request.args.get('equipo', 'PIVOT-LOTE-A2')
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM telemetria_actual WHERE equipo_id = ?", (equipo_id,))
    fila = cursor.fetchone()
    conn.close()

    if fila:
        return jsonify({
            "equipo_id": fila['equipo_id'],
            "estado": fila['estado_sistema'],
            "latitud": fila['latitud'],
            "longitud": fila['longitud'],
            "presion": round(fila['presion_terminal'], 2),
            "posicion_angular": f"{fila['posicion_actual']}°",
            "rssi": fila['rssi'],
            "actualizacion": fila['ultima_actualizacion']
        }), 200
    else:
        lat_def = -25.1794 if equipo_id == "PIVOT-LOTE-A2" else -25.1750
        lng_def = -63.8632 if equipo_id == "PIVOT-LOTE-A2" else -63.8500
        return jsonify({
            "equipo_id": equipo_id,
            "latitud": lat_def,
            "longitud": lng_def,
            "presion": 0.0,
            "posicion_angular": "0°",
            "rssi": "-- dBm",
            "actualizacion": "Sin datos"
        }), 200

# --------------------------
# INICIO Y CIERRE DE SESIÓN
# --------------------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        usuario = request.form.get('username', '').strip()
        clave = request.form.get('password', '')
        if usuario in usuarios_sistema and usuarios_sistema[usuario] == clave:
            login_user(User(usuario))
            return redirect(url_for('index'))
        else:
            error = "Usuario o contraseña incorrectos."
    return render_template('login.html', error=error)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("Sesión cerrada correctamente.", "info")
    return redirect(url_for('login'))

# --------------------------
# GESTIÓN DE STOCK
# --------------------------
@app.route('/stock', methods=['GET', 'POST'])
@login_required
def stock():
    conn = conectar_db()
    cursor = conn.cursor()

    if request.method == 'POST':
        parte = request.form.get('parte', '').strip().upper()
        item = request.form.get('item', '').strip()
        motor = request.form.get('motor', '').strip()
        cantidad = int(request.form.get('cantidad', 0))
        pasillo = request.form.get('pasillo', '').strip()
        estante = request.form.get('estante', '').strip()

        if parte and item:
            cursor.execute('''
                INSERT INTO inventario (parte, item, motor, cantidad, pasillo, estante)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(parte) DO UPDATE SET
                    cantidad = cantidad + excluded.cantidad,
                    item = excluded.item,
                    motor = excluded.motor,
                    pasillo = excluded.pasillo,
                    estante = excluded.estante
            ''', (parte, item, motor, cantidad, pasillo, estante))
            conn.commit()
            flash(f"Insumo {parte} actualizado correctamente.", "success")
        else:
            flash("Complete el código de parte y descripción.", "warning")

        return redirect(url_for('stock'))

    cursor.execute("SELECT * FROM inventario ORDER BY parte ASC")
    items_stock = cursor.fetchall()
    conn.close()

    return render_template('stock.html', inventario=items_stock)

# --------------------------
# MANTENIMIENTO PREVENTIVO
# --------------------------
@app.route('/mantenimiento', methods=['GET', 'POST'])
@login_required
def mantenimiento():
    conn = conectar_db()
    cursor = conn.cursor()

    if request.method == 'POST':
        equipo = request.form.get('equipo_asignado', '').strip()
        frecuencia = float(request.form.get('frecuencia_horas', 0))
        horas_act = float(request.form.get('horas_actuales', 0))
        descripcion = request.form.get('descripcion_tarea', '').strip()
        proximo = horas_act + frecuencia

        if equipo and descripcion and frecuencia > 0:
            cursor.execute('''
                INSERT INTO control_services 
                (equipo_asignado, horas_actuales, horas_proximo_service, frecuencia_horas, descripcion_tarea)
                VALUES (?, ?, ?, ?, ?)
            ''', (equipo, horas_act, proximo, frecuencia, descripcion))
            conn.commit()
            flash("Plan de mantenimiento guardado.", "success")
        else:
            flash("Complete todos los campos obligatorios.", "warning")

        return redirect(url_for('mantenimiento'))

    cursor.execute("SELECT * FROM control_services ORDER BY horas_proximo_service ASC")
    servicios = cursor.fetchall()
    conn.close()

    return render_template('mantenimiento.html', servicios=servicios)

# --------------------------
# ÓRDENES DE TRABAJO
# --------------------------
@app.route('/crear-ot', methods=['POST'])
@login_required
def crear_ot():
    equipo_id = request.form.get('equipo_id', '').strip()
    tarea = request.form.get('tarea', '').strip()
    responsable = request.form.get('responsable', '').strip()
    prioridad = request.form.get('prioridad', 'MEDIA')
    repuesto = request.form.get('repuesto_asociado', '').strip().upper()
    fecha_hoy = datetime.now().strftime('%Y-%m-%d')

    if equipo_id and tarea and responsable:
        conn = conectar_db()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO ordenes_trabajo 
            (equipo_id, tarea, responsable, prioridad, repuesto_asociado, fecha, estado)
            VALUES (?, ?, ?, ?, ?, ?, 'PENDIENTE')
        ''', (equipo_id, tarea, responsable, prioridad, repuesto, fecha_hoy))
        conn.commit()
        conn.close()
        flash("Orden de trabajo creada correctamente.", "success")
    else:
        flash("Complete los campos obligatorios.", "warning")

    return redirect(url_for('index', equipo=equipo_id or 'PIVOT-LOTE-A2'))

@app.route('/finalizar-ot/<int:ot_id>')
@login_required
def finalizar_ot(ot_id):
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM ordenes_trabajo WHERE id = ?", (ot_id,))
    ot = cursor.fetchone()

    if ot:
        if ot['repuesto_asociado']:
            cursor.execute('UPDATE inventario SET cantidad = MAX(0, cantidad - 1) WHERE parte = ?', (ot['repuesto_asociado'],))
        cursor.execute("UPDATE ordenes_trabajo SET estado = 'DESPACHADA' WHERE id = ?", (ot_id,))
        conn.commit()
        flash("Orden finalizada y repuestos descontados.", "success")
    else:
        flash("Orden no encontrada.", "danger")

    conn.close()
    return redirect(url_for('index', equipo=ot['equipo_id'] if ot else 'PIVOT-LOTE-A2'))

# --------------------------
# GESTIÓN DE ALERTAS
# --------------------------
@app.route('/desactivar-alerta/<int:alerta_id>')
@login_required
def desactivar_alerta(alerta_id):
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("SELECT equipo_id FROM alertas_criticas WHERE id = ?", (alerta_id,))
    alerta = cursor.fetchone()

    if alerta:
        cursor.execute("UPDATE alertas_criticas SET activa = 0 WHERE id = ?", (alerta_id,))
        cursor.execute("UPDATE telemetria_actual SET estado_sistema = 'MARCHA EN AGUA' WHERE equipo_id = ?", (alerta['equipo_id'],))
        conn.commit()
        flash("Alerta marcada como solucionada.", "success")
    else:
        flash("Alerta no encontrada.", "danger")

    conn.close()
    return redirect(url_for('index', equipo=alerta['equipo_id'] if alerta else 'PIVOT-LOTE-A2'))

# --------------------------
# REPORTES Y EXPORTACIÓN
# --------------------------
@app.route('/reportes')
@login_required
def reportes():
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM registro_riego ORDER BY id DESC")
    todos_riegos = cursor.fetchall()
    conn.close()
    return render_template('reportes.html', riegos=todos_riegos)

@app.route('/descargar-datos-ciclo/<equipo_id>')
@login_required
def descargar_datos_ciclo(equipo_id):
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, fecha, lamina_programada, lamina_mm, horas_operadas, presion_bar, duracion_vuelta, estado_operacion 
        FROM registro_riego WHERE equipo_id = ? ORDER BY id ASC
    ''', (equipo_id,))
    filas = cursor.fetchall()
    conn.close()

    def generar_csv():
        output = io.StringIO()
        writer = csv.writer(output, delimiter=';')
        writer.writerow([
            'Nro_Turno', 'Fecha', 'Lamina_Programada_mm', 'Lamina_Real_mm',
            'Horas_Marcha', 'Presion_Bar', 'Duracion_Horas', 'Estado'
        ])
        for fila in filas:
            writer.writerow([
                fila['id'], fila['fecha'], fila['lamina_programada'], fila['lamina_mm'],
                fila['horas_operadas'], fila['presion_bar'], fila['duracion_vuelta'], fila['estado_operacion']
            ])
        return output.getvalue()

    response = Response(generar_csv(), mimetype='text/csv; charset=utf-8')
    response.headers.set("Content-Disposition", f"attachment; filename=historial_riego_{equipo_id}_{datetime.now().strftime('%Y%m%d')}.csv")
    return response

# --------------------------
# EJECUCIÓN DE LA APLICACIÓN
# --------------------------
if __name__ == '__main__':
    puerto = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=puerto, debug=False)
