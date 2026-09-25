"""
Script de Backup e Manutenção do CasaIA SQLite
Automatize backups, limpeza e estatísticas
"""

import sqlite3
import shutil
import os
from datetime import datetime
from pathlib import Path

DB_PATH = "casaia.db"
BACKUP_DIR = "backups"

# Criar pasta de backups se não existir
Path(BACKUP_DIR).mkdir(exist_ok=True)

def conectar_db():
    """Conecta ao banco SQLite"""
    return sqlite3.connect(DB_PATH)

def fazer_backup():
    """Faz backup do banco de dados"""
    if not os.path.exists(DB_PATH):
        print("❌ Banco de dados não encontrado (casaia.db)")
        return
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{BACKUP_DIR}/casaia_{timestamp}.db"
    
    shutil.copy(DB_PATH, backup_path)
    tamanho = os.path.getsize(backup_path) / 1024  # KB
    
    print(f"✅ Backup criado: {backup_path}")
    print(f"   Tamanho: {tamanho:.1f} KB")

def ver_estatisticas():
    """Mostra estatísticas do banco"""
    conn = conectar_db()
    cursor = conn.cursor()
    
    print("\n📊 ESTATÍSTICAS DO CASAIA")
    print("=" * 50)
    
    # Despensa
    cursor.execute("SELECT COUNT(*) FROM despensa")
    qtd_despensa = cursor.fetchone()[0]
    print(f"🍎 Itens na Despensa: {qtd_despensa}")
    
    cursor.execute("SELECT COUNT(*) FROM despensa WHERE datetime(validade) < date('now')")
    vencidos = cursor.fetchone()[0]
    print(f"   ⚠️  Itens vencidos: {vencidos}")
    
    cursor.execute("SELECT COUNT(*) FROM despensa WHERE datetime(validade) < date('now', '+3 days')")
    criticos = cursor.fetchone()[0]
    print(f"   🔴 Críticos (< 3 dias): {criticos}")
    
    # Automações
    cursor.execute("SELECT COUNT(*) FROM automacoes")
    qtd_auto = cursor.fetchone()[0]
    print(f"\n🤖 Automações: {qtd_auto}")
    
    cursor.execute("SELECT COUNT(*) FROM automacoes WHERE ativo = 1")
    ativas = cursor.fetchone()[0]
    print(f"   ✅ Ativas: {ativas}")
    
    # Histórico
    cursor.execute("SELECT COUNT(*) FROM historico")
    qtd_historico = cursor.fetchone()[0]
    print(f"\n📜 Comandos no Histórico: {qtd_historico}")
    
    cursor.execute("SELECT MAX(timestamp) FROM historico")
    ultimo = cursor.fetchone()[0]
    if ultimo:
        print(f"   ⏰ Último comando: {ultimo}")
    
    conn.close()
    print("=" * 50 + "\n")

def listar_despensa():
    """Lista todos os itens da despensa"""
    conn = conectar_db()
    cursor = conn.cursor()
    
    print("\n📋 ITENS NA DESPENSA")
    print("=" * 80)
    
    cursor.execute("""
        SELECT id, item, quantidade, unidade, validade, consumo_diario
        FROM despensa
        ORDER BY validade ASC
    """)
    
    itens = cursor.fetchall()
    
    if not itens:
        print("Nenhum item cadastrado")
    else:
        print(f"{'ID':<4} {'Item':<20} {'Qtd':<8} {'Validade':<12} {'Consumo/dia':<12}")
        print("-" * 80)
        
        for item in itens:
            print(f"{item[0]:<4} {item[1]:<20} {item[2]:<8} {item[4]:<12} {item[5]:<12}")
    
    conn.close()
    print("=" * 80 + "\n")

def listar_automacoes():
    """Lista todas as automações"""
    conn = conectar_db()
    cursor = conn.cursor()
    
    print("\n⚙️ AUTOMAÇÕES")
    print("=" * 100)
    
    cursor.execute("""
        SELECT id, nome, condicao, acao, ativo
        FROM automacoes
        ORDER BY id ASC
    """)
    
    automacoes = cursor.fetchall()
    
    if not automacoes:
        print("Nenhuma automação cadastrada")
    else:
        print(f"{'ID':<4} {'Nome':<25} {'Condição':<30} {'Ação':<30} {'Ativa':<6}")
        print("-" * 100)
        
        for auto in automacoes:
            status = "✅" if auto[4] else "❌"
            print(f"{auto[0]:<4} {auto[1]:<25} {auto[2]:<30} {auto[3]:<30} {status:<6}")
    
    conn.close()
    print("=" * 100 + "\n")

def limpar_historico(dias=30):
    """Remove histórico com mais de X dias"""
    conn = conectar_db()
    cursor = conn.cursor()
    
    cursor.execute(f"""
        DELETE FROM historico 
        WHERE datetime(timestamp) < datetime('now', '-{dias} days')
    """)
    
    deletados = cursor.rowcount
    conn.commit()
    conn.close()
    
    print(f"✅ {deletados} registros do histórico removidos (> {dias} dias)")

def resetar_banco():
    """Apaga TODOS os dados (cuidado!)"""
    resposta = input("⚠️ ATENÇÃO! Isso vai deletar TODOS os dados. Tem certeza? (s/n): ")
    
    if resposta.lower() != 's':
        print("❌ Operação cancelada")
        return
    
    resposta2 = input("Digite 'DELETAR' para confirmar: ")
    
    if resposta2 == "DELETAR":
        os.remove(DB_PATH)
        print("✅ Banco de dados deletado!")
        print("   Execute 'python main.py' para criar um novo banco vazio")
    else:
        print("❌ Operação cancelada")

def menu():
    """Menu principal"""
    while True:
        print("\n🏠 CasaIA - Manutenção do Banco SQLite")
        print("=" * 50)
        print("1. 💾 Fazer Backup")
        print("2. 📊 Ver Estatísticas")
        print("3. 🍎 Listar Despensa")
        print("4. ⚙️  Listar Automações")
        print("5. 🗑️  Limpar Histórico (> 30 dias)")
        print("6. 🆘 Resetar Banco (PERIGOSO!)")
        print("7. 🚪 Sair")
        print("=" * 50)
        
        opcao = input("Escolha uma opção: ").strip()
        
        if opcao == "1":
            fazer_backup()
        elif opcao == "2":
            ver_estatisticas()
        elif opcao == "3":
            listar_despensa()
        elif opcao == "4":
            listar_automacoes()
        elif opcao == "5":
            limpar_historico(30)
        elif opcao == "6":
            resetar_banco()
        elif opcao == "7":
            print("👋 Até logo!")
            break
        else:
            print("❌ Opção inválida")

if __name__ == "__main__":
    menu()
