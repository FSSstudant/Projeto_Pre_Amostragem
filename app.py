import streamlit as st
import datetime
import pandas as pd
from database import (
    criar_tabelas,
    cadastrar_cliente, 
    listar_clientes, 
    criar_ordem_servico,
    listar_ordens_servico,
    cadastrar_pontos_lote,
    listar_pontos_por_os,
    deletar_ponto_amostra,
    atualizar_ponto_amostra,
    gerar_pdf_cadeia_custodia,
    gerar_pdf_plano_amostragem,
    gerar_excel_ordem_servico,
    atualizar_status_os
)
import re

def validar_e_formatar_documento(doc):
    """Remove caracteres não numéricos e aplica máscara de CPF ou CNPJ."""
    numeros = re.sub(r'\D', '', doc)
    
    if len(numeros) == 11:
        # Formata como CPF: 000.000.000-00
        return f"{numeros[:3]}.{numeros[3:6]}.{numeros[6:9]}-{numeros[9:]}"
    elif len(numeros) == 14:
        # Formata como CNPJ: 00.000.000/0000-00
        return f"{numeros[:2]}.{numeros[2:5]}.{numeros[5:8]}/{numeros[8:12]}-{numeros[12:]}"
    else:
        return None # Retorna None se o tamanho for inválido
    
criar_tabelas()
st.set_page_config(page_title="Gestão de Pré-Amostragem", layout="wide")

st.title(" Sistema de Gestão de Pré-Amostragem Ambiental")
st.write("Plataforma de Integração Comercial e Setor de Amostragem")

aba1, aba2, aba3, aba4 = st.tabs([
    "📋 1. Cadastrar Cliente", 
    "📝 2. Nova Ordem de Serviço (OS)",
    "📍 3. Planejamento de Amostragem",
    "📄 4. Emissão de Documentos (Plano de Amostragem/Cadeia de Custódia)"
])

# Lista padronizada de opções de matrizes e parâmetros
OPCOES_MATRIZES = [
    "ASP - Água Superficial",
    "ACH - Água de Consumo Humano",
    "ASB - Água Subterrânea",
    "EFL - Efluentes Líquidos Industriais",
    "ATM - Gases Poluentes",
    "EAT - Emissões Atmosféricas",
    "NPS - Nível de Pressão Sonora",
    "ACT - Acústica Ambiental",
    "Solo - Parâmetros Físico-Químicos/Microbiológicos",
    "RS - Resíduos Fixados no Solo",
    "VOC - Volatile Organic Compounds"
]

OPCOES_PARAMETROS = [
    "pH", "Temperatura", "Oxigênio Dissolvido (OD)", "Condutividade Elétrica",
    "DBO5,20", "DQO", "Sólidos Suspensos Totais (SST)", "Óleos e Graxas",
    "Metais Pesados (Pb, Cd, Cr, Ni, Cu, Zn)", "Coliformes Termotolerantes / E. coli",
    "BTEX (Benzeno, Tolueno, Etilbenzeno, Xilenos)", "Turbidez",
    "SO2", "NO2", "CO", "Material Particulado 2,5 e 10", "Ruído Contínuo Leq"
]

