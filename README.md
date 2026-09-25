# 🏠 CasaIA - Assistente Inteligente para Casa

Um assistente residencial moderno e inteligente com integração de IA, automações, gerenciador de despensa e controle MQTT.

![Python](https://img.shields.io/badge/Python-3.8%2B-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-Latest-green)
![License](https://img.shields.io/badge/License-MIT-yellow)

---

## 🎯 Funcionalidades

✨ **Chat com IA** - Assistente inteligente alimentado por Groq  
🤖 **Automações** - Crie regras automáticas (se-então)  
🍎 **Gerenciador de Despensa** - Controle itens, datas de validade e sugestões de receitas  
📊 **Telemetria em Tempo Real** - Monitoramento de temperatura e umidade via WebSocket  
⚡ **Comandos Rápidos** - Controle sua casa com cliques  
🌙 **Tema Dark/Light** - Interface adaptável  
📱 **Responsivo** - Funciona em desktop, tablet e mobile  
🔌 **MQTT Support** - Integração com Arduino/ESP32  

---

## 📦 Instalação

### Pré-requisitos
- Python 3.8+
- pip
- (Opcional) Broker MQTT local (Mosquitto)

### 1. Clonar/Baixar os Arquivos
```bash
# Crie uma pasta para o projeto
mkdir casaia && cd casaia

# Copie os arquivos main.py e index.html para esta pasta
```

### 2. Criar Ambiente Virtual
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

### 3. Instalar Dependências
```bash
pip install fastapi uvicorn paho-mqtt groq python-multipart python-dotenv
```

### 4. Configurar Groq API (IMPORTANTE!)

**Passo 1:** Acesse [https://console.groq.com](https://console.groq.com)

**Passo 2:** Crie uma conta gratuita

**Passo 3:** Gere uma chave API na seção "API Keys"

**Passo 4:** Configure a variável de ambiente

#### Windows (Command Prompt)
```cmd
set GROQ_API_KEY=sua_chave_aqui
```

#### Windows (PowerShell)
```powershell
$env:GROQ_API_KEY="sua_chave_aqui"
```

#### Linux/Mac
```bash
export GROQ_API_KEY="sua_chave_aqui"
```

#### Permanente (criar arquivo `.env`)
```bash
# Crie um arquivo .env na raiz do projeto
GROQ_API_KEY=sua_chave_aqui
MQTT_BROKER=127.0.0.1
MQTT_PORT=1883
```

---

## 🚀 Executar

### Iniciar o Servidor
```bash
python main.py
```

Você verá algo como:
```
🏠 CasaIA iniciando...
📡 IA Status: ✅ Groq Ativado
INFO:     Uvicorn running on http://127.0.0.1:8000
```

### Abrir no Navegador
```
http://localhost:8000
```

---

## 🤖 Usando a IA

O assistente CasaIA entende comandos em linguagem natural:

### Exemplos de Perguntas
- **"Como economizar energia em casa?"** 
- **"Qual é a melhor temperatura para dormir?"**
- **"Como aproveitar frango que vence amanhã?"**
- **"Que receita posso fazer com leite e ovos?"**
- **"Dicas para manter a casa fresca?"**

### Perguntas Populares (Atalhos)
Clique nos botões de perguntas populares para fazer consultas rápidas.

---

## 🔧 Configuração MQTT (Arduino/ESP32)

Se você tem sensores conectados via MQTT:

### 1. Instalar Broker Mosquitto
```bash
# Ubuntu/Debian
sudo apt-get install mosquitto mosquitto-clients

# Windows - Download em: https://mosquitto.org/download/

# Mac
brew install mosquitto
```

### 2. Iniciar o Broker
```bash
# Linux/Mac
mosquitto

# Windows
mosquitto.exe -c mosquitto.conf
```

### 3. Código Arduino/ESP32 (Exemplo)
```cpp
#include <WiFi.h>
#include <PubSubClient.h>

WiFiClient espClient;
PubSubClient client(espClient);

void setup() {
  WiFi.begin("SSID", "PASSWORD");
  client.setServer("127.0.0.1", 1883);
  client.connect("esp32_sensor");
}

void loop() {
  float temp = readTemperature();
  float humidity = readHumidity();
  
  String payload = "{\"valor\":" + String(temp) + ",\"umidade\":" + String(humidity) + ",\"dispositivo_id\":\"esp32_sala\"}";
  
  client.publish("casaia/sensor/dados", payload.c_str());
  delay(10000);
}
```

---

## 📚 Estrutura dos Arquivos

```
casaia/
├── main.py              # Backend FastAPI
├── index.html           # Frontend
├── .env                 # Variáveis de ambiente (não versione!)
├── venv/                # Ambiente virtual
└── README.md            # Este arquivo
```

---

## 🎨 Design

### Tema Dark/Light
Clique no ícone de lua/sol no topo para alternar temas. A preferência é salva no navegador.

### Cores e Componentes
- **Gradientes Modernos** - Azul e roxo para destaque
- **Glass Morphism** - Efeito vidro translúcido
- **Animações Suaves** - Transições fluidas entre estados
- **Tailwind CSS** - Framework de utilidade

---

## 🔐 Segurança

### Recomendações
1. **Nunca compartilhe sua chave Groq** - Mantenha em `.env`
2. **Use CORS com cuidado** - Mude `allow_origins=["*"]` em produção
3. **Autenticação** - Considere adicionar um sistema de login
4. **HTTPS** - Use certificados SSL em produção
5. **MQTT com senha** - Configure autenticação no Mosquitto

### Variáveis de Ambiente
```bash
GROQ_API_KEY=sk_xxx_yyy_zzz
MQTT_BROKER=127.0.0.1
MQTT_PORT=1883
```

---

## 🐛 Troubleshooting

### Erro: "ModuleNotFoundError: No module named 'groq'"
```bash
pip install groq
```

### Erro: "MQTT Connection Refused"
- Verifique se o Mosquitto está rodando
- Verifique a porta (padrão 1883)
- Mude `MQTT_BROKER` para 127.0.0.1 ou seu IP

### Erro: "GROQ_API_KEY não definida"
- Certifique-se que você definiu a variável de ambiente
- Reinicie o terminal/PowerShell após definir
- Verifique se a chave é válida em https://console.groq.com

### Chat não aparece
- Verifique o console (F12) para erros JavaScript
- Certifique-se que a API está rodando em localhost:8000
- Limpe o cache do navegador (Ctrl+Shift+Del)

### WebSocket desconectado
- Verifique a conexão de rede
- Recarregue a página
- Reinicie o servidor

---

## 📖 API Endpoints

### Chat com IA
```
POST /api/ia/pergunta
Body: {"pergunta": "Como economizar energia?"}
Response: {"resposta": "..."}
```

### Comandos
```
POST /executar-comando
Body: {"comando": "abrir janela"}
Response: {"resposta": "..."}
```

### Despensa
```
GET /api/despensa
POST /api/despensa
DELETE /api/despensa/{id}
POST /api/despensa/receitas
```

### Automações
```
GET /api/automacoes
POST /api/automacoes
DELETE /api/automacoes/{id}
```

### Estado
```
GET /api/estado
POST /api/modo?modo=Normal
GET /api/historico?limite=20
```

### WebSocket
```
WS /ws
```

---

## 🚀 Próximos Passos

### Melhorias Planejadas
- [ ] Autenticação com login
- [ ] Integração com Google Home/Alexa
- [ ] Gráficos de consumo de energia
- [ ] Notificações push
- [ ] Histórico persistente (banco de dados)
- [ ] Backup e restauração de configurações
- [ ] Multi-usuário (admin, moradores)
- [ ] Integração com calendário (Google Calendar)
- [ ] Visão noturna com câmera
- [ ] Voice input/output

### Deploying em Produção

#### Heroku
```bash
# Instale Heroku CLI
# Faça login
heroku login

# Crie app
heroku create seu-app-casaia

# Configure variáveis
heroku config:set GROQ_API_KEY=sua_chave

# Deploy
git push heroku main
```

#### PythonAnywhere
1. Faça upload dos arquivos
2. Configure a aplicação WSGI
3. Defina variáveis de ambiente no dashboard

#### Docker
```dockerfile
FROM python:3.10-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "main.py"]
```

---

## 💡 Dicas

### Otimizar Resposta da IA
- Perguntas específicas = respostas melhores
- A IA usa contexto (temperatura, despensa, modo)
- Cache automático para perguntas repetidas

### Automações Úteis
- **Noturnas:** `temperatura < 20 → Ligar AC`
- **Economia:** `temperatura > 30 → Desligar equipamentos`
- **Segurança:** `modo = Ausência → Travar portas`
- **Conforto:** `horário = 22:00 → Modo Noite`

### Performance
- WebSocket para telemetria em tempo real
- Cache de respostas IA para reduzir latência
- Groq é muito rápido (< 100ms geralmente)

---

## 📄 Licença

MIT License - Sinta-se livre para usar e modificar!

---

## 🤝 Contribuindo

Tem ideias? Encontrou um bug?  
Sinta-se livre para abrir issues ou pull requests!

---

## 📞 Suporte

### Documentação
- [FastAPI Docs](https://fastapi.tiangolo.com/)
- [Groq API](https://console.groq.com/docs)
- [MQTT Guide](https://mqtt.org/)

### Comunidades
- Stack Overflow (tag: fastapi, mqtt, groq)
- GitHub Discussions
- Reddit r/homeautomation

---

**Feito com ❤️ para automação residencial inteligente**

```
    🏠
   /   \
  /     \
 |  AI  |
 |      |
  \    /
   \__/
```

Versão: 1.0.0  
Última atualização: Julho 2026
