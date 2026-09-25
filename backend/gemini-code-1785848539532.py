import os
import time
import asyncio
from typing import List, Optional
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import requests

# ===== CONFIGURAÇÃO DE BANCO DE DADOS (SQLite) =====
DATABASE_URL = "sqlite:///./casa_inteligente.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class ItemDespensaBD(Base):
    __tablename__ = "despensa"
    id = Column(Integer, primary_key=True, index=True)
    item = Column(String, index=True)
    quantidade = Column(Float)
    unidade = Column(String)

class AutomacaoBD(Base):
    __tablename__ = "automacoes"
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String)
    condicao = Column(String)
    acao = Column(String)
    ativa = Column(Boolean, default=True)

class LogBD(Base):
    __tablename__ = "logs"
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    origem = Column(String)
    mensagem = Column(String)

Base.metadata.create_all(bind=engine)

# ===== ESTRUTURAS DE DADOS =====
class ItemDespensa(BaseModel):
    item: str
    quantidade: float
    unidade: str

class Automacao(BaseModel):
    nome: str
    condicao: str
    acao: str
    ativa: bool = True

class ComandoIA(BaseModel):
    comando: str

# ===== GERENCIADOR WEBSOCKET =====
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                pass

manager = ConnectionManager()

# ===== ESTADO DA CASA =====
estado_casa = {
    "lampada_sala": False,
    "ar_condicionado": False,
    "temperatura_ar": 22,
    "modo_casa": "Normal",
    "sensores": {
        "temperatura_amb": 25.5,
        "umidade_amb": 60,
        "presenca_sala": False
    }
}

app = FastAPI(title="Casa Inteligente & Dashboard")

# Montagem de estáticos se a pasta existir
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

# Helper de logging
def registrar_log(origem: str, mensagem: str):
    db = SessionLocal()
    try:
        log = LogBD(origem=origem, mensagem=mensagem)
        db.add(log)
        db.commit()
    finally:
        db.close()

def obter_resposta_ia(prompt: str) -> str:
    # Função placeholder para integração com LLM/Gemini
    return f"Processado via IA: Entendido comando '{prompt}'. Operação finalizada."

