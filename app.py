import streamlit as st
import uuid
import os
from datetime import date, datetime
from db import (
    init_db, add_receita, get_total_receitas_mes,
    salvar_sessao, carregar_sessao, limpar_sessao,
    add_conta, get_contas,
    add_subconta, get_subcontas, delete_subconta, pode_excluir_subconta,
    salvar_valor_subconta, get_saldos_mes, registrar_gasto,
    registrar_transferencia,
    registrar_emprestimo, listar_emprestimos, listar_parcelas, quitar_parcela
)
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
import io
from reportlab.lib.enums import TA_LEFT

# =========================================================
# LOGIN CONFIG
# =========================================================
USERNAME = os.environ.get("APP_USER", "")
PASSWORD = os.environ.get("APP_PASS", "")

# =========================================================
# INIT
# =========================================================
init_db()

if "logged_in" not in st.session_state:
    token = carregar_sessao()
    if token:
        st.session_state.logged_in = True
        st.session_state.page = "dashboard"
    else:
        st.session_state.logged_in = False
        st.session_state.page = "login"
if "page" not in st.session_state:
    st.session_state.page = "login" if not st.session_state.logged_in else "dashboard"
if "gasto_info" not in st.session_state:
    st.session_state.gasto_info = None
if "ultimo_mes" not in st.session_state:
    st.session_state.ultimo_mes = date.today().strftime("%m/%Y")
if "emprestimo_detalhe" not in st.session_state:
    st.session_state.emprestimo_detalhe = None
if "confirmar_quitacao" not in st.session_state:
    st.session_state.confirmar_quitacao = None  # (pid, valor, valor_orig)

# =========================================================
# HELPERS
# =========================================================
def brl(v: float) -> str:
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def date_br_input(label: str, key=None, default=None):
    if default is None:
        default = date.today()
    val_str = st.text_input(label, value=default.strftime("%d/%m/%Y"), key=key)
    try:
        d = datetime.strptime(val_str.strip(), "%d/%m/%Y").date()
        return d, d.strftime("%d/%m/%Y"), False
    except Exception:
        st.warning("Use o formato DD/MM/AAAA")
        return None, val_str, True

# =========================================================
# RESERVAS - Garantir existência
# =========================================================
def garantir_reservas():
    contas = get_contas()
    conta_dict = {nome: cid for cid, nome in contas}
    if "Sistema" not in conta_dict:
        add_conta("Sistema")
        contas = get_contas()
        conta_dict = {nome: cid for cid, nome in contas}
    subcontas = get_subcontas()
    nomes_sub = [s_nome for _, s_nome, _ in subcontas]
    if "Reservas" not in nomes_sub:
        add_subconta("Reservas", conta_dict["Sistema"])

garantir_reservas()

# =========================================================
# FECHAMENTO DE MÊS
# =========================================================
def fechamento_mes(ano_mes_atual):
    ultimo = st.session_state.ultimo_mes
    if ano_mes_atual != ultimo:
        sobras = get_saldos_mes(ultimo)
        reservas = [s for s in get_subcontas() if s[1] == "Reservas"]
        if reservas:
            reservas_id = reservas[0][0]
            hoje = date.today().strftime("%d/%m/%Y")
            for sid, conta_nome, sub_nome, inicial, atual in sobras:
                if atual > 0 and sub_nome != "Reservas":
                    registrar_transferencia(
                        hoje,
                        sid,
                        reservas_id,
                        atual,
                        f"Sobra automática de {ultimo}",
                        ultimo
                    )
        st.session_state.ultimo_mes = ano_mes_atual

