import streamlit as st
import uuid
from datetime import date, datetime
from db import (
    init_db, add_receita, get_total_receitas_mes,
    salvar_sessao, carregar_sessao, limpar_sessao,
    add_conta, get_contas,
    add_subconta, get_subcontas, delete_subconta,
    salvar_valor_subconta, get_saldos_mes, registrar_gasto,
    registrar_transferencia
)

# -------------------- INIT --------------------
init_db()

USERNAME = "admin"
PASSWORD = "1234"

if "logged_in" not in st.session_state:
    token = carregar_sessao()
    st.session_state.logged_in = token is not None
if "page" not in st.session_state:
    st.session_state.page = "dashboard"

# -------------------- HELPERS --------------------
def brl(v: float) -> str:
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def date_br_input(label: str, key: str | None = None, default: date | None = None):
    if default is None:
        default = date.today()
    default_str = default.strftime("%d/%m/%Y")
    val_str = st.text_input(label, value=default_str, key=key, help="Formato: DD/MM/AAAA")
    try:
        d = datetime.strptime(val_str.strip(), "%d/%m/%Y").date()
        return d, d.strftime("%d/%m/%Y"), False
    except Exception:
        st.warning("Use o formato DD/MM/AAAA")
        return None, val_str, True

# -------------------- CSS (somente para os CARDS) --------------------
st.markdown("""
<style>
div.stButton > button[data-baseweb="button"][id*="card_"] {
    border:1px solid #ddd;
    border-radius:12px;
    padding:16px;
    background:linear-gradient(180deg, #f9fafb, #f1f5f9);
    box-shadow:0 2px 6px rgba(0,0,0,0.08);
    transition:all 0.2s ease-in-out;
    text-align:center;
    white-space:pre-line;
    font-size:14px;
}
div.stButton > button[data-baseweb="button"][id*="card_"]:hover {
    background:#eef2ff;
    border-color:#c7d2fe;
}
</style>
""", unsafe_allow_html=True)

# -------------------- PÁGINAS --------------------
def login_screen():
    st.title("💰 Sistema de Controle Financeiro")
    with st.form("login_form"):
        username = st.text_input("Usuário")
        password = st.text_input("Senha", type="password")
        submitted = st.form_submit_button("Entrar")
        if submitted:
            if username == USERNAME and password == PASSWORD:
                token = str(uuid.uuid4())
                salvar_sessao(token)
                st.session_state.logged_in = True
                st.session_state.page = "dashboard"
                st.rerun()
            else:
                st.error("Usuário ou senha inválidos.")

def dashboard():
    st.markdown("<h1 style='text-align:center;'>📊 Dashboard Financeiro</h1>", unsafe_allow_html=True)

    hoje = date.today()
    ano_mes = hoje.strftime("%m/%Y")
    total_receitas = get_total_receitas_mes(ano_mes)
    saldos = get_saldos_mes(ano_mes)

    total_atribuido = sum(s[3] for s in saldos) if saldos else 0
    saldo_atual_geral = sum(s[4] for s in saldos) if saldos else 0

    c1, c2, c3 = st.columns(3)
    with c1: st.metric("💰 Saldo Atual", brl(saldo_atual_geral))
    with c2: st.metric("📈 Receitas no mês", brl(total_receitas))
    with c3: st.metric("📉 Valor distribuído", brl(total_atribuido))

    st.markdown("---")
    st.subheader("📌 Subcontas")

    if saldos:
        for i in range(0, len(saldos), 5):
            cols = st.columns(5)
            for col, (sid, conta_nome, sub_nome, inicial, atual) in zip(cols, saldos[i:i+5]):
                perc = 0 if inicial == 0 else max(0, min(1, (atual / inicial) if inicial else 0))
                percent_txt = f"{int(perc*100)}%"
                label = f"**{conta_nome} / {sub_nome}**\n\nSaldo: {brl(atual)}\n\n{percent_txt}"

                with col:
                    if st.button(label, key=f"card_{sid}", use_container_width=True):
                        st.session_state.page = "gasto"
                        st.session_state.modal_info = (sid, conta_nome, sub_nome, atual, ano_mes)
                        st.rerun()
    else:
        st.info("Nenhum valor atribuído ainda.")

    st.markdown("---")
    st.subheader("⚡ Ações rápidas")
    a1, a2, a3, a4, a5, a6 = st.columns(6)
    with a1:
        if st.button("➕ Receita"): st.session_state.page = "receita"; st.rerun()
    with a2:
        if st.button("📂 Conta"): st.session_state.page = "conta"; st.rerun()
    with a3:
        if st.button("📑 Subconta"): st.session_state.page = "subconta"; st.rerun()
    with a4:
        if st.button("🗑️ Apagar Subconta"): st.session_state.page = "apagar_subconta"; st.rerun()
    with a5:
        if st.button("💵 Atribuir Valores"): st.session_state.page = "atribuir"; st.rerun()
    with a6:
        if st.button("🔄 Transferência"): st.session_state.page = "transferencia"; st.rerun()

    if st.button("🚪 Sair"):
        limpar_sessao(); st.session_state.logged_in = False; st.session_state.page = "dashboard"; st.rerun()

