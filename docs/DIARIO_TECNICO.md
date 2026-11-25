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


## 2026-11-16 — Aplicacao recuperada no Codespaces
Acesso privado, implantacao do cadastro e recuperacao do frontend confirmados. Fonte ba06f86, main blob da298ea; detalhes e bloqueio de automacao em docs/missoes/RECUPERACAO_OPERACIONAL_20261116.md. Nenhum dado operacional alterado.


## 2026-11-16 — Agente permanente instalado e reinicio aprovado
Autorizacao especifica recebida; agente e monitor e984357 instalados. Nove testes de guardas e cinco E2E PASS. Reinicio completo com hooks automaticos, estado persistido e 11 JSONs preservados PASS. Issue #17 rejeitada conforme esperado. Rebuild nao ensaiado. Detalhes: docs/missoes/AGENTE_PERMANENTE_20261116.md.


## MARCO CONGELADO — Editor Visual e ficha de produtos — 2026-11-16
- Por decisão de homologação do usuário, a versão de referência é o código efetivamente em execução no Codespaces, branch local teste/cadastro-filtros-20261113.
- O módulo Editor Visual/ficha de produtos está suficientemente maduro para avançar aos módulos de dados; congelado funcionalmente salvo correções de defeitos.
- Próxima etapa: entrada, modelagem, transformação e conexão de dados aos gráficos e produtos.
- A branch remota marco/editor-visual-homologado-20261116 reproduz o commit do Codespaces; branches experimentais anteriores não são consideradas homologadas automaticamente.
- Dados operacionais, layouts persistidos, bancos, builds e node_modules ficam fora do Git. Nenhum merge/reset/rebase ou limpeza de dados.
- Validação do marco: build React e verificações HTTP 8506, /api/overview, /visual-editor; testes funcionais adicionais podem ser necessários.
- Registro gerado em UTC: 2026-11-16T23:02:02.127347+00:00.


## 2026-11-17 — Testes amplos e primeira integração React dos motores recuperados
- Criados scripts/bi_factory_analytics_adapter.py, API analytics, web/bi_factory/src/DataWorkspace.jsx e testes unitários/HTTP/Playwright. Mantidos catálogo/Editor Visual congelados.
- Execução CI #44186453294 aprovou 417 testes principais, um slow e nove PostgreSQL; cinco skips devido a condições da suíte/ambiente. Corrigido skip de fixture PMCG ausente e configuração PGPASSWORD em testes sintéticos. E2E browser em validação na workflow posterior.
- Arquivos originais dos uploads serão armazenados em storage/working/react_analytics por análise, não versionados no Git; uploads de terceiros e dados operacionais não foram processados.
- Documentação: docs/RELATORIO_VALIDACAO_MOTORES_20261117.md; branch isolada, sem implantação Codespaces e sem alteração do marco homologado.

## 2026-11-17 — Consolidação da bateria de verificação
- Execução validada https://github.com/edineilemes-source/bi-factory-seppe/actions/runs/44187616806: 418 testes principais aprovados, um slow aprovado, nove PostgreSQL aprovados, um E2E Chromium aprovado, cinco ignorados por condições; quatro jobs verdes. Novo teste de inicialização direta da API criado após o erro real encontrado no E2E.
- Installer criado na branch feat/integracao-react-pipeline-legado-20261117, sem implantação Codespaces nem mutação de dados. O código dos quatro arquivos de aplicação alvo é o mesmo do SHA testado 10c68b71. O Editor Visual do marco 751e292d permanece congelado.
- npm ci informa quatro alertas high de segurança nas dependências; relatório técnico registra risco, sem alteração automática das dependências.


## 2026-11-24 — Implementação de pesquisa oficial em Conhecimento