# =========================================================
# CSS
# =========================================================
st.markdown("""
<style>
.stApp { background:#ffffff; color:#111827; }
h1,h2,h3 { color:#111827; }
/* ===== CARDS SUBCONTAS ===== */
.card-btn > button {
  border-radius: 10px;
  border: 1px solid #d1d5db;
  background: #f9fafb;
  color: #111827;
  height: auto;
  padding: 15px;
  white-space: pre-line;
  text-align: left;
  font-size: 14px;
  font-weight: 500;
  box-shadow: 0 2px 6px rgba(0,0,0,0.08);
}
.card-btn > button:hover {
  background: #111827;
  color: #fff;
  border-color: #111827;
  transform: translateY(-3px);
}

/* ===== CARDS EMPRÉSTIMOS ===== */
div[data-testid="stButton"] > button.emp-card {
  border-radius: 12px;
  border: 1px solid #e0e0e0;
  background: #fafafa;
  color: #111827;
  padding: 16px;
  text-align: left;
  font-size: 15px;
  font-weight: 500;
  box-shadow: 0 2px 6px rgba(0,0,0,0.08);
  white-space: pre-line;
  margin-bottom: 15px;
}
div[data-testid="stButton"] > button.emp-card:hover {
  background: #4f46e5;
  color: #fff;
  border-color: #4f46e5;
  transform: translateY(-3px);
}

/* ===== TABELA DE PARCELAS ===== */
.table-parcelas {
  width: 100%;
  border-collapse: collapse;
  margin-top: 15px;
}
.table-parcelas th, .table-parcelas td {
  padding: 8px 12px;
  border: 1px solid #e5e7eb;
  text-align: center;
  font-size: 14px;
}
.table-parcelas tr:nth-child(even) { background-color: #f9fafb; }
.table-parcelas tr.quitada { background-color: #dcfce7; }
.table-parcelas tr.aberta { background-color: #fee2e2; }
.table-parcelas tr.antecipada { background-color: #dbeafe; }

/* ===== BOTÕES RÁPIDOS ===== */
div[data-testid="column"] div.stButton > button {
  width: 130px;
  height: 100px;
  border-radius: 14px;
  border: 1px solid #d1d5db;
  background: #f9fafb;
  color: #111827;
  font-size: 14px;
  font-weight: 600;
  text-align: center;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  box-shadow: 0 2px 6px rgba(0,0,0,0.1);
  transition: all .2s ease-in-out;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
}
div[data-testid="column"] div.stButton > button:hover {
  background: #111827;
  color: #fff;
  border-color: #111827;
  transform: translateY(-3px);
}
</style>
""", unsafe_allow_html=True)
# =========================================================
# DASHBOARD
# =========================================================
def dashboard():
    hoje = date.today()
    ano_mes = hoje.strftime("%m/%Y")
    fechamento_mes(ano_mes)

    # Botão de sair no canto superior esquerdo + título
    col_sair, col_titulo = st.columns([1, 6])
    with col_sair:
        if st.button("🚪 Sair", key="btn_sair", help="Encerrar sessão"):
            limpar_sessao()
            st.session_state.logged_in = False
            st.session_state.page = "login"
            st.rerun()
    with col_titulo:
        st.title("📊 Dashboard Financeiro")

    agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    st.caption(f"📅 Data/Hora atual: {agora}")

    total_receitas = get_total_receitas_mes(ano_mes)
    saldos = get_saldos_mes(ano_mes)
    total_atribuido = sum(s[3] for s in saldos) if saldos else 0
    saldo_atual = sum(s[4] for s in saldos) if saldos else 0

    c1, c2, c3 = st.columns(3)
    c1.metric("Saldo Atual", brl(saldo_atual))
    c2.metric("Receitas no mês", brl(total_receitas))
    c3.metric("Valor distribuído", brl(total_atribuido))

    # Card de Reservas fixo
    saldos_reserva = [s for s in saldos if s[2] == "Reservas"]
    if saldos_reserva:
        sid, c_nome, s_nome, inicial, atual = saldos_reserva[0]
        st.markdown(f"""
        <div style='
            position: fixed; top: 100px; right: 40px;
            width: 170px; height: 170px;
            border-radius: 50%;
            background-color: #dbeafe;
            display: flex; flex-direction: column;
            justify-content: center; align-items: center;
            box-shadow: 0 4px 10px rgba(0,0,0,0.25);
            font-weight: bold; color: #1e3a8a;
            z-index: 999;
        '>
            <div style="font-size:18px;">💰 {s_nome}</div>
            <div style="font-size:16px;">{brl(atual)}</div>
        </div>
        """, unsafe_allow_html=True)

    # Gasto manual
    if st.session_state.gasto_info:
        sid, conta, sub, atual, am = st.session_state.gasto_info
        st.subheader(f"Registrar gasto – {conta}/{sub}")
        with st.form("gasto_form"):
            _, data_str, err = date_br_input("Data")
            valor = st.number_input("Valor", min_value=0.0, step=0.01)
            desc = st.text_input("Descrição")
            salvar = st.form_submit_button("Salvar")
            if salvar:
                if not err and valor > 0:
                    if valor > atual:
                        st.error("Saldo insuficiente para registrar este gasto.")
                    else:
                        registrar_gasto(data_str, valor, desc, sid, am)
                        st.success("Gasto registrado!")
                        st.session_state.gasto_info = None
                        st.rerun()
        if st.button("Fechar"):
            st.session_state.gasto_info = None
            st.rerun()

    st.subheader("📌 Subcontas")
    saldos_normais = [s for s in saldos if s[2] != "Reservas"]
    if saldos_normais:
        for i in range(0, len(saldos_normais), 3):
            cols = st.columns(3)
            for col, (sid, c_nome, s_nome, inicial, atual) in zip(cols, saldos_normais[i:i+3]):
                perc = 0 if (inicial or 0) == 0 else int((atual / max(inicial,1e-9))*100)
                label = f"{c_nome}/{s_nome}\nSaldo: {brl(atual)}\n{perc}%"
                with col:
                    with st.container():
                        st.markdown('<div class="card-btn">', unsafe_allow_html=True)
                        if st.button(label, key=f"card_{sid}", use_container_width=True):
                            st.session_state.gasto_info = (sid, c_nome, s_nome, atual, ano_mes)
                            st.rerun()
                        st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.info("Nenhuma subconta cadastrada.")

    # Ações rápidas
    st.subheader("⚡ Ações rápidas")
    botoes = [
        ("➕", "Nova Receita", "receita"),
        ("📂", "Cadastrar Conta", "conta"),
        ("📑", "Cadastrar Subconta", "subconta"),
        ("🗑️", "Excluir Subconta", "apagar_subconta"),
        ("💵", "Atribuir Valores", "atribuir"),
        ("🔄", "Transferir Saldo", "transferencia"),
        ("💳", "Empréstimos", "emprestimos"),
        ("📊", "Relatório Mensal", "relatorio"),
        ("🚪", "Sair", "sair"),
    ]
    cols = st.columns(4)
    for (icone, texto, destino), col in zip(botoes[:4], cols):
        with col:
            if st.button(f"{icone}\n{texto}", key=f"quick_{destino}"):
                if destino == "sair":
                    limpar_sessao()
                    st.session_state.logged_in = False
                    st.session_state.page = "login"
                    st.rerun()
                else:
                    st.session_state.page = destino
                    st.rerun()
    cols = st.columns(4)
    for (icone, texto, destino), col in zip(botoes[4:], cols):
        with col:
            if st.button(f"{icone}\n{texto}", key=f"quick_{destino}"):
                if destino == "sair":
                    limpar_sessao()
                    st.session_state.logged_in = False
                    st.session_state.page = "login"
                    st.rerun()
                else:
                    st.session_state.page = destino
                    st.rerun()

