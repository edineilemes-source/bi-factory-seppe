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

## 2026-11-10 — Missão 3: pré-validação operacional do backup

- Branch confirmada `feat/unificar-8504-8510`; HEAD/upstream armazenado
  `df31b6adb699cdbd7e56efeac579517540ae5290`, 0/0; sem fetch/consulta viva remota.
- Decisão **BLOQUEADO para ensaio integral real**. Storage tem 2.646.921.208 bytes
  (2.524,30 MiB), 37 arquivos/18 diretórios; excede 256 MiB em 9,86 vezes.
  Dois SQLite identificados por assinatura, sem abrir conexão operacional.
- Gravadores identificados no código: API/editor, Streamlit/repositório SQLite,
  prepared/transformação, MVP e ETL fiscal. Nenhum entrypoint BI ou escuta nas
  portas esperadas observado no namespace local; não prova estado externo.
- `artifacts/staged` é origem fora de storage configurada e ausente localmente;
  substituições de caminhos e referências persistidas externas seguem pendentes.
- Captura exige suspensão global de escritas; não há barreira validada que
  preserve disponibilidade. Procedimento com captura, verificação, restauração
  isolada e rollback proposto em `docs/missoes/RELATORIO_PREVALIDACAO_BACKUP.md`.
- PASS: 20 testes sintéticos (0,97 s), pip check e diff --check. Sem teste real.
- Somente documentação alterada; dados e não rastreados preservados. Sem backup
  real, chaves operacionais, envio, alteração/parada de serviços, commit ou push.
- Próximo passo: resolver capacidade/formato, barreira de escritas, inventário
  externo e custódia/destino/RPO/RTO antes de autorizar captura operacional.

## 2026-11-10 — Missão 4: arquitetura de backup e recuperação

- Branch `feat/unificar-8504-8510`, HEAD/upstream armazenado
  `b61f7fde3b63bb58e43c9eb3c3914cf117f76e1a`, 0/0; sem fetch/consulta viva remota.
- Preparação offline: política A/B/C/D em `config/backup/policy.json`, planejador
  `scripts/backup_architecture.py`, template comentado de agendamento em
  `ops/backup/schedule.cron.disabled`, testes e relatório obrigatório
  `docs/missoes/RELATORIO_ARQUITETURA_BACKUP.md`.
- Git mirror/bundle para código e Restic BSD-2-Clause candidato para B+C;
  execução, remoto e agenda desativados. Restic não instalado nem executado.
  Produtor de staging/barreira/runner continuam pendentes, não entregues como
  executor operacional. Ferramenta anterior e seu limite preservados.
- Propostos: 14 diários/8 semanais/12 mensais; RPO 24 h, RTO código 2 h e
  completo 8 h, sujeitos a aceite e medição. Retenção só dry-run; sem limpeza.
- PASS: 47 testes sintéticos (20 anteriores + 27 novos), 4,35 s; pip check,
  CLI offline e diff --check. Simulação streaming >4 GiB não é ensaio Restic.
- Decisão **BLOQUEADO para produção**: consistência global, origens externas,
  revisão de segredos/histórico, custódia/destinos e recuperação real pendentes.
- Alterações anteriores destes documentos e não rastreados preservados. Nenhum
  backup real, conexão a banco operacional, transferência, serviço persistente,
  interrupção, exclusão, staging Git, commit ou push. Próxima ação: homologar
  executor/barreira em fixtures antes de qualquer ativação operacional.

## 2026-11-11 — Correção inicial de navegação no editor (GitHub, não homologada)
- Branch isolada `fix/editor-visual-navegacao-pastas-20261111`, commit inicial `2a451da584e5b3b5e83f1512d637d1260fa9a39d`.
- `web/bi_factory/src/main.jsx`: seletor de pasta de novo produto mostra caminho hierárquico (`Finanças Públicas / Receitas`); removidos controles externos de alternância Visualizar/Voltar e Fechar que recriavam iframe e podiam perder edição não salva.
- Nenhum arquivo de dados, produto, layout ou banco alterado. Sem merge e sem sincronização automática com Codespaces.
- Testes locais e E2E: NÃO EXECUTADOS; requer CI e homologação no ambiente Codespaces. Tela branca de produtos concluídos, bordas, undo e restante do editor ainda pendentes; não declarar resolvidos.

