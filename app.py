from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, Response
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os
import io
import csv
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = 'agroriego_secreto_marcelocarabajal_2026'
DATABASE = 'agroriego_stock.db'

# --- CONFIGURACIÓN DE LOGIN SEGURA ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, id):
        self.id = id

# 🔐 CONTRASEÑA CIFRADA (NUNCA EN TEXTO PLANO)
usuarios_sistema = {"marcelo": generate_password_hash("agro2026")}

@login_manager.user_loader
def load_user(user_id):
    if user_id in usuarios_sistema:
        return User(user_id)
    return None

# --- RUTA DE LOGIN ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username in usuarios_sistema and check_password_hash(usuarios_sistema[username], password):
            user = User(username)
            login_user(user)
            return redirect(url_for('index'))
        else:
            flash('Usuario o contraseña incorrectos', 'danger')
    return '''
        <div style="background:#0b0f19; color:white; height:100vh; display:flex; flex-direction:column; justify-content:center; align-items:center; font-family:sans-serif;">
            <form method="POST" style="background:#131c2e; padding:30px; border-radius:12px; border:1px solid #233554; display:flex; flex-direction:column; gap:15px; width:300px;">
                <h3 style="margin:0; text-align:center;">AgroRiego Pro - Acceso</h3>
                <input type="text" name="username" placeholder="Usuario (marcelo)" required style="padding:10px; background:#0f172a; border:1px solid #233554; color:white; border-radius:6px;">
                <input type="password" name="password" placeholder="Contraseña" required style="padding:10px; background:#0f172a; border:1px solid #233554; color:white; border-radius:6px;">
                <button type="submit" style="background:#10b981; color:white; border:none; padding:12px; font-weight:bold; border-radius:6px; cursor:pointer;">Ingresar al Sistema</button>
            </form>
        </div>
    '''

# --- RUTA DE CERRAR SESIÓN ---
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Sesión cerrada correctamente.', 'success')
    return redirect(url_for('login'))

# --- BASE DE DATOS ---
def conectar_db():
    conn = sqlite3.connect(DATABASE, timeout=30.0)
    conn.row_factory = sqlite3.Row
    return conn