# ==========================================
# ABA 1: CADASTRO DE CLIENTES
# ==========================================
with aba1:
    st.subheader("Cadastro de Novo Empreendimento / Cliente")
    
    with st.form("form_cliente", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            razao_social = st.text_input("Razão Social / Nome do Empreendimento:*")
            cnpj = st.text_input("CNPJ / CPF:*")
        with col2:
            endereco = st.text_input("Endereço Completo do Local de Coleta:*")
            contato = st.text_input("Telefone / E-mail do Responsável:*")
        
        btn_salvar_cliente = st.form_submit_button("Salvar Cliente no Banco de Dados")
        
        if btn_salvar_cliente:
            if razao_social and cnpj and endereco and contato:
                # Chama a validação e formatação
                cnpj_cpf_formatado = validar_e_formatar_documento(cnpj)
                
                if not cnpj_cpf_formatado:
                    st.error("❌ CNPJ ou CPF inválido! Digite 11 dígitos para CPF ou 14 para CNPJ.")
                else:
                    sucesso = cadastrar_cliente(razao_social, cnpj_cpf_formatado, endereco, contato)
                    if sucesso:
                        st.success(f"✅ Cliente '{razao_social}' cadastrado com sucesso! (Doc: {cnpj_cpf_formatado})")
                    else:
                        st.error("❌ Erro: Já existe um cliente cadastrado com este CNPJ/CPF.")
            else:
                st.warning("⚠️ Por favor, preencha todos os campos obrigatórios (*).")

# ==========================================
# ABA 2: ABERTURA DE ORDEM DE SERVIÇO (OS)
# ==========================================
with aba2:
    st.subheader("Abertura de Ordem de Serviço")
    
    clientes_cadastrados = listar_clientes()
    
    if not clientes_cadastrados:
        st.info("Nenhum cliente cadastrado no momento. Cadastre um cliente na Aba 1 antes de criar uma OS.")
    else:
        opcoes_clientes = {f"{c[1]} (CNPJ: {c[2]})": c[0] for c in clientes_cadastrados}
        
        with st.form("form_os", clear_on_submit=True):
            cliente_selecionado_nome = st.selectbox("Selecione o Cliente / Empreendimento:*", list(opcoes_clientes.keys()))
            
            col1, col2 = st.columns(2)
            with col1:
                data_solicitacao = st.date_input("Data da Solicitação:", datetime.date.today())
                legislacao = st.selectbox(
                    "Legislação Ambiental de Referência:*",
                    [
                        "Resolução CONAMA 357/2005 (Águas Superficiais)",
                        "Resolução CONAMA 430/2011 (Lançamento de Efluentes)",
                        "Portaria GM/MS nº 888/2021 (Água de Consumo Humano)",
                        "Resolução CONAMA 420/2009 (Qualidade do Solo)",
                        "Outra Normativa / Requisito Específico"
                    ]
                )
            with col2:
                lab_destino = st.selectbox(
                    "Destino Primário das Amostras:*",
                    ["Laboratório Interno (LEFQ / LEMB)", "Provedor Externo (Laboratório Parceiro)", "Misto (Interno e Provedor Externo)"]
                )
            
            btn_gerar_os = st.form_submit_button("Gerar e Gravar Ordem de Serviço")
            
            if btn_gerar_os:
                id_cliente = opcoes_clientes[cliente_selecionado_nome]
                id_os = criar_ordem_servico(
                    id_cliente, 
                    str(data_solicitacao), 
                    legislacao, 
                    lab_destino
                )
                st.success(f"Ordem de Serviço **OS nº {id_os}** gerada e gravada com sucesso!")

# ==========================================
# ABA 3: PLANEJAMENTO DE AMOSTRAGEM
# ==========================================
with aba3:
    st.subheader("📋 Planejamento da Amostragem (Definição de Pontos e Parâmetros)")
    
    ordens = listar_ordens_servico()
    if not ordens:
        st.warning("Nenhuma Ordem de Serviço cadastrada. Cadastre uma OS na Aba 2 primeiro.")
    else:
        opcoes_os = {f"OS nº {o[0]} - {o[1]} [{o[3]}]": o[0] for o in ordens}
        os_selecionada = st.selectbox("Selecione a Ordem de Serviço para configurar:", list(opcoes_os.keys()))
        id_os_selecionada = opcoes_os[os_selecionada]
        os_atual = next(o for o in ordens if o[0] == id_os_selecionada)
        status_atual = os_atual[3]
        if status_atual == "Concluída":
            st.success(f"**Status Atual:** {status_atual} ✅")
        elif status_atual == "Em Planejamento":
            st.warning(f"**Status Atual:** {status_atual} 🚧")
        else:
            st.error(f"**Status Atual:** {status_atual} ❌")

        with st.expander("🔄 Alterar Status da OS"):
            col_status, col_btn_status = st.columns([3, 1])
            with col_status:
                lista_status = ["Em Planejamento", "Concluída", "Cancelada"]
                # Pega o índice do status atual para deixá-lo selecionado por padrão
                idx_atual = lista_status.index(status_atual) if status_atual in lista_status else 0
                novo_status = st.selectbox("Definir novo status para esta OS:", lista_status, index=idx_atual)

            with col_btn_status:
                st.write("") # Espaçamento para alinhar o botão
                st.write("")
                if st.button("Atualizar Status", use_container_width=True):
                    atualizar_status_os(id_os_selecionada, novo_status)
                    st.rerun() # Recarrega a tela instantaneamente
        
        st.divider()
        
        col_cad, col_list = st.columns([1, 1])
        
        with col_cad:
            st.markdown("### ➕ Configurar Amostragem em Lote")
            
            qtd_pontos = st.number_input(
                "Quantidade de Pontos a Serem Coletados:*", 
                min_value=1, 
                max_value=20, 
                value=3, 
                step=1
            )
            
            opcoes_matriz = [
                "ASP - Água Superficial",
                "ASB - Água Subterrânea",
                "ACH - Água de Chuva",
                "EFL - Efluente Líquido"
            ]
            matriz_selecionada = st.selectbox("Matriz Ambiental (Sigla):*", opcoes_matriz)
            sigla_matriz = matriz_selecionada.split(" - ")[0]
            
            opcoes_parametros = [
                "pH", "Temperatura", "Condutividade Elétrica", 
                "Salinidade", "Sólidos Totais Dissolvidos", "Potencial de Oxidação",
                "Turbidez", "Oxigênio Dissolvido", "DBO", "DQO"
            ]
            parametros_selecionados = st.multiselect(
                "Parâmetros Analíticos Requeridos (Aplicados a todos os pontos):*", 
                opcoes_parametros,
                default=["pH", "Temperatura", "Condutividade Elétrica"]
            )
            
            if st.button("Gerar e Salvar Pontos de Amostragem"):
                if not parametros_selecionados:
                    st.error("Selecione ao menos um parâmetro analítico.")
                else:
                    str_parametros = ", ".join(parametros_selecionados)
                    cadastrar_pontos_lote(id_os_selecionada, qtd_pontos, sigla_matriz, str_parametros)
                    st.success(f"{qtd_pontos} pontos cadastrados com sucesso para a OS nº {id_os_selecionada}!")
                    st.rerun()

        with col_list:
            st.markdown("### 📜 Pontos Cadastrados nesta OS")
            pontos = listar_pontos_por_os(id_os_selecionada)
            
            if not pontos:
                st.info("Nenhum ponto cadastrado para esta OS ainda.")
            else:
                for p in pontos:
                    id_ponto, cod_amostra, ident, mat, params = p
                    with st.container(border=True):
                        st.markdown(f"**Código:** `:green[{cod_amostra}]` | **Matriz:** `:gray-badge[{mat}]`")
                        st.caption(f"**Local:** {ident}")
                        st.caption(f"**Parâmetros:** {params}")
                        
                        col_btn1, col_btn2 = st.columns([1, 1])
                        with col_btn1:
                            if st.button(f"🗑️ Excluir", key=f"del_{id_ponto}"):
                                deletar_ponto_amostra(id_ponto)
                                st.rerun()
                        
                        # Expansor para formulário de edição
                        with st.expander(f"✏️ Editar {cod_amostra}"):
                            with st.form(key=f"form_edit_{id_ponto}"):
                                novo_ident = st.text_input("Identificação do Local:", value=ident)
                                nova_matriz = st.text_input("Sigla da Matriz:", value=mat)
                                novos_params = st.text_area("Parâmetros (separados por vírgula):", value=params)
                                
                                btn_atualizar = st.form_submit_button("Salvar Alterações")
                                if btn_atualizar:
                                    atualizar_ponto_amostra(id_ponto, novo_ident, nova_matriz, novos_params)
                                    st.success(f"Ponto {cod_amostra} atualizado com sucesso!")
                                    st.rerun()

# ==========================================
# ABA 4: EMISSÃO DE DOCUMENTOS
# ==========================================
with aba4:
    st.subheader("📄 Emissão de Documentos de Campo")
    
    ordens = listar_ordens_servico()
    if not ordens:
        st.warning("Nenhuma Ordem de Serviço cadastrada.")
    else:
        opcoes_os = {f"OS nº {o[0]} - {o[1]} [{o[3]}]": o[0] for o in ordens}
        os_doc_selecionada = st.selectbox("Selecione a Ordem de Serviço para emissão:", list(opcoes_os.keys()), key="doc_os")
        id_os_doc = opcoes_os[os_doc_selecionada]
        
        st.divider()
        
        col_pdf1, col_pdf2 = st.columns(2)
        
        with col_pdf1:
            st.markdown("### 📋 Plano de Amostragem")
            st.write("Documento com diretrizes da OS, lista de pontos e parâmetros requeridos para orientar a equipe de amostragem.")
            
            pdf_plano_bytes = gerar_pdf_plano_amostragem(id_os_doc)
            if pdf_plano_bytes:
                st.download_button(
                    label="📥 Baixar Plano de Amostragem (PDF)",
                    data=pdf_plano_bytes,
                    file_name=f"Plano_Amostragem_OS_{id_os_doc}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
        
        with col_pdf2:
            st.markdown("### 📝 Cadeia de Custódia")
            st.write("Ficha de campo com campos e matrizes em branco para preenchimento manual dos dados medidos *in loco*.")
            
            pdf_cadeia_bytes = gerar_pdf_cadeia_custodia(id_os_doc)
            if pdf_cadeia_bytes:
                st.download_button(
                    label="📥 Baixar Cadeia de Custódia (PDF)",
                    data=pdf_cadeia_bytes,
                    file_name=f"Cadeia_Custodia_OS_{id_os_doc}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )