import serial
import time
import threading

PORTA_SERIAL = 'COM7'
BAUD_RATE = 9600

def ler_resposta_arduino(conexao_serial):
    while True:
        try:
            if conexao_serial.in_waiting > 0:
                resposta = conexao_serial.readline().decode('utf-8', errors='ignore').strip()
                if resposta:
                    print(f"\n[ARDUINO] {resposta}")
                    print("Comando (A = Abrir, F = Fechar, Q = Sair): ", end='', flush=True)
        except Exception as e:
            print(f"\n[ERRO NA LEITURA]: {e}")
            break

def main():
    try:
        print(f"A conectar ao CasaIA na porta {PORTA_SERIAL}...")
        arduino = serial.Serial(PORTA_SERIAL, BAUD_RATE, timeout=1)
        time.sleep(2)
        print("Conexão estabelecida com sucesso!")

        thread_leitura = threading.Thread(target=ler_resposta_arduino, args=(arduino,), daemon=True)
        thread_leitura.start()

        while True:
            comando = input("Comando (A = Abrir, F = Fechar, Q = Sair): ").strip().upper()

            if comando == 'A':
                arduino.write(b'A')
                print(">> Enviado comando para ABRIR...")
            elif comando == 'F':
                arduino.write(b'F')
                print(">> Enviado comando para FECHAR...")
            elif comando == 'Q':
                print("A encerrar conexão com o CasaIA...")
                arduino.close()
                break
            else:
                print("Opção inválida! Utilize apenas A, F ou Q.")

    except serial.SerialException:
        print(f"\n[ERRO DE CONEXÃO]: Não foi possível abrir a porta {PORTA_SERIAL}.")
        print("Certifique-se de que o Monitor Serial na Arduino IDE está FECHADO.")
    except KeyboardInterrupt:
        print("\nPrograma encerrado.")

if __name__ == "__main__":
    main()