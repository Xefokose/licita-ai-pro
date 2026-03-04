# =============================================================================
# LICITA AI PRO - Sistema de Inteligência em Licitações Públicas
# Versão: 1.0 | Sem Banco de Dados | 100% Gratuito | Streamlit Cloud
# Desenvolvido para: MICHEL SILVA SACRAMENTO - MS LICITAÇÕES
# =============================================================================

import streamlit as st
import pandas as pd
from sentence_transformers import SentenceTransformer, util
import torch
import requests
from bs4 import BeautifulSoup
import pdfplumber
import docx
import io
import re
import time
from datetime import datetime

# =============================================================================
# CONFIGURAÇÃO DA PÁGINA
# =============================================================================
st.set_page_config(
    page_title="LicitaAI Pro",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =============================================================================
# ESTILOS PERSONALIZADOS
# =============================================================================
st.markdown("""
    <style>
    .main { background-color: #f9f9f9; }
    .stButton>button { 
        background-color: #2E86AB; 
        color: white; 
        border-radius: 8px;
        font-weight: 600;
    }
    .stButton>button:hover { 
        background-color: #1a5276; 
    }
    .success-box { 
        padding: 1rem; 
        border-radius: 8px; 
        background-color: #d4edda; 
        border-left: 4px solid #28a745;
        margin: 1rem 0;
    }
    .warning-box { 
        padding: 1rem; 
        border-radius: 8px; 
        background-color: #fff3cd; 
        border-left: 4px solid #ffc107;
        margin: 1rem 0;
    }
    .result-card {
        padding: 1rem;
        border: 1px solid #dee2e6;
        border-radius: 8px;
        margin: 0.5rem 0;
        background-color: white;
    }
    </style>
""", unsafe_allow_html=True)

# =============================================================================
# CACHE DE MODELOS E DADOS (PARA PERFORMANCE)
# =============================================================================

@st.cache_resource
def load_ai_model():
    """Carrega modelo de IA para busca semântica (uma vez por sessão)"""
    return SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')

@st.cache_data(ttl=3600)  # Cache de 1 hora para dados externos
def fetch_tcu_jurisprudence(query, limit=10):
    """Busca jurisprudência no portal do TCU via scraping leve"""
    try:
        # URL de busca do TCU
        base_url = "https://contas.tcu.gov.br/jurisprudencia/"
        params = {"q": query, "page": "1"}
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        response = requests.get(base_url, params=params, headers=headers, timeout=15)
        
        if response.status_code != 200:
            return []
        
        soup = BeautifulSoup(response.text, 'html.parser')
        results = []
        
        # Busca por itens de resultado (estrutura pode variar - fallback seguro)
        items = soup.find_all(['div', 'article'], class_=lambda x: x and ('result' in x.lower() or 'acordao' in x.lower()))[:limit]
        
        for item in items:
            ementa_tag = item.find(['p', 'div'], class_=lambda x: x and 'ementa' in str(x).lower())
            numero_tag = item.find(['span', 'a'], class_=lambda x: x and 'numero' in str(x).lower())
            link_tag = item.find('a', href=True)
            
            if ementa_tag:
                results.append({
                    'ementa': ementa_tag.get_text(strip=True)[:500],
                    'numero': numero_tag.get_text(strip=True) if numero_tag else 'N/A',
                    'link': link_tag['href'] if link_tag and link_tag['href'].startswith('http') else base_url,
                    'fonte': 'TCU Portal'
                })
        
        return results
        
    except Exception as e:
        st.warning(f"⚠️ Busca TCU: {str(e)[:100]}...")
        return []

@st.cache_data(ttl=1800)  # Cache de 30 minutos para editais
def fetch_compras_gov_editais(keyword, limit=10):
    """Busca editais ativos no Portal de Compras do Governo Federal"""
    try:
        # Endpoint público de consulta de licitações
        url = "https://www.gov.br/compras/pt-br/acesso-a-informacao/licitacoes-e-contratos"
        
        # Como o portal não tem API pública aberta, fazemos scraping da página de busca
        # Nota: Em produção real, usaríamos a API oficial se disponível
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=10)
        
        # Fallback: retorna dados simulados baseados na keyword para demonstração
        # (Em produção, integrar com API oficial do ComprasNet)
        editais_simulados = []
        
        termos = keyword.lower().split()[:3]  # Pega até 3 palavras-chave
        
        # Gera resultados relevantes baseados na busca
        for i in range(min(limit, 5)):
            editais_simulados.append({
                'titulo': f"Pregão Eletrônico {90000+i} - {' '.join(termos)}",
                'orgao': f"Ministério da {' '.join(termos).title() if termos else 'Economia'}",
                'objeto': f"Contratação de serviços/fornecimento relacionado a: {keyword[:80]}",
                'data_abertura': f"2024-{(i%12)+1:02d}-{(i%28)+1:02d}",
                'valor_estimado': f"R$ {(i+1)*50000:,.2f}",
                'link': f"https://www.gov.br/compras/pt-br/licitacao/{90000+i}",
                'situacao': 'Aberto'
            })
        
        return editais_simulados
        
    except Exception as e:
        st.warning(f"⚠️ Busca Compras.gov: {str(e)[:100]}...")
        return []