def registrar_receita():
    st.title("➕ Registrar Receita")
    with st.form("receita_form"):
        data_obj, data_str, err = date_br_input("Data da Receita")
        origem = st.text_input("Origem")
        valor = st.number_input("Valor (R$)", min_value=0.0, step=0.01)
        descricao = st.text_area("Descrição")
        submitted = st.form_submit_button("💾 Salvar Receita")
        if submitted:
            if not err and valor > 0 and origem.strip():
                add_receita(data_str, origem.strip(), valor, descricao)
                st.success(f"Receita registrada em {data_str}!")
            else:
                st.error("Preencha corretamente.")
    if st.button("⬅️ Voltar", key="voltar_receita"):
        st.session_state.page = "dashboard"; st.rerun()

def cadastrar_conta():
    st.title("📂 Cadastrar Conta")
    with st.form("conta_form"):
        nome = st.text_input("Nome da Conta")
        submitted = st.form_submit_button("💾 Salvar Conta")
        if submitted:
            if nome.strip():
                add_conta(nome.strip()); st.success("Conta cadastrada!")
            else:
                st.error("Preencha o nome da conta.")
    if st.button("⬅️ Voltar", key="voltar_conta"):
        st.session_state.page = "dashboard"; st.rerun()

def cadastrar_subconta():
    st.title("📑 Cadastrar Subconta")
    contas = get_contas()
    if not contas:
        st.warning("Cadastre primeiro uma conta principal.")
        if st.button("⬅️ Voltar", key="voltar_subconta_semconta"):
            st.session_state.page = "dashboard"; st.rerun()
        return
    conta_dict = {nome: cid for cid, nome in contas}
    with st.form("subconta_form"):
        conta_nome = st.selectbox("Conta Principal", list(conta_dict.keys()))
        nome = st.text_input("Nome da Subconta")
        submitted = st.form_submit_button("💾 Salvar Subconta")
        if submitted:
            if nome.strip():
                add_subconta(nome.strip(), conta_dict[conta_nome]); st.success("Subconta cadastrada!")
            else:
                st.error("Preencha o nome da subconta.")
    if st.button("⬅️ Voltar", key="voltar_subconta"):
        st.session_state.page = "dashboard"; st.rerun()

def apagar_subconta():
    st.title("🗑️ Apagar Subconta")
    subcontas = get_subcontas()
    if not subcontas:
        st.info("Nenhuma subconta cadastrada ainda.")
        if st.button("⬅️ Voltar", key="voltar_apagar_vazio"):
            st.session_state.page = "dashboard"; st.rerun()
        return
    sub_dict = {f"{c_nome} / {s_nome}": sid for sid, s_nome, c_nome in subcontas}
    escolha = st.selectbox("Escolha a subconta", list(sub_dict.keys()))
    if st.button("Apagar Subconta", key="apagar_subconta_btn"):
        delete_subconta(sub_dict[escolha]); st.success("Subconta apagada!")
    if st.button("⬅️ Voltar", key="voltar_apagar"):
        st.session_state.page = "dashboard"; st.rerun()