# =========================================================
# PÁGINAS DE OPERAÇÕES (contas, subcontas, etc.)
# =========================================================
def registrar_receita():
    st.title("➕ Registrar Receita")
    with st.form("receita_form"):
        _, data_str, err = date_br_input("Data da Receita")
        origem = st.text_input("Origem")
        valor = st.number_input("Valor", min_value=0.0, step=0.01)
        descricao = st.text_area("Descrição")
        submitted = st.form_submit_button("Salvar Receita")
        if submitted:
            if not err and valor > 0 and origem.strip():
                add_receita(data_str, origem.strip(), valor, descricao)
                st.success(f"Receita registrada em {data_str}!")
            else:
                st.error("Preencha corretamente.")
    if st.button("Voltar"):
        st.session_state.page = "dashboard"; st.rerun()

def cadastrar_conta():
    st.title("📂 Cadastrar Conta")
    with st.form("conta_form"):
        nome = st.text_input("Nome da Conta")
        submitted = st.form_submit_button("Salvar Conta")
        if submitted:
            if nome.strip():
                add_conta(nome.strip())
                st.success("Conta cadastrada!")
            else:
                st.error("Preencha o nome da conta.")
    if st.button("Voltar"):
        st.session_state.page = "dashboard"; st.rerun()

def cadastrar_subconta():
    st.title("📑 Cadastrar Subconta")
    contas = get_contas()
    if not contas:
        st.warning("Cadastre primeiro uma conta principal.")
        if st.button("Voltar"):
            st.session_state.page = "dashboard"; st.rerun()
        return
    conta_dict = {nome: cid for cid, nome in contas}
    with st.form("subconta_form"):
        conta_nome = st.selectbox("Conta Principal", list(conta_dict.keys()))
        nome = st.text_input("Nome da Subconta")
        submitted = st.form_submit_button("Salvar Subconta")
        if submitted:
            if nome.strip():
                add_subconta(nome.strip(), conta_dict[conta_nome])
                st.success("Subconta cadastrada!")
            else:
                st.error("Preencha o nome da subconta.")
    if st.button("Voltar"):
        st.session_state.page = "dashboard"; st.rerun()

