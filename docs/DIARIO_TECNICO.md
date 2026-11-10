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
