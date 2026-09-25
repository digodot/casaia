from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import paho.mqtt.client as mqtt
import json
import asyncio
import os
from datetime import datetime, timedelta

app = FastAPI(title="CasaIA - Central de Automação Local")

conexoes_ativas = []
MQTT_BROKER = "127.0.0.1"
MQTT_PORT = 1883
MQTT_TOPICO_SENSOR = "casaia/sensor/dados"
MQTT_TOPICO_COMANDO = "casaia/arduino/comando"

# Estado geral da automação
estado_casa = {
    "temperatura": 24.0,
    "dispositivo": "NENHUM SENSOR",
    "tipo": "temperatura",
    "consumo_energia_kwh": 14.8,
    "previsao_tempo_externo": "Ensolarado, máxima de 29°C, sem chuva"
}

# --- BANCO DE DADOS TEMPORÁRIO DA DESPENSA ---
despensa = [
    {"id": 1, "item": "Leite", "quantidade": 2.0, "unidade": "L", "validade": (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d"), "consumo_diario": 0.5},
    {"id": 2, "item": "Ovos", "quantidade": 4.0, "unidade": "un", "validade": (datetime.now() + timedelta(days=10)).strftime("%Y-%m-%d"), "consumo_diario": 2.0},
    {"id": 3, "item": "Peito de Frango", "quantidade": 1.2, "unidade": "kg", "validade": (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d"), "consumo_diario": 0.4}
]
proximo_id = 4

# Modelos de dados para as requisições
class ItemDespensaRequest(BaseModel):
    item: str
    quantidade: float
    unidade: str
    validade: str
    consumo_diario: float

class ComandoRequest(BaseModel):
    comando: str

# --- ENDPOINTS DO MÓDULO DE DESPENSA ---

@app.get("/api/despensa")
def obter_despensa():
    itens_processados = []
    hoje = datetime.now()
    
    for produto in despensa:
        try:
            validade = datetime.strptime(produto["validade"], "%Y-%m-%d")
            dias_para_estragar = (validade - hoje).days + 1
        except Exception:
            dias_para_estragar = 99
            
        consumo = produto.get("consumo_diario", 1.0)
        dias_restantes_estoque = int(produto["quantidade"] / consumo) if consumo > 0 else 99
        data_acaba = (hoje + timedelta(days=dias_restantes_estoque)).strftime("%d/%m")
        
        status_validade = "OK"
        if dias_para_estragar <= 2:
            status_validade = "CRÍTICO"
        elif dias_para_estragar <= 5:
            status_validade = "ALERTA"
            
        status_estoque = "Suficiente"
        if dias_restantes_estoque <= 2:
            status_estoque = f"Acaba até {data_acaba}"

        itens_processados.append({
            **produto,
            "dias_para_estragar": dias_para_estragar,
            "status_validade": status_validade,
            "previsao_esgotar": status_estoque
        })
    return itens_processados

@app.post("/api/despensa")
def adicionar_item(item: ItemDespensaRequest):
    global proximo_id
    novo_item = {
        "id": proximo_id,
        "item": item.item,
        "quantidade": item.quantidade,
        "unidade": item.unidade,
        "validade": item.validade,
        "consumo_diario": item.consumo_diario
    }
    despensa.append(novo_item)
    proximo_id += 1
    return {"status": "sucesso", "item": novo_item}

@app.delete("/api/despensa/{item_id}")
def remover_item(item_id: int):
    global despensa
    despensa = [i for i in despensa if i["id"] != item_id]
    return {"status": "sucesso"}

@app.post("/api/despensa/receitas")
def sugerir_receitas():
    hoje = datetime.now()
    ingredientes_criticos = [i["item"] for i in despensa if (datetime.strptime(i["validade"], "%Y-%m-%d") - hoje).days <= 3]
    
    if not ingredientes_criticos:
        return {"receita": "💡 **Sugestão da IA:** Seus ingredientes estão com ótimos prazos de validade! Que tal preparar um prato básico usando seu estoque atual?"}

    sugestao = (
        f"💡 **Sugestão da IA para evitar desperdício:**\n\n"
        f"Seu estoque de **{', '.join(ingredientes_criticos)}** está muito próximo do vencimento.\n"
        f"Minha recomendação é preparar uma **Refeição Integrada Express** focando no consumo rápido destes alimentos hoje de forma criativa!"
    )
    return {"receita": sugestao}

# --- CENTRAL DE PROCESSAMENTO DE COMANDOS (ROTA COM ARDUINO) ---

def processar_comando_local(comando_texto: str) -> str:
    cmd = comando_texto.lower()
    
    if "abrir" in cmd or "abre" in cmd:
        mqtt_client.publish(MQTT_TOPICO_COMANDO, "ABRIR")
        return "🔄 [Central]: Enviando comando via USB para o Arduino ABRIR o servo motor..."
        
    elif "fechar" in cmd or "fecha" in cmd:
        mqtt_client.publish(MQTT_TOPICO_COMANDO, "FECHAR")
        return "🔄 [Central]: Enviando comando via USB para o Arduino FECHAR o servo motor..."
        
    elif "despensa" in cmd:
        return f"🍎 [Despensa]: Você possui {len(despensa)} itens cadastrados no momento."
        
    elif any(palavra in cmd for palavra in ["tempo", "previsão", "clima"]):
        return f"🌦️ [Central]: A previsão externa indica: {estado_casa['previsao_tempo_externo']}."
        
    elif any(palavra in cmd for palavra in ["energia", "consumo", "luz"]):
        return f"⚡ [Central]: Consumo geral acumulado hoje está em {estado_casa['consumo_energia_kwh']} kWh."
        
    return f"🏠 [Central]: Telemetria do {estado_casa['dispositivo']} acusa {estado_casa['temperatura']}°C."

@app.post("/executar-comando")
def ejecutar_comando_casa(req: ComandoRequest):
    resposta = processar_comando_local(req.comando)
    return {"resposta": resposta}

# --- INFRAESTRUTURA DE CONEXÃO MQTT E WEBSOCKET ---

def on_connect(client, userdata, flags, rc, properties=None):
    print("[MQTT] Conectado com sucesso ao Broker Mosquitto!")
    client.subscribe(MQTT_TOPICO_SENSOR)

def on_message(client, userdata, msg):
    try:
        payload = msg.payload.decode('utf-8').strip()
        if payload.startswith("'") and payload.endswith("'"):
            payload = payload[1:-1]
            
        dados = json.loads(payload)
        estado_casa["temperatura"] = float(dados.get("valor", 24.0))
        estado_casa["dispositivo"] = dados.get("dispositivo_id", "Desconhecido").replace("esp32_", "").upper()
        
        for websocket in conexoes_ativas:
            asyncio.run_coroutine_threadsafe(
                websocket.send_text(json.dumps({
                    "dispositivo_id": estado_casa["dispositivo"], 
                    "valor": estado_casa["temperatura"]
                })), 
                loop_principal
            )
    except Exception as e:
        print(f"[MQTT ERRO]: {e}")

mqtt_client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message

@app.on_event("startup")
def startup_event():
    global loop_principal
    loop_principal = asyncio.get_event_loop()
    mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
    mqtt_client.loop_start()

@app.on_event("shutdown")
def shutdown_event():
    mqtt_client.loop_stop()
    mqtt_client.disconnect()

@app.get("/", response_class=HTMLResponse)
def ler_dashboard():
    # Isso garante que ele ache a pasta templates não importa de onde você chame
    diretorio_atual = os.path.dirname(os.path.abspath(__file__))
    caminho_html = os.path.join(diretorio_atual, "templates", "index.html")
    with open(caminho_html, "r", encoding="utf-8") as f:
        return f.read()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    conexoes_ativas.append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except Exception:
        conexoes_ativas.remove(websocket)