# ===== ROTAS DE PÁGINA =====
@app.get("/", response_class=HTMLResponse)
def read_root():
    if os.path.exists("index.html"):
        with open("index.html", "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>index.html não encontrado no diretório raiz</h1>"

# ===== WEBSOCKET =====
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    # Envia estado inicial assim que conecta
    await websocket.send_json({"tipo": "estado", "dados": estado_casa})
    try:
        while True:
            data = await websocket.receive_text()
            # Mantém a conexão viva escutando pings ou mensagens
            await websocket.send_json({"tipo": "pong", "mensagem": data})
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# ===== API ESTADO E CONTROLE =====
@app.get("/api/estado")
def get_estado():
    return estado_casa

@app.post("/api/dispositivos/alternar")
async def alternar_dispositivo(dispositivo: str, estado: bool):
    if dispositivo in estado_casa:
        estado_casa[dispositivo] = estado
        registrar_log("Dispositivo", f"{dispositivo} alterado para {estado}")
        await manager.broadcast({"tipo": "estado", "dados": estado_casa})
        return {"status": "sucesso", "dispositivo": dispositivo, "novo_estado": estado}
    raise HTTPException(status_code=404, detail="Dispositivo não encontrado")

@app.post("/api/modo")
async def alterar_modo(modo: str):
    estado_casa["modo_casa"] = modo
    registrar_log("Modo", f"Modo alterado para {modo}")
    await manager.broadcast({"tipo": "estado", "dados": estado_casa})
    return {"status": "sucesso", "modo": modo}

# ===== API DESPENSA =====
@app.get("/api/despensa")
def listar_despensa():
    db = SessionLocal()
    itens = db.query(ItemDespensaBD).all()
    db.close()
    return [{"id": i.id, "item": i.item, "quantidade": i.quantidade, "unidade": i.unidade} for i in itens]

@app.post("/api/despensa")
def adicionar_despensa(item: ItemDespensa):
    db = SessionLocal()
    novo = ItemDespensaBD(item=item.item, quantidade=item.quantidade, unidade=item.unidade)
    db.add(novo)
    db.commit()
    db.refresh(novo)
    db.close()
    registrar_log("Despensa", f"Adicionado {item.quantidade} {item.unidade} de {item.item}")
    return {"status": "sucesso", "id": novo.id}

@app.delete("/api/despensa/{item_id}")
def remover_despensa(item_id: int):
    db = SessionLocal()
    item = db.query(ItemDespensaBD).filter(ItemDespensaBD.id == item_id).first()
    if item:
        db.delete(item)
        db.commit()
        db.close()
        return {"status": "sucesso"}
    db.close()
    raise HTTPException(status_code=404, detail="Item não encontrado")

@app.post("/api/despensa/receitas")
def gerar_receita():
    db = SessionLocal()
    itens = db.query(ItemDespensaBD).all()
    db.close()
    lista = ", ".join([f"{i.quantidade} {i.unidade} de {i.item}" for i in itens])
    if not lista:
        return {"receita": "A despensa está vazia! Adicione itens primeiro."}
    return {"receita": obter_resposta_ia(f"Crie uma receita rápida usando: {lista}")}

# ===== API CLIMA E MARÉ =====
@app.post("/api/clima/atualizar/{cidade}")
def atualizar_clima(cidade: str):
    # Simulação estruturada de retorno de clima/maré para a API
    dados_retorno = {
        "clima": {
            "temperatura": 28.5,
            "sensacao": 31.0,
            "umidade": 75,
            "velocidade_vento": 18,
            "condicao": "Ensolarado com poucas nuvens"
        },
        "mare": {
            "proxima_alta": "14:30 (2.1m)",
            "proxima_baixa": "08:15 (0.3m)",
            "melhor_hora": "07:00 - 10:00",
            "condicao": "Excelente para banho"
        }
    }
    return dados_retorno

@app.post("/api/ia/sugestao-praia")
def sugestao_praia():
    return {"resposta": "O dia está ideal para praia! Maré baixa pela manhã com vento moderado. Leve protetor solar."}

# ===== API AUTOMAÇÕES, TUYA E IA =====
@app.get("/api/automacoes")
def listar_automacoes():
    db = SessionLocal()
    auto = db.query(AutomacaoBD).all()
    db.close()
    return [{"id": a.id, "nome": a.nome, "condicao": a.condicao, "acao": a.acao, "ativa": a.ativa} for a in auto]

@app.post("/api/automacoes")
def criar_automacao(auto: Automacao):
    db = SessionLocal()
    nova = AutomacaoBD(nome=auto.nome, condicao=auto.condicao, acao=auto.acao, ativa=auto.ativa)
    db.add(nova)
    db.commit()
    db.close()
    return {"status": "sucesso"}

@app.get("/api/tuya/dispositivos")
def tuya_dispositivos():
    return [
        {"id": "t1", "nome": "Lâmpada Inteligente RGB", "tipo": "Luz", "status": "online", "estado": True},
        {"id": "t2", "nome": "Tomada Inteligente TV", "tipo": "Tomada", "status": "online", "estado": False}
    ]

@app.post("/api/ia/comando")
def processar_comando_ia(cmd: ComandoIA):
    resposta = obter_resposta_ia(cmd.comando)
    registrar_log("IA", f"Comando: {cmd.comando}")
    return {"resposta": resposta}

@app.get("/api/historico")
def listar_historico():
    db = SessionLocal()
    logs = db.query(LogBD).order_by(LogBD.timestamp.desc()).limit(50).all()
    db.close()
    return [{"id": l.id, "timestamp": l.timestamp.strftime("%Y-%m-%d %H:%M:%S"), "origem": l.origem, "mensagem": l.mensagem} for l in logs]