def apagar_subconta():
    st.title("🗑️ Excluir Subconta")
    subcontas = get_subcontas()
    if not subcontas:
        st.info("Nenhuma subconta cadastrada ainda.")
        if st.button("Voltar"):
            st.session_state.page = "dashboard"; st.rerun()
        return
    sub_dict = {f"{c_nome} / {s_nome}": sid for sid, s_nome, c_nome in subcontas if s_nome != "Reservas"}
    if not sub_dict:
        st.info("Nenhuma subconta excluível disponível.")
        if st.button("Voltar"):
            st.session_state.page = "dashboard"; st.rerun()
        return
    escolha = st.selectbox("Escolha a subconta", list(sub_dict.keys()))
    if st.button("Excluir"):
        sid = sub_dict[escolha]
        if pode_excluir_subconta(sid):
            delete_subconta(sid)
            st.success("Subconta excluída!")
        else:
            st.error("Não é possível excluir uma subconta que ainda possui saldo.")
    if st.button("Voltar"):
        st.session_state.page = "dashboard"; st.rerun()
def atribuir_valores():
    st.title("💵 Atribuir Valores")
    hoje = date.today()
    ano_mes = hoje.strftime("%m/%Y")
    subcontas = [s for s in get_subcontas() if s[1] != "Reservas"]
    total_receitas = get_total_receitas_mes(ano_mes)
    st.info(f"Receita total do mês {ano_mes}: {brl(total_receitas)}")
    if not subcontas:
        st.warning("Nenhuma subconta cadastrada ainda.")
        if st.button("Voltar"):
            st.session_state.page = "dashboard"; st.rerun()
        return
    with st.form("atribuir_form"):
        distribuicao = {}
        for sid, sub_nome, conta_nome in subcontas:
            valor = st.number_input(f"{conta_nome} / {sub_nome}", min_value=0.0, step=0.01, key=f"val_{sid}")
            distribuicao[sid] = valor
        submitted = st.form_submit_button("Salvar Atribuições")
        if submitted:
            soma = sum(distribuicao.values())
            if soma > total_receitas:
                st.error("A soma das atribuições é maior que a receita.")
            else:
                for sid, valor in distribuicao.items():
                    if valor > 0:
                        salvar_valor_subconta(ano_mes, sid, valor)
                st.success("Valores atribuídos com sucesso!")
    if st.button("Voltar"):
        st.session_state.page = "dashboard"; st.rerun()

