import os
import time
import serial
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from google import genai
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

# Endpoint para servir a ração (Conexão Serial sob demanda para evitar PermissionError)
@app.post("/api/alimentar")
def alimentar_gato():
    porta_com = 'COM7'
    try:
        # Abre a porta apenas no momento do clique
        with serial.Serial(porta_com, 9600, timeout=1) as arduino:
            time.sleep(2.5)  # Tempo de espera necessário para o reset do Arduino
            
            arduino.reset_input_buffer()
            arduino.reset_output_buffer()
            
            arduino.write(b'G')  # Envia o comando para o motor rodar
            time.sleep(0.5)
            
            return {"status": "sucesso", "mensagem": "Comando enviado! Ração servida com sucesso."}
    except serial.SerialException as e:
        raise HTTPException(
            status_code=503,
            detail=f"Não foi possível aceder à {porta_com}. Certifique-se de que a Arduino IDE está FECHADA. Erro: {e}"
        )

# Endpoint para o Chat de IA utilizando Gemini
from google.genai import types

# Endpoint para o Chat de IA utilizando Gemini
# Lista global para armazenar o histórico da conversa na memória do servidor
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
        
        # Adiciona a nova mensagem do utilizador ao histórico
        historico_chat.append({"role": "user", "parts": [{"text": payload.pergunta}]})
        
        # Envia todo o histórico de conversação para o Gemini manter o contexto
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=historico_chat
        )
        
        # Adiciona a resposta da IA ao histórico
        historico_chat.append({"role": "model", "parts": [{"text": response.text}]})
        
        return {"resposta": response.text}
    except Exception as e:
        print(f"[ERRO GEMINI] {e}")
        return {"resposta": "Desculpe, ocorreu um erro ao processar a conversa."}

# Rota opcional para limpar a conversa quando você quiser
@app.post("/api/ia/limpar")
def limpar_historico():
    global historico_chat
    historico_chat = []
    return {"status": "sucesso", "mensagem": "Histórico de conversa limpo!"}
# -----------------------------------------------------------------------------
# 3. INICIALIZAÇÃO DO SERVIDOR WEB
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=False)