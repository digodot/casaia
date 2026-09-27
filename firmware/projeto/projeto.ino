#include <IRremote.hpp>
#include <Servo.h>

// -----------------------------------------------------------------------------
// DEFINIÇÃO DOS PINOS E HARDWARE (Arduino do Alimentador)
// -----------------------------------------------------------------------------
const int PINO_RECEPTOR_IR = 2;  // Receptor IR
const int PINO_RELE        = 4;  // Relé do Motor Misturador (Pino IN)
const int PINO_SERVO       = 9;  // Servomotor SG90 (Sinal)

// Pinos do LED RGB (PWM)
const int LED_R = 3;   // LED RGB Vermelho
const int LED_G = 5;   // LED RGB Verde
const int LED_B = 11;  // LED RGB Azul

Servo servoComporta;

// Tempos e Parâmetros de Funcionamento
const int TEMPO_MISTURAR_MS = 1500;  // Tempo que o relé/motor mistura (1.5s)
const int TEMPO_SERVIR_MS   = 2000;  // Tempo base de serviço

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
  digitalWrite(PINO_RELE, HIGH); // Relé desligado (Módulos Active LOW)

  // Configuração das saídas do LED RGB
  pinMode(LED_R, OUTPUT);
  pinMode(LED_G, OUTPUT);
  pinMode(LED_B, OUTPUT);

  // Configuração e Posição Inicial do Servomotor
  servoComporta.attach(PINO_SERVO);
  servoComporta.write(0); // Comporta fechada (0 graus)

  // ESTADO INICIAL: LED VERDE E DEMAIS CORES TOTALMENTE APAGADOS
  definirCorRGB(0, 0, 0);
  Serial.println("\n>>> CasaIA: Alimentador Pronto (Aguardando IR/Serial) <<<");
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
  
  // Movimento repetido (3 pulsos) para soltar grãos presos
  for (int i = 0; i < 3; i++) {
    servoComporta.write(180);    // Abre a comporta (180 graus)
    delay(800);
    servoComporta.write(30);     // Recua ligeiramente para soltar a ração
    delay(300);
  }
  
  servoComporta.write(0);        // Fecha totalmente a comporta
  delay(300);

  // 3. FINALIZADO: APAGA TOTALMENTE O LED
  definirCorRGB(0, 0, 0);
}

// -----------------------------------------------------------------------------
// LOOP PRINCIPAL
// -----------------------------------------------------------------------------
void loop() {
  // Garantia de que o LED continua apagado enquanto o sistema aguarda
  // (Caso ocorra alguma interferência nos pinos PWM)
  
  // 1. COMANDOS RECEBIDOS VIA SERIAL (PYTHON / DASHBOARD)
  if (Serial.available() > 0) {
    char cmd = Serial.read();
    if (cmd == 'G' || cmd == 'g') {
      // Acende LED Verde para sinalizar ativação por comando
      definirCorRGB(0, 255, 0);
      delay(500);
      servirRacao("DASHBOARD PYTHON");
    }
  }

  // 2. COMANDOS VIA CONTROLO REMOTO IR
  if (IrReceiver.decode()) {
    uint32_t codigoHex = IrReceiver.decodedIRData.decodedRawData;

    if (codigoHex > 0) {
      // ACENDE O LED VERDE SOMENTE AQUI (NO MOMENTO DA DETEÇÃO IR)
      definirCorRGB(0, 255, 0);
      delay(800); // Mantém o LED Verde visível confirmando a leitura
      
      servirRacao("CONTROLE REMOTO IR");
    }

    delay(150);
    IrReceiver.resume();
  }

  delay(50);
}