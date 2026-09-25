import tkinter as tk
from tkinter import messagebox
import serial
import time
import threading
import csv
from datetime import datetime
import os

# Configuração da Porta Serial
PORTA_SERIAL = 'COM7'  # Ajuste para a COM correspondente ao seu Arduino
BAUD_RATE = 9600
ARQUIVO_LOG = 'historico_acesso.csv'

class CasaIADashboard:
    def __init__(self, root):
        self.root = root
        self.root.title("CasaIA - Painel Central de Automação")
        self.root.geometry("480x620")
        self.root.resizable(False, False)
        self.root.configure(bg="#1e1e2e")

        self.conexao_serial = None
        self.rodando = True

        self.inicializar_csv()
        self.setup_ui()
        self.conectar_arduino()

    def inicializar_csv(self):
        """ Cria o arquivo CSV com cabeçalho caso não exista """
        if not os.path.exists(ARQUIVO_LOG):
            with open(ARQUIVO_LOG, mode='w', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                writer.writerow(["Data/Hora", "Evento/Origem", "Estado Resultante"])

    def registrar_csv(self, evento, estado):
        """ Grava o registro de acesso/alimentação com data e hora no CSV """
        data_hora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        try:
            with open(ARQUIVO_LOG, mode='a', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                writer.writerow([data_hora, evento, estado])
        except Exception as e:
            print(f"Erro ao salvar no CSV: {e}")

    def setup_ui(self):
        # Título Principal
        lbl_titulo = tk.Label(
            self.root, text="CasaIA - Automação Residencial", font=("Helvetica", 16, "bold"),
            bg="#1e1e2e", fg="#cdd6f4"
        )
        lbl_titulo.pack(pady=12)

        # Painel de Estado da Tranca
        self.lbl_status = tk.Label(
            self.root, text="TRANCA: DESCONHECIDA", font=("Helvetica", 13, "bold"),
            bg="#313244", fg="#f9e2af", width=32, height=2, relief="flat"
        )
        self.lbl_status.pack(pady=8)

        # Frame dos Botões da Tranca (Abrir / Fechar)
        frame_tranca = tk.LabelFrame(
            self.root, text=" Controlo de Fechadura ", font=("Helvetica", 10, "bold"),
            bg="#1e1e2e", fg="#a6adc8", bd=1, relief="groove"
        )
        frame_tranca.pack(pady=10, padx=20, fill="x")

        self.btn_abrir = tk.Button(
            frame_tranca, text="🔓 ABRIR", font=("Helvetica", 11, "bold"),
            bg="#a6e3a1", fg="#11111b", width=12, height=2, bd=0,
            cursor="hand2", command=self.enviar_abrir
        )
        self.btn_abrir.grid(row=0, column=0, padx=15, pady=10)

        self.btn_fechar = tk.Button(
            frame_tranca, text="🔒 FECHAR", font=("Helvetica", 11, "bold"),
            bg="#f38ba8", fg="#11111b", width=12, height=2, bd=0,
            cursor="hand2", command=self.enviar_fechar
        )
        self.btn_fechar.grid(row=0, column=1, padx=15, pady=10)

        # Frame do Alimentador do Gato
        frame_gato = tk.LabelFrame(
            self.root, text=" Alimentador Automático do Gato ", font=("Helvetica", 10, "bold"),
            bg="#1e1e2e", fg="#a6adc8", bd=1, relief="groove"
        )
        frame_gato.pack(pady=10, padx=20, fill="x")

        self.btn_alimentar = tk.Button(
            frame_gato, text="🐱 ALIMENTAR GATO", font=("Helvetica", 12, "bold"),
            bg="#cba6f7", fg="#11111b", width=26, height=2, bd=0,
            cursor="hand2", command=self.enviar_alimentar_gato
        )
        self.btn_alimentar.pack(pady=10, padx=10)

        # Caixa de Texto para Logs / Histórico em Tempo Real
        lbl_log = tk.Label(
            self.root, text="Histórico de Eventos (Salvo em CSV):", font=("Helvetica", 10),
            bg="#1e1e2e", fg="#a6adc8"
        )
        lbl_log.pack(anchor="w", padx=25, pady=(10, 2))

        self.txt_log = tk.Text(
            self.root, height=8, width=52, font=("Consolas", 9),
            bg="#181825", fg="#a6e3a1", bd=0, insertbackground="white"
        )
        self.txt_log.pack(padx=25, pady=5)

    def log_mensagem(self, msg):
        """ Exibe mensagens no log da GUI """
        self.txt_log.insert(tk.END, f"{msg}\n")
        self.txt_log.see(tk.END)

    def conectar_arduino(self):
        try:
            self.conexao_serial = serial.Serial(PORTA_SERIAL, BAUD_RATE, timeout=1)
            time.sleep(2)
            self.log_mensagem(f"[SISTEMA] Conectado com sucesso na porta {PORTA_SERIAL}")
            
            thread_leitura = threading.Thread(target=self.ler_serial_arduino, daemon=True)
            thread_leitura.start()
        except Exception as e:
            self.log_mensagem(f"[ERRO] Falha ao abrir a porta {PORTA_SERIAL}")
            messagebox.showerror("Erro de Conexão", f"Certifique-se de que o Monitor Serial na Arduino IDE está fechado!\n\nDetalhes: {e}")

    def enviar_abrir(self):
        if self.conexao_serial and self.conexao_serial.is_open:
            self.conexao_serial.write(b'A')
            self.log_mensagem(">> Enviado: Comando ABRIR Fechadura")

    def enviar_fechar(self):
        if self.conexao_serial and self.conexao_serial.is_open:
            self.conexao_serial.write(b'F')
            self.log_mensagem(">> Enviado: Comando FECHAR Fechadura")

    def enviar_alimentar_gato(self):
        if self.conexao_serial and self.conexao_serial.is_open:
            self.conexao_serial.write(b'G')
            self.log_mensagem(">> Enviado: Comando SERVIR RAÇÃO para o Gato")

    def ler_serial_arduino(self):
        while self.rodando:
            try:
                if self.conexao_serial and self.conexao_serial.in_waiting > 0:
                    resposta = self.conexao_serial.readline().decode('utf-8', errors='ignore').strip()
                    if resposta:
                        self.log_mensagem(f"[ARDUINO] {resposta}")
                        
                        # Tranca de Acesso
                        if "STATUS:TRANCA_ABERTA" in resposta:
                            self.lbl_status.config(text="TRANCA: ABERTA", bg="#a6e3a1", fg="#11111b")
                            self.registrar_csv("Fechadura", "ABERTA")
                        elif "STATUS:TRANCA_FECHADA" in resposta:
                            self.lbl_status.config(text="TRANCA: FECHADA", bg="#f38ba8", fg="#11111b")
                            self.registrar_csv("Fechadura", "FECHADA")
                        
                        # Alimentador de Gatos
                        elif "Servindo racao" in resposta:
                            self.registrar_csv("Alimentador Gato", "RAÇÃO SERVIDA")
            except Exception:
                break

if __name__ == "__main__":
    root = tk.Tk()
    app = CasaIADashboard(root)
    root.mainloop()