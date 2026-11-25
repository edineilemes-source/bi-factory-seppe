# Biblioteca documental, leitura e contexto normativo na Modelagem — BI Factory SEPPE

**Entrega de código em branch:** feat/conhecimento-biblioteca-leitura-modelagem-20261125
**Data:** 25/11/2026
**Estado:** implementado no GitHub; instalação e homologação HTTP/PDF no Codespaces ainda não confirmadas.

## Objetivo e fluxo aprovado

1. Na seção **Conhecimento**, informar um assunto (ex.: CAPAG, empenho, balanço, receita, despesa) e pesquisar em portais oficiais. As referências têm URL, órgão e classificação. Links THOT sem extensão PDF deixam de ser anunciados como PDF sem comprovação.
2. Selecionar fontes, clicar em **Aprovar e incorporar**. O sistema só baixa PDFs oficiais quando aprovados. Uma referência HTML não é tratada como arquivo PDF.
3. Na **Biblioteca de documentos do projeto**, ver os documentos incorporados, confirmar se existe cópia efetiva no Codespaces, **Abrir PDF** em outra aba, **Baixar PDF**, **Excluir do acervo** (lixeira recuperável) ou **Restaurar**.
4. Marcar até seis PDFs disponíveis e clicar em **Ler e indexar arquivos**. O motor extrai texto localmente com **pypdf (BSD-3-Clause)**, limitado a 240 páginas por documento; PDF digitalizado sem texto selecionável fica identificado como **requer OCR**, nunca como "entendido".
5. O índice de evidências fica por projeto. Página, trecho, URL original, título, SHA-256, edição/vigência e data de leitura ficam vinculados. Consultar **CAPAG**, **poupança corrente**, **empenho**, **liquidez relativa**, **receita realizada**, etc., nos documentos indexados.
6. Na aba **Modelagem**, para cada campo da planilha, o componente **ModelKnowledgeContext** tenta localizar conceitos nos documentos do mesmo projeto e apresenta os trechos com página/origem. A opção **Pedir interpretação à IA local** usa esses trechos em RAG via Ollama, **apenas quando um modelo já está configurado**. Sem Ollama, a indexação e busca documental funcionam normalmente.

**Importante:** RAG não "treina o modelo": o índice documental é consultado a cada pergunta, e a IA recebe trechos recuperados. Classificações, vigência e fórmulas só serão aprovadas após conferência humana. Nenhuma fórmula é aplicada automaticamente às tabelas de Receita/Despesa.

## Fontes CAPAG e semântica

- Tesouro Transparente, <https://www.tesourotransparente.gov.br/temas/estados-e-municipios/capacidade-de-pagamento-capag>. CAPAG está associada a endividamento, poupança corrente e liquidez relativa na metodologia citada (Portaria Normativa MF 1.583/2023, com alteração posterior).
- Distinguir "poupança corrente" de "poupança líquida" e conferir **Portaria vigente para o exercício analisado** antes de calcular. Não supor que a fórmula se mantém estável entre edições.
- As fontes STN/MDF/MCASP/Planalto continuam cadastradas. A descoberta inicial usa portais selecionados; ainda não é mecanismo exaustivo semelhante ao Google, apenas interface de resultados com origem auditável.

## Estrutura de persistência operacional

- Originais: \`storage/working/projects/<projeto>/originals/<sha256>.pdf\`
- Lixeira reversível: \`storage/working/projects/<projeto>/trash/<sha256>.pdf\`
- Acervo e metadados: \`storage/working/projects/<projeto>/knowledge.json\`; entradas excluídas ficam marcadas com \`deleted_at\` para auditoria e deixam de aparecer na lista corrente.
- Índice documental: \`storage/working/projects/<projeto>/document_index.json\` com páginas e trechos associados aos originais. PDFs removidos são excluídos das consultas do mesmo projeto, embora o índice histórico continue armazenado para recuperação.
- Dependência OSS isolada: \`.git/knowledge-deps\` (pypdf). Nenhuma instalação ou download de modelo de IA é executado automaticamente.
- Os PDFs **não são automaticamente versionados ou enviados para o GitHub**, e não se misturam entre projetos.

## API implementada

| Método | Rota | Objetivo |
|---|---|---|
| GET | /api/projects/{id}/library | Acervo, disponibilidade real dos PDFs, indexação |
| GET | /api/projects/{id}/documents/{uuid}/view | Exibir cópia PDF local no navegador com SHA validado |
| GET | /api/projects/{id}/documents/{uuid}/download | Baixar cópia PDF armazenada |
| DELETE | /api/projects/{id}/documents/{uuid} | Remover logicamente do acervo e mover original para lixeira recuperável |
| POST | /api/projects/{id}/documents/{uuid}/restore | Restaurar PDF ou referência arquivada |
| POST | /api/projects/{id}/read-documents | Indexar até seis PDFs aprovados, com origem e página |
| GET | /api/projects/{id}/concepts?query=... | Recuperar evidências documentais para a Modelagem |
| POST | /api/projects/{id}/interpret | Interpretação opcional RAG/Ollama, sempre pendente de revisão |

## Limitações e segurança

- Sem IA local, **não** há interpretação semântica geral nem formulação assistida; há indexação textual e trechos recuperáveis, com correspondência de termos.
- PDFs escaneados, criptografados, sem texto selecionável ou acima dos limites são sinalizados; OCR não é executado automaticamente. A indexação inicial tem limite de páginas e caracteres por página.
- A integridade SHA-256 é checada antes de abrir ou ler cada original; links externos não são usados como caminho de arquivo no servidor.
- A exclusão é recuperável, com trilha de auditoria. Indexação existente fica indisponível para documentos removidos.
- Páginas HTML oficiais podem ser arquivadas como referências; a leitura automática implementada nesta entrega é **somente PDF**.
- O catálogo de Produtos, o Editor Visual e os dados fiscais não são alterados.

## Instalação e verificação

\`\`\`bash
cd /workspaces/bi-factory-seppe && \
git fetch origin fix/conhecimento-installer-autoteste-preservacao-20261124 feat/conhecimento-biblioteca-leitura-modelagem-20261125 && \
git show origin/feat/conhecimento-biblioteca-leitura-modelagem-20261125:scripts/instalar_biblioteca_ia_modelagem.py | python3 -
\`\`\`

O instalador prepara modificações sem mudar a branch, faz backup em \`.git/backups\`, concilia arquivos locais por merge de 3 vias, injeta um componente na área Modelagem, instala somente pypdf em diretório isolado (se necessário), roda testes Python + build React e então reinicia **apenas a API 8505** conhecida. Se existir conflito não conciliável, aborta antes de gravar. Não reinicia ou modifica a 8507 experimental.

**Testes automatizados**: workflow \`.github/workflows/bi-knowledge-official.yml\` executa sintaxe Python, testes de pesquisa, biblioteca e exclusão/restauração, integração da modelagem e compilação React. Execuções completas do Codespaces, navegador e download de PDF oficial permanecem pendentes.