## 2026-11-11 — Ampliação da correção do editor visual (GitHub, ainda não homologada)
- Branch `fix/editor-visual-navegacao-pastas-20261111`; commits de código `9a165a60`, `4cb8ea59`, `ba77e864`, workflow `55b07a34`.
- Editor GridStack: controles de fonte/negrito/itálico; sincronização do texto editado com painel; borda transparente/colorida/espessura; remover título do objeto texto; desfazer básico com histórico limitado; limpar página com confirmação; fechar editor com evento ao React.
- React: fechamento contextual do editor e preservação do iframe ao salvar para evitar remontagem/perda de edição. Cadastro mostra caminho hierárquico das pastas.
- CI de build React e sintaxe JavaScript adicionado; resultado ainda não confirmado. Nenhum dado persistido alterado no GitHub. **Não houve atualização do Codespaces nem validação da porta 8504.**
- Pendente: homologar todos os fluxos, tela em branco de produtos fechados, desfazer para todas as mutações, estilos no modo de visualização, retorno de navegação e persistência real; não declarar produção pronta.

## 2026-11-10 — Missão 5: homologação sintética incremental

- Branch confirmada `feat/unificar-8504-8510`; HEAD/upstream armazenado
  `b09fffaf2b341b71b3c2f10f7840f79448080312`, 0/0. Sem fetch ou consulta viva
  do remoto do projeto. Terminal local disponível; sem commit/push.
- **APROVADO exclusivamente no laboratório sintético; produção BLOQUEADA.**
  Restic **0.19.1**, BSD-2-Clause (LICENSE da tag), realmente executado após
  SHA-256 do download conferido com SHA256SUMS oficial. Sem verificação GPG
  independente ou instalação persistente; binário privado em /tmp.
- Criado `scripts/homologate_backup_synthetic.py`, sem origens operacionais
  configuráveis: mkdtemp privado, ambiente de subprocessos limitado, sem rede,
  limpeza ou integração com serviços. Relatório:
  `docs/missoes/RELATORIO_HOMOLOGACAO_BACKUP.md`.
- PASS: 18 verificações em 33,819 s / 36 subprocessos: arquivo esparso real de
  2.164.260.864 bytes, incremental, terceira captura sem novos blocos, duas versões
  restauradas/hash conferido, check completo, senha incorreta, destino existente,
  snapshot parcial, mudança concorrente, corrupção e backend local ausente.
- Protótipo flock multiprocesso SQLite+JSON: 40 gerações, 31 capturas coerentes,
  recuperação Restic conjunta e liberação após exceção. Sem barreira, intervalo
  inconsistente observado; sem integração operacional. Git bundle sintético
  recuperou duas branches, duas tags e versões com refs/OIDs iguais e fsck válido.
- PASS: 47 testes anteriores em 5,47 s, pip check e diff --check. Primeira
  tentativa parou na permissão somente leitura de pack copiado; corrigida apenas
  a cópia sintética de corrupção e repetida a bateria inteira.
- Nenhuma captura/leitura de conteúdo operacional, alteração em bancos existentes,
  módulos BI, serviços ou não rastreados anteriores. Nenhum envio, exclusão,
  agendamento, staging ou commit do projeto. Laboratórios preservados em /tmp,
  não duráveis. Flags execution_enabled/remote_enabled/schedule_enabled: false.
- Produção exige adesão de todos os gravadores, crash recovery/timeout, staging
  selado/runner e catálogo de gerações aceitas, inventário externo/segredos,
  custódia/destinos/capacidade, reconstrução completa e RPO/RTO representativos.
  Restic retornar zero e inventário antes/depois não provam consistência global.

## 2026-11-12 — Consolidação do Editor Visual e inicializador

- Corrigido incremento do campo version para produtos legados sem versão.
- Salvamento do layout retornou HTTP 200.
- Persistência confirmada após fechar e reabrir o produto teste 5.
- Inicializador scripts/start_bi_factory_codespaces.sh criado.
- Portas 8505 e 8506 verificadas.
- Rotas /, /api/overview, /visual-editor/index.html e
  /echarts-studio.html responderam com sucesso.
