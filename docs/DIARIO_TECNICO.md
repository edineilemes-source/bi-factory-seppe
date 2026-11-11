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

## 2026-11-11 — Correções editor e ECharts (branch isolada)
- Branch `fix/editor-completo-homologacao-20261111`. Corrigida remount do iframe ao salvar (evita perder estado não salvo), adicionado Refazer, remoção de outline azul na visualização, propriedades de contorno de figuras e snapshot de undo na inserção ECharts.
- Arquivos: `web/bi_factory/src/main.jsx`, `prototypes/editor-visual/index.html`, `scripts/test_editor_full.cjs`, `.github/workflows/test-editor-full.yml`.
- Testes: ver run 43054626669; sem alteração de dados operacionais. Ainda pendentes: validação de produtos reais, hierarquia de pastas existente, fluxo completo ECharts e sincronização com Codespaces 8506. Não houve merge/deploy.
