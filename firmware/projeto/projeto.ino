#include <IRremote.hpp>
#include <Servo.h>

// -----------------------------------------------------------------------------
// DEFINIÇÃO DOS PINOS E HARDWARE (Arduino do Alimentador - COM7)
// -----------------------------------------------------------------------------
const int PINO_RECEPTOR_IR = 2;  // Receptor IR
const int PINO_RELE        = 4;  // Relé do Motor Misturador (Pino IN do relé)
const int PINO_TRIG        = 6;  // Sensor Ultrassónico (Trigger)
const int PINO_ECHO        = 7;  // Sensor Ultrassónico (Echo)
const int PINO_SERVO       = 9;  // Servomotor SG90 (Sinal)

// Pinos do LED RGB (PWM)
const int LED_R = 3;   // LED RGB Vermelho
const int LED_G = 5;   // LED RGB Verde
const int LED_B = 11;  // LED RGB Azul

Servo servoComporta;

// Tempos e Parâmetros de Funcionamento
const int DISTANCIA_GATO_CM    = 15;     // Distância máxima do gato (cm)
const int TEMPO_MISTURAR_MS    = 1500;   // Tempo que o relé/motor mistura (1.5 segundos)
const int TEMPO_SERVIR_MS      = 2000;   // Tempo que o servo fica aberto (2 segundos)
const unsigned long TEMPO_ESPERA = 10000; // Intervalo mínimo entre refeições automáticas (10 segundos)

unsigned long ultimaRefeicao = 0;

// -----------------------------------------------------------------------------
// CONFIGURAÇÃO INICIAL (SETUP)
// -----------------------------------------------------------------------------
void setup() {
  Serial.begin(9600);
  delay(500);

  // Inicialização do Receptor IR
  IrReceiver.begin(PINO_RECEPTOR_IR, DISABLE_LED_FEEDBACK);

  // Configuração do Relé Misturador
  pinMode(PINO_RELE, OUTPUT);
  digitalWrite(PINO_RELE, HIGH); // Relé desligado inicialmente (Módulos Active LOW)

  // Configuração do Sensor Ultrassónico
  pinMode(PINO_TRIG, OUTPUT);
  pinMode(PINO_ECHO, INPUT);

  // Configuração das saídas do LED RGB
  pinMode(LED_R, OUTPUT);
  pinMode(LED_G, OUTPUT);
  pinMode(LED_B, OUTPUT);

  // Configuração e Posição Inicial do Servomotor
  servoComporta.attach(PINO_SERVO);
  servoComporta.write(0); // Comporta fechada (0 graus)

  // Estado Inicial: LED Verde = Sistema Pronto
  definirCorRGB(0, 255, 0);
  Serial.println("\n>>> CasaIA: Alimentador de Gatos Pronto <<<");
}

// -----------------------------------------------------------------------------
// FUNÇÃO PARA CONTROLO DO LED RGB
// -----------------------------------------------------------------------------
void definirCorRGB(int r, int g, int b) {
  analogWrite(LED_R, r);
  analogWrite(LED_G, g);
  analogWrite(LED_B, b);
}

// -----------------------------------------------------------------------------
// FUNÇÃO PARA MEDIR DISTÂNCIA COM O ULTRASSÓNICO
// -----------------------------------------------------------------------------
long medirDistancia() {
  digitalWrite(PINO_TRIG, LOW);
  delayMicroseconds(2);
  digitalWrite(PINO_TRIG, HIGH);
  delayMicroseconds(10);
  digitalWrite(PINO_TRIG, LOW);

  long duracao = pulseIn(PINO_ECHO, HIGH);
  return (duracao * 0.034) / 2;
}

// -----------------------------------------------------------------------------
// FUNÇÃO PRINCIPAL: SEQUÊNCIA DE ALIMENTAÇÃO
// -----------------------------------------------------------------------------
void servirRacao(String origem) {
  Serial.print("EVT: Servindo racao via ");
  Serial.println(origem);
  
  // 1. MISTURAR RAÇÃO VIA RELÉ (LED Laranja/Amarelo)
  definirCorRGB(255, 100, 0);    // Cor Laranja = Misturando
  digitalWrite(PINO_RELE, LOW);  // Liga o relé do motor misturador
  delay(TEMPO_MISTURAR_MS);      // Funciona durante 1.5s
  digitalWrite(PINO_RELE, HIGH); // Desliga o relé do motor
  
  delay(300); // Pausa técnica de segurança

  // 2. SERVIR RAÇÃO VIA SERVOMOTOR (LED Azul)
  definirCorRGB(0, 0, 255);      // Cor Azul = Servindo
  servoComporta.write(180);       // Abre a comporta (180 graus)
  delay(TEMPO_SERVIR_MS);        // Mantém aberto durante 2s
  
  servoComporta.write(0);        // Fecha a comporta (0 graus)
  delay(300);

  // 3. FINALIZADO: VOLTA AO ESTADO PRONTO (LED Verde)
  definirCorRGB(0, 255, 0);      // Cor Verde = Pronto
  ultimaRefeicao = millis();
}

// -----------------------------------------------------------------------------
// LOOP PRINCIPAL
// -----------------------------------------------------------------------------
void loop() {
  // 1. COMANDOS RECEBIDOS VIA SERIAL (PYTHON / DASHBOARD / PINGO)
  if (Serial.available() > 0) {
    char cmd = Serial.read();
    if (cmd == 'G' || cmd == 'g') {
      servirRacao("DASHBOARD PYTHON");
    }
  }

  // 2. COMANDOS VIA CONTROLO REMOTO IR
  if (IrReceiver.decode()) {
    uint32_t codigoHex = IrReceiver.decodedIRData.decodedRawData;

    if (codigoHex > 0) {
      servirRacao("CONTROLE REMOTO IR");
    }

    delay(150);
    IrReceiver.resume();
  }

  // 3. ATIVAÇÃO VIA SENSOR ULTRASSÓNICO DE PROXIMIDADE
  long distancia = medirDistancia();

  if (distancia > 0 && distancia <= DISTANCIA_GATO_CM) {
    if (millis() - ultimaRefeicao >= TEMPO_ESPERA) {
      servirRacao("SENSOR DE PROXIMIDADE");
    }
  }

  delay(100);
}