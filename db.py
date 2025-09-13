import sqlite3
from datetime import datetime

DB_NAME = "finance.db"

# -------------------- INIT --------------------
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    # Sessão (corrigido para incluir criado_em)
    c.execute("""
    CREATE TABLE IF NOT EXISTS sessao (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        token TEXT,
        criado_em TEXT
    )
    """)

    # Receitas
    c.execute("""
    CREATE TABLE IF NOT EXISTS receitas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        data TEXT,
        origem TEXT,
        valor REAL,
        descricao TEXT,
        ano_mes TEXT
    )
    """)

    # Contas principais
    c.execute("""
    CREATE TABLE IF NOT EXISTS contas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT UNIQUE
    )
    """)

    # Subcontas
    c.execute("""
    CREATE TABLE IF NOT EXISTS subcontas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT,
        conta_id INTEGER,
        FOREIGN KEY (conta_id) REFERENCES contas(id)
    )
    """)

    # Atribuições mensais
    c.execute("""
    CREATE TABLE IF NOT EXISTS subconta_atribuicoes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        subconta_id INTEGER,
        ano_mes TEXT,
        saldo_inicial REAL,
        saldo_atual REAL,
        FOREIGN KEY (subconta_id) REFERENCES subcontas(id)
    )
    """)

    # Gastos
    c.execute("""
    CREATE TABLE IF NOT EXISTS gastos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        data TEXT,
        valor REAL,
        descricao TEXT,
        subconta_id INTEGER,
        ano_mes TEXT,
        FOREIGN KEY (subconta_id) REFERENCES subcontas(id)
    )
    """)

    # Transferências
    c.execute("""
    CREATE TABLE IF NOT EXISTS transferencias (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        data TEXT,
        subconta_origem INTEGER,
        subconta_destino INTEGER,
        valor REAL,
        justificativa TEXT,
        mes_ano TEXT
    )
    """)

    # Empréstimos
    c.execute("""
    CREATE TABLE IF NOT EXISTS emprestimos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        instituicao TEXT,
        contrato TEXT,
        tipo TEXT,
        primeira_parcela TEXT,
        qtd_parcelas INTEGER,
        valor_parcela REAL
    )
    """)

    # Parcelas de empréstimos
    c.execute("""
    CREATE TABLE IF NOT EXISTS parcelas_emprestimo (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        emprestimo_id INTEGER,
        mes_ano TEXT,
        valor_original REAL,
        valor_quitado REAL,
        data_quitacao TEXT,
        FOREIGN KEY (emprestimo_id) REFERENCES emprestimos(id)
    )
    """)

    conn.commit()
    conn.close()