def transferir_saldo():
    st.title("🔄 Transferir Saldo")
    hoje = date.today()
    ano_mes = hoje.strftime("%m/%Y")
    subcontas = get_subcontas()
    if not subcontas or len(subcontas) < 2:
        st.warning("É necessário ter ao menos duas subcontas.")
        if st.button("Voltar"):
            st.session_state.page = "dashboard"; st.rerun()
        return
    sub_dict = {f"{c_nome} / {s_nome}": sid for sid, s_nome, c_nome in subcontas}
    with st.form("transfer_form"):
        origem = st.selectbox("Origem", list(sub_dict.keys()))
        destino = st.selectbox("Destino", list(sub_dict.keys()))
        valor = st.number_input("Valor", min_value=0.0, step=0.01)
        justificativa = st.text_area("Justificativa")
        submitted = st.form_submit_button("Confirmar Transferência")
        if submitted:
            if origem == destino:
                st.error("Origem e destino não podem ser iguais.")
            elif valor <= 0:
                st.error("O valor deve ser positivo.")
            else:
                saldos = get_saldos_mes(ano_mes)
                saldo_origem = [s for s in saldos if s[0] == sub_dict[origem]]
                saldo_origem = saldo_origem[0][4] if saldo_origem else 0
                if valor > saldo_origem:
                    st.error("Saldo insuficiente.")
                elif not justificativa.strip():
                    st.error("Informe uma justificativa.")
                else:
                    registrar_transferencia(
                        hoje.strftime("%d/%m/%Y"),
                        sub_dict[origem],
                        sub_dict[destino],
                        valor,
                        justificativa,
                        ano_mes
                    )
                    st.success("Transferência realizada!")
    if st.button("Voltar"):
        st.session_state.page = "dashboard"; st.rerun()

