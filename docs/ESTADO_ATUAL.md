# ESTADO ATUAL — BI Factory SEPPE

> Documento canônico de continuidade. Atualizado em 2026-11-10. **Não confundir observações do Codespaces com estado confirmado do GitHub.**
> Repositório: `edineilemes-source/bi-factory-seppe`. Branch de desenvolvimento informada: `feat/unificar-8504-8510`.

## Regra de retomada (obrigatória)
1. Ler **este arquivo**, `AGENTS.md`, o último registro em `docs/DIARIO_TECNICO.md` e o código dos arquivos afetados **antes** de propor mudanças.
2. Verificar `git status -sb`, `git log -5 --oneline`, branch e divergência local/remoto **no Codespaces** antes de editar ou sincronizar. O conector GitHub **não acessa** terminal, arquivos não commitados, processos ou bancos locais.
3. Registrar cada entrega: objetivo, arquivos alterados, decisão, testes executados e resultados, pendências, SHA local e remoto, eventual migração de dados. Atualizar este arquivo na mesma entrega.
4. Nunca afirmar que teste passou sem resultado observável. Separar: **confirmado**, **relatado**, **pendente**.
5. Nunca sobrescrever dados, apagar arquivos, fazer reset, merge, rebase, commit ou push silenciosamente. Para mudanças destrutivas ou sincronização com risco de conflito, apresentar diagnóstico e obter aprovação.
6. O código e os dados reais prevalecem sobre esta documentação quando houver divergência; **corrigir a documentação**, não inventar estado.

## Mapa do sistema (confirmado por inspeção do GitHub)
| Área | Local | Papel |
|---|---|---|
| UI principal React/Vite | `web/bi_factory/src/main.jsx` | Produtos, ficha, edição e iframe do editor |
| Configuração Vite | `web/bi_factory/vite.config.js` | Proxy de `/api`, `/visual-editor`, `/echarts-studio.html` para 8505 |
| UI do editor | `prototypes/editor-visual/index.html` | GridStack 10.3.1, ECharts 5, figuras livres, filtros, edição e salvamento |
| API unificada | `scripts/serve_bi_factory_api.py` | API Python, catálogo, relatórios e ponte com editor |
| API/serviço do editor | `prototypes/editor-visual/server.py` | Rotas de produtos e layouts, servidor standalone opcional 8510 |
| Catálogo | `scripts/bi_factory_catalog.py` | Operações JSON com gravação atômica |
| Cadastro de produtos | `storage/information_products/registry.json` | Dados de catálogo **se o arquivo existir no ambiente** |
| Pastas | `storage/information_products/folders.json` | Hierarquia |
| Metadados adicionais | `storage/information_products/metadata/` | JSON por produto |
| Layouts | `storage/information_products/layouts/` | JSON por produto |
| Componentes compartilhados | `storage/information_products/shared_components.json` | Biblioteca |
| Painéis/projetos | `storage/dashboard_projects/products/` | JSON por produto |
| Dados fiscais | `storage/reports/official_fiscal/` | Relatórios e CSV usados em gráficos |
| Testes do editor em CI | `.github/workflows/bi-editor-tests.yml` | **Somente na branch isolada de testes**, não nesta branch |

**Atenção:** caminhos de armazenamento indicam destinos no código, **não** provam que dados estejam presentes no GitHub. Não há inventário verificado de conteúdo, tamanho, backups ou sincronização desses diretórios.

## Ambiente conhecido
- Codespaces: `/workspaces/bi-factory-seppe`.
- Em testes manuais recentes: UI Vite na **8506**, API Python na **8505**; a configuração versionada de Vite declara **8504** por padrão. Confirmar comandos/portas reais em execução a cada retomada, sem presumir que serviços estejam ativos.
- Editor usado nos testes: `http://127.0.0.1:8506/visual-editor/index.html`.
- Dependências de testes instaladas **localmente e fora do repositório** em `/tmp/bi-browser-test`, sujeitas a perda ao recriar ambiente.
- Portas do Codespaces devem permanecer **privadas**. Para acessar, verificar a aba **PORTS**, encaminhamento e serviço em execução.
- Não há ferramenta conectada nesta conversa que execute comandos no terminal do Codespaces. GitHub permite ler e alterar arquivos **versionados**, não inspecionar estado local não enviado.

## Validações manuais reportadas (sessão 2026-11-10)
| Verificação | Resultado reportado |
|---|---|
| UI principal e `/api/overview` | HTTP 200 |
| Editor e bibliotecas GridStack/ECharts | HTTP 200, carregadas |
| Inserção de texto e título | PASS |
| Inserção de retângulo, quadrado, losango, elipse, seta e linha | PASS; figuras em `[data-shape-id]`, fora de `.grid-stack-item` |
| Arrastar objeto GridStack | PASS; coordenadas alteradas |
| Arrastar retângulo | PASS; posição (265,115) → (395,195) |
| Controle de redimensionamento | **Detectado**, não testado funcionalmente |
| Camadas | Figura `z-index:1001`, GridStack `z-index:1`; **não** prova funcionamento de enviar atrás |
| Erros JavaScript durante os testes acima | Nenhum reportado |
| Redimensionamento, z-order interativo, gráficos reais, filtros dinâmicos, persistência na API | **PENDENTE** |

