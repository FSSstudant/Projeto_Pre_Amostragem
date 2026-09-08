import sqlite3
import pandas as pd
import io
import math
import re
from fpdf import FPDF

def sanitizar_texto(texto):
    """Converte e limpa caracteres Unicode incompatíveis com a codificação Latin-1 padrão do FPDF."""
    if texto is None:
        return ""
    if not isinstance(texto, str):
        texto = str(texto)
        
    substituicoes = {
        'Ω': 'Ohm',
        '≤': '<=',
        '≥': '>=',
        '–': '-',
        '—': '-',
        '“': '"',
        '”': '"',
        '‘': "'",
        '’': "'",
        '•': '*',
        '…': '...',
        'µ': 'u',
    }
    for orig, sub in substituicoes.items():
        texto = texto.replace(orig, sub)
        
    return texto.encode('latin-1', 'replace').decode('latin-1')


def criar_tabelas():
    """Cria a estrutura de tabelas no banco de dados SQLite, caso não existam."""
    conexao = sqlite3.connect("pre_amostragem.db")
    cursor = conexao.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS clientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            razao_social TEXT NOT NULL,
            cnpj TEXT UNIQUE NOT NULL,
            endereco TEXT NOT NULL,
            contato TEXT NOT NULL
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ordens_servico (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_cliente INTEGER NOT NULL,
            data_solicitacao TEXT NOT NULL,
            legislacao_aplicavel TEXT NOT NULL,
            laboratorio_destino TEXT NOT NULL,
            FOREIGN KEY (id_cliente) REFERENCES clientes (id)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pontos_amostra (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_os INTEGER NOT NULL,
            codigo_amostra TEXT NOT NULL,
            identificacao_ponto TEXT NOT NULL,
            matriz TEXT NOT NULL,
            parametros TEXT NOT NULL,
            FOREIGN KEY (id_os) REFERENCES ordens_servico (id)
        )
    """)
    cursor.execute("PRAGMA table_info(ordens_servico)")
    colunas_os = [col[1] for col in cursor.fetchall()]

    if 'status' not in colunas_os:
        cursor.execute("ALTER TABLE ordens_servico ADD COLUMN status TEXT DEFAULT 'Em Planejamento'")
    
    conexao.commit()
    conexao.close()


def cadastrar_cliente(razao_social, cnpj, endereco, contato):
    try:
        conexao = sqlite3.connect("pre_amostragem.db")
        cursor = conexao.cursor()
        cursor.execute("""
            INSERT INTO clientes (razao_social, cnpj, endereco, contato)
            VALUES (?, ?, ?, ?)
        """, (razao_social, cnpj, endereco, contato))
        conexao.commit()
        conexao.close()
        return True
    except sqlite3.IntegrityError:
        return False


def listar_clientes():
    conexao = sqlite3.connect("pre_amostragem.db")
    cursor = conexao.cursor()
    cursor.execute("SELECT id, razao_social, cnpj, endereco, contato FROM clientes")
    clientes = cursor.fetchall()
    conexao.close()
    return clientes


def criar_ordem_servico(id_cliente, data_solicitacao, legislacao_aplicavel, laboratorio_destino):
    conexao = sqlite3.connect("pre_amostragem.db")
    cursor = conexao.cursor()
    cursor.execute("""
        INSERT INTO ordens_servico (id_cliente, data_solicitacao, legislacao_aplicavel, laboratorio_destino)
        VALUES (?, ?, ?, ?)
    """, (id_cliente, data_solicitacao, legislacao_aplicavel, laboratorio_destino))
    id_os = cursor.lastrowid
    conexao.commit()
    conexao.close()
    return id_os


def listar_ordens_servico():
    conexao = sqlite3.connect("pre_amostragem.db")
    cursor = conexao.cursor()
    cursor.execute("""
        SELECT os.id, c.razao_social, os.data_solicitacao, os.status
        FROM ordens_servico os
        JOIN clientes c ON os.id_cliente = c.id
        ORDER BY os.id DESC
    """)
    ordens = cursor.fetchall()
    conexao.close()
    return ordens


def atualizar_status_os(id_os, novo_status):
    """Atualiza o status de uma Ordem de Serviço específica."""
    conexao = sqlite3.connect("pre_amostragem.db")
    cursor = conexao.cursor()
    cursor.execute("""
        UPDATE ordens_servico 
        SET status = ? 
        WHERE id = ?
    """, (novo_status, id_os))
    conexao.commit()
    conexao.close()


def cadastrar_pontos_lote(id_os, quantidade_pontos, matriz, parametros):
    """Cadastra múltiplos pontos de amostragem de uma única vez para uma OS."""
    conexao = sqlite3.connect("pre_amostragem.db")
    cursor = conexao.cursor()
    
    cursor.execute("SELECT codigo_amostra FROM pontos_amostra WHERE id_os = ?", (id_os,))
    codigos_existentes = cursor.fetchall()
    
    maior_sequencial = 0
    prefixo_busca = f"AM-OS{id_os}-P"
    
    for (cod,) in codigos_existentes:
        if cod.startswith(prefixo_busca):
            try:
                num = int(cod.replace(prefixo_busca, ""))
                if num > maior_sequencial:
                    maior_sequencial = num
            except ValueError:
                continue
                
    for i in range(1, quantidade_pontos + 1):
        num_ponto = maior_sequencial + i
        codigo_amostra = f"AM-OS{id_os}-P{num_ponto}"
        identificacao_ponto = f"Ponto P-{num_ponto:02d}"
        
        cursor.execute("""
            INSERT INTO pontos_amostra (id_os, codigo_amostra, identificacao_ponto, matriz, parametros)
            VALUES (?, ?, ?, ?, ?)
        """, (id_os, codigo_amostra, identificacao_ponto, matriz, parametros))
        
    conexao.commit()
    conexao.close()


def listar_pontos_por_os(id_os):
    conexao = sqlite3.connect("pre_amostragem.db")
    cursor = conexao.cursor()
    cursor.execute("""
        SELECT id, codigo_amostra, identificacao_ponto, matriz, parametros
        FROM pontos_amostra
        WHERE id_os = ?
        ORDER BY id ASC
    """, (id_os,))
    pontos = cursor.fetchall()
    conexao.close()
    return pontos


def deletar_ponto_amostra(id_ponto):
    conexao = sqlite3.connect("pre_amostragem.db")
    cursor = conexao.cursor()
    cursor.execute("DELETE FROM pontos_amostra WHERE id = ?", (id_ponto,))
    conexao.commit()
    conexao.close()


def atualizar_ponto_amostra(id_ponto, identificacao_ponto, matriz, parametros):
    """Atualiza as informações de um ponto de amostragem no banco de dados."""
    conexao = sqlite3.connect("pre_amostragem.db")
    cursor = conexao.cursor()
    cursor.execute("""
        UPDATE pontos_amostra 
        SET identificacao_ponto = ?, matriz = ?, parametros = ?
        WHERE id = ?
    """, (identificacao_ponto, matriz, parametros, id_ponto))
    conexao.commit()
    conexao.close()


# --- MÓDULO DE EMISSÃO DE PDF (FORMULÁRIOS FM 034 AM E FM 037 AM) ---

class PDF_FM034_AM(FPDF):
    """Classe geradora da Ficha de Cadeia de Custódia - FM 034 AM"""
    def __init__(self, num_cc=""):
        super().__init__(orientation='P', unit='mm', format='A4')
        self.num_cc = sanitizar_texto(num_cc)

    def header(self):
        self.set_font("Arial", "B", 8)
        
        # Coluna 1: Título
        self.set_xy(10, 10)
        self.cell(110, 12, "", border=1)
        self.set_xy(12, 11)
        self.cell(106, 4, sanitizar_texto("CADEIA DE CUSTÓDIA"), border=0, align="C", ln=1)
        self.set_font("Arial", "", 6.5)
        self.cell(106, 3, sanitizar_texto("(ÁGUA BRUTA, TRATADA E RESIDUÁRIA E EFLUENTE LÍQUIDO)"), border=0, align="C", ln=1)
        
        # Coluna 2: Controle de Documento
        self.set_xy(120, 10)
        self.cell(45, 12, "", border=1)
        self.set_xy(121, 11)
        self.cell(43, 3.5, "FM 034 AM", border=0, align="C", ln=1)
        self.cell(43, 3, sanitizar_texto("Elaborado por: SG|AM"), border=0, align="C", ln=1)
        self.cell(43, 3, sanitizar_texto("Aprovado por: GT"), border=0, align="C", ln=1)
        
        # Coluna 3: Revisão e Número da CC
        self.set_xy(165, 10)
        self.cell(35, 12, "", border=1)
        self.set_xy(166, 11)
        self.cell(33, 3.5, "Data: 01/07/2025", border=0, align="C", ln=1)
        self.cell(33, 3, sanitizar_texto("Revisão: 01"), border=0, align="C", ln=1)
        self.set_font("Arial", "B", 7)
        self.cell(33, 3.5, sanitizar_texto(f"Cadeia N°: {self.num_cc}"), border=0, align="C", ln=1)
        
        self.ln(3)

    def footer(self):
        self.set_y(-15)
        self.set_font("Arial", "", 5.5)
        legenda = sanitizar_texto("Legenda: ACH-Água para Consumo; ASP-Água Superficial; ASB-Água Subterrânea; EFL-Efluente Líquido; PC-Proposta Comercial; OS-Ordem de Serviço.")
        self.cell(150, 4, legenda, border=0, align="L")
        self.set_font("Arial", "I", 7)
        self.cell(40, 4, sanitizar_texto(f"Página {self.page_no()}/{{nb}}"), border=0, align="R")


def gerar_pdf_cadeia_custodia(id_os):
    """Gera a Ficha de Cadeia de Custódia conforme o modelo oficial FM 034 AM."""
    conexao = sqlite3.connect("pre_amostragem.db")
    cursor = conexao.cursor()
    
    cursor.execute("""
        SELECT os.id, c.razao_social, c.cnpj, c.endereco, c.contato, 
               os.data_solicitacao, os.legislacao_aplicavel, os.laboratorio_destino, c.id
        FROM ordens_servico os
        JOIN clientes c ON os.id_cliente = c.id
        WHERE os.id = ?
    """, (id_os,))
    dados_os = cursor.fetchone()
    
    cursor.execute("""
        SELECT codigo_amostra, identificacao_ponto, matriz, parametros
        FROM pontos_amostra
        WHERE id_os = ?
        ORDER BY id ASC
    """, (id_os,))
    pontos = cursor.fetchall()
    conexao.close()
    
    if not dados_os:
        return None

    num_cc = f"CC-{dados_os[0]:04d}"
    pdf = PDF_FM034_AM(num_cc=num_cc)
    pdf.alias_nb_pages()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    # Bloco 1: Identificação do Empreendimento
    pdf.set_font("Arial", "B", 7.5)
    pdf.set_fill_color(220, 220, 220)
    pdf.cell(190, 4.5, sanitizar_texto("IDENTIFICAÇÃO DO EMPREENDIMENTO"), border=1, ln=1, align="C", fill=True)
    
    pdf.set_font("Arial", "", 7)
    pdf.cell(120, 4.5, sanitizar_texto(f"Empreendimento: {dados_os[1][:60]}"), border=1)
    pdf.cell(70, 4.5, sanitizar_texto(f"Cód. do Cliente: CLI-{dados_os[8]:03d}"), border=1, ln=1)
    pdf.cell(120, 4.5, sanitizar_texto(f"Endereço: {dados_os[3][:60]}"), border=1)
    pdf.cell(70, 4.5, sanitizar_texto("PC N°: -"), border=1, ln=1)
    pdf.cell(120, 4.5, sanitizar_texto("Ponto de Referência: Local da Amostragem"), border=1)
    pdf.cell(70, 4.5, sanitizar_texto(f"Responsável: {dados_os[4][:35]}"), border=1, ln=1)
    pdf.cell(120, 4.5, sanitizar_texto(f"Plano de Amostragem: PA-{dados_os[0]:04d}"), border=1)
    pdf.cell(70, 4.5, sanitizar_texto(f"OS N°: OS-{dados_os[0]:04d}"), border=1, ln=1)
    
    pdf.ln(2)

    # Bloco 2: Identificações da Amostragem
    pdf.set_font("Arial", "B", 7.5)
    pdf.cell(190, 4.5, sanitizar_texto("IDENTIFICAÇÕES DA AMOSTRAGEM"), border=1, ln=1, align="C", fill=True)
    pdf.set_font("Arial", "I", 6.5)
    pdf.cell(190, 4, sanitizar_texto("Método de Amostragem: SMEWW, 24ª ed. - 1060 - Coleta e Preservação de Amostras"), border="LRB", ln=1)
    
    pdf.set_font("Arial", "B", 6.5)
    pdf.cell(22, 5, sanitizar_texto("Cód. Amostra"), border=1, align="C")
    pdf.cell(38, 5, sanitizar_texto("Identificação"), border=1, align="C")
    pdf.cell(35, 5, sanitizar_texto("Localização"), border=1, align="C")
    pdf.cell(18, 5, sanitizar_texto("Matriz"), border=1, align="C")
    pdf.cell(22, 5, sanitizar_texto("Data/Hora"), border=1, align="C")
    pdf.cell(40, 5, sanitizar_texto("Preservação/Acondic."), border=1, align="C")
    pdf.cell(15, 5, sanitizar_texto("Qt. Frascos"), border=1, align="C", ln=1)
    
    pdf.set_font("Arial", "", 6.5)
    num_linhas = max(len(pontos), 5)
    for i in range(num_linhas):
        if i < len(pontos):
            cod, ident, mat = pontos[i][0], pontos[i][1], pontos[i][2]
        else:
            cod, ident, mat = "", "", ""
            
        pdf.cell(22, 4.5, sanitizar_texto(cod), border=1, align="C")
        pdf.cell(38, 4.5, sanitizar_texto(ident[:25]), border=1, align="L")
        pdf.cell(35, 4.5, "", border=1)
        pdf.cell(18, 4.5, sanitizar_texto(mat[:10]), border=1, align="C")
        pdf.cell(22, 4.5, "__/__ __:__", border=1, align="C")
        pdf.cell(40, 4.5, sanitizar_texto("Resfriado <= 6°C / Pres. Quím."), border=1, align="L")
        pdf.cell(15, 4.5, "", border=1, ln=1)

    pdf.ln(2)

    # Bloco 3: Medições in loco
    pdf.set_font("Arial", "B", 7.5)
    pdf.cell(190, 4.5, sanitizar_texto("MEDIÇÕES IN LOCO"), border=1, ln=1, align="C", fill=True)
    
    params_in_loco = [
        "pH",
        "Temperatura da Amostra (°C)",
        "Condutividade Elétrica (uS/cm)",
        "Oxigênio Dissolvido (ppm/%)",
        "Sólidos Totais Dissolvidos (ppm)",
        "Salinidade (ppt/%)",
        "Resistividade (Ohm cm/KOhm cm)",
        "Potencial de Óxido/Redução (mV)"
    ]
    
    pdf.set_font("Arial", "B", 6.5)
    pdf.cell(52, 4.5, sanitizar_texto("Parâmetros"), border=1, align="C")
    for col in range(1, 7):
        pdf.cell(23, 4.5, f"Ponto {col}", border=1, align="C")
    pdf.ln(4.5)
    
    pdf.set_font("Arial", "", 6.5)
    for p_name in params_in_loco:
        pdf.cell(52, 4, sanitizar_texto(p_name), border=1, align="L")
        for _ in range(6):
            pdf.cell(23, 4, "", border=1)
        pdf.ln(4)
        
    pdf.set_font("Arial", "", 6.5)
    pdf.cell(95, 4.5, sanitizar_texto("Chuva nas Últimas 24 hrs:  (  ) Sim   (  ) Não"), border=1)
    pdf.cell(95, 4.5, sanitizar_texto("Temp. Ar °C: ______ | Umidade (%): ______ | Pressão: ______"), border=1, ln=1)
    pdf.cell(190, 6, sanitizar_texto("Observações: "), border=1, ln=1)

    pdf.ln(2)

    # Bloco 4: Recepção e Inspeção
    pdf.set_font("Arial", "B", 7.5)
    pdf.cell(190, 4.5, sanitizar_texto("RECEPÇÃO E INSPEÇÃO DA AMOSTRA"), border=1, ln=1, align="C", fill=True)
    
    pdf.set_font("Arial", "", 6.5)
    pdf.cell(95, 4.5, sanitizar_texto("Responsável Transporte:  (  ) Cliente   (  ) Soludy"), border=1)
    pdf.cell(95, 4.5, sanitizar_texto("Desvio?  (  ) Sim  (  ) Não   | Se sim, qual? _________________"), border=1, ln=1)
    pdf.cell(190, 4.5, sanitizar_texto("Envio para Ensaio:  (  ) Físico-Químico   (  ) Microbiológico"), border=1, ln=1)
    
    pdf.ln(3)

    # Assinaturas
    pdf.set_font("Arial", "", 6.5)
    y_ass = pdf.get_y()
    
    pdf.line(10, y_ass + 5, 65, y_ass + 5)
    pdf.set_xy(10, y_ass + 5.5)
    pdf.cell(55, 3, "AMOSTRADOR", border=0, align="C")
    
    pdf.line(75, y_ass + 5, 130, y_ass + 5)
    pdf.set_xy(75, y_ass + 5.5)
    pdf.cell(55, 3, sanitizar_texto("CIENTE DA COLETA"), border=0, align="C")
    
    pdf.line(140, y_ass + 5, 195, y_ass + 5)
    pdf.set_xy(140, y_ass + 5.5)
    pdf.cell(55, 3, sanitizar_texto("RECEBIDO PELO LAB / DATA"), border=0, align="C")

    return bytes(pdf.output())


class PDF_FM037_AM(FPDF):
    """Classe geradora do Plano de Amostragem - FM 037 AM"""
    def __init__(self, num_pa=""):
        super().__init__(orientation='P', unit='mm', format='A4')
        self.num_pa = sanitizar_texto(num_pa)

    def header(self):
        self.set_font("Arial", "B", 8)
        
        self.set_xy(10, 10)
        self.cell(110, 12, "", border=1)
        self.set_xy(12, 11)
        self.cell(106, 4, sanitizar_texto("PLANO DE AMOSTRAGEM DE ÁGUAS, EFLUENTES,"), border=0, align="C", ln=1)
        self.cell(106, 4, sanitizar_texto("SOLOS, SEDIMENTOS E RESÍDUO"), border=0, align="C", ln=1)
        
        self.set_xy(120, 10)
        self.cell(45, 12, "", border=1)
        self.set_xy(121, 11)
        self.cell(43, 3.5, "FM 037 AM", border=0, align="C", ln=1)
        self.cell(43, 3, sanitizar_texto("Elaborado por: AM"), border=0, align="C", ln=1)
        self.cell(43, 3, sanitizar_texto("Aprovado por: SG"), border=0, align="C", ln=1)
        
        self.set_xy(165, 10)
        self.cell(35, 12, "", border=1)
        self.set_xy(166, 11)
        self.cell(33, 3.5, "Data: 18/05/2026", border=0, align="C", ln=1)
        self.cell(33, 3, sanitizar_texto("Revisão: 01"), border=0, align="C", ln=1)
        self.set_font("Arial", "B", 7)
        self.cell(33, 3.5, sanitizar_texto(f"Plano N°: {self.num_pa}"), border=0, align="C", ln=1)
        
        self.ln(3)

    def footer(self):
        self.set_y(-12)
        self.set_font("Arial", "", 6)
        self.cell(0, 4, sanitizar_texto("Tv. São Roque, 98 - Cruzeiro - Belém/PA | Contato: (91) 98203-6889 | gestao@soludy.com.br"), border=0, align="C")


def gerar_pdf_plano_amostragem(id_os):
    """Gera o PDF do Plano de Amostragem oficial FM 037 AM."""
    conexao = sqlite3.connect("pre_amostragem.db")
    cursor = conexao.cursor()
    
    cursor.execute("""
        SELECT os.id, c.razao_social, c.cnpj, c.endereco, c.contato, 
               os.data_solicitacao, os.legislacao_aplicavel, os.laboratorio_destino
        FROM ordens_servico os
        JOIN clientes c ON os.id_cliente = c.id
        WHERE os.id = ?
    """, (id_os,))
    dados_os = cursor.fetchone()
    
    cursor.execute("""
        SELECT codigo_amostra, identificacao_ponto, matriz, parametros
        FROM pontos_amostra
        WHERE id_os = ?
        ORDER BY id ASC
    """, (id_os,))
    pontos = cursor.fetchall()
    conexao.close()
    
    if not dados_os:
        return None

    num_pa = f"PA-{dados_os[0]:04d}"
    pdf = PDF_FM037_AM(num_pa=num_pa)
    pdf.alias_nb_pages()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    pdf.set_font("Arial", "", 7.5)
    
    pdf.cell(190, 5, sanitizar_texto(f"Empreendimento: {dados_os[1]}"), border=1, ln=1)
    pdf.cell(120, 5, sanitizar_texto(f"Local de Amostragem: {dados_os[3]}"), border=1)
    pdf.cell(70, 5, sanitizar_texto(f"Contato: {dados_os[4]}"), border=1, ln=1)
    
    pdf.ln(2)
    
    pdf.set_font("Arial", "B", 7.5)
    pdf.cell(190, 4.5, sanitizar_texto("1. Objetivo do Serviço"), border=1, ln=1, fill=True)
    pdf.set_font("Arial", "", 7)
    pdf.cell(190, 4.5, sanitizar_texto("Amostragem ambiental e caracterização analítica para controle de qualidade e conformidade normativa."), border="LRB", ln=1)
    
    pdf.set_font("Arial", "B", 7.5)
    pdf.cell(190, 4.5, sanitizar_texto("2. Especificações do Cliente e Requisitos Legais"), border=1, ln=1, fill=True)
    pdf.set_font("Arial", "", 7)
    pdf.cell(190, 4.5, sanitizar_texto(f"Legislação de Referência: {dados_os[6]}"), border="LRB", ln=1)
    
    pdf.ln(2)
    
    pdf.set_font("Arial", "B", 7.5)
    pdf.cell(190, 4.5, sanitizar_texto("3. Matrizes e Quantidade de Pontos Planejados"), border=1, ln=1, fill=True)
    pdf.set_font("Arial", "", 7)
    pdf.cell(190, 4.5, sanitizar_texto(f"Quantidade Total de Pontos Configurados nesta OS: {len(pontos)} ponto(s)"), border="LRB", ln=1)
    
    pdf.ln(2)
    
    pdf.set_font("Arial", "B", 7.5)
    pdf.cell(190, 4.5, sanitizar_texto("4. Definição dos Pontos de Amostragem e Parâmetros Requeridos"), border=1, ln=1, fill=True)
    
    pdf.set_font("Arial", "B", 6.5)
    pdf.cell(25, 5, sanitizar_texto("Código"), border=1, align="C")
    pdf.cell(45, 5, sanitizar_texto("Identificação"), border=1, align="C")
    pdf.cell(20, 5, sanitizar_texto("Matriz"), border=1, align="C")
    pdf.cell(100, 5, sanitizar_texto("Parâmetros Analíticos Requeridos"), border=1, align="C", ln=1)
    
    pdf.set_font("Arial", "", 6.5)
    for p in pontos:
        cod, ident, mat, param = str(p[0]), str(p[1]), str(p[2]), str(p[3])
        
        largura_text = pdf.get_string_width(sanitizar_texto(param))
        linhas = math.ceil(largura_text / 96)
        altura = max(5.0, linhas * 3.5 + 1.5)
        
        x_init, y_init = pdf.get_x(), pdf.get_y()
        
        pdf.cell(25, altura, sanitizar_texto(cod), border=1, align="C")
        pdf.cell(45, altura, sanitizar_texto(ident[:28]), border=1, align="L")
        pdf.cell(20, altura, sanitizar_texto(mat[:10]), border=1, align="C")
        
        x_param = pdf.get_x()
        pdf.cell(100, altura, "", border=1)
        pdf.set_xy(x_param + 1, y_init + 1)
        pdf.multi_cell(98, 3, sanitizar_texto(param), border=0, align="L")
        pdf.set_xy(x_init, y_init + altura)

    pdf.ln(2)

    pdf.set_font("Arial", "B", 7.5)
    pdf.cell(190, 4.5, sanitizar_texto("5. Programa de Garantia da Validade dos Resultados e Preservação"), border=1, ln=1, fill=True)
    pdf.set_font("Arial", "", 7)
    pdf.cell(190, 4.5, sanitizar_texto(f"Destino das Amostras: {dados_os[7]} | Preservação: Resfriamento <= 6°C e adição de reagentes específicos."), border="LRB", ln=1)

    return bytes(pdf.output())


def gerar_excel_ordem_servico(id_os):
    """Gera a planilha Excel com o resumo da Ordem de Serviço e pontos."""
    conexao = sqlite3.connect("pre_amostragem.db")
    cursor = conexao.cursor()
    
    cursor.execute("""
        SELECT os.id, c.razao_social, c.cnpj, c.endereco, c.contato, 
               os.data_solicitacao, os.legislacao_aplicavel, os.laboratorio_destino
        FROM ordens_servico os
        JOIN clientes c ON os.id_cliente = c.id
        WHERE os.id = ?
    """, (id_os,))
    dados_os = cursor.fetchone()
    
    cursor.execute("""
        SELECT codigo_amostra AS 'Código Único', 
               identificacao_ponto AS 'Identificação do Ponto', 
               matriz AS 'Matriz (Sigla)', 
               parametros AS 'Parâmetros Analíticos'
        FROM pontos_amostra
        WHERE id_os = ?
        ORDER BY id ASC
    """, (id_os,))
    pontos = cursor.fetchall()
    conexao.close()
    
    if not dados_os:
        return None

    df_pontos = pd.DataFrame(pontos, columns=['Código Único', 'Identificação do Ponto', 'Matriz (Sigla)', 'Parâmetros Analíticos'])
    
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df_pontos.to_excel(writer, sheet_name=f"OS_{id_os}", index=False, startrow=6)
        
        worksheet = writer.sheets[f"OS_{id_os}"]
        worksheet["A1"] = f"ORDEM DE SERVIÇO Nº: {dados_os[0]}"
        worksheet["A2"] = f"Cliente: {dados_os[1]} | CNPJ: {dados_os[2]}"
        worksheet["A3"] = f"Endereço: {dados_os[3]}"
        worksheet["A4"] = f"Legislação: {dados_os[6]} | Destino: {dados_os[7]}"
        
    return buffer.getvalue()