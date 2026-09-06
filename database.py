import sqlite3
import pandas as pd
import io
from fpdf import FPDF

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
        SELECT os.id, c.razao_social, os.data_solicitacao
        FROM ordens_servico os
        JOIN clientes c ON os.id_cliente = c.id
        ORDER BY os.id DESC
    """)
    ordens = cursor.fetchall()
    conexao.close()
    return ordens

import re

def cadastrar_pontos_lote(id_os, quantidade_pontos, matriz, parametros):
    """
    Cadastra múltiplos pontos de amostragem de uma única vez para uma OS,
    aplicando a mesma matriz e a mesma lista de parâmetros a todos eles.
    """
    conexao = sqlite3.connect("pre_amostragem.db")
    cursor = conexao.cursor()
    
    # Identifica o maior sequencial existente para não duplicar códigos
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
                
    # Insere sequencialmente a quantidade solicitada de pontos
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


# --- MÓDULO DE EMISSÃO DE PDF COM ALINHAMENTO CORRIGIDO ---

class PDF_Cadeia_Custodia(FPDF):
    def header(self):
        self.set_font("Arial", "B", 13)
        self.cell(0, 8, "FICHA DE CAMPO E CADEIA DE CUSTÓDIA", border=0, ln=1, align="C")
        self.set_font("Arial", "I", 8)
        self.cell(0, 4, "Sistema de Gestão de Pré-Amostragem Ambiental", border=0, ln=1, align="C")
        self.ln(4)

    def footer(self):
        self.set_y(-15)
        self.set_font("Arial", "I", 8)
        self.cell(0, 10, f"Página {self.page_no()}/{{nb}}", align="C")


import math

def gerar_pdf_cadeia_custodia(id_os):
    """Gera a Ficha de Cadeia de Custódia com tabelas em branco para registro in loco."""
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

    pdf = PDF_Cadeia_Custodia()
    pdf.alias_nb_pages()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    # Cabeçalho da Ordem de Serviço
    pdf.set_font("Arial", "B", 9)
    pdf.set_fill_color(220, 220, 220)
    pdf.cell(0, 6, f"ORDEM DE SERVIÇO Nº: {dados_os[0]}", border=1, ln=1, fill=True)
    
    pdf.set_font("Arial", "", 8)
    pdf.cell(100, 5, f"Cliente: {dados_os[1]}", border=1)
    pdf.cell(90, 5, f"CNPJ/CPF: {dados_os[2]}", border=1, ln=1)
    
    pdf.cell(190, 5, f"Endereço de Coleta: {dados_os[3]}", border=1, ln=1)
    pdf.cell(100, 5, f"Contato: {dados_os[4]}", border=1)
    pdf.cell(90, 5, f"Data da Solicitação: {dados_os[5]}", border=1, ln=1)
    
    pdf.cell(110, 5, f"Legislação: {dados_os[6]}", border=1)
    pdf.cell(80, 5, f"Destino: {dados_os[7]}", border=1, ln=1)
    
    pdf.ln(4)
    
    # TABELA 1: Identificação dos Pontos de Coleta (Em Branco para o Campo)
    pdf.set_font("Arial", "B", 8)
    pdf.cell(20, 7, "Código", border=1, align="C")
    pdf.cell(35, 7, "Identificação", border=1, align="C")
    pdf.cell(45, 7, "Matriz (ASP, ASB, etc.)", border=1, align="C")
    pdf.cell(25, 7, "Data", border=1, align="C")
    pdf.cell(20, 7, "Hora", border=1, align="C")
    pdf.cell(25, 7, "Localização", border=1, align="C")
    pdf.cell(20, 7, "Qtd Frascos", border=1, align="C", ln=1)
    
    pdf.set_font("Arial", "", 8)
    
    # Se existirem pontos cadastrados na OS, imprime linhas pré-preenchidas com os códigos
    num_linhas_tabela1 = max(len(pontos), 6)
    
    for i in range(num_linhas_tabela1):
        if i < len(pontos):
            cod = pontos[i][0]
            ident = pontos[i][1]
            mat = pontos[i][2]
        else:
            cod, ident, mat = "", "", ""
            
        pdf.cell(20, 6, cod, border=1, align="C")
        pdf.cell(35, 6, ident, border=1, align="L")
        pdf.cell(45, 6, mat, border=1, align="C")
        pdf.cell(25, 6, "___ / ___ / ____", border=1, align="C")
        pdf.cell(20, 6, "__ : __", border=1, align="C")
        pdf.cell(25, 6, "", border=1)
        pdf.cell(20, 6, "", border=1, ln=1)
        
    pdf.ln(5)
    
    # TABELA 2: Matriz de Medição de Parâmetros In Loco (Pontos 1 a 6)
    lista_parametros_padrao = [
        "pH",
        "Condutividade Elétrica",
        "Salinidade",
        "Sólidos Totais Dissolvidos",
        "Potencial de Oxidação",
        "Temperatura"
    ]
    
    # Se houver parâmetros específicos cadastrados na OS, utiliza-os
    if pontos and pontos[0][3]:
        params_os = [p.strip() for p in pontos[0][3].split(",")]
        if len(params_os) > 0:
            lista_parametros_padrao = params_os

    pdf.set_font("Arial", "B", 8)
    pdf.cell(52, 6, "Parâmetros", border=1, align="C", fill=True)
    for num_col in range(1, 7):
        pdf.cell(23, 6, str(num_col), border=1, align="C", fill=True)
    pdf.ln(6)
    
    pdf.set_font("Arial", "", 8)
    for param in lista_parametros_padrao:
        pdf.cell(52, 6, param[:30], border=1, align="L")
        for _ in range(6):
            pdf.cell(23, 6, "", border=1)
        pdf.ln(6)
        
    pdf.ln(6)
    
    # Seção de Assinaturas
    pdf.set_font("Arial", "B", 8)
    pdf.cell(0, 5, "REGISTRO DE CAMPO E RESPONSABILIDADE DA COLETA", border=0, ln=1)
    pdf.ln(5)
    
    pdf.set_font("Arial", "", 8)
    pdf.cell(90, 4, "________________________________________", border=0, ln=0, align="C")
    pdf.cell(10, 4, "", border=0, ln=0)
    pdf.cell(90, 4, "________________________________________", border=0, ln=1, align="C")
    
    pdf.cell(90, 4, "Técnico de Amostragem (Assinatura)", border=0, ln=0, align="C")
    pdf.cell(10, 4, "", border=0, ln=0)
    pdf.cell(90, 4, "Recebido pelo Laboratório (Assinatura)", border=0, ln=1, align="C")
    
    return bytes(pdf.output())


def gerar_excel_ordem_servico(id_os):
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

def gerar_pdf_plano_amostragem(id_os):
    """Gera o PDF do Plano de Amostragem contendo as diretrizes e parâmetros do serviço."""
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

    pdf = PDF_Cadeia_Custodia()  # Utiliza a mesma classe base de PDF
    pdf.alias_nb_pages()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    # Título do Documento
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 6, "PLANO DE AMOSTRAGEM AMBIENTAL", border=0, ln=1, align="C")
    pdf.ln(3)
    
    # Tabela de Informações da OS
    pdf.set_font("Arial", "B", 9)
    pdf.set_fill_color(220, 220, 220)
    pdf.cell(0, 6, f"ORDEM DE SERVIÇO Nº: {dados_os[0]}", border=1, ln=1, fill=True)
    
    pdf.set_font("Arial", "", 8)
    pdf.cell(100, 5, f"Cliente: {dados_os[1]}", border=1)
    pdf.cell(90, 5, f"CNPJ/CPF: {dados_os[2]}", border=1, ln=1)
    
    pdf.cell(190, 5, f"Endereço de Coleta: {dados_os[3]}", border=1, ln=1)
    pdf.cell(100, 5, f"Contato: {dados_os[4]}", border=1)
    pdf.cell(90, 5, f"Data da Solicitação: {dados_os[5]}", border=1, ln=1)
    
    pdf.cell(110, 5, f"Legislação: {dados_os[6]}", border=1)
    pdf.cell(80, 5, f"Destino: {dados_os[7]}", border=1, ln=1)
    
    pdf.ln(4)
    
    # Tabela de Pontos e Parâmetros
    pdf.set_font("Arial", "B", 9)
    pdf.cell(0, 6, "PONTOS PLANEJADOS E PARÂMETROS REQUERIDOS", border=1, ln=1, fill=True)
    
    pdf.set_font("Arial", "B", 8)
    pdf.cell(25, 6, "Código", border=1, align="C")
    pdf.cell(45, 6, "Identificação", border=1, align="C")
    pdf.cell(20, 6, "Matriz", border=1, align="C")
    pdf.cell(100, 6, "Parâmetros Requeridos", border=1, align="C", ln=1)
    
    pdf.set_font("Arial", "", 8)
    
    for p in pontos:
        cod, ident, mat, param = str(p[0]), str(p[1]), str(p[2]), str(p[3])
        largura_col_param = 100
        
        largura_texto = pdf.get_string_width(param)
        linhas_estimadas = math.ceil(largura_texto / (largura_col_param - 4))
        if linhas_estimadas < 1:
            linhas_estimadas = 1
            
        altura_linha_texto = 4.5
        altura_total = max(7.0, linhas_estimadas * altura_linha_texto + 2.5)
        
        x_inicial = pdf.get_x()
        y_inicial = pdf.get_y()
        
        pdf.cell(25, altura_total, "", border=1)
        pdf.cell(45, altura_total, "", border=1)
        pdf.cell(20, altura_total, "", border=1)
        pdf.cell(100, altura_total, "", border=1)
        
        pdf.set_xy(x_inicial, y_inicial)
        pdf.cell(25, altura_total, cod, border=0, align="C")
        pdf.cell(45, altura_total, ident[:25], border=0, align="L")
        pdf.cell(20, altura_total, mat[:10], border=0, align="C")
        
        x_param = pdf.get_x()
        pdf.set_xy(x_param + 1, y_inicial + 1.5)
        pdf.multi_cell(largura_col_param - 2, altura_linha_texto, param, border=0, align="L")
        
        pdf.set_xy(x_inicial, y_inicial + altura_total)
        
    return bytes(pdf.output())