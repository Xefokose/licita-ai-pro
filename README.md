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

Exemplo: numero_acordao|ementa|colegiado
387/2024|É possível a inversão de fases...|Plenário

## ⚠️ Limitações do Plano Gratuito

- **Performance**: Primeira execução pode levar 2-3 minutos
- **Cache**: Modelo recarrega após 1h de inatividade
- **Base de dados**: Máximo recomendado: 1.000 acórdãos para performance
- **Privacidade**: Não envie dados sigilosos (CPF, valores exatos, nomes)

## 🔧 Desenvolvimento

- Framework: Streamlit (Python)
- IA: sentence-transformers (HuggingFace)
- Deploy: Streamlit Cloud (gratuito)
- Dados: TCU Portal + Compras.gov (scraping leve)

## 📞 Suporte

Desenvolvido para **MICHEL SILVA SACRAMENTO**  
MS LICITAÇÕES | CNPJ: 43.298.867/0001-88