- Inicializador validado com serviços já ativos.
- Inicialização com serviços desligados ainda não homologada.
- Integração dos commits remotos concluída sem conflitos.
- Dados operacionais preservados.
- Implantação na Hostinger permanece adiada.

## 2026-11-13 — Alterações aguardando homologação
- PR draft #4, branch `homolog/cadastro-filtros-echarts-20261113`: cadastro, pastas inline, projeto/responsável técnico, prévia após layout salvo, aviso ECharts e isolamento de filtros por objeto.
- Código enviado ao GitHub em branch isolada; **não** publicado no Codespaces, não integrado na branch principal e sem testes funcionais confirmados.
- Antes de liberar: conferir divergências do Codespaces, build do frontend, sintaxe JS do editor, teste de persistência dos metadados, hierarquia de pastas e teste de Despesa/Receita.


## 2026-11-16 — Correção isolada de Novo produto (pendente homologação)
- Branch de correção: fix/novo-produto-ficha-isolada-20261116; código commit 4ccbce8.
- Corrigido web/bi_factory/src/main.jsx: Novo produto descarta a seleção visual da ficha anterior, fecha overlays e abre somente o formulário novo; ficha selecionada só aparece fora do modo criação; botão de salvar fica bloqueado durante requisição e exige nome.
- Dados e API não alterados. Inspeção estática do diff realizada; build, teste de interface e implantação no Codespaces ainda NÃO confirmados. Branch local teste/cadastro-filtros-20261113 não existe no remoto; preservar alterações locais e reconciliar antes de aplicar.

- Ponte de aplicação segura proposta em scripts/bi_factory_patch_agent.py (commit c16cbe9), restrita a um patch de web/bi_factory/src/main.jsx; instalação local e homologação pendentes. Não confundir código versionado com agente em execução.

## 2026-11-16 — Recuperação e testes integrados
- Branch `fix/recuperacao-homologacao-20261116`, base `d094880` (inclui correção `4ccbce8` e ponte `c16cbe9`).
- Clone real do GitHub neste ambiente; não é o terminal do Codespaces operacional.
- Endereço externo informado respondeu HTTP 401 com `www-authenticate: tunnel`, em vez de 404, na consulta sem autenticação. Isso confirma barreira de autenticação do túnel, não a disponibilidade da UI autenticada nem a causa histórica do 404.
- GitHub CLI local sem login; navegador em github.com/codespaces redirecionou ao login. Conector permite código, mas não expõe API/SSH de Codespaces. Implantação e inspeção remota dependem dessa autenticação.
- Cadastro: trava síncrona de envio e encerramento do draft após confirmação do POST, mesmo quando refresh do catálogo falha; evita novo envio de um produto já persistido.
- Porta padrão Vite/npm unificada em 8506. Monitor passa a iniciar também o agente de patch existente, mantendo as restrições de branch/arquivo. Não amplia permissões de patch.
- API não abre mais aba automaticamente pelo devcontainer; frontend continua encaminhado, sem alteração de visibilidade.
- Testes integrados adicionados em `tests/e2e/test_product_flow.py`, com todas as constantes de storage redirecionadas a fixture temporária; workflow `.github/workflows/product-flow.yml`.
- PASS local: build React, sintaxe Python/Bash, diff --check. BLOCKED local: Chromium impedido por socket Operation not permitted; execução E2E será feita no Actions. Não declarar testes E2E aprovados até resultado do workflow.
- Nenhum dado operacional alterado. Reinício/rebuild, encaminhamento autenticado e implantação operacional ainda não verificados.


