from flask import Flask, jsonify, render_template, send_from_directory
import serial
import time

app = Flask(__name__, static_folder='frontend', template_folder='frontend')

# Configuração da Porta Serial do Alimentador
PORTA_SERIAL = 'COM8'  # Ajuste para a COM do seu Arduino
BAUD_RATE = 9600

try:
    arduino = serial.Serial(PORTA_SERIAL, BAUD_RATE, timeout=1)
    time.sleep(2)
    print(f"[SISTEMA] Conectado ao Arduino na porta {PORTA_SERIAL}")
except Exception as e:
    arduino = None
    print(f"[AVISO] Não foi possível abrir {PORTA_SERIAL}: {e}")

# Rota para abrir o frontend
@app.route('/')
def home():
    return send_from_directory('frontend', 'index.html')

# Rota para disparar a ação de alimentar
@app.route('/api/alimentar', methods=['POST', 'GET'])
def alimentar_gato():
    if arduino and arduino.is_open:
        arduino.write(b'G')
        return jsonify({"status": "sucesso", "mensagem": "Comando enviado para o alimentador!"})
    else:
        return jsonify({"status": "erro", "mensagem": "Arduino não está conectado"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)