# -------------------- SESSÕES --------------------
def salvar_sessao(token):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("DELETE FROM sessao")
    cur.execute("INSERT INTO sessao (token, criado_em) VALUES (?, ?)", 
                (token, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def carregar_sessao():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT token, criado_em FROM sessao LIMIT 1")
    row = cur.fetchone()
    conn.close()
    if row:
        token, criado_em = row
        dt = datetime.fromisoformat(criado_em)
        if (datetime.now() - dt).total_seconds() <= 3600:  # 1h
            return token
    return None

def limpar_sessao():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("DELETE FROM sessao")
    conn.commit()
    conn.close()

# -------------------- RECEITAS --------------------
def add_receita(data, origem, valor, descricao):
    d = datetime.strptime(data, "%d/%m/%Y")
    ano_mes = d.strftime("%m/%Y")
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("INSERT INTO receitas (data, origem, valor, descricao, ano_mes) VALUES (?,?,?,?,?)",
                (data, origem, valor, descricao, ano_mes))
    conn.commit()
    conn.close()

    verificar_quitacoes_automaticas(ano_mes, data)

def get_total_receitas_mes(ano_mes):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT SUM(valor) FROM receitas WHERE ano_mes=?", (ano_mes,))
    total = cur.fetchone()[0]
    conn.close()
    return total if total else 0

# -------------------- CONTAS --------------------
def add_conta(nome):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO contas (nome) VALUES (?)", (nome,))
    conn.commit()
    conn.close()

def get_contas():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT id, nome FROM contas ORDER BY nome")
    rows = cur.fetchall()
    conn.close()
    return rows

# -------------------- SUBCONTAS --------------------
def add_subconta(nome, conta_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("INSERT INTO subcontas (nome, conta_id) VALUES (?, ?)", (nome, conta_id))
    conn.commit()
    conn.close()

def get_subcontas():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
    SELECT s.id, s.nome, c.nome
    FROM subcontas s
    JOIN contas c ON s.conta_id = c.id
    ORDER BY c.nome, s.nome
    """)
    rows = cur.fetchall()
    conn.close()
    return rows

def pode_excluir_subconta(subconta_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT SUM(saldo_atual)
        FROM subconta_atribuicoes
        WHERE subconta_id=?
    """, (subconta_id,))
    total = cur.fetchone()[0]
    conn.close()
    return (total or 0) == 0

def delete_subconta(subconta_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("DELETE FROM subcontas WHERE id=?", (subconta_id,))
    cur.execute("DELETE FROM subconta_atribuicoes WHERE subconta_id=?", (subconta_id,))
    cur.execute("DELETE FROM gastos WHERE subconta_id=?", (subconta_id,))
    conn.commit()
    conn.close()

# -------------------- ATRIBUIÇÕES --------------------
def salvar_valor_subconta(ano_mes, subconta_id, valor):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
    SELECT id, saldo_inicial, saldo_atual
    FROM subconta_atribuicoes
    WHERE subconta_id=? AND ano_mes=?
    """, (subconta_id, ano_mes))
    row = cur.fetchone()
    if row:
        id_, saldo_inicial, saldo_atual = row
        saldo_atual += valor
        cur.execute("UPDATE subconta_atribuicoes SET saldo_atual=? WHERE id=?",
                    (saldo_atual, id_))
    else:
        cur.execute("INSERT INTO subconta_atribuicoes (subconta_id, ano_mes, saldo_inicial, saldo_atual) VALUES (?,?,?,?)",
                    (subconta_id, ano_mes, valor, valor))
    conn.commit()
    conn.close()

def get_saldos_mes(ano_mes):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
    SELECT s.id, c.nome, s.nome, sa.saldo_inicial, sa.saldo_atual
    FROM subcontas s
    JOIN contas c ON s.conta_id = c.id
    LEFT JOIN subconta_atribuicoes sa ON sa.subconta_id = s.id AND sa.ano_mes=?
    ORDER BY c.nome, s.nome
    """, (ano_mes,))
    rows = cur.fetchall()
    conn.close()
    result = []
    for sid, c_nome, s_nome, inicial, atual in rows:
        inicial = inicial if inicial else 0
        atual = atual if atual else 0
        result.append((sid, c_nome, s_nome, inicial, atual))
    return result

# -------------------- GASTOS --------------------
def registrar_gasto(data, valor, descricao, subconta_id, ano_mes):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("INSERT INTO gastos (data, valor, descricao, subconta_id, ano_mes) VALUES (?,?,?,?,?)",
                (data, valor, descricao, subconta_id, ano_mes))
    cur.execute("""
    UPDATE subconta_atribuicoes
    SET saldo_atual = saldo_atual - ?
    WHERE subconta_id=? AND ano_mes=?
    """, (valor, subconta_id, ano_mes))
    conn.commit()
    conn.close()

# -------------------- TRANSFERÊNCIAS --------------------
def registrar_transferencia(data, origem, destino, valor, justificativa, mes_ano):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute("UPDATE subconta_atribuicoes SET saldo_atual = saldo_atual - ? WHERE subconta_id=? AND ano_mes=?", (valor, origem, mes_ano))
    c.execute("UPDATE subconta_atribuicoes SET saldo_atual = saldo_atual + ? WHERE subconta_id=? AND ano_mes=?", (valor, destino, mes_ano))

    c.execute("""
    INSERT INTO transferencias (data, subconta_origem, subconta_destino, valor, justificativa, mes_ano)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (data, origem, destino, valor, justificativa, mes_ano))

    conn.commit()
    conn.close()

# -------------------- EMPRÉSTIMOS --------------------
def registrar_emprestimo(instituicao, contrato, tipo, primeira_parcela, qtd_parcelas, valor_parcela):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO emprestimos (instituicao, contrato, tipo, primeira_parcela, qtd_parcelas, valor_parcela)
        VALUES (?,?,?,?,?,?)
    """, (instituicao, contrato, tipo, primeira_parcela, qtd_parcelas, valor_parcela))
    emprestimo_id = cur.lastrowid

    mes, ano = map(int, primeira_parcela.split("/"))
    for i in range(qtd_parcelas):
        mes_atual = (mes + i - 1) % 12 + 1
        ano_atual = ano + (mes + i - 1) // 12
        mes_ano = f"{mes_atual:02d}/{ano_atual}"
        cur.execute("""
            INSERT INTO parcelas_emprestimo (emprestimo_id, mes_ano, valor_original, valor_quitado, data_quitacao)
            VALUES (?,?,?,?,?)
        """, (emprestimo_id, mes_ano, valor_parcela, None, None))

    conn.commit()
    conn.close()

def listar_emprestimos():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT id, instituicao, contrato, tipo, qtd_parcelas, valor_parcela FROM emprestimos")
    rows = cur.fetchall()
    conn.close()

    result = []
    for (eid, inst, contrato, tipo, qtd, valor) in rows:
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("SELECT SUM(valor_original - IFNULL(valor_quitado, valor_original)) FROM parcelas_emprestimo WHERE emprestimo_id=? AND valor_quitado IS NOT NULL", (eid,))
        economia = cur.fetchone()[0]
        conn.close()
        economia = economia if economia else 0
        result.append((eid, inst, contrato, tipo, qtd, valor, economia))
    return result

def listar_parcelas(emprestimo_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT id, mes_ano, valor_original, valor_quitado, data_quitacao FROM parcelas_emprestimo WHERE emprestimo_id=? ORDER BY id", (emprestimo_id,))
    rows = cur.fetchall()
    conn.close()
    return rows

def quitar_parcela(parcela_id, valor_quitado, data_quitacao):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        UPDATE parcelas_emprestimo
        SET valor_quitado=?, data_quitacao=?
        WHERE id=?
    """, (valor_quitado, data_quitacao, parcela_id))
    conn.commit()
    conn.close()

def verificar_quitacoes_automaticas(ano_mes, data_receita):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT id, emprestimo_id, valor_original
        FROM parcelas_emprestimo
        WHERE mes_ano=? AND valor_quitado IS NULL
        ORDER BY id
    """, (ano_mes,))
    parcelas = cur.fetchall()

    for pid, eid, valor in parcelas:
        cur.execute("""
            UPDATE parcelas_emprestimo
            SET valor_quitado=?, data_quitacao=?
            WHERE id=?
        """, (valor, data_receita, pid))

        cur.execute("SELECT instituicao, contrato FROM emprestimos WHERE id=?", (eid,))
        inst, contrato = cur.fetchone()
        descricao = f"Parcela empréstimo {inst} contrato {contrato}"
        cur.execute("INSERT INTO gastos (data, valor, descricao, subconta_id, ano_mes) VALUES (?,?,?,?,?)",
                    (data_receita, valor, descricao, None, ano_mes))

    conn.commit()
    conn.close()

# -------------------- NOVO: EXCLUIR EMPRÉSTIMO --------------------
def excluir_emprestimo(emprestimo_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("DELETE FROM parcelas_emprestimo WHERE emprestimo_id=?", (emprestimo_id,))
    cur.execute("DELETE FROM emprestimos WHERE id=?", (emprestimo_id,))
    conn.commit()
    conn.close()