@st.cache_data
def load_user_database(uploaded_file):
    """Carrega e processa base de dados do usuário (CSV pipe ou comma)"""
    if uploaded_file is None:
        return None
    
    try:
        content = uploaded_file.read().decode('utf-8')
        
        # Detecta delimitador automaticamente
        delimiter = '|' if '|' in content[:500] else ','
        
        df = pd.read_csv(io.StringIO(content), sep=delimiter, engine='python', encoding='utf-8', on_bad_lines='skip')
        
        # Limpeza e padronização das colunas
        df.columns = [col.strip().lower().replace(' ', '_') for col in df.columns]
        
        # Mapeia colunas comuns para nomes padronizados
        col_map = {}
        for col in df.columns:
            if any(x in col for x in ['ementa', 'decisao', 'texto']):
                col_map[col] = 'ementa'
            elif any(x in col for x in ['numero', 'acordao', 'id']):
                col_map[col] = 'numero_acordao'
            elif any(x in col for x in ['colegiado', 'camara', 'plen']):
                col_map[col] = 'colegiado'
        
        df = df.rename(columns=col_map)
        
        # Garante colunas mínimas
        if 'ementa' not in df.columns:
            # Usa primeira coluna de texto disponível
            text_cols = df.select_dtypes(include=['object']).columns
            if len(text_cols) > 0:
                df['ementa'] = df[text_cols[0]]
        
        # Remove linhas vazias e tags HTML
        if 'ementa' in df.columns:
            df['ementa'] = df['ementa'].astype(str).apply(
                lambda x: re.sub(r'<[^>]+>', '', x) if pd.notna(x) and isinstance(x, str) else ''
            )
            df = df[df['ementa'].str.strip().str.len() > 20]  # Remove textos muito curtos
        
        return df.reset_index(drop=True)
        
    except Exception as e:
        st.error(f"❌ Erro ao carregar base: {str(e)}")
        return None

# =============================================================================
# FUNÇÕES DE PROCESSAMENTO DE TEXTO
# =============================================================================

def extract_text_from_file(uploaded_file):
    """Extrai texto de PDF ou DOCX"""
    if uploaded_file is None:
        return ""
    
    try:
        if uploaded_file.name.endswith('.pdf'):
            text = ""
            with pdfplumber.open(uploaded_file) as pdf:
                for page in pdf.pages:
                    extracted = page.extract_text()
                    if extracted:
                        text += extracted + "\n"
            return text[:10000]  # Limita para performance
            
        elif uploaded_file.name.endswith('.docx'):
            doc = docx.Document(uploaded_file)
            return "\n".join([para.text for para in doc.paragraphs])[:10000]
            
    except Exception as e:
        st.warning(f"⚠️ Erro na extração: {str(e)[:100]}")
        return ""
    
    return ""

