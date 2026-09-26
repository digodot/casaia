import os
import time
import tempfile
import serial
import requests
import uvicorn
import tinytuya
import subprocess
from gtts import gTTS
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from google import genai
from dotenv import load_dotenv

# Carrega as variáveis de ambiente (.env)
caminho_env = os.path.join(os.path.dirname(__file__), "..", ".env")
load_dotenv(caminho_env)

app = FastAPI(title="CasaIA - Central de Automação")

# Estados globais
estado_tomadas = {}
historico_chat = []

# =============================================================================
# 1. MODELOS DE DADOS
# =============================================================================
class PerguntaIA(BaseModel):
    pergunta: str

class ComandoTomada(BaseModel):
    device_id: str
    ip: str
    local_key: str
    acao: str  # "ligar", "desligar" ou "alternar"

# =============================================================================
# 2. FERRAMENTAS E FUNÇÕES DO GEMINI (FUNCTION CALLING)
# =============================================================================
def alimentar_gato_funcao():
    porta_com = '/dev/ttyUSB0'
    try:
        with serial.Serial(porta_com, 9600, timeout=1) as arduino:
            time.sleep(2.5)
            arduino.reset_input_buffer()
            arduino.reset_output_buffer()
            arduino.write(b'G')
            time.sleep(0.5)
            return {"sucesso": True, "mensagem": "Ração servida com sucesso! 🐱"}
    except Exception as e:
        return {"sucesso": False, "mensagem": f"Erro no Arduino: {e}"}

def controlar_tomada_funcao(device_id: str, ip: str, local_key: str, acao: str):
    try:
        device = tinytuya.OutletDevice(
            dev_id=device_id,
            address=ip,
            local_key=local_key,
            version=3.3
        )
        if acao == "ligar":
            device.turn_on()
            status = "ligada"
        elif acao == "desligar":
            device.turn_off()
            status = "desligada"
        else:
            estado_atual = device.status().get('dps', {}).get('1', False)
            if estado_atual:
                device.turn_off()
                status = "desligada"
            else:
                device.turn_on()
                status = "ligada"
        
        estado_tomadas[device_id] = status
        return {"sucesso": True, "mensagem": f"Tomada {status} com sucesso! ⚡"}
    except Exception as e:
        return {"sucesso": False, "mensagem": f"Erro ao controlar tomada: {e}"}