# =========================================================
# PÁGINA DE EMPRÉSTIMOS
# =========================================================
def emprestimos_page():
    st.title("💳 Empréstimos")

    # Botão de voltar logo abaixo do título
    if st.button("⬅️ Voltar para o Dashboard"):
        st.session_state.page = "dashboard"
        st.rerun()

    if st.session_state.emprestimo_detalhe:
        eid = st.session_state.emprestimo_detalhe
        st.subheader("📌 Detalhes do Empréstimo")
        parcelas = listar_parcelas(eid)

        if st.session_state.confirmar_quitacao:
            pid, novo_valor, valor_orig = st.session_state.confirmar_quitacao
            st.warning(f"Tem certeza que deseja confirmar a quitação antecipada desta parcela? Valor: {brl(novo_valor)} (original {brl(valor_orig)})")
            if st.button("✅ Confirmar quitação antecipada"):
                data_q = date.today().strftime("%d/%m/%Y")
                quitar_parcela(pid, novo_valor, data_q)
                st.success("Parcela quitada antecipadamente!")
                st.session_state.confirmar_quitacao = None
                st.rerun()
            if st.button("❌ Cancelar"):
                st.session_state.confirmar_quitacao = None
                st.rerun()
            return

        # Render tabela de parcelas
        st.markdown("<table class='table-parcelas'><tr><th>Mês/Ano</th><th>Valor Original</th><th>Status</th><th>Ação</th></tr>", unsafe_allow_html=True)

        for pid, mes_ano, valor_orig, valor_quitado, data_q in parcelas:
            if valor_quitado:
                if valor_quitado < valor_orig:
                    row_class = "antecipada"
                    status = f"Quitada antecipada: {brl(valor_quitado)} em {data_q}"
                else:
                    row_class = "quitada"
                    status = f"Quitada: {brl(valor_quitado)} em {data_q}"
                action = "-"
            else:
                row_class = "aberta"
                status = "Em aberto"
                novo_valor = st.number_input(f"Valor quitação {mes_ano}", min_value=0.0, step=0.01, key=f"quit_{pid}")
                if st.button(f"Quitar {mes_ano}", key=f"btn_quit_{pid}"):
                    if novo_valor and novo_valor < valor_orig:
                        st.session_state.confirmar_quitacao = (pid, novo_valor, valor_orig)
                        st.rerun()
                    else:
                        data_q = date.today().strftime("%d/%m/%Y")
                        quitar_parcela(pid, valor_orig, data_q)
                        st.success("Parcela quitada!")
                        st.rerun()
                action = "⬅️ Botão acima"

            st.markdown(f"<tr class='{row_class}'><td>{mes_ano}</td><td>{brl(valor_orig)}</td><td>{status}</td><td>{action}</td></tr>", unsafe_allow_html=True)

        st.markdown("</table>", unsafe_allow_html=True)

        if st.button("Voltar"):
            st.session_state.emprestimo_detalhe = None
            st.rerun()
    else:
        st.subheader("➕ Novo Empréstimo")
        with st.form("emp_form"):
            instituicao = st.text_input("Instituição Bancária")
            contrato = st.text_input("Número do Contrato")
            tipo = st.text_input("Tipo de Empréstimo")
            primeira_parcela = st.text_input("Primeira Parcela (MM/AAAA)")
            qtd = st.number_input("Quantidade de Parcelas", min_value=1, step=1)
            valor = st.number_input("Valor da Parcela", min_value=0.0, step=0.01)
            submitted = st.form_submit_button("Cadastrar")
            if submitted:
                if instituicao and contrato and tipo and primeira_parcela and qtd > 0 and valor > 0:
                    registrar_emprestimo(instituicao, contrato, tipo, primeira_parcela, int(qtd), valor)
                    st.success("Empréstimo registrado!")
                    st.rerun()
                else:
                    st.error("Preencha todos os campos corretamente.")

        st.subheader("📋 Empréstimos Registrados")
        emprestimos = listar_emprestimos()
        if emprestimos:
            for i in range(0, len(emprestimos), 3):
                cols = st.columns(3, gap="large")
                for col, (eid, inst, contrato, tipo, qtd, valor, economia) in zip(cols, emprestimos[i:i+3]):
                    with col:
                        card_html = f"""
                        <div style="
                            background-color: #ffffff;
                            border-radius: 12px;
                            padding: 18px;
                            box-shadow: 0px 2px 6px rgba(0,0,0,0.15);
                            font-family: Arial, sans-serif;
                            color: #333333;
                            line-height: 1.6;
                        ">
                            <p><b>💳 Instituição:</b> {inst}</p>
                            <p><b>📑 Contrato:</b> {contrato}</p>
                            <p><b>🏷️ Tipo:</b> {tipo}</p>
                            <p><b>📅 Parcelas:</b> {qtd}</p>
                            <p><b>💰 Valor da Parcela:</b> {brl(valor)}</p>
                        </div>
                        """
                        if st.button("Selecionar", key=f"emp_{eid}", use_container_width=True):
                            st.session_state.emprestimo_detalhe = eid
                            st.rerun()
                        st.markdown(card_html, unsafe_allow_html=True)
        else:
            st.info("Nenhum empréstimo cadastrado.")
# =========================================================
# RELATÓRIO MENSAL
# =========================================================
def relatorio_mensal():
    st.title("📊 Relatório Mensal")

    # Botão para voltar ao dashboard
    if st.button("⬅️ Voltar para o Dashboard"):
        st.session_state.page = "dashboard"
        st.rerun()

    # Seleção de mês e ano
    meses = {
        "Janeiro": "01",
        "Fevereiro": "02",
        "Março": "03",
        "Abril": "04",
        "Maio": "05",
        "Junho": "06",
        "Julho": "07",
        "Agosto": "08",
        "Setembro": "09",
        "Outubro": "10",
        "Novembro": "11",
        "Dezembro": "12",
    }

    coluna1, coluna2 = st.columns(2)
    with coluna1:
        mes_nome = st.selectbox("Selecione o mês", list(meses.keys()))
        mes = meses[mes_nome]
    with coluna2:
        ano = st.selectbox("Selecione o ano", list(range(2025, datetime.now().year + 2)))

    ano_mes = f"{mes}/{ano}"
    st.markdown(f"📅 Relatório de referência: **{mes_nome}/{ano}**")

    # Botão para gerar relatório
    if st.button("📄 Gerar Relatório em PDF"):
        gerar_pdf_relatorio(ano_mes)

