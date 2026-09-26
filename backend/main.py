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

# -----------------------------------------------------------------------------
# 1. MODELOS DE DADOS
# -----------------------------------------------------------------------------
class PerguntaIA(BaseModel):
    pergunta: str

class ComandoTomada(BaseModel):
    device_id: str
    ip: str
    local_key: str
    acao: str  # "ligar", "desligar" ou "alternar"

# Histórico global do Chat
historico_chat = []

# -----------------------------------------------------------------------------
# 2. ROTAS PRINCIPAIS E DASHBOARD
# -----------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
def ler_index():
    caminho_index = os.path.join(os.path.dirname(__file__), "templates", "index.html")
    if os.path.exists(caminho_index):
        with open(caminho_index, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Erro: Ficheiro index.html não encontrado na pasta templates!</h1>"

# -----------------------------------------------------------------------------
# 3. SÍNTESE DE VOZ E AUTOMAÇÃO
# -----------------------------------------------------------------------------
@app.post("/api/automacao/bom-dia")
def dar_bom_dia():
    api_key = os.getenv("GEMINI_API_KEY")
    
    if not api_key:
        mensagem = "Bom dia! Bem-vindo de volta à CasaIA."
    else:
        try:
            client = genai.Client(api_key=api_key)
            prompt = (
                "Escreva uma saudação de bom dia muito curta, motivadora e natural "
                "para o dono da casa inteligente CasaIA. Máximo 2 frases."
            )
            resposta = client.models.generate_content(
    model='gemini-2.5-flash',
    contents=prompt
)
            mensagem = resposta.text
        except Exception as e:
            print(f"[ERRO GEMINI VOZ] {e}")
            mensagem = "Bom dia! Tenha um excelente dia."

    try:
        # Gera o ficheiro de áudio MP3 temporário
        tts = gTTS(text=mensagem, lang='pt', slow=False)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
            caminho_audio = fp.name
            tts.save(caminho_audio)

        # Reproduz o áudio via mpg123 no Linux (sem engasgos)
        try:
            subprocess.run(["mpg123", "-q", caminho_audio], check=True)
        except Exception as e:
            print(f"[ERRO MPG123] {e}")

        # Remove o ficheiro temporário
        try:
            os.remove(caminho_audio)
        except Exception:
            pass

        return {"status": "sucesso", "mensagem_falada": mensagem}
    except Exception as e:
        print(f"[ERRO AUDIO] {e}")
        return {"status": "erro", "mensagem": f"Erro ao reproduzir áudio: {e}"}

# -----------------------------------------------------------------------------
# 4. HARDWARE E HARDWARE IOT (ARDUINO & TOMADAS)
# -----------------------------------------------------------------------------
@app.post("/api/alimentar")
def alimentar_gato():
    porta_com = '/dev/ttyUSB0'  # No Raspberry Pi
    try:
        with serial.Serial(porta_com, 9600, timeout=1) as arduino:
            time.sleep(2.5)
            arduino.reset_input_buffer()
            arduino.reset_output_buffer()
            arduino.write(b'G')
            time.sleep(0.5)
            return {"status": "sucesso", "mensagem": "Comando enviado! Ração servida com sucesso."}
    except serial.SerialException as e:
        raise HTTPException(
            status_code=503,
            detail=f"Erro ao conectar ao Arduino. Erro: {e}"
        )

@app.post("/api/tomada/controlar")
def controlar_tomada(dados: ComandoTomada):
    try:
        device = tinytuya.OutletDevice(
            dev_id=dados.device_id,
            address=dados.ip,
            local_key=dados.local_key,
            version=3.3
        )
        
        if dados.acao == "ligar":
            device.turn_on()
            status = "ligada"
        elif dados.acao == "desligar":
            device.turn_off()
            status = "desligada"
        elif dados.acao == "alternar":
            estado_atual = device.status().get('dps', {}).get('1', False)
            if estado_atual:
                device.turn_off()
                status = "desligada"
            else:
                device.turn_on()
                status = "ligada"
        else:
            raise HTTPException(status_code=400, detail="Ação inválida")

        return {"status": "sucesso", "estado": status}
    except Exception as e:
        return {"status": "erro", "mensagem": str(e)}

@app.get("/api/webhook/tomada/{acao}")
def webhook_tomada(acao: str):
    dados = ComandoTomada(
        device_id="SEU_DEVICE_ID",
        ip="192.168.10.X",
        local_key="SUA_LOCAL_KEY",
        acao=acao
    )
    return controlar_tomada(dados)

# -----------------------------------------------------------------------------
# 5. CHAT COM IA (GEMINI)
# -----------------------------------------------------------------------------
@app.post("/api/ia/pergunta")
def perguntar_ia(payload: PerguntaIA):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return {"resposta": f"Recebi a pergunta: '{payload.pergunta}'. (Configure GEMINI_API_KEY no .env!)"}
    
    try:
        client = genai.Client(api_key=api_key)
        historico_chat.append({"role": "user", "parts": [{"text": payload.pergunta}]})
        
        response = client.models.generate_content(
    model='gemini-2.5-flash',
    contents=historico_chat
)
        
        texto_resposta = response.text
        historico_chat.append({"role": "model", "parts": [{"text": texto_resposta}]})

        # Sintetiza e toca a resposta por voz no alto-falante do Raspberry Pi
        try:
            tts = gTTS(text=texto_resposta, lang='pt', slow=False)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
                caminho_audio = fp.name
                tts.save(caminho_audio)

            subprocess.run(["mpg123", "-q", caminho_audio], check=True)

            try:
                os.remove(caminho_audio)
            except Exception:
                pass
        except Exception as err_audio:
            print(f"[ERRO AUDIO IA] {err_audio}")

        return {"resposta": texto_resposta}
    except Exception as e:
        print(f"[ERRO GEMINI] {e}")
        return {"resposta": "Desculpe, ocorreu um erro ao processar a conversa."}
    
@app.post("/api/ia/limpar")
def limpar_historico():
    global historico_chat
    historico_chat = []
    return {"status": "sucesso", "mensagem": "Histórico de conversa limpo!"}

# -----------------------------------------------------------------------------
# 6. CLIMA, MARÉ E SUGESTÕES DE PRAIA
# -----------------------------------------------------------------------------
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
            response = client.models.generate_content(
    model='gemini-2.5-flash',
    contents=historico_chat
)
            return {"sugestao": resposta.text, "melhor_hora": "07:30 - 10:30"}
        except Exception as e:
            print(f"[ERRO GEMINI PRAIA] {e}")
            
    return {
        "sugestao": "O dia está ótimo para aproveitar a praia! Lembre-se de usar protetor solar e se hidratar.",
        "melhor_hora": "08:00 - 11:00"
    }

# -----------------------------------------------------------------------------
# 7. DESPENSA E OUTRAS CONSULTAS
# -----------------------------------------------------------------------------
@app.get("/api/despensa")
def obter_despensa():
    return []

# -----------------------------------------------------------------------------
# 8. INICIALIZAÇÃO DO SERVIDOR WEB (SEMPRE NO FIM!)
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)