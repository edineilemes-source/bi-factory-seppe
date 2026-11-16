# DIÁRIO TÉCNICO — BI Factory SEPPE

## 2026-11-10 — Marco de continuidade
**Objetivo:** impedir perda de contexto entre conversas, sessões e ferramentas.

**Decisão:** GitHub é o registro versionado canônico de código, arquitetura, decisões, testes e pendências; dados locais e estado operacional do Codespaces exigem verificação separada. `docs/ESTADO_ATUAL.md` é a primeira leitura em toda retomada.

**Observações anteriores confirmadas por saída do terminal enviada pelo usuário:** inserção dos objetos, movimentação de GridStack e retângulo, presença de controle de resize e ausência de erros JS nesses testes. Não há comprovação de resize funcional, z-order interativo, filtros reais ou persistência API.

**GitHub:** branch de desenvolvimento `feat/unificar-8504-8510`. Correção JS em commit local `607951a`, ainda não confirmada no remoto. Branch de testes `test/editor-playwright-ci` criada com correção isolada e workflow Playwright; resultado de execução não confirmado.

**Riscos abertos:** divergência local/remoto; dados não versionados em `storage/`; configuração Vite 8504 versus porta 8506 observada; dependências Playwright instaladas em `/tmp`; ausência de terminal remoto nesta integração.

**Próxima ação:** inventário não destrutivo do Codespaces, reconciliar histórico sem perda de dados, consolidar inicialização e executar testes integrados.

### Modelo obrigatório para entradas futuras
- Data/hora e objetivo
- Branch e SHA local/remoto
- Arquivos e dados alterados
- Decisões técnicas e motivos
- Testes: PASS / FAIL / BLOCKED e evidências
- Riscos, pendências e próxima ação
- Estado de commit/push e sincronização

## 2026-11-10 — Missão de backup seguro e recuperação

- Data/hora: 2026-11-10, 21:33 UTC (validação consolidada).
- Objetivo: backup consistente de SQLite e artefatos persistidos, criptografia
  autenticada, manifesto SHA-256, recuperação isolada e preparação sem envio.
- Branch: `feat/unificar-8504-8510`; SHA local e upstream armazenado:
  `60e34d8f7e23b58b5142eb59ad18ba1ab6df9e3c` (0/0). GitHub ao vivo não consultado.
- Arquivos: `scripts/secure_backup.py`, `requirements-backup.txt`,
  `tests/test_secure_backup.py`, `.gitignore`, `docs/ESTADO_ATUAL.md`, este diário
  e `docs/missoes/RELATORIO_BACKUP_SEGURO.md`.
- Decisões: ferramenta offline independente; pausa dos gravadores declarada pelo
  operador; inventário antes/depois; cópias privadas dos bancos e journals antes
  da API SQLite para preservar até SHM operacional; AES-256-GCM e manifesto interno;
  destino de recuperação novo e externo; preparação cifrada com upload desabilitado.
- Testes: PASS, 17 testes direcionados sintéticos; pip check e git diff --check
  PASS. Falha inicial de preservação SHM corrigida e coberta. Sem E2E ou teste
  de envio. Bateria e detalhes constam no relatório.
- Dados: nenhuma captura/restauração operacional, nenhuma migração, exclusão ou
  sobrescrita. Arquivos não rastreados preexistentes preservados.
- Riscos/pendências: pausa real, limite 256 MiB/10.000 entradas, temporários
  plaintext privados, custódia de chaves, inventário externo, ensaio de recuperação,
  retenção/RPO/RTO e validação futura do remoto privado.
- Commit/push: não executados, conforme solicitação; entrega no working tree.

## 2026-11-10, 21:55 UTC — Missão 2: auditoria do backup

- Objetivo: auditar segurança e selecionar arquivos publicáveis, sem publicar.
- Branch `feat/unificar-8504-8510`; SHA local e upstream armazenado
  `e2ddc98e1d189d2c10b930c04c8eb5d2668b1ca8`; 0/0, sem consulta viva ao GitHub.
- Arquivos: script e testes de backup, requirements-backup.txt, registros de
  continuidade, nota no relatório anterior e novo RELATORIO_AUDITORIA_BACKUP.md.
  .gitignore da missão anterior revisado e mantido.
- Correções comprovadas: patch cryptography 46.0.7 para CVE-2026-39892;
  validação comum de nomes na captura/verificação, incluindo recusa de alias de raiz.
