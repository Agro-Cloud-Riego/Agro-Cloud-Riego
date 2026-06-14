import serial
import requests
import time

# CONFIGURACIÓN: Ajustá el puerto si no es el COM8
PUERTO_SERIAL = 'COM8' 
BAUDIOS = 115200
URL_SERVIDOR = 'http://127.0.0.1:5000/api/telemetria' # La ruta de tu app.py

print(u"📡 Iniciando puente USB -> Servidor Web...")

try:
    # Abrimos el puerto COM8 para escuchar la Heltec
    ser = serial.Serial(PUERTO_SERIAL, BAUDIOS, timeout=1)
    time.sleep(2) # Espera a que se estabilice la conexión
    print(u"✅ Conectado exitosamente al Heltec en " + PUERTO_SERIAL)
except Exception as e:
    print(u"❌ Error al conectar con el puerto: ", e)
    exit()

while True:
    try:
        if ser.in_waiting > 0:
            # Lee la línea que manda la placa Heltec
            linea = ser.readline().decode('utf-8').strip()
            
            # Verificamos que sea un JSON válido antes de mandarlo
            if linea.startswith('{') and linea.endswith('}'):
                print(f"📥 Datos recibidos del Heltec: {linea}")
                
                # Le mandamos el dato al vuelo a tu servidor Flask
                headers = {'Content-Type': 'application/json'}
                respuesta = requests.post(URL_SERVIDOR, data=linea, headers=headers)
                
                if respuesta.status_code == 200 or respuesta.status_code == 201:
                    print("🚀 ¡Enviado al Dashboard con éxito!")
                else:
                    print(f"⚠️ El servidor respondió con error: {respuesta.status_code}")
                    
    except Exception as e:
        print("❌ Error en la transmisión: ", e)
        break
    time.sleep(0.1)