def inicializar_db():
    conn = conectar_db()
    cursor = conn.cursor()
    
    # Inventario
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
    
    # Órdenes de Trabajo
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
    
    # Registro de Riego
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS registro_riego (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            equipo_id TEXT NOT NULL,
            fecha TEXT NOT NULL,
            horas_operadas REAL NOT NULL,
            horas_parada TEXT,
            duracion_vuelta REAL,
            posicion_grados REAL,
            lamina_mm REAL NOT NULL,
            estado_operacion TEXT,
            presion_bar REAL,
            lamina_programada REAL DEFAULT 0.0,
            nro_vuelta INTEGER
        )
    ''')
    
    # Alertas
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
    
    # Servicios
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
    
    # Telemetría (AHORA GUARDAMOS FECHA REAL)
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
    
    # Datos iniciales
    cursor.execute("SELECT COUNT(*) FROM telemetria_actual")
    if cursor.fetchone()[0] == 0:
        ahora = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute("INSERT INTO telemetria_actual VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                       ("PIVOT-LOTE-A2", -25.1794, -63.8632, 1.8, 145, "MARCHA EN AGUA", "-88 dBm", ahora))
        cursor.execute("INSERT INTO telemetria_actual VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                       ("FRONTAL-F22", -25.1750, -63.8500, 0.0, 0, "PARADO FALTA PRESION", "-94 dBm", ahora))
        
    cursor.execute("SELECT COUNT(*) FROM control_services")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO control_services VALUES (NULL, ?, ?, ?, ?, ?)",
                       ("Pivot A2", 214.5, 250.0, 250.0, "Cambio aceite caja reductora central y filtros"))
        cursor.execute("INSERT INTO control_services VALUES (NULL, ?, ?, ?, ?, ?)",
                       ("Frontal F22", 480.0, 500.0, 500.0, "Engrase general de cardanes y revisión de alineación"))
        
    conn.commit()
    conn.close()

inicializar_db()

# --- PANEL PRINCIPAL ---
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
            ahora = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute('INSERT INTO alertas_criticas VALUES (NULL, ?, ?, ?, ?, 1)', (eq_id, tipo_falla, desc, ahora))
            cursor.execute('UPDATE telemetria_actual SET estado_sistema = ?, ultima_actualizacion = ? WHERE equipo_id = ?', (f"FALLA: {tipo_falla}", ahora, eq_id))
            conn.commit()
            flash("Alerta registrada", "danger")
            return redirect(url_for('index', equipo=eq_id))

    cursor.execute("SELECT * FROM telemetria_actual WHERE equipo_id = ?", (equipo_seleccionado,))
    fila_telemetria = cursor.fetchone()
    data_equipo = {}

    if fila_telemetria:
        estado_final = fila_telemetria['estado_sistema']
        presion_final = fila_telemetria['presion_terminal']
        caudal_final = "185.000" if "MARCHA" in estado_final else "0"
        lectura_humana = fila_telemetria['ultima_actualizacion']
        try:
            ultima_vez = datetime.strptime(fila_telemetria['ultima_actualizacion'], '%Y-%m-%d %H:%M:%S')
            if datetime.now() - ultima_vez > timedelta(minutes=5):
                estado_final = "❌ DETENIDO (Sin Señal)"
                presion_final = 0.0
                caudal_final = "0"
                lectura_humana = ultima_vez.strftime('%d/%m/%Y %H:%M') + " (Inactivo)"
            else:
                lectura_humana = "Hace " + str((datetime.now() - ultima_vez).seconds // 60) + " min"
        except:
            lectura_humana = "Fecha inválida"

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
        data_equipo = {"id": equipo_seleccionado, "nombre_corto": equipo_seleccionado, "lote": "Desconocido", "estado": "SIN DATOS", "presion":0, "caudal":"0", "posicion_tramo":"0°", "ultima_lectura":"Nunca", "senal":"--", "lat":-25.1794, "lng":-63.8632}

    todos_equipos = {"PIVOT-LOTE-A2": {"nombre_corto":"Pivot Lote A2"}, "FRONTAL-F22": {"nombre_corto":"Frontal F22"}}

    cursor.execute("SELECT * FROM ordenes_trabajo WHERE equipo_id = ? AND estado = 'PENDIENTE'", (equipo_seleccionado,))
    ots = cursor.fetchall()

    cursor.execute("SELECT parte, item, motor FROM inventario WHERE cantidad > 0")
    repuestos = cursor.fetchall()

    cursor.execute("SELECT * FROM alertas_criticas WHERE activa = 1")
    alertas_activas = cursor.fetchall()

    cursor.execute("SELECT SUM(lamina_mm) as mm_tot FROM registro_riego WHERE equipo_id = ?", (equipo_seleccionado,))
    total_acumulado_mm = cursor.fetchone()['mm_tot'] or 0.0

    cursor.execute("SELECT fecha, lamina_mm, posicion_grados FROM registro_riego WHERE equipo_id = ? AND estado_operacion != 'EN MARCHA' ORDER BY id DESC LIMIT 7", (equipo_seleccionado,))
    registros_grafico = cursor.fetchall()[::-1]
    fechas_riego = [r['fecha'] for r in registros_grafico]
    laminas_riego = [r['lamina_mm'] for r in registros_grafico]
    horas_riego = [r['posicion_grados'] or 0 for r in registros_grafico]

    conn.close()
    return render_template('dashboard.html', data=data_equipo, todos_equipos=todos_equipos, ot=ots, repuestos=repuestos, alertas=alertas_activas, total_acumulado_mm=round(total_acumulado_mm,1), fechas_riego=fechas_riego, laminas_riego=laminas_riego, horas_riego=horas_riego)

# --- REGISTRO DE RIEGO ---
@app.route('/registrar-riego', methods=['GET','POST'])
@login_required
def registrar_riego():
    conn = conectar_db()
    cursor = conn.cursor()
    if request.method == 'POST':
        form_accion = request.form.get('form_accion')
        if form_accion == 'iniciar':
            eq_id = request.form.get('equipo_id','').strip().upper()
            fecha_inicio = request.form.get('fecha_inicio')
            try:
                hs_inicio = float(request.form.get('hs_inicio',0))
                avance = float(request.form.get('avance',20))
                nro_vuelta = int(request.form.get('nro_vuelta')) if request.form.get('nro_vuelta') else None
            except ValueError:
                flash("⚠️ Los valores deben ser números", "danger")
                return redirect(url_for('registrar_riego'))

            cursor.execute('INSERT INTO registro_riego VALUES (NULL, ?, ?, ?, NULL, NULL, NULL, 0.0, "EN MARCHA", 0.0, ?, ?)', (eq_id, fecha_inicio, hs_inicio, avance, nro_vuelta))
            ahora = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute('UPDATE telemetria_actual SET estado_sistema="MARCHA EN AGUA", ultima_actualizacion=? WHERE equipo_id=?', (ahora, eq_id))
            conn.commit()
            flash(f"✅ Turno abierto para {eq_id}", "success")

        elif form_accion == 'finalizar':
            reg_id = request.form.get('registro_id')
            fecha_fin = request.form.get('fecha_fin')
            try:
                hs_fin = float(request.form.get('hs_fin',0))
                lamina = float(request.form.get('lamina_mm',0))
                presion = float(request.form.get('presion_bar',0))
            except ValueError:
                flash("⚠️ Valores numéricos incorrectos", "danger")
                return redirect(url_for('registrar_riego'))
            obs = request.form.get('observacion','Sin fallas')

            cursor.execute("SELECT horas_operadas, equipo_id FROM registro_riego WHERE id=?", (reg_id,))
            reg = cursor.fetchone()
            if reg:
                hs_ini = reg['horas_operadas']
                eq_id = reg['equipo_id']
                tiempo_recorrido = hs_fin - hs_ini
                cursor.execute('UPDATE registro_riego SET horas_parada=?, duracion_vuelta=?, posicion_grados=?, lamina_mm=?, estado_operacion=?, presion_bar=? WHERE id=?', (fecha_fin, hs_fin, tiempo_recorrido, lamina, obs, presion, reg_id))

                # ✅ CORREGIDO: SOLO ACTUALIZA EL EQUIPO CORRECTO
                mapa = {"PIVOT-LOTE-A2":"Pivot A2", "FRONTAL-F22":"Frontal F22"}
                nombre = mapa.get(eq_id, eq_id)
                cursor.execute('UPDATE control_services SET horas_actuales = horas_actuales + ? WHERE equipo_asignado = ?', (tiempo_recorrido, nombre))

                ahora = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute('UPDATE telemetria_actual SET estado_sistema="PARADO", presion_terminal=0, ultima_actualizacion=? WHERE equipo_id=?', (ahora, eq_id))
                conn.commit()
                flash(f"✅ Registro cerrado. Tiempo: {round(tiempo_recorrido,1)} hs", "success")

        conn.close()
        return redirect(url_for('registrar_riego'))

    cursor.execute("SELECT id, equipo_id, fecha, horas_operadas, nro_vuelta FROM registro_riego WHERE estado_operacion='EN MARCHA'")
    activos = cursor.fetchall()
    cursor.execute("SELECT id, equipo_id, fecha as fecha_inicio, horas_operadas as hs_inicio, horas_parada as fecha_fin, duracion_vuelta as hs_fin, posicion_grados as tiempo_recorrido, lamina_mm as lamina, estado_operacion as observacion, presion_bar, nro_vuelta FROM registro_riego WHERE estado_operacion!='EN MARCHA' ORDER BY id DESC LIMIT 15")
    historial = cursor.fetchall()
    cursor.execute("SELECT SUM(lamina_mm) as total FROM registro_riego WHERE estado_operacion!='EN MARCHA'")
    total_mm = cursor.fetchone()['total'] or 0
    conn.close()
    return render_template('registrar_riego.html', activos=activos, historial=historial, total_acumulado_mm=round(total_mm,1), fecha_hoy=datetime.now().strftime('%Y-%m-%d'))

# --- API MAPA ---
@app.route('/api/status')
def api_status():
    eq = request.args.get('equipo','PIVOT-LOTE-A2')
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM telemetria_actual WHERE equipo_id=?", (eq,))
    fila = cursor.fetchone()
    conn.close()
    if fila:
        return jsonify({
            "equipo_id": fila['equipo_id'], "estado": fila['estado_sistema'],
            "latitud": fila['latitud'], "longitud": fila['longitud'],
            "presion": fila['presion_terminal'], "posicion_angular": f"{fila['posicion_actual']}°",
            "rssi": fila['rssi'], "actualizacion": fila['ultima_actualizacion']
        })
    return jsonify({"equipo_id":eq, "latitud":-25.1794, "longitud":-63.8632, "presion":0, "posicion_angular":"0°", "rssi":"--", "actualizacion":"Sin datos"})

# --- STOCK ---
@app.route('/stock', methods=['GET','POST'])
@login_required
def stock():
    conn = conectar_db()
    cursor = conn.cursor()
    if request.method == 'POST':
        parte = request.form.get('parte','').strip().upper()
        item = request.form.get('item','')
        motor = request.form.get('motor','')
        try:
            amount = int(request.form.get('cantidad',0))
        except ValueError:
            flash("Cantidad debe ser número", "danger")
            return redirect(url_for('stock'))
        pasillo = request.form.get('pasillo','')
        estante = request.form.get('estante','')

        if amount == 0:
            flash("Cantidad no puede ser cero", "warning")
            return redirect(url_for('stock'))

        # ✅ EVITA STOCK NEGATIVO
        cursor.execute('''
            INSERT INTO inventario VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(parte) DO UPDATE SET
                cantidad = MAX(0, cantidad + excluded.cantidad),
                item = CASE WHEN excluded.item!='' THEN excluded.item ELSE item END,
                motor = CASE WHEN excluded.motor!='' THEN excluded.motor ELSE motor END,
                pasillo = CASE WHEN excluded.pasillo!='' THEN excluded.pasillo ELSE pasillo END,
                estante = CASE WHEN excluded.estante!='' THEN excluded.estante ELSE estante END
        ''', (parte, item, motor, amount, pasillo, estante))
        conn.commit()
        flash(f"✅ Insumo {parte} actualizado", "success")
        conn.close()
        return redirect(url_for('stock'))

    cursor.execute("SELECT * FROM inventario ORDER BY parte")
    items = cursor.fetchall()
    conn.close()
    return render_template('stock.html', inventario=items)

# --- MANTENIMIENTO ---
@app.route('/mantenimiento', methods=['GET','POST'])
@login_required
def mantenimiento():
    conn = conectar_db()
    cursor = conn.cursor()
    if request.method == 'POST':
        equipo = request.form.get('equipo_asignado')
        try:
            freq = float(request.form.get('frecuencia_horas',0))
            horas_act = float(request.form.get('horas_actuales',0))
        except ValueError:
            flash("Valores numéricos incorrectos", "danger")
            return redirect(url_for('mantenimiento'))
        desc = request.form.get('descripcion_tarea','')
        prox = horas_act + freq
        cursor.execute('INSERT INTO control_services VALUES (NULL, ?, ?, ?, ?, ?)', (equipo, horas_act, prox, freq, desc))
        conn.commit()
        flash("✅ Servicio guardado", "success")
        conn.close()
        return redirect(url_for('mantenimiento'))

    cursor.execute("SELECT * FROM control_services ORDER BY id DESC")
    servicios = cursor.fetchall()
    conn.close()
    return render_template('mantenimiento.html', servicios=servicios)

# --- OTRAS RUTAS ---
@app.route('/crear-ot', methods=['POST'])
@login_required
def crear_ot():
    eq = request.form.get('equipo_id')
    tarea = request.form.get('tarea')
    resp = request.form.get('responsable')
    prioridad = request.form.get('prioridad')
    repuesto = request.form.get('repuesto_asociado','')
    fecha = datetime.now().strftime('%Y-%m-%d')
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO ordenes_trabajo VALUES (NULL, ?, ?, ?, ?, ?, ?, "PENDIENTE")', (eq, tarea, resp, prioridad, repuesto, fecha))
    conn.commit()
    conn.close()
    flash("✅ Orden creada", "success")
    return redirect(url_for('index', equipo=eq))

@app.route('/finalizar-ot/<int:ot_id>')
@login_required
def finalizar_ot(ot_id):
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM ordenes_trabajo WHERE id=?", (ot_id,))
    ot = cursor.fetchone()
    if ot:
        if ot['repuesto_asociado']:
            cursor.execute('UPDATE inventario SET cantidad = MAX(0, cantidad - 1) WHERE parte=?', (ot['repuesto_asociado'],))
        cursor.execute('UPDATE ordenes_trabajo SET estado="DESPACHADA" WHERE id=?', (ot_id,))
        conn.commit()
    conn.close()
    flash("✅ Orden cerrada", "success")
    return redirect(url_for('index', equipo=ot['equipo_id'] if ot else 'PIVOT-LOTE-A2'))

@app.route('/desactivar-alerta/<int:alerta_id>')
@login_required
def desactivar_alerta(alerta_id):
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("SELECT equipo_id FROM alertas_criticas WHERE id=?", (alerta_id,))
    al = cursor.fetchone()
    cursor.execute('UPDATE alertas_criticas SET activa=0 WHERE id=?', (alerta_id,))
    if al:
        ahora = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('UPDATE telemetria_actual SET estado_sistema="MARCHA EN AGUA", ultima_actualizacion=? WHERE equipo_id=?', (ahora, al['equipo_id']))
    conn.commit()
    conn.close()
    flash("✅ Alerta solucionada", "success")
    return redirect(url_for('index', equipo=al['equipo_id'] if al else 'PIVOT-LOTE-A2'))

@app.route('/reportes')
@login_required
def reportes():
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM registro_riego ORDER BY id DESC")
    datos = cursor.fetchall()
    conn.close()
    return render_template('reportes.html', riegos=datos)

@app.route('/descargar-datos-ciclo/<equipo_id>')
@login_required
def descargar(equipo_id):
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM registro_riego WHERE equipo_id=? ORDER BY id", (equipo_id,))
    filas = cursor.fetchall()
    conn.close()
    def generar():
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['ID','Fecha','Hs Inicio','Hs Parada','Duracion','Tiempo Recorrido','Lamina','Estado','Presion','Lamina Prog','Nro Vuelta'])
        for f in filas:
            writer.writerow([f['id'],f['fecha'],f['horas_operadas'],f['horas_parada'],f['duracion_vuelta'],f['posicion_grados'],f['lamina_mm'],f['estado_operacion'],f['presion_bar'],f['lamina_programada'],f['nro_vuelta']])
        return output.getvalue()
    return Response(generar(), mimetype="text/csv", headers={"Content-Disposition":f"attachment; filename=riego_{equipo_id}.csv"})

if __name__ == '__main__':
    puerto = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=puerto, debug=False)