- **Objetivo:** atender consulta por tema antes da modelagem de Receita/Despesa, com descoberta de leis, normas, MCASP, MDF, PCASP, Siconfi e aprovação manual de documentos originais para cada projeto.
- **Origem:** branch `feat/conhecimento-pesquisa-oficial-20261124`, baseada no estado do GitHub `fix/editor8507-integrado-catalogo-8506-20261124`; Codespaces local não foi acessado.
- **Alterações:** novo `scripts/bi_knowledge_official.py`, rotas GET/POST em `scripts/serve_bi_factory_api.py`, interface `web/bi_factory/src/KnowledgeStart.jsx`, testes Python, CI, documentação e instalador não destrutivo.
- **Decisões:** sem dependência paga para buscar; fontes somente oficiais, documentos com links auditáveis, seleção e aprovação antes de baixar PDFs, 25 MiB por PDF, SHA-256 e deduplicação. Sem `git push` de PDFs; dado operacional fica sob storage/working/projects. IA local Ollama opcional apenas para termos auxiliares, não para fabricar fontes. Teste real com internet condicionado ao Codespaces.
- **Testes:** primeiro CI apresentou falha no caminho relativo quando usando pasta temporária; corrigido. GitHub Actions `45415488183` concluiu com sucesso, incluindo cinco testes Python e build React. CI adicional com verificação de sintaxe do instalador disparado após esse resultado.
- **Risco:** a pesquisa inicial não é busca exaustiva; bloqueios de portal, páginas JS ou PDF sem extensão podem reduzir cobertura, e os resultados relatam essas limitações.
- **Segurança:** nenhum dado do usuário nem segredo versionado; URLs oficiais com validação de domínio/redirecionamento; somente alterações de código na branch separada; nenhuma migração de dados nem serviço reiniciado.
- **Próxima etapa:** executar instalador no Codespaces, confirmar API/React, experimentar pesquisas e importações aprovadas, e depois vincular normas selecionadas a medidas da modelagem.