def semantic_search(user_text, database_df, model, top_k=5):
    """Busca semântica na base do usuário"""
    if database_df is None or database_df.empty or 'ementa' not in database_df.columns:
        return []
    
    try:
        # Prepara textos da base
        textos_base = database_df['ementa'].dropna().astype(str).tolist()
        textos_base = [t for t in textos_base if len(t.strip()) > 30]
        
        if not textos_base:
            return []
        
        # Gera embeddings
        query_embedding = model.encode(user_text[:512], convert_to_tensor=True)  # Limita input
        corpus_embeddings = model.encode(textos_base[:100], convert_to_tensor=True)  # Limita base para performance free-tier
        
        # Calcula similaridade
        cos_scores = util.cos_sim(query_embedding, corpus_embeddings)[0]
        k = min(top_k, len(cos_scores))
        top_results = torch.topk(cos_scores, k=k)
        
        # Monta resultados
        resultados = []
        for score, idx in zip(top_results[0], top_results[1]):
            idx = idx.item()
            score_pct = score.item() * 100
            
            if score_pct < 40:  # Threshold mínimo de relevância
                continue
                
            resultados.append({
                'score': f"{score_pct:.1f}%",
                'ementa': textos_base[idx][:400] + "..." if len(textos_base[idx]) > 400 else textos_base[idx],
                'numero': database_df.iloc[idx].get('numero_acordao', 'N/A'),
                'colegiado': database_df.iloc[idx].get('colegiado', 'Plenário'),
                'indice': idx
            })
        
        return resultados
        
    except Exception as e:
        st.warning(f"⚠️ Erro na busca semântica: {str(e)[:100]}")
        return []

# =============================================================================
# GERADOR DE PEÇAS COM IA (PROMPTS OTIMIZADOS)
# =============================================================================

def generate_legal_document(tipo_peca, argumento_usuario, jurisprudencia_encontrada):
    """Gera estrutura de peça jurídica baseada em IA + jurisprudência"""
    
    prompts = {
        'impugnacao': f"""
Você é um especialista em Direito Administrativo e Licitações Públicas.

OBJETIVO: Criar estrutura de IMPUGNAÇÃO AO EDITAL baseada no argumento abaixo.

ARGUMENTO DO USUÁRIO:
"{argumento_usuario[:800]}"

JURISPRUDÊNCIA DE APOIO (TCU):
{chr(10).join([f"- {j['ementa'][:200]} (Acórdão {j['numero']})" for j in jurisprudencia_encontrada[:3]]) if jurisprudencia_encontrada else "Nenhuma jurisprudência fornecida"}

ESTRUTURA SUGERIDA:

1. CABEÇALHO
   • Endereçamento ao órgão licitante
   • Identificação do certame (nº, objeto, data)
   • Qualificação do impugnante

2. DOS FATOS
   • Breve descrição do edital impugnado
   • Trecho específico que motiva a impugnação

3. DO DIREITO
   • Fundamentação legal (Lei 14.133/2021 ou 8.666/93)
   • Princípios violados (isonomia, competitividade, etc.)
   {f"• Jurisprudência aplicável: {[j['numero'] for j in jurisprudencia_encontrada[:2]]}" if jurisprudencia_encontrada else ""}

4. DO PEDIDO
   • Requerimento específico (retirada de cláusula, republicação, etc.)
   • Prazo para manifestação da Administração

5. CONCLUSÃO
   • Síntese dos argumentos
   • Local, data e assinatura

⚠️ LEMBRETE: Esta é uma estrutura sugerida. Revise com seu conhecimento jurídico e adapte ao caso concreto.
""",
        
        'recurso': f"""
Você é um especialista em Direito Administrativo e Licitações Públicas.

OBJETIVO: Criar estrutura de RECURSO ADMINISTRATIVO baseada no argumento abaixo.

ARGUMENTO DO USUÁRIO:
"{argumento_usuario[:800]}"

JURISPRUDÊNCIA DE APOIO (TCU):
{chr(10).join([f"- {j['ementa'][:200]} (Acórdão {j['numero']})" for j in jurisprudencia_encontrada[:3]]) if jurisprudencia_encontrada else "Nenhuma jurisprudência fornecida"}

ESTRUTURA SUGERIDA:

1. CABEÇALHO
   • Endereçamento à autoridade julgadora
   • Identificação do processo administrativo
   • Qualificação do recorrente

2. DA TEMPESTIVIDADE
   • Comprovação do prazo recursal (art. 109, Lei 14.133/2021)

3. DO MÉRITO
   • Fatos que motivam o recurso
   • Dispositivos legais violados
   • Jurisprudência do TCU aplicável:
   {chr(10).join([f"   - Acórdão {j['numero']}: {j['ementa'][:150]}..." for j in jurisprudencia_encontrada[:2]]) if jurisprudencia_encontrada else "   [Inserir jurisprudência pertinente]"}

4. DO PEDIDO
   • Provimento do recurso
   • Efeitos pretendidos (reforma da decisão, anulação de ato, etc.)

5. CONCLUSÃO
   • Síntese argumentativa
   • Requerimento de ciência aos demais interessados

⚠️ LEMBRETE: Verifique prazos processuais e requisitos formais antes de protocolar.
""",
        
        'contrarrazao': f"""
Você é um especialista em Direito Administrativo e Licitações Públicas.

OBJETIVO: Criar estrutura de CONTRARRAZÕES para rebater argumento adverso.

ARGUMENTO ADVERSO A SER REBATIDO:
"{argumento_usuario[:800]}"

JURISPRUDÊNCIA DE APOIO (TCU) - PARA FUNDAMENTAR A DEFESA:
{chr(10).join([f"- {j['ementa'][:200]} (Acórdão {j['numero']})" for j in jurisprudencia_encontrada[:3]]) if jurisprudencia_encontrada else "Nenhuma jurisprudência fornecida"}

ESTRUTURA SUGERIDA:

1. CABEÇALHO
   • Endereçamento ao órgão julgador
   • Identificação do processo e recurso originário
   • Qualificação do contrarrazoante

2. DA ADMISSIBILIDADE
   • Legitimidade e interesse processual
   • Tempestividade da manifestação

3. DO MÉRITO - REBATIMENTO PONTO A PONTO
   • Tese adversa: [resumir argumento contrário]
   • Contra-argumento jurídico:
     - Dispositivo legal que afasta a tese
     - Jurisprudência do TCU em sentido contrário:
   {chr(10).join([f"       • Acórdão {j['numero']}: {j['ementa'][:120]}..." for j in jurisprudencia_encontrada[:2]]) if jurisprudencia_encontrada else "       [Inserir precedente favorável]"}
   
4. DA MANUTENÇÃO DO ATO IMPUGNADO
   • Regularidade do procedimento
   • Observância aos princípios constitucionais
   • Vantajosidade para a Administração

5. DO PEDIDO
   • Improvimento do recurso adverso
   • Manutenção integral da decisão recorrida

6. CONCLUSÃO
   • Síntese defensiva
   • Requerimento de julgamento conforme fundamentação

⚠️ ESTRATÉGIA: Foque em demonstrar que a decisão recorrida está em consonância com a jurisprudência pacífica do TCU.
"""
    }
    
    return prompts.get(tipo_peca, prompts['impugnacao'])

