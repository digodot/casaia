import serial
import paho.mqtt.client as mqtt
import time

# --- CONFIGURAÇÕES ---
PORTA_SERIAL = 'COM7'  # Sua porta do Arduino
BAUD_RATE = 9600
MQTT_BROKER = "127.0.0.1"
MQTT_TOPICO_COMANDO = "casaia/arduino/comando"

# Conecta ao Arduino via USB
print(f"Conectando ao Arduino na porta {PORTA_SERIAL}...")
try:
    arduino = serial.Serial(PORTA_SERIAL, BAUD_RATE, timeout=1)
    time.sleep(2)  # Aguarda o Arduino reiniciar após plugar
    print("Arduino conectado com sucesso!")
except Exception as e:
    print(f"Erro ao conectar no Arduino: {e}")
    exit()

# Função que roda quando um comando chega do painel via MQTT
def on_message(client, userdata, msg):
    comando_recebido = msg.payload.decode('utf-8').strip().upper()
    print(f"[Ponte] Comando recebido do painel: {comando_recebido}")
    
    if comando_recebido in ["ABRIR", "FECHAR"]:
        # Envia a palavra direto para o cabo USB do Arduino
        arduino.write(f"{comando_recebido}\n".encode('utf-8'))
        print(f"[Ponte] Enviado para o Arduino: {comando_recebido}")

# Conecta no Broker Mosquitto
mqtt_client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
mqtt_client.on_message = on_message
mqtt_client.connect(MQTT_BROKER, 1883, 60)
mqtt_client.subscribe(MQTT_TOPICO_COMANDO)
mqtt_client.loop_start()

print("Ponte Serial-MQTT rodando e aguardando comandos do painel...")

try:
    while True:
        # Fica lendo se o Arduino responder algo de volta
        if arduino.in_waiting > 0:
            resposta = arduino.readline().decode('utf-8').strip()
            if resposta:
                print(f"[Arduino diz]: {resposta}")
        time.sleep(0.1)
except KeyboardInterrupt:
    print("Desconectando ponte...")
finally:
    arduino.close()
    mqtt_client.loop_stop()