def gerar_pdf_relatorio(ano_mes):
    receitas_total = get_total_receitas_mes(ano_mes)
    saldos = get_saldos_mes(ano_mes)
    total_atribuido = sum(saldo[3] for saldo in saldos) if saldos else 0
    saldo_atual = sum(saldo[4] for saldo in saldos) if saldos else 0

    reservas = [saldo for saldo in saldos if saldo[2] == "Reservas"]
    saldo_reservas = reservas[0][4] if reservas else 0

    emprestimos = listar_emprestimos()

    # Criar PDF em memória
    buffer = io.BytesIO()
    documento = SimpleDocTemplate(buffer, pagesize=A4)
    elementos = []
    estilos = getSampleStyleSheet()
    estilos.add(ParagraphStyle(name="Titulo", fontSize=16, leading=20, spaceAfter=15, alignment=1))
    estilos.add(ParagraphStyle(name="Subtitulo", fontSize=12, leading=14, spaceAfter=10, textColor=colors.HexColor("#4f46e5")))
    estilos.add(ParagraphStyle(name="Texto", fontSize=10, leading=12))

    # Cabeçalho
    elementos.append(Paragraph("📊 Relatório Mensal de Orçamento e Finanças", estilos["Titulo"]))
    elementos.append(Paragraph(f"Mês/Ano: {ano_mes}", estilos["Texto"]))
    elementos.append(Spacer(1, 12))

    # Resumo Executivo
    elementos.append(Paragraph("Resumo Executivo", estilos["Subtitulo"]))
    resumo_dados = [
        [Paragraph("Receitas no mês", estilos["Texto"]), Paragraph(brl(receitas_total), estilos["Texto"])],
        [Paragraph("Total atribuído em subcontas", estilos["Texto"]), Paragraph(brl(total_atribuido), estilos["Texto"])],
        [Paragraph("Saldo atual consolidado", estilos["Texto"]), Paragraph(brl(saldo_atual), estilos["Texto"])],
        [Paragraph("Saldo em Reservas", estilos["Texto"]), Paragraph(brl(saldo_reservas), estilos["Texto"])]
    ]
    tabela_resumo = Table(resumo_dados, colWidths=[250, 150])
    tabela_resumo.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
        ("GRID", (0,0), (-1,-1), 0.5, colors.grey),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
    ]))
    elementos.append(tabela_resumo)
    elementos.append(Spacer(1, 18))

    # Subcontas
    elementos.append(Paragraph("Subcontas – Planejamento vs. Execução", estilos["Subtitulo"]))
    dados_subcontas = [[
        Paragraph("Subconta", estilos["Texto"]),
        Paragraph("Planejado", estilos["Texto"]),
        Paragraph("Gasto", estilos["Texto"]),
        Paragraph("Saldo", estilos["Texto"])
    ]]
    for sid, conta, subconta, valor_inicial, valor_atual in saldos:
        dados_subcontas.append([
            Paragraph(f"{conta}/{subconta}", estilos["Texto"]),
            Paragraph(brl(valor_inicial), estilos["Texto"]),
            Paragraph(brl(valor_inicial - valor_atual), estilos["Texto"]),
            Paragraph(brl(valor_atual), estilos["Texto"])
        ])
    tabela_subcontas = Table(dados_subcontas, colWidths=[200, 100, 100, 100])
    tabela_subcontas.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#dbeafe")),
        ("GRID", (0,0), (-1,-1), 0.5, colors.grey),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
    ]))
    elementos.append(tabela_subcontas)
    elementos.append(Spacer(1, 18))

    # Empréstimos (apenas com parcelas quitadas no mês)
    elementos.append(Paragraph("Empréstimos", estilos["Subtitulo"]))
    emprestimos_filtrados = []
    for eid, instituicao, contrato, tipo, quantidade_parcelas, valor_parcela, economia in emprestimos:
        parcelas = listar_parcelas(eid)
        parcelas_quitadas_no_mes = [
            (pid, mes_ano, valor_orig, valor_quitado, data_q)
            for pid, mes_ano, valor_orig, valor_quitado, data_q in parcelas
            if valor_quitado and data_q and data_q.endswith(ano_mes)  # ex: "15/01/2025".endswith("01/2025")
        ]
        if parcelas_quitadas_no_mes:
            emprestimos_filtrados.append((instituicao, contrato, tipo, quantidade_parcelas, valor_parcela))

    if emprestimos_filtrados:
        dados_emprestimos = [[
            Paragraph("Instituição", estilos["Texto"]),
            Paragraph("Contrato", estilos["Texto"]),
            Paragraph("Tipo", estilos["Texto"]),
            Paragraph("Parcelas", estilos["Texto"]),
            Paragraph("Valor Parcela", estilos["Texto"])
        ]]
        for instituicao, contrato, tipo, quantidade_parcelas, valor_parcela in emprestimos_filtrados:
            dados_emprestimos.append([
                Paragraph(instituicao, estilos["Texto"]),
                Paragraph(contrato, estilos["Texto"]),
                Paragraph(tipo, estilos["Texto"]),
                Paragraph(str(quantidade_parcelas), estilos["Texto"]),
                Paragraph(brl(valor_parcela), estilos["Texto"])
            ])
        tabela_emprestimos = Table(dados_emprestimos, colWidths=[100, 150, 100, 80, 100])
        tabela_emprestimos.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#fef3c7")),
            ("GRID", (0,0), (-1,-1), 0.5, colors.grey),
            ("VALIGN", (0,0), (-1,-1), "TOP"),
        ]))
        elementos.append(tabela_emprestimos)
    else:
        elementos.append(Paragraph("Nenhum empréstimo com parcelas quitadas neste mês.", estilos["Texto"]))

    # Gerar PDF
    documento.build(elementos)
    pdf = buffer.getvalue()
    buffer.close()

    # Botão de download
    st.download_button(
        label="📥 Baixar Relatório Mensal em PDF",
        data=pdf,
        file_name=f"relatorio_{ano_mes.replace('/', '-')}.pdf",
        mime="application/pdf"
    )

# =========================================================
# ROUTER / LOGIN
# =========================================================
if not st.session_state.logged_in or st.session_state.page == "login":
    st.title("💰 Sistema de Controle Financeiro")
    with st.form("login_form"):
        user = st.text_input("Usuário")
        pwd = st.text_input("Senha", type="password")
        if st.form_submit_button("Entrar"):
            if user == USERNAME and pwd == PASSWORD and user and pwd:
                token = str(uuid.uuid4())
                salvar_sessao(token)
                st.session_state.logged_in = True
                st.session_state.page = "dashboard"
                st.rerun()
            else:
                st.error("Usuário ou senha inválidos.")
else:
    if st.session_state.page == "dashboard":
        dashboard()
    elif st.session_state.page == "receita":
        registrar_receita()
    elif st.session_state.page == "conta":
        cadastrar_conta()
    elif st.session_state.page == "subconta":
        cadastrar_subconta()
    elif st.session_state.page == "apagar_subconta":
        apagar_subconta()
    elif st.session_state.page == "atribuir":
        atribuir_valores()
    elif st.session_state.page == "transferencia":
        transferir_saldo()
    elif st.session_state.page == "emprestimos":
        emprestimos_page()
    elif st.session_state.page == "relatorio":
        relatorio_mensal()
