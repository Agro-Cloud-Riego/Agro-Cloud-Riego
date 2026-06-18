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

# --- CONFIGURACIÓN DE BASE DE DATOS OPTIMIZADA CON TIMEOUT ---
def conectar_db():
    # El timeout de 30 segundos previene bloqueos 'database is locked' en Render
    conn = sqlite3.connect(DATABASE, timeout=30.0)
    conn.row_factory = sqlite3.Row
    return conn

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
    
    # Tabla de Órdenes de Trabajo (OT)
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
    
    # Tabla de Historial Hidrológico / Libro de Riego
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
            lamina_programada REAL DEFAULT 0.0
        )
    ''')
    
    # Tabla de Historial de Alertas Críticas
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
    
    # Tabla de Control de Horas Físicas y Servicios
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
    
    # Tabla de Telemetría Dinámica Real (Hardware LoRa / Simulación)
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
    
    # Datos semilla de telemetría si no existen
    cursor.execute("SELECT COUNT(*) FROM telemetria_actual")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO telemetria_actual VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                       ("PIVOT-LOTE-A2", -25.1794, -63.8632, 1.8, 145, "MARCHA EN AGUA", "-88 dBm", "Hace 2 min"))
        cursor.execute("INSERT INTO telemetria_actual VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                       ("FRONTAL-F22", -25.1750, -63.8500, 0.0, 0, "PARADO FALTA PRESION", "-94 dBm", "Hace 14 min"))
        
    # Datos semilla de servicios si no existen
    cursor.execute("SELECT COUNT(*) FROM control_services")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO control_services (equipo_asignado, horas_actuales, horas_proximo_service, frecuencia_horas, descripcion_tarea) VALUES (?, ?, ?, ?, ?)",
                       ("Pivot A2", 214.5, 250.0, 250.0, "Cambio aceite caja reductora central y filtros"))
        cursor.execute("INSERT INTO control_services (equipo_asignado, horas_actuales, horas_proximo_service, frecuencia_horas, descripcion_tarea) VALUES (?, ?, ?, ?, ?)",
                       ("Frontal F22", 480.0, 500.0, 500.0, "Engrase general de cardanes y revisión de alineación"))
        
    conn.commit()
    conn.close()

# Inicializar Base de Datos al arrancar la app
inicializar_db()

# --- RUTA PRINCIPAL: DASHBOARD DE MONITOREO LORA ---
@app.route('/', methods=['GET', 'POST'])
@login_required
def index():
    conn = conectar_db()
    cursor = conn.cursor()
    
    equipo_seleccionado = request.args.get('equipo', 'PIVOT-LOTE-A2')
    
    if request.method == 'POST':
        form_tipo = request.form.get('form_tipo')
        eq_id = request.form.get('equipo_id')
        
        if form_tipo == 'nueva_alerta':
            tipo_falla = request.form.get('tipo_falla')
            desc = request.form.get('descripcion')
            ahora = datetime.now().strftime('%H:%M - %d/%m')
            
            cursor.execute('''
                INSERT INTO alertas_criticas (equipo_id, tipo_falla, descripcion, fecha_hora, activa)
                VALUES (?, ?, ?, ?, 1)
            ''', (eq_id, tipo_falla, desc, ahora))
            
            cursor.execute('''
                UPDATE telemetria_actual 
                SET estado_sistema = ?, ultima_actualizacion = 'Alerta Reportada'
                WHERE equipo_id = ?
            ''', (f"FALLA: {tipo_falla}", eq_id))
            
            conn.commit()
            conn.close()
            flash("Alerta de rotura emitida al panel técnico.", "danger")
            return redirect(url_for('index', equipo=equipo_seleccionado))

    cursor.execute("SELECT * FROM telemetria_actual WHERE equipo_id = ?", (equipo_seleccionado,))
    fila_telemetria = cursor.fetchone()
    
    if fila_telemetria:
        estado_final = fila_telemetria['estado_sistema']
        presion_final = fila_telemetria['presion_terminal']
        caudal_final = "185.000" if "MARCHA" in estado_final else "0"
        
        # --- PARSEO DE FECHA Y HORA EN TIEMPO REAL ---
        lectura_humana = fila_telemetria['ultima_actualizacion']
        try:
            # Intentamos leer el timestamp real si viene del hardware
            ultima_vez = datetime.strptime(fila_telemetria['ultima_actualizacion'], '%Y-%m-%d %H:%M:%S')
            
            # Si pasaron más de 5 minutos sin reportar, asumimos inactividad técnica
            if datetime.now() - ultima_vez > timedelta(minutes=5):
                estado_final = "❌ DETENIDO (Desconectado / Sin Señal)"
                presion_final = 0.0
                caudal_final = "0"
                lectura_humana = ultima_vez.strftime('%d/%m/%Y %H:%M') + " (Inactivo)"
            else:
                # Formato ordenado legible: Día/Mes/Año Hora:Minutos
                lectura_humana = ultima_vez.strftime('%d/%m/%Y %H:%M')
        except Exception:
            # Si el registro es una semilla vieja o texto ('Hace 2 min', 'Turno Cargado'), se mantiene sin romper la app
            pass

        data_equipo = {
            "id": fila_telemetria['equipo_id'],
            "nombre_corto": "Pivot Lote A2" if fila_telemetria['equipo_id'] == "PIVOT-LOTE-A2" else "Frontal F22",
            "lote": "Lote A2 - Maíz (156 Ha)" if fila_telemetria['equipo_id'] == "PIVOT-LOTE-A2" else "Cuadro Norte - Soja (210 Ha)",
            "estado": estado_final,
            "presion": presion_final, 
            "caudal": caudal_final,
            "posicion_tramo": f"{fila_telemetria['posicion_actual']}°",
            "ultima_lectura": lectura_humana,
            "senal": fila_telemetria['rssi'] if "Inactivo" not in lectura_humana else "-- dBm",
            "lat": fila_telemetria['latitud'],
            "lng": fila_telemetria['longitud']
        }
    else:
        data_equipo = {"id": equipo_seleccionado, "nombre_corto": equipo_seleccionado, "lote": "Lote Desconocido", "estado": "DESCONECTADO", "presion": 0.0, "caudal": "0", "posicion_tramo": "0°", "ultima_lectura": "Nunca", "senal": "--", "lat": -25.1794, "lng": -63.8632}

    todos_equipos = {
        "PIVOT-LOTE-A2": {"nombre_corto": "Pivot Lote A2"},
        "FRONTAL-F22": {"nombre_corto": "Frontal F22"}
    }
    
    cursor.execute("SELECT * FROM ordenes_trabajo WHERE equipo_id = ? AND estado = 'PENDIENTE'", (equipo_seleccionado,))
    ots = cursor.fetchall()
    
    cursor.execute("SELECT parte, item, motor FROM inventario WHERE cantidad > 0")
    repuestos = cursor.fetchall()
    
    cursor.execute("SELECT * FROM alertas_criticas WHERE activa = 1")
    alertas_activas = cursor.fetchall()
    
    cursor.execute("SELECT SUM(lamina_mm) as mm_tot FROM registro_riego WHERE equipo_id = ?", (equipo_seleccionado,))
    total_acumulado_mm = cursor.fetchone()['mm_tot'] or 0.0
    
    cursor.execute("SELECT fecha, lamina_mm, horas_operadas FROM registro_riego WHERE equipo_id = ? ORDER BY id DESC LIMIT 7", (equipo_seleccionado,))
    registros_grafico = cursor.fetchall()[::-1]
    
    fechas_riego = [r['fecha'] for r in registros_grafico]
    laminas_riego = [r['lamina_mm'] for r in registros_grafico]
    horas_riego = [r['horas_operadas'] for r in registros_grafico]
    
    conn.close()
    
    return render_template('dashboard.html', 
                           data=data_equipo, 
                           todos_equipos=todos_equipos, 
                           ot=ots, 
                           repuestos=repuestos, 
                           alertas=alertas_activas,
                           total_acumulado_mm=round(total_acumulado_mm, 1),
                           fechas_riego=fechas_riego,
                           laminas_riego=laminas_riego,
                           horas_riego=horas_riego)

# --- SECCIÓN: REGISTRO DE RIEGO (CARGA 100% MANUAL) ---
@app.route('/registrar-riego', methods=['GET', 'POST'])
@login_required
def registrar_riego():
    conn = conectar_db()
    cursor = conn.cursor()
    
    equipo_id = request.args.get('equipo', 'PIVOT-LOTE-A2')
    
    if request.method == 'POST':
        equipo_id = request.form.get('equipo_id', equipo_id).strip()
        lamina_prog = request.form.get('lamina_programada')
        lamina_prog_val = float(lamina_prog) if lamina_prog else 0.0
        fecha_riego = request.form.get('fecha')
        
        horas_operadas = float(request.form.get('horas_operadas', 0))
        lamina_real = float(request.form.get('lamina_mm', 0))
        presion_trabajo = float(request.form.get('presion_bar', 0.0))
        
        cursor.execute('''
            INSERT INTO registro_riego (equipo_id, lamina_mm, horas_operadas, presion_bar, posicion_grados, estado_operacion, fecha, lamina_programada) 
            VALUES (?, ?, ?, ?, 0, 'MARCHA', ?, ?)
        ''', (equipo_id, lamina_real, horas_operadas, presion_trabajo, fecha_riego, lamina_prog_val))
        
        mapa_equipos = {"PIVOT-LOTE-A2": "Pivot A2", "FRONTAL-F22": "Frontal F22"}
        nombre_mapeado = mapa_equipos.get(equipo_id, equipo_id)
        
        if horas_operadas > 0:
            cursor.execute('''
                UPDATE control_services 
                SET horas_actuales = horas_actuales + ?
                WHERE equipo_asignado = ?
            ''', (horas_operadas, nombre_mapeado))
        
        cursor.execute('''
            UPDATE telemetria_actual
            SET estado_sistema = 'MARCHA EN AGUA', presion_terminal = ?, ultima_actualizacion = 'Turno Cargado'
            WHERE equipo_id = ?
        ''', (presion_trabajo, equipo_id))
        
        conn.commit()
        conn.close() 
        
        flash(f"Registro de riego para '{equipo_id}' guardado correctamente.", "success")
        return redirect(url_for('index', equipo=equipo_id))

    cursor.execute("SELECT SUM(lamina_mm) as mm_tot FROM registro_riego WHERE equipo_id = ?", (equipo_id,))
    total_acumulado_mm = cursor.fetchone()['mm_tot'] or 0.0
    
    cursor.execute("SELECT equipo_id, fecha, lamina_mm, lamina_programada, horas_operadas, presion_bar FROM registro_riego ORDER BY id DESC LIMIT 10")
    riegos_cargados = cursor.fetchall()
    
    equipos_mapa = {
        "PIVOT-LOTE-A2": {"id": "PIVOT-LOTE-A2", "lote": "Lote A2 - Maíz (156 Ha)", "nombre_corto": "Pivot Lote A2"},
        "FRONTAL-F22": {"id": "FRONTAL-F22", "lote": "Cuadro Norte - Soja (210 Ha)", "nombre_corto": "Frontal F22"}
    }
    
    data_equipo = equipos_mapa.get(equipo_id, {"id": equipo_id, "lote": "Carga Manual", "nombre_corto": equipo_id})
    
    conn.close() 
    fecha_hoy = datetime.now().strftime('%Y-%m-%d')
    
    return render_template('registrar_riego.html', 
                           data=data_equipo, 
                           riegos=riegos_cargados, 
                           total_acumulado_mm=round(total_acumulado_mm, 1), 
                           fecha_hoy=fecha_hoy,
                           user=current_user)

# --- ENDPOINT API PARA EL MAPA ---
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
            "equipo_id": fila['equipo_id'], "estado": fila['estado_sistema'],
            "latitud": fila['latitud'], "longitud": fila['longitud'],
            "presion": fila['presion_terminal'], "posicion_angular": f"{fila['posicion_actual']}°",
            "rssi": fila['rssi'], "actualizacion": fila['ultima_actualizacion']
        }), 200
    else:
        lat_def = -25.1794 if equipo_id == "PIVOT-LOTE-A2" else -25.1750
        lng_def = -63.8632 if equipo_id == "PIVOT-LOTE-A2" else -63.8500
        return jsonify({
            "equipo_id": equipo_id, "latitud": lat_def, "longitud": lng_def,
            "presion": 0.0, "posicion_angular": "0°", "rssi": "0 dBm",
            "actualizacion": "Sin hardware"
        }), 200

# --- ACCESO Y SEGURIDAD ---
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
            error = "Credenciales de operador incorrectas."
    return render_template('login.html', error=error)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# --- CONTROL DE STOCK ---
@app.route('/stock', methods=['GET', 'POST'])
@login_required
def stock():
    conn = conectar_db()
    cursor = conn.cursor()
    
    if request.method == 'POST':
        parte = request.form.get('parte').strip().upper()
        item = request.form.get('item')
        motor = request.form.get('motor')
        amount = int(request.form.get('cantidad', 0))
        pasillo = request.form.get('pasillo')
        estante = request.form.get('estante')
        
        cursor.execute('''
            INSERT INTO inventario (parte, item, motor, cantidad, pasillo, estante)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(parte) DO UPDATE SET
                cantidad = cantidad + excluded.cantidad,
                item = excluded.item,
                motor = excluded.motor,
                pasillo = excluded.pasillo,
                estante = excluded.estante
        ''', (parte, item, motor, amount, pasillo, estante))
        conn.commit()
        conn.close()
    
        flash(f"Insumo [{parte}] actualizado.", "success")
        return redirect(url_for('stock'))
        
    cursor.execute("SELECT * FROM inventario ORDER BY parte ASC")
    items_stock = cursor.fetchall()
    conn.close()
    return render_template('stock.html', inventario=items_stock)

# --- MANTENIMIENTO PREVENTIVO ---
@app.route('/mantenimiento', methods=['GET', 'POST'])
@login_required
def mantenimiento():
    conn = conectar_db()
    cursor = conn.cursor()
    
    if request.method == 'POST':
        equipo = request.form.get('equipo_asignado')
        freq = float(request.form.get('frecuencia_horas'))
        horas_act = float(request.form.get('horas_actuales', 0))
        desc = request.form.get('descripcion_tarea')
        prox = horas_act + freq
        
        cursor.execute('''
            INSERT INTO control_services (equipo_asignado, horas_actuales, horas_proximo_service, frecuencia_horas, descripcion_tarea)
            VALUES (?, ?, ?, ?, ?)
        ''', (equipo, horas_act, prox, freq, desc))
        conn.commit()
        conn.close()
        flash("Plan de service preventivo guardado.", "success")
        return redirect(url_for('mantenimiento'))
        
    cursor.execute("SELECT * FROM control_services ORDER BY id DESC")
    servicios = cursor.fetchall()
    conn.close()
    return render_template('mantenimiento.html', servicios=servicios)

# --- ÓRDENES DE TRABAJO (OT) ---
@app.route('/crear-ot', methods=['POST'])
@login_required
def crear_ot():
    equipo_id = request.form.get('equipo_id')
    tarea = request.form.get('tarea')
    responsable = request.form.get('responsable')
    prioridad = request.form.get('prioridad')
    repuesto_asociado = request.form.get('repuesto_asociado')
    fecha_hoy = datetime.now().strftime('%Y-%m-%d')
    
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO ordenes_trabajo (equipo_id, tarea, responsable, prioridad, repuesto_asociado, fecha, estado)
        VALUES (?, ?, ?, ?, ?, ?, 'PENDIENTE')
    ''', (equipo_id, tarea, responsable, prioridad, repuesto_asociado, fecha_hoy))
    conn.commit()
    conn.close()
    
    flash("Orden técnica lanzada con éxito.", "success")
    return redirect(url_for('index', equipo=equipo_id))

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
    conn.close()
    flash("Orden técnica cerrada y repuestos descontados.", "success")
    return redirect(url_for('index', equipo=ot['equipo_id'] if ot else 'PIVOT-LOTE-A2'))

