import os
import time
import serial
import uvicorn
import tinytuya
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from google import genai
from google.genai import types
from dotenv import load_dotenv

# Carrega as variáveis do ficheiro .env na raiz
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
from gtts import gTTS
import pygame

# Endpoint para a IA dar Bom Dia falado no alto-falante do Pi
import tempfile

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
                model='gemini-2.0-flash',
                contents=prompt
            )
            mensagem = resposta.text
        except Exception as e:
            print(f"[ERRO GEMINI VOZ] {e}")
            mensagem = "Bom dia! Tenha um excelente dia."

    try:
        # Gera o ficheiro de áudio com a resposta
        tts = gTTS(text=mensagem, lang='pt', slow=False)
        
        # Cria um ficheiro temporário único com extensão .mp3 para evitar bloqueios de escrita
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
            caminho_audio = fp.name
            tts.save(caminho_audio)

        # Para e reinicia o mixer do Pygame de forma limpa
        if pygame.mixer.get_init():
            pygame.mixer.music.stop()
            pygame.mixer.quit()

        pygame.mixer.init()
        pygame.mixer.music.load(caminho_audio)
        pygame.mixer.music.play()

        # Aguarda terminar a reprodução do áudio
        while pygame.mixer.music.get_busy():
            time.sleep(0.1)

        # Descarrega o ficheiro e fecha o áudio
        pygame.mixer.music.unload()
        pygame.mixer.quit()

        # Apaga o ficheiro temporário para não acumular lixo no disco
        try:
            os.remove(caminho_audio)
        except Exception:
            pass

        return {"status": "sucesso", "mensagem_falada": mensagem}
        
    except Exception as e:
        print(f"[ERRO AUDIO] {e}")
        return {"status": "erro", "mensagem": f"Erro ao reproduzir áudio: {e}"}
# -----------------------------------------------------------------------------
# 2. ROTAS DA APLICAÇÃO
# -----------------------------------------------------------------------------

# Rota principal para carregar o Dashboard em HTML
@app.get("/", response_class=HTMLResponse)
def ler_index():
    caminho_index = os.path.join(os.path.dirname(__file__), "templates", "index.html")
    if os.path.exists(caminho_index):
        with open(caminho_index, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Erro: Ficheiro index.html não encontrado na pasta templates!</h1>"

# Endpoint para servir a ração
@app.post("/api/alimentar")
def alimentar_gato():
    porta_com = '/dev/ttyACM0'  # No Raspberry Pi costuma ser /dev/ttyACM0 ou /dev/ttyUSB0
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

# Endpoint para o Chat de IA utilizando Gemini
historico_chat = []

@app.post("/api/ia/pergunta")
def perguntar_ia(payload: PerguntaIA):
    api_key = os.getenv("GEMINI_API_KEY")
    
    if not api_key:
        return {
            "resposta": f"Recebi a pergunta: '{payload.pergunta}'. (Defina GEMINI_API_KEY no ficheiro .env para ativar as respostas!)"
        }
    
    try:
        client = genai.Client(api_key=api_key)
        historico_chat.append({"role": "user", "parts": [{"text": payload.pergunta}]})
        
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=historico_chat
        )
        
        historico_chat.append({"role": "model", "parts": [{"text": response.text}]})
        return {"resposta": response.text}
    except Exception as e:
        print(f"[ERRO GEMINI] {e}")
        return {"resposta": "Desculpe, ocorreu um erro ao processar a conversa."}

@app.post("/api/ia/limpar")
def limpar_historico():
    global historico_chat
    historico_chat = []
    return {"status": "sucesso", "mensagem": "Histórico de conversa limpo!"}

# Endpoint para Controle das Tomadas Inteligentes (Smart Life / Tuya)
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

# -----------------------------------------------------------------------------
# 3. INICIALIZAÇÃO DO SERVIDOR WEB
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)

    # Endpoint rápido para acionar via Webhook/Google Assistant
@app.get("/api/webhook/tomada/{acao}")
def webhook_tomada(acao: str):
    # Reutiliza a lógica da tomada inteligente
    dados = ComandoTomada(
        device_id="SEU_DEVICE_ID", # Coloque os dados reais quando estiver em casa
        ip="192.168.10.X",
        local_key="SUA_LOCAL_KEY",
        acao=acao
    )
    return controlar_tomada(dados)