# =============================================================================
# 3. ROTAS PRINCIPAIS E DASHBOARD
# =============================================================================
@app.get("/", response_class=HTMLResponse)
def ler_index():
    caminho_index = os.path.join(os.path.dirname(__file__), "templates", "index.html")
    if os.path.exists(caminho_index):
        with open(caminho_index, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Erro: Ficheiro index.html não encontrado na pasta templates!</h1>"

# =============================================================================
# 4. SÍNTESE DE VOZ E AUTOMAÇÃO
# =============================================================================
@app.post("/api/automacao/bom-dia")
def dar_bom_dia():
    api_key = os.getenv("GEMINI_API_KEY")
    mensagem = "Bom dia! Bem-vindo de volta à CasaIA."
    
    if api_key:
        try:
            client = genai.Client(api_key=api_key)
            prompt = "Escreva uma saudação de bom dia muito curta e motivadora para a casa inteligente CasaIA. Máximo 2 frases."
            for modelo in ['gemini-2.0-flash', 'gemini-1.5-flash']:
                try:
                    res = client.models.generate_content(model=modelo, contents=prompt)
                    if res.text:
                        mensagem = res.text
                        break
                except Exception:
                    continue
        except Exception as e:
            print(f"[ERRO GEMINI BOM DIA] {e}")

    try:
        tts = gTTS(text=mensagem, lang='pt', slow=False)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
            caminho_audio = fp.name
            tts.save(caminho_audio)

        try:
            subprocess.run(["mpg123", "-q", caminho_audio], check=True)
        except Exception:
            pass

        try:
            os.remove(caminho_audio)
        except Exception:
            pass

        return {"status": "sucesso", "mensagem_falada": mensagem}
    except Exception as e:
        return {"status": "erro", "mensagem": f"Erro ao reproduzir áudio: {e}"}

# =============================================================================
# 5. HARDWARE E TOMADAS
# =============================================================================
@app.post("/api/alimentar")
def alimentar_gato():
    resultado = alimentar_gato_funcao()
    if resultado["sucesso"]:
        return {"status": "sucesso", "mensagem": resultado["mensagem"]}
    raise HTTPException(status_code=503, detail=resultado["mensagem"])

@app.post("/api/tomada/controlar")
def controlar_tomada(dados: ComandoTomada):
    return controlar_tomada_funcao(dados.device_id, dados.ip, dados.local_key, dados.acao)

@app.get("/api/webhook/tomada/{acao}")
def webhook_tomada(acao: str):
    dados = ComandoTomada(device_id="SEU_DEVICE_ID", ip="192.168.10.X", local_key="SUA_LOCAL_KEY", acao=acao)
    return controlar_tomada(dados)

# =============================================================================
# 6. CHAT COM IA (GEMINI COM RESILIÊNCIA E VOZ)
# =============================================================================
@app.post("/api/ia/pergunta")
def perguntar_ia(payload: PerguntaIA):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return {"resposta": f"Recebi: '{payload.pergunta}'. (Configure GEMINI_API_KEY no .env!)"}
    
    texto_resposta = None
    client = genai.Client(api_key=api_key)

    # Execução de comandos diretos via comando de voz/texto
    pergunta_lower = payload.pergunta.lower()
    if "alimentar" in pergunta_lower or "gato" in pergunta_lower or "ração" in pergunta_lower:
        res_alim = alimentar_gato_funcao()
        texto_resposta = res_alim["mensagem"]
    
    if not texto_resposta:
        # Tenta os modelos com fallback automático contra erro 503/404
        for modelo in ['gemini-2.0-flash', 'gemini-1.5-flash']:
            try:
                response = client.models.generate_content(
                    model=modelo,
                    contents=payload.pergunta
                )
                if response.text:
                    texto_resposta = response.text
                    break
            except Exception as e:
                print(f"[AVISO GEMINI - {modelo}] {type(e).__name__}: {e}")

    if not texto_resposta:
        texto_resposta = "Os servidores do Gemini estão temporariamente sobrecarregados. Por favor, tente novamente em alguns instantes."

    # Toca a resposta no alto-falante do Pi (se mpg123 estiver disponível)
    try:
        tts = gTTS(text=texto_resposta[:300], lang='pt', slow=False)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
            caminho_audio = fp.name
            tts.save(caminho_audio)
        try:
            subprocess.run(["mpg123", "-q", caminho_audio], check=True)
        except Exception:
            pass
        try:
            os.remove(caminho_audio)
        except Exception:
            pass
    except Exception:
        pass

    return {"resposta": texto_resposta}

@app.post("/api/ia/limpar")
def limpar_historico():
    global historico_chat
    historico_chat = []
    return {"status": "sucesso", "mensagem": "Histórico de conversa limpo!"}

# =============================================================================
# 7. CLIMA, MARÉ E SUGESTÕES DE PRAIA
# =============================================================================
@app.get("/api/clima")
@app.post("/api/clima/atualizar/{cidade}")
def atualizar_clima_cidade(cidade: str = "Recife"):
    coordenadas = {
        "Recife": (-8.05428, -34.8813),
        "Rio de Janeiro": (-22.9068, -43.1729),
        "Salvador": (-12.9714, -38.5014),
        "Fortaleza": (-3.7172, -38.5433),
        "Natal": (-5.7945, -35.2110),
        "Maceió": (-9.6658, -35.7353)
    }
    
    lat, lon = coordenadas.get(cidade, (-8.05428, -34.8813))
    
    try:
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m&timezone=auto"
        res = requests.get(url, timeout=5)
        dados = res.json()["current"]
        
        codigos_tempo = {
            0: "Céu limpo ☀️", 1: "Predominantemente limpo 🌤️", 
            2: "Parcialmente nublado ⛅", 3: "Nublado ☁️", 
            45: "Nevoeiro 🌫️", 61: "Chuva fraca 🌧️", 
            63: "Chuva moderada 🌧️", 80: "Pancadas de chuva 🌦️"
        }
        
        return {
            "clima": {
                "temperatura": dados["temperature_2m"],
                "sensacao": dados["apparent_temperature"],
                "umidade": dados["relative_humidity_2m"],
                "velocidade_vento": dados["wind_speed_10m"],
                "condicao": codigos_tempo.get(dados["weather_code"], "Ensolarado 🌤️")
            },
            "mare": {
                "proxima_alta": "04:15 / 16:30",
                "proxima_baixa": "10:20 / 22:45",
                "melhor_hora": "07:00 - 10:00",
                "condicao": "Maré ideal para banho 🌊"
            }
        }
    except Exception as e:
        print(f"[ERRO CLIMA] {e}")
        return {"clima": None, "mare": None}

@app.get("/api/praia/sugestao")
def sugestao_praia():
    api_key = os.getenv("GEMINI_API_KEY")
    if api_key:
        try:
            client = genai.Client(api_key=api_key)
            prompt = "Dê uma sugestão muito curta (máximo 2 frases) para aproveitar a praia no Nordeste hoje."
            for modelo in ['gemini-2.0-flash', 'gemini-1.5-flash']:
                try:
                    response = client.models.generate_content(model=modelo, contents=prompt)
                    if response.text:
                        return {"sugestao": response.text, "melhor_hora": "07:30 - 10:30"}
                except Exception:
                    continue
        except Exception as e:
            print(f"[ERRO GEMINI PRAIA] {e}")
            
    return {
        "sugestao": "O dia está ótimo para aproveitar a praia! Lembre-se de usar protetor solar e se hidratar.",
        "melhor_hora": "08:00 - 11:00"
    }

# =============================================================================
# 8. DESPENSA E OUTRAS CONSULTAS
# =============================================================================
@app.get("/api/despensa")
def obter_despensa():
    return []

# =============================================================================
# 9. INICIALIZAÇÃO DO SERVIDOR WEB
# =============================================================================
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)