import pandas as pd
from datetime import datetime
from plyer import notification
import os

# ======================
# 📁 CAMINHOS DINÂMICOS
# ======================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

PASTA_DADOS = os.path.join(BASE_DIR, "dados")
PASTA_LOGS = os.path.join(BASE_DIR, "logs")

# cria pastas se não existirem
os.makedirs(PASTA_DADOS, exist_ok=True)
os.makedirs(PASTA_LOGS, exist_ok=True)

# ======================
# 🔍 BUSCAR EXCEL AUTOMÁTICO
# ======================
arquivos = [
    f for f in os.listdir(PASTA_DADOS)
    if f.endswith(".xlsx") and "controle" not in f.lower()
]

if not arquivos:
    print("❌ Nenhum arquivo de férias encontrado!")
    exit()

arquivo_origem = os.path.join(PASTA_DADOS, arquivos[0])
arquivo_tratado = os.path.join(PASTA_DADOS, "controle_tratado.xlsx")

print("📂 Usando arquivo:", arquivo_origem)

# ======================
# 📊 LER PLANILHA
# ======================
df = pd.read_excel(arquivo_origem, skiprows=1)

df.columns = df.columns.str.strip()

print("📌 Colunas encontradas:", df.columns)

dados = []

# ======================
# 🔄 TRATAMENTO
# ======================
for _, row in df.iterrows():
    try:
        nome = str(row.get("Nome", "")).strip()
        codigo = row.get("Código")

        inicio = pd.to_datetime(row.get("Início"), errors="coerce", dayfirst=True)
        fim = pd.to_datetime(row.get("Fim"), errors="coerce", dayfirst=True)
        data_bloqueio = pd.to_datetime(row.get("Data de Bloqueio"), errors="coerce", dayfirst=True)

        if nome == "" or nome.lower() == "nan":
            continue

        dados.append({
            "Nome": nome,
            "Código": codigo,
            "Início Férias": inicio.date() if pd.notnull(inicio) else None,
            "Fim Férias": fim.date() if pd.notnull(fim) else None,
            "Data de Bloqueio": data_bloqueio.date() if pd.notnull(data_bloqueio) else None
        })

    except Exception as e:
        print(f"Erro ao processar linha: {e}")
        continue

# ======================
# 💾 GERAR CONTROLE
# ======================
df_final = pd.DataFrame(dados)
df_final.to_excel(arquivo_tratado, index=False)

print("✅ Planilha controle gerada!")

# ======================
# 📅 VERIFICAR HOJE
# ======================
hoje = datetime.now().date()
usuarios = []

for _, row in df_final.iterrows():
    try:
        if row.get("Data de Bloqueio") == hoje:
            usuarios.append(row.get("Nome"))
    except:
        continue

# ======================
# 🔔 NOTIFICAÇÃO
# ======================
if usuarios:
    lista = "\n".join(usuarios)

    notification.notify(
        title="⚠️ Bloquear Usuários Hoje",
        message=lista,
        timeout=20
    )

    print("🔔 Notificação enviada!")
else:
    print("Nenhum bloqueio hoje.")

# ======================
# 📝 LOG (para agendador)
# ======================
log_path = os.path.join(PASTA_LOGS, "log.txt")

with open(log_path, "a", encoding="utf-8") as f:
    f.write("\n========================\n")
    f.write(f"Rodou em: {datetime.now()}\n")
    f.write(f"Arquivo usado: {arquivo_origem}\n")
    f.write(f"Usuários: {usuarios}\n")