- Testes PASS: 17 originais antes, 20 após; pip check e git diff --check.
  Licenças OSS identificadas; candidatos sem indícios na triagem de dados sensíveis.
- Resultado APROVADO somente para os oito arquivos enumerados no relatório.
  Arquivos operacionais excluídos e preservados; dados/módulos BI não alterados.
- Pendências: ensaio real, custódia/retenção/RPO/RTO, origens externas, scanner
  abrangente de advisories e verificação de privacidade remota.
- Sem backup real, interrupção de serviços, staging, commit, push ou migração.

## 2026-11-10 — Missão 3: pré-validação operacional (UTC)

- Objetivo: preparar ensaio sem interromper BI; inspeção local somente de leitura.
- Branch `feat/unificar-8504-8510`; SHA local/upstream armazenado
  `df31b6adb699cdbd7e56efeac579517540ae5290`; 0/0, GitHub vivo não consultado.
- Arquivos alterados: relatório novo RELATORIO_PREVALIDACAO_BACKUP.md e os dois
  documentos de continuidade. Nenhum dado/banco/módulo operacional alterado.
- Confirmados: 2.646.921.208 bytes/55 entradas em storage; dois SQLite por cabeçalho;
  ausência local de artifacts/staged; gravadores pelo código; sem serviços BI
  ou portas esperadas observados. Limitações de processos/externos no relatório.
- Decisão BLOQUEADO: 9,86 vezes o limite, sem barreira global validada de escrita,
  referências externas e requisitos de destino/custódia/RPO/RTO pendentes.
- Testes PASS: 20 sintéticos em 0,97 s; pip check; diff --check final. Nenhuma
  execução de testes com dados reais, conexão SQLite operacional ou backup real.
- Procedimento proposto: resolver capacidade, coordenar somente escritas com
  disponibilidade comprovada, capturar conjunto íntegro, verificar offline,
  restaurar em ambiente isolado sem acesso à origem e liberar barreira em falha.
- Sem chaves operacionais, rede/envio, parada/início de serviço, staging, commit
  ou push; todos os não rastreados preexistentes preservados.

## 2026-11-10 UTC — Missão 4: arquitetura sustentável de recuperação

- Objetivo: separar A/B/C/D e preparar recuperação de código completo e dados
  escaláveis sem executar operação real. Instruções e três relatórios lidos.
- Branch `feat/unificar-8504-8510`; SHA local/upstream armazenado
  `b61f7fde3b63bb58e43c9eb3c3914cf117f76e1a`, 0/0. Sem consulta viva ao GitHub.
- Arquivos novos: config/backup/policy.json, scripts/backup_architecture.py,
  ops/backup/schedule.cron.disabled, tests/test_backup_architecture.py e
  docs/missoes/RELATORIO_ARQUITETURA_BACKUP.md. Atualizados ESTADO_ATUAL e diário,
  preservando modificações preexistentes. Nenhum dado ou módulo BI alterado.
- Decisão: Git mirror independente com gerações/bundles; Restic BSD-2-Clause
  avaliado na documentação oficial para incrementais/deduplicação e multigiB.
  Planejador emite somente argumentos simbólicos; execução/rede/agenda bloqueadas.
  Sem runner/barreira/staging operacional implementado; risco explicitado.
- Política proposta: retenção 14/8/12, recuperação isolada com ID explícito,
  RPO 24 h e RTO 2 h código/8 h completo, sem comprovação operacional.
- Testes PASS: bateria consolidada 47 testes em 4,35 s (20 anteriores e 27 novos),
  pip check, CLI offline e git diff --check. Streaming >4 GiB simulado com memória
  limitada; não é benchmark ou teste Restic real. Restic ausente no ambiente.
- BLOQUEADO para produção: barreira global, produtor/runner, inventário externo,
  revisão privada de segredos/histórico, destinos/custódia, lock de ambiente e
  ensaio completo com medição. Relatório detalha licenças e recuperação periódica.
- Sem backup real, transferência, abertura de SQLite operacional, instalação ou
  interrupção de serviço, exclusão, staging Git, commit ou push. Próxima ação:
  homologar executor e coordenação somente em dados sintéticos antes de ativar.

