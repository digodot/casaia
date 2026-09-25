from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI, WebSocket, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import paho.mqtt.client as mqtt
import json
import asyncio
import os
from datetime import datetime, timedelta
from typing import Optional, List
import re

# ========== INTEGRAÇÃO GROQ API ==========
try:
    from groq import Groq
    GROQ_DISPONIVEL = True
except ImportError:
    GROQ_DISPONIVEL = False
    print("⚠️ Groq não instalado. Execute: pip install groq")

app = FastAPI(title="CasaIA - Assistente Inteligente para Casa")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ========== CONFIGURAÇÕES ==========
MQTT_BROKER = "127.0.0.1"
MQTT_PORT = 1883
MQTT_TOPICO_SENSOR = "casaia/sensor/dados"
MQTT_TOPICO_COMANDO = "casaia/arduino/comando"
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

conexoes_ativas = []
loop_principal = None

# ========== ESTADO GLOBAL ==========
estado_casa = {
    "temperatura": 24.0,
    "umidade": 55,
    "dispositivo": "ESP32-SALA",
    "tipo": "temperatura",
    "consumo_energia_kwh": 14.8,
    "previsao_tempo_externo": "Ensolarado, máxima de 29°C, sem chuva",
    "ultimo_update": datetime.now().isoformat(),
    "dispositivos_ativos": ["Luz Sala", "Ventilador", "TV"],
    "modo_casa": "Normal"  # Normal, Ausência, Noite, Festa
}