### Resultado confirmado da execução de 2026-11-16
- Código publicado: `bc033a0c0241ce38835b93031b780429d770bfd3`; ajuste de runner `34409549c2f00f122420bdca6e41964a8ea1383b`; PR #16, base fix/novo-produto-ficha-isolada-20261116.
- PASS: 5 testes E2E reais no Chromium/React/API em fixture isolada, Actions run 43906062599, job 133435093946. Abrange criação consecutiva, estados limpos, IDs/códigos distintos, edição/reabertura, layout, repetição, erro API e falha de refresh pós-POST. Verificação do editor e build também PASS, run 43906062601.
- PASS adicional local: quatro verificações da API HTTP real em fixture: dois cadastros; edição/reabertura; layout com preservação do primeiro produto; persistência em disco.
- A primeira execução CI falhou na instalação porque ubuntu-latest passou a Ubuntu 26.04, incompatível com Playwright 1.58; corrigido fixando ubuntu-24.04, segunda execução aprovada.
- BLOCKED operacional (3 grupos): acesso externo autenticado; implantação no Codespaces; persistência após restart/rebuild. Sem alegação de resolução do 404 histórico. Automação CI comprovada; monitor/agentes apenas alterados no código, sem prova de instalação remota.
- Tentativa de autenticação no navegador escolheu Google; inspeção seguinte bloqueada por revisão automática por risco de acesso a conteúdo privado Google fora do escopo. Nenhuma verificação posterior nem contorno executado.
- Próxima ação indispensável: autorização para concluir autenticação Google exclusivamente destinada ao GitHub/Codespaces; então inspecionar estado remoto e aplicar/testar sem sobrescrever trabalho local. Nenhum dado operacional modificado.


## 2026-11-16 — Implantação e acesso externo confirmados
Aplicação e Produtos acessíveis com porta privada; main.jsx implantado (blob da298ea), recuperação automática do frontend comprovada e 11 JSONs preservados. Cinco E2E aprovados no CI. Reinício completo/rebuild e instalação persistente do agente ainda pendentes. Detalhes: docs/missoes/RECUPERACAO_OPERACIONAL_20261116.md.


## 2026-11-16 — Agente permanente autorizado
Usuário autorizou especificamente instalar o agente de patches restrito e iniciar automaticamente no Codespaces. Preparados monitor com fechamento do descritor de lock nos filhos e lock próprio em .git, agente singleton com estado em .git e manutenção de todas as restrições de aplicação anteriores. Nove testes isolados passaram; Bash/Python/diff aprovados. Instalação e teste de recuperação operacional em andamento; não declarar rebuild aprovado sem ensaio. Arquivos: scripts/autostart_bi_factory_codespaces.sh, scripts/bi_factory_patch_agent.py, tests/test_patch_agent_guards.py, .github/workflows/agent-guards.yml. Base 0eab87f; sem dados operacionais alterados.


## 2026-11-16 — Instalação permanente e reinício comprovados
Instalados agente/monitor e984357 no Codespaces após autorização específica. Estado migrado para .git e singleton ativo. Nove testes de guardas passaram localmente, no Codespaces e em Actions 43911070572; cinco E2E em 43911070390 também aprovados. Parada completa observada, reinício pelo botão oficial e inicialização automática de monitor/agentes/API/Vite comprovados, sem comandos manuais para iniciar serviços. Hashes de 11 JSONs e main.jsx preservados. Issue #17 rejeitada conforme esperado após reinício, encerrada como teste aprovado. Aplicação externa/Produtos voltou em porta privada. Rebuild do devcontainer permanece NÃO ENSAIADO. Detalhes: docs/missoes/AGENTE_PERMANENTE_20261116.md.


## 2026-11-16 — Exclusão com confirmação interpretada incorretamente
- Base GitHub 7ae0426, branch fix/recuperacao-homologacao-20261116 / PR #16. Inspeção: delete_product retorna item.product_id e deleted, mas apiPost exige item.id; exclusão pode ser efetivada e a interface acusar falha antes do refresh.
- Correção: validar contrato específico de exclusão; retirar linha/ficha após confirmação; falha posterior de refresh não oferece repetição de exclusão já concluída. Três testes E2E sintéticos adicionados para sucesso, refresh pós-exclusão falho e erro de API.
- Testes novos ainda aguardam CI. Sem executor/navegador disponíveis nesta sessão; não houve implantação nem exclusão operacional. Relato de Visualizar ainda sem causa confirmada; verificar proxy /visual-editor e carregamento do iframe no Codespaces antes de declarar resolvido.
- Atualização do ensaio anterior: Full Rebuild executado; novo hostname e API automática confirmados, aplicação externa abriu. Conferência de 41 arquivos interrompida após progresso 20/41 por perda do ambiente. registry.json divergiu (751 -> 1151 bytes), mantido intacto; catálogo mostra produto adicional teste 6. Origem da alteração não comprovada. Não declarar validação completa nem perda de dados.