@app.route('/desactivar-alerta/<int:alerta_id>')
@login_required
def desactivar_alerta(alerta_id):
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("SELECT equipo_id FROM alertas_criticas WHERE id = ?", (alerta_id,))
    al = cursor.fetchone()
    cursor.execute("UPDATE alertas_criticas SET activa = 0 WHERE id = ?", (alerta_id,))
    if al:
        cursor.execute("UPDATE telemetria_actual SET estado_sistema = 'MARCHA EN AGUA' WHERE equipo_id = ?", (al['equipo_id'],))
    conn.commit()
    conn.close()
    flash("Alerta técnica solucionada.", "success")
    return redirect(url_for('index', equipo=al['equipo_id'] if al else 'PIVOT-LOTE-A2'))
    
# --- REPORTES Y EXPORTACIÓN ---
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
    cursor.execute('SELECT id, fecha, lamina_programada, lamina_mm, horas_operadas, presion_bar FROM registro_riego WHERE equipo_id = ? ORDER BY id ASC', (equipo_id,))
    filas = cursor.fetchall()
    conn.close()
    
    def generar_csv():
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Nro_Turno', 'Fecha_Operacion', 'Lamina_Programada_mm', 'Lamina_Real_Aplicada_mm', 'Horas_Marcha_Panel', 'Presion_Trabajo_Bar'])
        for f in filas:
            writer.writerow([f['id'], f['fecha'], f['lamina_programada'], f['lamina_mm'], f['horas_operadas'], f['presion_bar']])
        return output.getvalue()
        
    response = Response(generar_csv(), mimetype='text/csv')
    response.headers.set("Content-Disposition", f"attachment; filename=historial_riego_{equipo_id}.csv")
    return response

# --- ADAPTADOR DE PUERTOS PARA PRODUCCIÓN EN LA NUBE ---
if __name__ == '__main__':
    puerto = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=puerto, debug=True)