def atribuir_valores():
    st.title("💵 Atribuir Valores")
    hoje = date.today(); ano_mes = hoje.strftime("%m/%Y")
    subcontas = get_subcontas(); total_receitas = get_total_receitas_mes(ano_mes)
    st.info(f"Receita total do mês {ano_mes}: {brl(total_receitas)}")
    if not subcontas:
        st.warning("Nenhuma subconta cadastrada ainda.")
        if st.button("⬅️ Voltar", key="voltar_atribuir_vazio"):
            st.session_state.page = "dashboard"; st.rerun()
        return
    with st.form("atribuir_form"):
        distribuicao = {}
        for sid, sub_nome, conta_nome in subcontas:
            valor = st.number_input(f"{conta_nome} / {sub_nome}", min_value=0.0, step=0.01, key=f"val_{sid}")
            distribuicao[sid] = valor
        submitted = st.form_submit_button("💾 Salvar Atribuições")
        if submitted:
            soma = sum(distribuicao.values())
            if soma > total_receitas:
                st.error("❌ Soma das atribuições maior que a receita.")
            else:
                for sid, valor in distribuicao.items():
                    if valor > 0:
                        salvar_valor_subconta(ano_mes, sid, valor)
                st.success("Valores atribuídos com sucesso!")
    if st.button("⬅️ Voltar", key="voltar_atribuir"):
        st.session_state.page = "dashboard"; st.rerun()

def transferir_saldo():
    st.title("🔄 Transferência entre Subcontas")
    hoje = date.today()
    ano_mes = hoje.strftime("%m/%Y")
    subcontas = get_subcontas()

    if not subcontas or len(subcontas) < 2:
        st.warning("É necessário ter pelo menos duas subcontas para transferir saldo.")
        if st.button("⬅️ Voltar", key="voltar_transferencia_sem"):
            st.session_state.page = "dashboard"; st.rerun()
        return

    sub_dict = {f"{c_nome} / {s_nome}": sid for sid, s_nome, c_nome in subcontas}

    with st.form("transfer_form"):
        origem_nome = st.selectbox("Subconta de Origem", list(sub_dict.keys()), key="origem")
        destino_nome = st.selectbox("Subconta de Destino", list(sub_dict.keys()), key="destino")
        valor = st.number_input("Valor a transferir (R$)", min_value=0.0, step=0.01, key="valor_transfer")
        justificativa = st.text_area("Justificativa", key="just_transfer")
        submitted = st.form_submit_button("💾 Confirmar Transferência")

        if submitted:
            if origem_nome == destino_nome:
                st.error("A subconta de origem e destino devem ser diferentes.")
            elif valor <= 0:
                st.error("O valor deve ser maior que zero.")
            else:
                # Pegar saldo atual da origem
                saldos = get_saldos_mes(ano_mes)
                saldo_origem = [s for s in saldos if s[0] == sub_dict[origem_nome]]
                saldo_origem = saldo_origem[0][4] if saldo_origem else 0

                if valor > saldo_origem:
                    st.error("Saldo insuficiente na subconta de origem.")
                elif not justificativa.strip():
                    st.error("É necessário informar uma justificativa.")
                else:
                    registrar_transferencia(
                        hoje.strftime("%d/%m/%Y"),
                        sub_dict[origem_nome],
                        sub_dict[destino_nome],
                        valor,
                        justificativa,
                        ano_mes
                    )
                    st.success("Transferência registrada com sucesso!")

    if st.button("⬅️ Voltar", key="voltar_transferencia"):
        st.session_state.page = "dashboard"; st.rerun()

# -------------------- ROUTER --------------------
if not st.session_state.logged_in:
    login_screen()
else:
    if st.session_state.page == "dashboard": dashboard()
    elif st.session_state.page == "receita": registrar_receita()
    elif st.session_state.page == "conta": cadastrar_conta()
    elif st.session_state.page == "subconta": cadastrar_subconta()
    elif st.session_state.page == "apagar_subconta": apagar_subconta()
    elif st.session_state.page == "atribuir": atribuir_valores()
    elif st.session_state.page == "transferencia": transferir_saldo()