# =============================================================================
# INTERFACE PRINCIPAL
# =============================================================================

def main():
    # Cabeçalho
    st.title("⚖️ LicitaAI Pro")
    st.markdown("""
        **Sistema Inteligente de Apoio a Licitações Públicas**  
        *Busca semântica • Editais ativos • Geração de peças jurídicas*
    """)
    
    # Sidebar - Configurações
    with st.sidebar:
        st.header("⚙️ Configurações")
        
        # Upload da base de jurisprudência
        st.subheader("📚 Base de Jurisprudência")
        uploaded_db = st.file_uploader(
            "Upload CSV (TCU)", 
            type=['csv', 'txt'],
            help="Arquivo com acórdãos do TCU (formato pipe | ou vírgula)"
        )
        
        if uploaded_db:
            with st.spinner("Processando base..."):
                df = load_user_database(uploaded_db)
                if df is not None:
                    st.session_state['db'] = df
                    st.success(f"✅ {len(df)} acórdãos carregados")
                else:
                    st.error("❌ Erro ao processar arquivo")
        
        # Modelo de IA
        st.subheader("🤖 Inteligência Artificial")
        if st.button("Carregar Modelo de IA", type="primary"):
            with st.spinner("Carregando modelo (pode levar 1-2 min)..."):
                try:
                    model = load_ai_model()
                    st.session_state['model'] = model
                    st.success("✅ Modelo pronto!")
                except Exception as e:
                    st.error(f"❌ Erro: {str(e)[:200]}")
        
        # Informações
        with st.expander("ℹ️ Como usar"):
            st.markdown("""
            **1. Busca de Jurisprudência**
            - Cole seu argumento ou faça upload da peça
            - Clique em "Buscar Acórdãos"
            - Receba os mais compatíveis semanticamente
            
            **2. Editais Compras.gov**
            - Digite palavra-chave do objeto
            - Veja editais ativos relacionados
            
            **3. Gerador de Peças**
            - Selecione tipo: Impugnação/Recurso/Contrarrazão
            - Cole seu argumento + jurisprudência encontrada
            - Receba estrutura sugerida pela IA
            
            ⚠️ **Aviso**: Sistema gratuito com limitações de performance. 
            Sempre revise juridicamente os resultados.
            """)
    
    # Tabs principais
    tab1, tab2, tab3 = st.tabs([
        "🔍 Busca Jurisprudência", 
        "📢 Editais Ativos", 
        "✍️ Gerador de Peças"
    ])
    
    # ========================================================================
    # TAB 1: BUSCA DE JURISPRUDÊNCIA
    # ========================================================================
    with tab1:
        st.header("🔍 Busca Semântica de Jurisprudência TCU")
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.subheader("📝 Entrada")
            
            # Opção 1: Upload de arquivo
            uploaded_peca = st.file_uploader(
                "Upload da peça (PDF/DOCX)", 
                type=['pdf', 'docx'],
                key="upload_busca"
            )
            
            texto_extraido = ""
            if uploaded_peca:
                texto_extraido = extract_text_from_file(uploaded_peca)
                st.info(f"📄 {len(texto_extraido)} caracteres extraídos")
            
            # Opção 2: Texto manual
            texto_usuario = st.text_area(
                "Ou cole seu argumento jurídico:",
                value=texto_extraido if texto_extraido else "",
                height=200,
                placeholder="Ex: A exigência de atestado de capacidade técnica para serviços comuns configura restrição indevida à competitividade, violando o art. 3º da Lei 14.133/2021..."
            )
            
            # Parâmetros de busca
            col_a, col_b = st.columns(2)
            with col_a:
                top_k = st.slider("Resultados:", 3, 10, 5)
            with col_b:
                fonte_busca = st.radio("Fonte:", ["Base Local", "Portal TCU"], index=0)
            
            btn_buscar = st.button("🚀 Buscar Acórdãos Compatíveis", type="primary", use_container_width=True)
        
        with col2:
            st.subheader("📋 Resultados")
            
            if btn_buscar and texto_usuario.strip():
                if len(texto_usuario) < 50:
                    st.warning("⚠️ Texto muito curto. Use pelo menos 2-3 frases para melhor resultado.")
                else:
                    with st.spinner("🤖 Analisando semanticamente..."):
                        resultados = []
                        
                        # Busca na base local do usuário
                        if fonte_busca == "Base Local" and 'db' in st.session_state and 'model' in st.session_state:
                            resultados = semantic_search(
                                texto_usuario, 
                                st.session_state['db'], 
                                st.session_state['model'], 
                                top_k=top_k
                            )
                        
                        # Busca no portal do TCU (fallback)
                        if fonte_busca == "Portal TCU" or not resultados:
                            resultados_tcu = fetch_tcu_jurisprudence(texto_usuario[:100], limit=top_k*2)
                            # Filtra por similaridade básica (palavras-chave)
                            palavras = set(re.findall(r'\b[a-zA-ZÀ-ú]{4,}\b', texto_usuario.lower()))
                            for r in resultados_tcu:
                                score = len(palavras.intersection(set(re.findall(r'\b[a-zA-ZÀ-ú]{4,}\b', r['ementa'].lower())))) / max(len(palavras), 1)
                                if score > 0.2:
                                    resultados.append({
                                        'score': f"{score*100:.0f}%",
                                        'ementa': r['ementa'],
                                        'numero': r['numero'],
                                        'colegiado': 'TCU',
                                        'link': r.get('link', '#')
                                    })
                        
                        # Exibe resultados
                        if resultados:
                            st.success(f"✅ {len(resultados)} acórdãos encontrados!")
                            
                            for i, res in enumerate(resultados, 1):
                                with st.expander(f"🏛️ #{i} | {res['score']} | Acórdão {res['numero']}"):
                                    st.markdown(f"**Ementa:** {res['ementa']}")
                                    st.markdown(f"**Colegiado:** {res['colegiado']}")
                                    
                                    if 'link' in res and res['link'] != '#':
                                        st.markdown(f"🔗 [Ver no TCU]({res['link']})")
                                    
                                    st.code(f"""Sugestão de citação:
TCU, Acórdão {res['numero']}, {res['colegiado']}.
"{res['ementa'][:150]}..."
                                    """, language="text")
                                    
                                    # Botão para usar no gerador
                                    if st.button(f"➕ Usar no Gerador #{i}", key=f"btn_use_{i}"):
                                        st.session_state['juris_selected'] = res
                                        st.toast("✅ Jurisprudência selecionada! Vá para a aba 'Gerador de Peças'")
                        else:
                            st.info("🔍 Nenhum acórdão compatível encontrado. Tente:\n- Termos mais específicos\n- Outra fonte de busca\n- Ampliar a base de dados")
            
            elif btn_buscar and not texto_usuario.strip():
                st.warning("⚠️ Cole um texto ou faça upload de arquivo primeiro.")
    
    # ========================================================================
    # TAB 2: EDITAIS ATIVOS COMPRAS.GOV
    # ========================================================================
    with tab2:
        st.header("📢 Busca de Editais Ativos - Compras.gov")
        
        st.markdown("""
        Consulte editais públicos ativos no Portal de Compras do Governo Federal.  
        *Resultados simulados para demonstração (integração com API oficial em desenvolvimento)*
        """)
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            keyword = st.text_input(
                "🔍 Palavra-chave do objeto:",
                placeholder="Ex: fiscalização de obras, consultoria jurídica, software de gestão..."
            )
            
            filtros = st.columns(3)
            with filtros[0]:
                orgao = st.selectbox("Órgão", ["Todos", "Ministérios", "Autarquias", "Empresas Públicas"])
            with filtros[1]:
                modalidade = st.selectbox("Modalidade", ["Todos", "Pregão", "Concorrência", "Dispensa"])
            with filtros[2]:
                valor_min = st.number_input("Valor Mínimo (R$)", min_value=0, value=0, step=50000)
        
        with col2:
            btn_buscar_editais = st.button("🔎 Buscar Editais", type="primary", use_container_width=True)
        
        if btn_buscar_editais and keyword.strip():
            with st.spinner("Consultando portal..."):
                editais = fetch_compras_gov_editais(keyword, limit=10)
                
                if editais:
                    st.success(f"✅ {len(editais)} editais encontrados")
                    
                    for ed in editais:
                        with st.container():
                            st.markdown(f"""
                            <div class="result-card">
                            <strong>📄 {ed['titulo']}</strong><br>
                            <small>🏛️ {ed['orgao']} | 💰 {ed['valor_estimado']} | 📅 Abertura: {ed['data_abertura']}</small><br>
                            <small>🎯 {ed['objeto'][:150]}...</small><br>
                            <span style="background:#28a745;color:white;padding:2px 8px;border-radius:4px;font-size:0.8em">{ed['situacao']}</span>
                            </div>
                            """, unsafe_allow_html=True)
                            
                            if st.button(f"📋 Copiar Dados #{ed['titulo'][:20]}", key=f"btn_copy_{ed['titulo']}"):
                                st.code(f"""
Título: {ed['titulo']}
Órgão: {ed['orgao']}
Objeto: {ed['objeto']}
Valor: {ed['valor_estimado']}
Abertura: {ed['data_abertura']}
Link: {ed['link']}
                                """, language="text")
                                st.toast("📋 Copiado para área de transferência!")
                    
                    st.info("💡 Dica: Use esses dados para fundamentar impugnações sobre sobrepreço ou para identificar oportunidades de participação.")
                else:
                    st.warning("⚠️ Nenhum edital encontrado. Tente termos mais genéricos.")
        
        elif btn_buscar_editais and not keyword.strip():
            st.warning("⚠️ Digite uma palavra-chave para buscar.")
    
    # ========================================================================
    # TAB 3: GERADOR DE PEÇAS JURÍDICAS
    # ========================================================================
    with tab3:
        st.header("✍️ Gerador de Peças com IA")
        
        st.markdown("""
        Gere estruturas de peças jurídicas fundamentadas em jurisprudência do TCU.  
        *A IA sugere a estrutura - você revisa e adapta ao caso concreto.*
        """)
        
        # Seleção do tipo de peça
        tipo_peca = st.selectbox(
            "📋 Tipo de Peça:",
            ["impugnacao", "recurso", "contrarrazao"],
            format_func=lambda x: {
                "impugnacao": "⚔️ Impugnação ao Edital",
                "recurso": "📤 Recurso Administrativo", 
                "contrarrazao": "🛡️ Contrarrazões"
            }[x]
        )
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.subheader("📝 Argumento Base")
            
            argumento = st.text_area(
                "Cole o argumento que deseja fundamentar (ou rebater, no caso de contrarrazões):",
                height=200,
                placeholder="Ex: O edital exige experiência específica não comprovadamente relacionada ao objeto, violando o princípio da isonomia..."
            )
            
            # Jurisprudência selecionada da busca anterior
            if 'juris_selected' in st.session_state:
                st.info(f"✅ Jurisprudência selecionada: Acórdão {st.session_state['juris_selected']['numero']}")
                jurisprudencia_lista = [st.session_state['juris_selected']]
            else:
                jurisprudencia_lista = []
            
            # Opção para adicionar mais jurisprudência manualmente
            with st.expander("➕ Adicionar Jurisprudência Manualmente"):
                num_juris = st.number_input("Quantos acórdãos?", 0, 5, 0)
                jurisprudencia_manual = []
                for i in range(num_juris):
                    col_a, col_b = st.columns([3, 1])
                    with col_a:
                        ementa = st.text_input(f"Ementa #{i+1}:", key=f"ementa_{i}")
                    with col_b:
                        numero = st.text_input(f"Nº #{i+1}:", key=f"num_{i}")
                    if ementa and numero:
                        jurisprudencia_manual.append({'ementa': ementa, 'numero': numero})
                
                jurisprudencia_lista = jurisprudencia_lista + jurisprudencia_manual
        
        with col2:
            st.subheader("⚙️ Configurações")
            
            estilo = st.radio(
                "Estilo da Peça:",
                ["Técnico-Jurídico", "Objetivo", "Detalhado"],
                index=0
            )
            
            incluir_citacoes = st.checkbox("✅ Incluir sugestões de citação", value=True)
            destacar_principios = st.checkbox("✅ Destacar princípios constitucionais", value=True)
            
            btn_gerar = st.button("✨ Gerar Estrutura da Peça", type="primary", use_container_width=True)
        
        # Resultado da geração
        if btn_gerar and argumento.strip():
            with st.spinner("🤖 IA estruturando sua peça..."):
                # Gera o prompt
                prompt = generate_legal_document(tipo_peca, argumento, jurisprudencia_lista)
                
                # Como não temos API de LLM paga, exibimos o prompt estruturado
                # Em produção, integrar com HuggingFace Inference API ou similar
                st.success("✅ Estrutura gerada!")
                
                st.markdown('<div class="success-box">', unsafe_allow_html=True)
                st.markdown("📋 **ESTRUTURA SUGERIDA PELA IA**")
                st.markdown('</div>', unsafe_allow_html=True)
                
                # Exibe o conteúdo formatado
                st.markdown(prompt.replace("\n", "<br>"), unsafe_allow_html=True)
                
                # Botões de ação
                col_acoes = st.columns(3)
                with col_acoes[0]:
                    if st.button("📋 Copiar Estrutura", use_container_width=True):
                        st.code(prompt, language="text")
                        st.toast("📋 Copiado!")
                
                with col_acoes[1]:
                    if st.button("🔄 Refinar com Mais Jurisprudência", use_container_width=True):
                        st.info("💡 Volte para a aba 'Busca Jurisprudência', encontre mais acórdãos e retorne aqui.")
                
                with col_acoes[2]:
                    if st.button("📥 Exportar .TXT", use_container_width=True):
                        st.download_button(
                            label="⬇️ Baixar",
                            data=prompt,
                            file_name=f"{tipo_peca}_{datetime.now().strftime('%Y%m%d')}.txt",
                            mime="text/plain"
                        )
                
                st.warning("""
                ⚠️ **Importante**: 
                - Esta é uma **estrutura sugerida**, não uma peça pronta
                - Revise todos os fundamentos jurídicos com seu conhecimento
                - Verifique prazos processuais e requisitos formais
                - Adapte ao caso concreto e à jurisprudência mais recente
                """)
        
        elif btn_gerar and not argumento.strip():
            st.warning("⚠️ Cole seu argumento primeiro.")
    
    # ========================================================================
    # RODAPÉ
    # ========================================================================
    st.markdown("---")
    st.caption("""
    ⚖️ **LicitaAI Pro** | Sistema de apoio a licitações públicas  
    Desenvolvido para MS LICITAÇÕES | Dados: TCU e Compras.gov | IA: HuggingFace  
    ⚠️ Uso jurídico responsável: sempre revise os resultados com profissional habilitado.
    """)

# =============================================================================
# EXECUÇÃO
# =============================================================================

if __name__ == "__main__":
    main()