- **CI final confirmado:** GitHub Actions [execução 45416126373](https://github.com/edineilemes-source/bi-factory-seppe/actions/runs/45416126373), commit do código `dd1e17f35232950a9ee6d3502985b8cf86ba5402`: sintaxe Python, cinco testes offline, `npm ci` e build React, todos PASS. Sem teste de navegação/HTTP a partir do Codespaces nesta entrega.

## 2026-11-24 — Instalação de Conhecimento: conflito local preservado e compatibilidade criada

- **Evidência do Codespaces fornecida pelo operador:** na branch local `teste/cadastro-filtros-20261113`, o instalador anterior interrompeu antes de qualquer escrita por conflito 3-way em `web/bi_factory/src/KnowledgeStart.jsx`. O `serve_bi_factory_api.py` apresentava diferenças conciliáveis; não há confirmação de instalação.
- **Correção no GitHub:** branch `fix/conhecimento-preservar-knowledge-local-20261124`; componente independente `web/bi_factory/src/OfficialKnowledgeSearch.jsx` e instalador `scripts/instalar_conhecimento_oficial_compat.py`. O instalador passa a preservar o JSX existente, inserindo uma importação e um componente na área da tela, sem substituir `KnowledgeStart.jsx` completo. Conserva backup, validação, rollback e mescla da API.
- **Testes confirmados:** [GitHub Actions 45438701588](https://github.com/edineilemes-source/bi-factory-seppe/actions/runs/45438701588), aprovação de sintaxe Python, pesquisa documental offline, simulações de tela local divergente e idempotência, validação JSX e build React.
- **Pendente:** execução do novo instalador no Codespaces, confirmação da tela Conhecimento e testes reais de download HTTPS. Se a tela local não corresponder à estrutura JSX conhecida, o instalador interrompe sem sobrescrever o arquivo. Nenhum serviço do Codespaces foi iniciado a partir desta conversa.

## 2026-11-24 — Correção do autodiagnóstico de instalação do módulo Conhecimento
- **Evidência real do Codespaces:** na branch local `teste/cadastro-filtros-20261113`, execução via `git show` do instalador `fix/conhecimento-preservar-knowledge-local-20261124` abortou no pré-teste com `ERRO AO INSTALAR PESQUISA OFICIAL: Código local foi perdido`. A falha ocorreu **antes da gravação** dos arquivos, não comprova perda real dos arquivos locais.
- **Causa:** a rotina incluía `import OfficialKnowledgeSearch` antes do comentário no topo do arquivo e depois exigia `merged_view.startswith(b"// comentario local")`. A condição contradizia a própria transformação. A análise revelou ainda que o teste `test_knowledge_compat_installer.py` importava o instalador, mas o instalador não o copiava para o Codespaces antes de rodar o teste.
- **Correções:** branch `fix/conhecimento-installer-autoteste-preservacao-20261124`; posicionamento do novo import após imports existentes, preservando cabeçalhos e comentários; inclusão de `scripts/instalar_conhecimento_oficial_compat.py` na lista de artefatos instalados; fortalecimento do teste para reconstrução byte a byte do conteúdo original ao retirar apenas as inserções; manutenção da idempotência e do backup/rollback. O instalador aponta agora para a nova branch.
- **Evidência de testes:** [GitHub Actions 45440486028](https://github.com/edineilemes-source/bi-factory-seppe/actions/runs/45440486028) **SUCCESS** no commit `47591aa6fb91274dd42c59b3b13bc341f7ec506e`: sintaxe Python, testes offline, preservação de KnowledgeStart, JSX e build React. Nenhuma instalação foi executada no Codespaces por esta conversa.
- **Próximo passo:** instalar a partir da nova branch e validar no Codespaces (API 8505, frontend do catálogo, pesquisa online), sem sobrescrever o editor 8507 nem os produtos existentes.

## 2026-11-25 — Biblioteca de Conhecimento, leitura e RAG da Modelagem

- **Objetivo:** a pesquisa oficial de CAPAG e demais temas deve permitir conferir PDFs aprovados, excluir/restaurar, selecionar documentos para leitura, e expor conceitos com referência documental à área Modelagem.
- **Código no GitHub:** branch \`feat/conhecimento-biblioteca-leitura-modelagem-20261125\`. Arquivos novos \`scripts/bi_knowledge_library.py\`, \`scripts/test_knowledge_library.py\`, \`web/bi_factory/src/KnowledgeLibrary.jsx\`, \`web/bi_factory/src/ModelKnowledgeContext.jsx\`, \`requirements-knowledge.txt\`, \`scripts/instalar_biblioteca_ia_modelagem.py\`, testes de compatibilidade e documento em \`docs/CONHECIMENTO_BIBLIOTECA_MODELAGEM_20261125.md\`. Adaptados \`serve_bi_factory_api.py\`, \`bi_factory_projects.py\`, \`bi_knowledge_official.py\`, \`OfficialKnowledgeSearch.jsx\` e o ponto de entrada de Modelagem.
- **Decisões:** distinguir URL de referência/HTML de PDF efetivo (não inferir PDF nos endereços THOT sem sufixo); abrir e baixar apenas arquivo com hash SHA-256 íntegro; exclusão em lixeira recuperável; indexação por página de PDFs aprovados com \`pypdf\` (BSD-3), limites e aviso de OCR necessário; consulta textual compartilhada por ID de projeto; Ollama opcional em loopback para interpretação RAG não homologada. CAPAG buscada prioritariamente em fontes oficiais e separada de documentos RGF/DCA sem pertinência.
- **Dados:** nenhuma alteração/remoção real no Codespaces foi executada nesta sessão. O índice proposto fica em \`storage/working/projects/<id>/document_index.json\`; originais e lixeira permanecem sob o mesmo projeto. Não enviar PDFs para Git automático.
- **Testes de CI confirmados:** [GitHub Actions 45640641188](https://github.com/edineilemes-source/bi-factory-seppe/actions/runs/45640641188) SUCCESS: sintaxe, extração pypdf de PDF sem texto, integridade, isolamento, remoção/restauração, recuperação de conceitos, inserção compatível em DataWorkspace, validação JSX e build React. Falhas detectadas em execuções anteriores foram corrigidas e testadas novamente.
- **Pendente:** ativar o instalador no Codespaces pela branch, conferir que a rota e os links de visualização abrem na 8506; testar downloads CAPAG/STN reais, PDF grande, arquivo digitalizado e Ollama local (não configurado). Testes de CI não equivalem a homologação no navegador.

## 2026-11-25 — Correção de dependência isolada pypdf na instalação de Conhecimento/Modelagem

- **Evidência do Codespaces fornecida pelo operador:** execução do instalador `scripts/instalar_biblioteca_ia_modelagem.py` em `teste/cadastro-filtros-20261113` instalou pypdf 6.21.4 com `pip --target /workspaces/bi-factory-seppe/.git/knowledge-deps`; testes de pesquisa oficial (5/5) passaram; biblioteca documental falhou em `test_real_pypdf_read_without_text_reports_ocr_pending` com `ModuleNotFoundError: No module named 'pypdf'`. Instalador restaurou os arquivos de código alterados ao encontrar falha no teste, **antes de reiniciar a API**. Não há evidência de perda de PDF, produto ou layout; a dependência no diretório isolado pode permanecer.
- **Causa técnica:** o instalador não adicionava `.git/knowledge-deps` ao `PYTHONPATH` dos subprocessos Python, apesar de instalar o pacote nesse destino com `pip --target`. O pacote instalado não fica automaticamente disponível no `sys.path` global.
- **Correção no GitHub:** branch `fix/biblioteca-pypdf-isolado-codespaces-20261125`, baseada em `feat/conhecimento-biblioteca-leitura-modelagem-20261125`. O instalador propagará `PYTHONPATH` aos subprocessos; reaproveitará a cópia de pypdf já presente na pasta isolada; verificará a importação de pypdf antes de avançar. Acrescentado teste unitário de propagação de ambiente e job específico de CI para execução com `pip --target` **sem instalação global**.
- **Validação confirmada:** [GitHub Actions 45641927969](https://github.com/edineilemes-source/bi-factory-seppe/actions/runs/45641927969), ambos jobs `knowledge-and-frontend` e `isolated-pypdf-codespaces` **SUCCESS**. Passaram: sintaxe Python, testes funcionais, preservação da Modelagem, build React, `pip --target`, `import pypdf` e teste real de PDF sob `PYTHONPATH` isolado.
- **Pendente:** executar a branch corrigida no Codespaces; checar reinício API 8505, catálogo 8506 e Biblioteca/Modelagem no navegador. Não há confirmação de que esta versão já esteja instalada no Codespaces.

## 2026-11-25 — Download automático em pesquisas oficiais, com foco CAPAG

- **Solicitação do operador:** não exigir abertura manual de sites oficiais para baixar PDFs; pesquisa por CAPAG exibia dezenas de documentos de RGF/DCA pouco relacionados e referências HTML em vez dos arquivos esperados. No navegador, a biblioteca continha documentos DCA/RGF e duas referências CAPAG sem PDF baixado.
- **Implementação no GitHub:** branch `feat/conhecimento-download-automatico-capag-20261125`; pesquisa CAPAG agora foca CAPAG/análise fiscal; adiciona Manual de Análise Fiscal de Estados e Municípios 2026 do Tesouro (URL de PDF original oficialmente verificada), além da página de publicação; backend `auto_download_for_project` usa apenas referências da pesquisa, percorre páginas de download/iframe em domínios oficiais, verifica assinatura PDF e limita cinco documentos por rodada. A interface traz **Baixar PDFs automaticamente** habilitado por padrão no clique em **Pesquisar fontes oficiais**, atualização imediata da Biblioteca e botão para retrobaixar PDFs de pesquisas antigas.
- **Verificação e governança:** PDF só é mostrado como armazenado após receber bytes `%PDF-` válidos, salvar em `storage/working/projects/<id>/originals/<SHA256>.pdf` e registrar URL, tópico e tamanho. Sem novo `git push` de dados. Documentos previamente excluídos não são reimportados automaticamente. O usuário pode abrir, excluir/restaurar e, separadamente, acionar a leitura/indexação.
- **Ressalvas:** portais com JavaScript, bloqueios, autenticação ou arquivo inexistente podem impedir recuperação; resposta lista falhas e não marca HTML como PDF. Primeira implantação real no Codespaces ainda pendente, bem como verificação de download dos documentos CAPAG do portal a partir da rede do Codespaces.
- **Instalador:** `scripts/instalar_download_automatico_conhecimento.py` (via `git fetch`/ `git show` da branch), altera apenas motor de pesquisa, API, interface de pesquisa e seus testes; faz backup/rollback e testes; não altera dados STN, catálogo de produtos, editor visual nem a porta 8507.