## 2026-11-11 — Início da correção urgente do editor visual
- Trabalho direto via GitHub em branch isolada `fix/editor-visual-navegacao-pastas-20261111` a partir de `feat/unificar-8504-8510`.
- Commit de código `2a451da584e5b3b5e83f1512d637d1260fa9a39d`: caminho completo das pastas no cadastro e retirada dos botões externos que alternavam `iframe` edit/preview e causavam remount.
- Sem acesso ao terminal do Codespaces; sem teste de execução real; nenhuma alteração em dados persistidos. CI ainda a verificar.
- Próximo: inspecionar editor `/visual-editor`, resolver visualização em branco e controles de objetos; manter PR draft até testes.

## 2026-11-11 — Correções incrementais do editor via GitHub
- Branch isolada `fix/editor-visual-navegacao-pastas-20261111`, PR #2 draft.
- Editor: controles de texto e bordas, histórico básico, limpeza confirmada, fechamento contextual, não recriar iframe ao salvar; React: caminhos hierárquicos das pastas.
- Workflow `.github/workflows/editor-visual-ci.yml` valida sintaxe JS inline e build React. Execução CI e homologação visual ainda não confirmadas.
- Sem acesso ao Codespaces; nenhum arquivo de dados alterado, nenhuma migração, nenhum merge. Próxima ação: checar CI, corrigir regressões e integrar para teste após validação.

## 2026-11-10, 22:51 UTC — Missão 5: homologação sintética Restic

- Objetivo: executar incremental e recuperação escalável apenas em fixtures,
  incluindo falhas, coordenação SQLite+JSON e reconstrução Git bundle.
- Branch `feat/unificar-8504-8510`; SHA local/upstream armazenado
  `b09fffaf2b341b71b3c2f10f7840f79448080312`, 0/0. Sem fetch/consulta viva do
  remoto do projeto. Instruções, quatro relatórios e código anterior lidos.
- Criados `scripts/homologate_backup_synthetic.py` e relatório obrigatório
  `docs/missoes/RELATORIO_HOMOLOGACAO_BACKUP.md`; atualizados ESTADO_ATUAL e diário.
  Política, ferramenta anterior e serviços mantidos; três flags false.
- Restic 0.19.1 oficial (go1.26.4 linux/amd64), BSD-2-Clause confirmada na tag;
  SHA-256 do bz2 comparado ao SHA256SUMS antes de executar. Sem assinatura GPG
  independente, instalação global ou serviço. Download público somente de
  ferramenta/metadados, sem envio de dados. Ensaios sem rede.
- PASS final: 18 verificações / 36 subprocessos em 33,819 s. Arquivo esparso
  2.164.260.864 bytes, incremental de 802.311 bytes lógicos novos/1.055 empacotados,
  terceira captura zero novos blocos; versões v1/v2 restauradas e hashes iguais.
  Senha errada código 12, init existente 1, backend ausente 10, parcial 3 com
  snapshot criado e rejeitado, corrupção 1; repositório original íntegro.
  Mudança concorrente retornou 0 no Restic e foi rejeitada pelo inventário.
- Coordenação: escritor em processo separado, 40 gerações, 31 capturas coerentes;
  intervalo SQLite/JSON incoerente sem lock demonstrado, lock comum eficaz,
  liberação em exceção e restauração Restic conjunta da geração 40 confirmadas.
  Bundle privado gerado do zero: duas branches/tags, refs iguais, fsck e versões
  recuperadas. Commits somente nesse Git sintético, nunca no projeto.
- Primeira tentativa (30,274 s) interrompida por pack copiado somente leitura;
  corrigido chmod apenas na cópia sintética de corrupção. Laboratórios mantidos
  em /tmp; evidência final em /tmp/seppe-m5-lab-xif380iz/evidence.json, sem senhas.
- Regressão PASS: 47 testes direcionados em 5,47 s; pip check; diff --check final.
  Nenhum teste operacional, startup de aplicação ou leitura de dados reais.
- Decisão: APROVADO para escopo sintético; BLOQUEADO para produção. Pendentes:
  barreira real global, timeout/crash recovery, staging/runner/catálogo, inventário
  externo/revisão de segredos, custódia/destino e carga/RPO/RTO representativos.
  Dados esparsos compressíveis não são benchmark de produção.
- Dados e não rastreados preservados. Sem backup real, alteração de banco
  existente, exclusão, parada de serviços, cron, staging, commit/push do projeto.

## 2026-11-12 — Correção de persistência e consolidação

- Identificada falha HTTP 400 no PUT de layout: KeyError 'version'.
- Causa: produtos legados sem campo version no registro.
- Corrigidas update_product e sync_product_components para iniciar
  a versão em zero quando ausente e incrementá-la.