# ========== BANCO DE DADOS TEMPORÁRIO ==========
despensa = [
    {"id": 1, "item": "Leite", "quantidade": 2.0, "unidade": "L", "validade": (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d"), "consumo_diario": 0.5},
    {"id": 2, "item": "Ovos", "quantidade": 4.0, "unidade": "un", "validade": (datetime.now() + timedelta(days=10)).strftime("%Y-%m-%d"), "consumo_diario": 2.0},
    {"id": 3, "item": "Peito de Frango", "quantidade": 1.2, "unidade": "kg", "validade": (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d"), "consumo_diario": 0.4}
]
proximo_id = 4

# Automações (regras que executam automaticamente)
automacoes = [
    {"id": 1, "nome": "Desligar luzes noturnas", "condicao": "temperatura < 15", "acao": "apagar luzes", "ativo": True},
    {"id": 2, "nome": "Ligar AC se quente", "condicao": "temperatura > 28", "acao": "ligar ar condicionado", "ativo": True},
]
proximo_id_automacao = 3

# Histórico de comandos
historico_comandos = []
proximo_id_comando = 1

# Cache de respostas IA
cache_ia = {}

# ========== MODELOS ==========
class ItemDespensaRequest(BaseModel):
    item: str
    quantidade: float
    unidade: str
    validade: str
    consumo_diario: float

class ComandoRequest(BaseModel):
    comando: str

class PerguntaIARequest(BaseModel):
    pergunta: str

class AutomacaoRequest(BaseModel):
    nome: str
    condicao: str
    acao: str

# ========== GROQ CLIENT ==========
if GROQ_DISPONIVEL and GROQ_API_KEY:
    groq_client = Groq(api_key=GROQ_API_KEY)
else:
    groq_client = None

def obter_resposta_ia(pergunta: str) -> str:
    """Processa pergunta com Groq API com contexto da casa"""
    
    # Verifica cache
    if pergunta in cache_ia:
        return cache_ia[pergunta]
    
    if not groq_client:
        return "🤖 IA não configurada. Configure GROQ_API_KEY como variável de ambiente."
    
    try:
        contexto = f"""Você é CasaIA, um assistente inteligente para automação residencial em português.
        
Contexto atual da casa:
- Temperatura: {estado_casa['temperatura']}°C
- Umidade: {estado_casa['umidade']}%
- Dispositivos ativos: {', '.join(estado_casa['dispositivos_ativos'])}
- Modo: {estado_casa['modo_casa']}
- Previsão: {estado_casa['previsao_tempo_externo']}
- Consumo de energia: {estado_casa['consumo_energia_kwh']} kWh

Itens na despensa (críticos até 3 dias):
"""
        hoje = datetime.now()
        for item in despensa:
            dias = (datetime.strptime(item['validade'], "%Y-%m-%d") - hoje).days
            if dias <= 3:
                contexto += f"- {item['item']}: {dias} dias para vencer\n"
        
        contexto += """
Você pode sugerir automações, receitas, dicas de economia de energia e outras funcionalidades.
Sempre responda em português, de forma amigável e concisa (máximo 3 linhas).
Nunca execute código ou faça ações perigosas.
"""
        
        resposta = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": contexto},
                {"role": "user", "content": pergunta}
            ],
            max_tokens=256,
            temperature=0.7
        )
        
        resultado = resposta.choices[0].message.content.strip()
        cache_ia[pergunta] = resultado
        return resultado
        
    except Exception as e:
        print(f"Erro Groq: {e}")
        return f"⚠️ Erro ao processar com IA: {str(e)}"

# ========== ENDPOINTS DA DESPENSA ==========
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
        pergunta = "Sugira um prato interessante para preparar em casa hoje"
    else:
        pergunta = f"Sugira uma receita rápida usando: {', '.join(ingredientes_criticos)} que estão vencendo"
    
    receita = obter_resposta_ia(pergunta)
    return {"receita": f"🧑‍🍳 {receita}"}

# ========== ENDPOINTS DA CENTRAL DE COMANDO ==========
def processar_comando_local(comando_texto: str) -> str:
    global proximo_id_comando
    
    cmd = comando_texto.lower().strip()
    resposta = ""
    
    # Processamento básico
    if "abrir" in cmd or "abre" in cmd:
        mqtt_client.publish(MQTT_TOPICO_COMANDO, "ABRIR")
        resposta = "🔄 Enviando comando ABRIR para o Arduino..."
        
    elif "fechar" in cmd or "fecha" in cmd:
        mqtt_client.publish(MQTT_TOPICO_COMANDO, "FECHAR")
        resposta = "🔄 Enviando comando FECHAR para o Arduino..."
        
    elif "despensa" in cmd:
        resposta = f"🍎 Você possui {len(despensa)} itens cadastrados."
        
    elif any(p in cmd for p in ["tempo", "previsão", "clima"]):
        resposta = f"🌦️ {estado_casa['previsao_tempo_externo']}"
        
    elif any(p in cmd for p in ["energia", "consumo", "luz"]):
        resposta = f"⚡ Consumo: {estado_casa['consumo_energia_kwh']} kWh"
        
    elif any(p in cmd for p in ["temperatura", "temp", "quente", "frio"]):
        resposta = f"🌡️ Temperatura atual: {estado_casa['temperatura']}°C (Umidade: {estado_casa['umidade']}%)"
        
    else:
        # Se não reconhecer, pergunta à IA
        resposta = f"🤖 {obter_resposta_ia(comando_texto)}"
    
    # Registra no histórico
    historico_comandos.append({
        "id": proximo_id_comando,
        "comando": comando_texto,
        "resposta": resposta,
        "timestamp": datetime.now().isoformat()
    })
    proximo_id_comando += 1
    
    return resposta

@app.post("/executar-comando")
def executar_comando_casa(req: ComandoRequest):
    resposta = processar_comando_local(req.comando)
    return {"resposta": resposta}

@app.post("/api/ia/pergunta")
def fazer_pergunta_ia(req: PerguntaIARequest):
    resposta = obter_resposta_ia(req.pergunta)
    return {"resposta": resposta}

# ========== ENDPOINTS DE AUTOMAÇÕES ==========
@app.get("/api/automacoes")
def listar_automacoes():
    return automacoes

@app.post("/api/automacoes")
def criar_automacao(req: AutomacaoRequest):
    global proximo_id_automacao
    nova = {
        "id": proximo_id_automacao,
        "nome": req.nome,
        "condicao": req.condicao,
        "acao": req.acao,
        "ativo": True
    }
    automacoes.append(nova)
    proximo_id_automacao += 1
    return {"status": "sucesso", "automacao": nova}

@app.delete("/api/automacoes/{auto_id}")
def deletar_automacao(auto_id: int):
    global automacoes
    automacoes = [a for a in automacoes if a["id"] != auto_id]
    return {"status": "sucesso"}

# ========== ENDPOINTS DE ESTADO ==========
@app.get("/api/estado")
def obter_estado():
    return estado_casa

@app.post("/api/modo")
def alterar_modo(modo: str):
    if modo in ["Normal", "Ausência", "Noite", "Festa"]:
        estado_casa["modo_casa"] = modo
        return {"status": "sucesso", "modo": modo}
    raise HTTPException(status_code=400, detail="Modo inválido")

@app.get("/api/historico")
def obter_historico(limite: int = 20):
    return sorted(historico_comandos, key=lambda x: x["timestamp"], reverse=True)[:limite]

# ========== HTML ==========
@app.get("/", response_class=HTMLResponse)
def ler_dashboard():
    return open("templates/index.html", "r", encoding="utf-8").read()

# ========== WEBSOCKET ==========
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    conexoes_ativas.append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except Exception:
        conexoes_ativas.remove(websocket)

# ========== MQTT ==========
def on_connect(client, userdata, flags, rc, properties=None):
    print("✅ [MQTT] Conectado ao Broker!")
    client.subscribe(MQTT_TOPICO_SENSOR)

def on_message(client, userdata, msg):
    try:
        payload = msg.payload.decode('utf-8').strip()
        if payload.startswith("'") and payload.endswith("'"):
            payload = payload[1:-1]
            
        dados = json.loads(payload)
        estado_casa["temperatura"] = float(dados.get("valor", 24.0))
        estado_casa["umidade"] = float(dados.get("umidade", 50))
        estado_casa["dispositivo"] = dados.get("dispositivo_id", "Desconhecido").upper()
        estado_casa["ultimo_update"] = datetime.now().isoformat()
        
        for websocket in conexoes_ativas:
            asyncio.run_coroutine_threadsafe(
                websocket.send_text(json.dumps({
                    "tipo": "telemetria",
                    "temperatura": estado_casa["temperatura"],
                    "umidade": estado_casa["umidade"],
                    "dispositivo_id": estado_casa["dispositivo"]
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
    try:
        mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
        mqtt_client.loop_start()
    except Exception as e:
        print(f"⚠️ MQTT não disponível: {e}")

@app.on_event("shutdown")
def shutdown_event():
    mqtt_client.loop_stop()
    mqtt_client.disconnect()

if __name__ == "__main__":
    import uvicorn
    print("🏠 CasaIA iniciando...")
    print(f"📡 IA Status: {'✅ Groq Ativado' if groq_client else '⚠️ Groq não configurado'}")
    uvicorn.run(app, host="0.0.0.0", port=8000)