## Divergência local/remoto conhecida
- Usuário confirmou commit **local** `607951a` (`fix: corrigir sintaxe JavaScript do editor visual`) na branch de desenvolvimento, sem push.
- No GitHub, a versão consultada de `prototypes/editor-visual/index.html` **ainda tinha** a concatenação inválida `'Produto +product.code+' ...`; a correção local é `'Produto ' + product.code + ...`.
- **Não fazer pull/rebase/merge automaticamente**: primeiro conferir `git status` e histórico do Codespaces. Este documento versionado pode criar divergência entre histórico local e remoto.
- Uma branch separada `test/editor-playwright-ci` foi criada com a correção de sintaxe aplicada nela e uma suíte Playwright no GitHub Actions; commits `805b758` e `5140bca`. **Execução do workflow e aprovação dos testes não verificadas.** A suíte testa uma página estática isolada, não substitui integração real com API e dados.

## Pendências prioritárias (ordem)
1. **Reconciliação segura** do estado Codespaces versus GitHub: branch, commits locais, arquivos alterados/não rastreados, presença de dados e backups, portas e processos. Não excluir nada.
2. Estabilizar inicialização do ambiente e documentação dos comandos de subida, com smoke test único e relatório consolidado.
3. Testar/ajustar editor embutido na ficha, figuras (resize e z-order), KPI sem moldura e integração de retorno ao mesmo gráfico ECharts.
4. Validar filtros por dimensão separados e atualização real de gráficos.
5. Testar salvamento e recuperação **na API**, com produto de teste isolado, sem tocar produtos reais.
6. Consolidar suíte E2E no fluxo de desenvolvimento **após** validação do CI e da configuração de servidor.

## Regras do produto
- Somente dependências Open Source com licença identificável.
- Não recriar ECharts: integrar estúdio existente; dimensões e medidas são definidas no Charts.
- Preservar produtos, pastas, metadados, gráficos e layouts existentes.
- Editor visual integrado à ficha de produto; não perder componente ao alternar Editor ↔ Charts.
- Evitar testes fragmentados: executar bateria consolidada e entregar relatório PASS/FAIL/BLOCKED.

## Atualização obrigatória
A cada entrega, atualizar: data, branch/SHA, resumo, caminhos, testes reais, dados afetados, pendências e próxima ação. Registrar detalhes cronológicos em `docs/DIARIO_TECNICO.md`. Se não houver acesso ao Codespaces, registrar explicitamente **não verificado localmente**.

## 2026-11-10 — Backup seguro e recuperação isolada (confirmado localmente)

- Nesta missão houve acesso real ao terminal de `/workspaces/bi-factory-seppe`;
  a nota anterior sobre ausência de terminal descreve a sessão anterior.
- Branch confirmada `feat/unificar-8504-8510`, SHA
  `60e34d8f7e23b58b5142eb59ad18ba1ab6df9e3c`; HEAD e upstream **localmente
  armazenado** coincidem (0/0). Sem fetch/consulta remota; não prova sincronização
  atual com o servidor GitHub. Alterações desta entrega não commitadas.
- Entregue `scripts/secure_backup.py` com dependência opcional em
  `requirements-backup.txt`, captura de toda `storage`, SQLite via backup API em
  cópia privada, AES-256-GCM, manifesto SHA-256 e restauração em destino novo externo.
- Consistência global exige pausa explícita de todos os gravadores; inventário
  antes/depois detecta mudanças. Sem mudança nos módulos operacionais existentes.
- Preparação local cifrada para `edineilemes-source/bi-factory-seppe-backup`,
  com envio desabilitado e sem qualquer operação de rede/Git.
- PASS: 17 testes sintéticos direcionados, ciclo CLI, integridade, corrupção,
  chave errada, WAL, isolamento, preservação, limites e falha de I/O; pip check
  e git diff --check. Nenhum backup/restauração de dados operacionais executado.
- Arquivos não rastreados existentes foram preservados. Limite de 256 MiB e
  10.000 entradas; chaves ficam fora do checkout, separadas dos backups.
- Pendentes: ensaio operacional com pausa planejada, inventário de caminhos
  externos, custódia de chaves, RPO/RTO, retenção e confirmação de privacidade do
  repositório de backup. Sem commit/push nem migração de dados.
- Relatório e procedimento: `docs/missoes/RELATORIO_BACKUP_SEGURO.md`.

## 2026-11-10 — Missão 2: auditoria do backup (confirmado localmente)

- Branch `feat/unificar-8504-8510`, HEAD `e2ddc98e1d189d2c10b930c04c8eb5d2668b1ca8`; upstream
  armazenado igual, 0/0. Estado vivo do GitHub não consultado; sem fetch.
- Auditoria APROVADA exclusivamente para os oito arquivos listados em
  `docs/missoes/RELATORIO_AUDITORIA_BACKUP.md`, sem publicação nesta execução.
- Corrigidos requisito com patch de segurança (cryptography 46.0.7) e captura
  de nomes recusados pelo verificador; alias de raiz também rejeitado.
- PASS: 17 testes originais antes, 20 após correções; pip check e diff --check.
  Triagem dos candidatos sem indícios detectados de segredos/dados pessoais.
- Arquivos operacionais não rastreados excluídos da seleção e preservados.
  Nenhum módulo do BI alterado, backup real, parada, commit ou push.
- Pendentes: ensaio operacional, custódia, retenção/RPO/RTO, origens externas,
  revisão abrangente de advisories e confirmação do remoto privado.