- Commit da correção e inicializador: 105255d.
- Merge das atualizações remotas: 73900fa.
- Teste funcional: HTTP 200 e reabertura do produto com alterações preservadas.
- Inicializador: sintaxe validada e quatro rotas HTTP aprovadas.
- Servidores existentes não foram reiniciados durante o teste.
- Teste de partida a frio permanece pendente.
- Missão 5 Restic: documentação sintética restaurada.
- Backup operacional/produção continua bloqueado.
- Nenhum dado operacional alterado nesta consolidação.

## 2026-11-13 — Pacote de homologação cadastro e filtros ECharts
- Branch isolada `homolog/cadastro-filtros-echarts-20261113`, PR #4 draft; sem merge na branch de desenvolvimento.
- Alterados: `web/bi_factory/src/main.jsx`, `scripts/bi_factory_catalog.py`, `prototypes/editor-visual/index.html`.
- Cadastro: pasta criada a partir do campo Pasta, projeto/responsável técnico no formulário inicial, abrir editor ao salvar, prévia apenas quando houver layout salvo.
- ECharts: aviso de um objeto por vez; filtros de dimensões/medidas vinculados a objetos, sem substituir Despesa por Receita; opção de criar objeto para medida não utilizada.
- Testes: BLOCKED — sem terminal Codespaces e sem validação visual/CI confirmada. Não afirmar homologação concluída.
- Dados operacionais: nenhuma edição; mudanças apenas no código versionado. Próxima ação: validar build, teste de regressão e liberar branch de homologação em Codespaces sem tocar produção.


## 2026-11-16 — Correção de cadastro de produto anterior visível
- Relato: ao clicar em Novo produto, formulário de criação e ficha anterior apareciam juntos; novo cadastro não era salvo corretamente.
- Inspeção: web/bi_factory/src/main.jsx não limpava selectedProduct em Novo produto; a renderização de selectedProduct era independente de creation; save não tinha trava de múltiplos envios.
- Código em branch isolada fix/novo-produto-ficha-isolada-20261116, commit 4ccbce8. Novo produto limpa estado visual anterior; formulário anterior não é renderizado durante criação; save bloqueia repetição, valida nome e abre editor do novo item.
- Testes: PASS inspeção estática de trechos; BLOCKED build/E2E/Chrome por ausência de terminal Codespaces no conector. Sem alterações em dados, API, storage, branch local ou processos.
- Pendência: reconciliação segura com branch local teste/cadastro-filtros-20261113 antes de integração; homologar criação de dois produtos consecutivos e persistência de ambos.

## 2026-11-16 — Ponte de aplicação controlada (não homologada)
- Criado scripts/bi_factory_patch_agent.py em branch isolada, commit c16cbe9: escuta issue [BI-AGENT] APLICAR com SHA completo e branch permitida; exige branch local esperada, commit alcançável, arquivo permitido, working tree do alvo limpo e git apply --check. Sem checkout/reset/merge, sem sobrescrever alterações, sem commit/push automático.
- A instalação/execução do novo agente no Codespaces ainda requer bootstrap único e teste ponta a ponta. O agente anterior [BI-AGENT] ABRIR não é capaz de instalar outro agente.

## 2026-11-16 — Recuperação com fixture e CI
- Base confirmada `d094880`, branch `fix/recuperacao-homologacao-20261116`. Código e documentação obrigatória lidos no clone.
- Causa adicional identificada por inspeção: POST bem-sucedido seguido de refresh malsucedido mantinha draft salvável. Corrigido encerrando criação após POST, mostrando aviso de catálogo e preservando produto criado no estado local; ref impede chamadas simultâneas.
- Alterados main.jsx, configuração Vite/npm (8506), monitor (retomada do agente patch), devcontainer (não abrir API), gitignore; adicionados suíte E2E isolada e workflow.
- PASS build/sintaxe/diff. E2E local BLOCKED por restrição do Chromium. Nenhuma conexão com dados de produção; fixture isolada para API real.
- Túnel externo respondeu 401/tunnel em consulta não autenticada; navegador Codespaces exigiu login, gh sem credencial. Falta sessão remota para verificar encaminhamento privado, processos, implantação e reinício/rebuild.
- Publicação autorizada em branch isolada para execução CI, sem merge, reset ou alteração do Codespaces.


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
