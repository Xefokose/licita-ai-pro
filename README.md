# ⚖️ LicitaAI Pro

Sistema inteligente de apoio a licitações públicas, desenvolvido para **MS LICITAÇÕES**.

## ✨ Funcionalidades

1. **🔍 Busca Semântica de Jurisprudência**
   - Compare seus argumentos com acórdãos do TCU usando IA
   - Upload de base própria (CSV) ou busca no portal TCU
   - Resultados com % de compatibilidade e sugestão de citação

2. **📢 Editais Ativos - Compras.gov**
   - Consulte licitações públicas por palavra-chave
   - Filtros por órgão, modalidade e valor
   - Dados prontos para fundamentar impugnações

3. **✍️ Gerador de Peças com IA**
   - Estruturas sugeridas para: Impugnação, Recurso, Contrarrazão
   - Fundamentação automática com jurisprudência selecionada
   - Exportação em texto para edição final

## 🚀 Como Usar

1. Acesse o link do Streamlit Cloud (fornecido após deploy)
2. Na barra lateral, faça upload da sua base de acórdãos (CSV)
3. Clique em "Carregar Modelo de IA" (aguarde 1-2 min na primeira vez)
4. Use as abas superiores para navegar entre as funcionalidades

## 📁 Formato da Base de Dados (CSV)

O sistema aceita arquivos com delimitador `|` (pipe) ou `,` (vírgula).

Colunas recomendadas:
- `ementa` ou `texto_decisao`: conteúdo do acórdão
- `numero_acordao`: número do acórdão
- `colegiado`: Plenário, 1ª Câmara, 2ª Câmara, etc.

Exemplo:
