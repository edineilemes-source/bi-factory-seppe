# Missão 3 — Pré-validação operacional do backup SEPPE

Data: 2026-11-10 (UTC). Decisão: **BLOQUEADO para ensaio controlado de captura integral real**.

## Estado confirmado e escopo

Terminal local em `/workspaces/bi-factory-seppe`; branch confirmada
`feat/unificar-8504-8510`. HEAD e upstream armazenado:
`df31b6adb699cdbd7e56efeac579517540ae5290`, divergência 0/0.
Sem fetch ou consulta ao GitHub ao vivo; igualdade local não prova sincronização remota.
Lidos AGENTS.md, ESTADO_ATUAL, DIARIO_TECNICO e os relatórios BACKUP_SEGURO e
AUDITORIA_BACKUP, além do código atual de captura e dos módulos gravadores.

Estado inicial: nenhum arquivo rastreado alterado; não rastreados preexistentes
`.vite/`, `FETCH_HEAD`, `prototypes/editor-visual/index.html.bak`,
`storage/dashboard_projects/`, `storage/information_products/`,
`web/bi_factory/dist/`, `web/bi_factory/node_modules/`, todos preservados.
Esta entrega altera somente este relatório e os dois registros de continuidade.
Nenhum staging, commit, push, backup real, geração de chave operacional,
restauração real, envio, alteração de banco ou interrupção/inicialização de serviço.

Método: metadados de filesystem (lstat), leitura apenas dos 16 bytes de assinatura
para classificar SQLite em storage, inspeção estática de código/configuração e
metadados de processos, descritores e portas. Nenhuma conexão SQLite operacional;
não se executou PRAGMA nos bancos reais, nem importação da aplicação. Não foram
lidos registros dos bancos ou conteúdo dos JSON/CSV/XLSX. Tamanhos lógicos,
não ocupação física, em bytes; observação pontual, não snapshot consistente.

## Inventário técnico

Raiz dos caminhos relativos: `/workspaces/bi-factory-seppe`.
`storage`: **37 arquivos regulares + 18 diretórios = 55 entradas**;
**2.646.921.208 bytes = 2.524,30 MiB = 2,465 GiB**.
Nenhum link ou arquivo especial observado nessa árvore. Dois bancos confirmados
pela assinatura SQLite; nenhum WAL, SHM, rollback journal ou `.partial` presente
no inventário. Isso não demonstra integridade ou ausência de transação futura.

| Caminho | Tipo | Bytes |
| --- | --- | ---: |
| `storage/bi_factory.sqlite3` | SQLite | 2678784 |
| `storage/dashboard_projects/products/444524b0-5df0-4fcd-8d6d-d8d09f9f3a6d.json` | json | 999 |
| `storage/dashboard_projects/products/d21ed11e-2adf-467f-b0c6-d676975b2f84.json` | json | 645 |
| `storage/dashboard_projects/products/e2f4dde4-7c47-462e-8c12-97b7cb3f3ca2.json` | json | 3713 |
| `storage/dashboard_projects/published.json` | json | 10741 |
| `storage/information_products/folders.json` | json | 649 |
| `storage/information_products/layouts/59fc9c5e-f046-40f6-a995-8540a477c116.json` | json | 346275 |
| `storage/information_products/layouts/c6664c93-8197-4df9-bdaf-79efa32284b3.json` | json | 6811 |
| `storage/information_products/metadata/c6664c93-8197-4df9-bdaf-79efa32284b3.json` | json | 104 |
| `storage/information_products/registry.json` | json | 2518 |
| `storage/information_products/shared_components.json` | json | 1310 |
| `storage/official/siconfi/rreo/2025/anexo01/rreo-2025-manifest.json` | json | 739 |
| `storage/official/siconfi/rreo/2025/anexo01/rreo-2025-p1-anexo01.json` | json | 162992 |
| `storage/official/siconfi/rreo/2025/anexo01/rreo-2025-p2-anexo01.json` | json | 161201 |
| `storage/official/siconfi/rreo/2025/anexo01/rreo-2025-p3-anexo01.json` | json | 162983 |
| `storage/official/siconfi/rreo/2025/anexo01/rreo-2025-p4-anexo01.json` | json | 163907 |
| `storage/official/siconfi/rreo/2025/anexo01/rreo-2025-p5-anexo01.json` | json | 166924 |
| `storage/official/siconfi/rreo/2025/anexo01/rreo-2025-p6-anexo01.json` | json | 172279 |
| `storage/originals/.gitkeep` | marcador | 1 |
| `storage/originals/rela de pagos PMCG 10 ago 2026.xlsx` | xlsx | 21380712 |
| `storage/reports/.gitkeep` | marcador | 1 |
| `storage/reports/bi_mvp/ca5cf2d7-98d8-4404-a5cd-916eda0810db/audit-60361740-7ad1-4ab7-82c4-d6bb3f3b005f.json` | json | 53587 |
| `storage/reports/bi_mvp/ca5cf2d7-98d8-4404-a5cd-916eda0810db/audit-e9d2f8a4-162d-445f-a020-b568ca01ef23.json` | json | 53579 |
| `storage/reports/bi_mvp/ca5cf2d7-98d8-4404-a5cd-916eda0810db/grain-report-v4.json` | json | 80226 |
| `storage/reports/official_fiscal/fiscal_dw.sqlite` | SQLite | 36864 |
| `storage/reports/official_fiscal/fiscal_dw_postgres.sql` | sql | 4585 |
| `storage/reports/official_fiscal/rreo-2025-dashboard.csv` | csv | 1672 |
| `storage/reports/official_fiscal/rreo-2025-dashboard.json` | json | 4537 |
| `storage/working/.gitkeep` | marcador | 1 |
| `storage/working/prepared/prepared-ca5cf2d7-98d8-4404-a5cd-916eda0810db-v1-fdaafed4.csv` | csv | 58371507 |
| `storage/working/prepared/prepared-ca5cf2d7-98d8-4404-a5cd-916eda0810db-v1-fdaafed4.transformations.jsonl.gz` | gz | 81220052 |
| `storage/working/prepared/prepared-ca5cf2d7-98d8-4404-a5cd-916eda0810db-v2-8d60c32c.csv` | csv | 58371507 |
| `storage/working/prepared/prepared-ca5cf2d7-98d8-4404-a5cd-916eda0810db-v2-8d60c32c.transformations.jsonl.gz` | gz | 81223485 |
| `storage/working/prepared-real-test/prepared-ca5cf2d7-98d8-4404-a5cd-916eda0810db-v1-28acff7d.csv` | csv | 58371690 |
| `storage/working/prepared-real-test/prepared-ca5cf2d7-98d8-4404-a5cd-916eda0810db-v1-28acff7d.transformations.jsonl` | jsonl | 2144111958 |
| `storage/working/prepared-real-test/prepared-ca5cf2d7-98d8-4404-a5cd-916eda0810db-v1-cf36cd7c.csv` | csv | 58371507 |
| `storage/working/prepared-real-test/prepared-ca5cf2d7-98d8-4404-a5cd-916eda0810db-v1-cf36cd7c.transformations.jsonl.gz` | gz | 81220163 |

### Origens fora do escopo padrão e configuração

- `artifacts/staged/`: destino operacional configurado por
  `app/components/dimensional_transformation_view.py` e
  `core/transformation/engine.py`; fora de storage, **ausente** nesta inspeção
  (sem bytes presentes). Uma captura padrão não o inclui quando existir.
- `core/persistence/sqlite_repository.py`: padrão `storage/bi_factory.sqlite3`,
  substituível por argumento `database_path`; `scripts/run_bi_mvp.py --database`
  aceita caminho externo. Não foi encontrado processo ativo que comprovasse
  substituição. Outros SQLite por extensão no checkout, excluindo dependências,
  Git e storage: nenhum; não foi feita varredura de todo o host nem detecção por
  assinatura fora de storage.
- `core/prepared/generation.py`: `artifact_root` substituível; padrão
  `storage/working/prepared/`. Transformação aceita `artifact_root`, workflow MVP
  aceita `root`, snapshot Siconfi aceita `output_dir`; podem apontar para fora do
  checkout. No código de chamada examinado, destinos concretos ficam nos caminhos
  inventariados ou em `artifacts/staged`. Caminhos relativos dependem do CWD.
- `BI_MVP_POSTGRES_DSN`/`--dsn` e configuração `PGHOST`, `PGPORT`, `PGDATABASE`,
  `PGUSER`, `PGPASSWORD` permitem PostgreSQL externo. São possibilidades do código,
  **não endpoints ativos confirmados**; backup SQLite/storage não cobre PostgreSQL.
  Não se transcrevem valores de conexão nem credenciais. Nenhuma conexão de rede.
- Encontrados apenas `.env.example` e `.devcontainer/devcontainer.json` como
  arquivos de configuração candidatos no checkout inspecionado; sem `.env` ou
  `secrets.toml` nessa busca (dependências e Git excluídos). Devcontainer encaminha
  8502/8503; isso não inicia nem comprova serviços ativos.
- Referências `artifact_location`, `artifact_root` e caminhos absolutos podem
  estar persistidos em SQLite/JSON. **Não inspecionados nesta missão**, que limita
  o inventário aos caminhos/tipos/tamanhos sem leitura de registros. A completude
  das origens externas permanece pendente; não se declara que inexistem.
- Código, configuração e dependências de execução não integram o pacote padrão.
  `.bak` do editor e builds foram preservados; não substituem backup operacional.

## Capacidade e limitações

O utilitário atual fixa `LIMIT = 268.435.456` bytes (256 MiB) e `MAX_FILES = 10000`.
O limite considera volume de origem e também ZIP sem compressão com manifesto;
posteriormente há enquadramento criptográfico. As 55 entradas cabem, o volume
**não cabe: 9,86 vezes o limite**, excedendo-o em **2.378.485.752 bytes** antes
mesmo do overhead. A conclusão vem dos tamanhos e da leitura do código; o comando
create não foi executado sobre a origem real.

- `storage/working/prepared/`: 279.186.551 bytes, excede sozinho 256 MiB.
- `storage/working/prepared-real-test/`: 2.342.075.318 bytes. O maior JSONL tem
  2.144.111.958 bytes (~2,00 GiB); o rótulo real-test não autoriza excluir ou apagar.
- Mesmo retirando hipoteticamente só esse JSONL, restariam 502.809.250 bytes,
  ainda acima do limite. Não houve exclusão, seleção parcial ou compressão real.
- Apenas aumentar LIMIT é inadequado sem revisão: há várias cópias em memória,
  ZIP_STORED e temporários SQLite em claro. Precisa de implementação escalável
  e auditada ou plano explícito de múltiplas capturas sob a mesma barreira de
  escrita, incluindo os arquivos individuais maiores que 256 MiB. Divisão por
  diretório sozinha não resolve o arquivo de 2 GiB; omiti-lo perde cobertura.
- Disco observado: checkout ~23,05 GB livres; `/tmp` ~43,14 GB livres; memória
  disponível ~5,07 GiB; swap 0. São valores pontuais do host, não reserva ou
  garantia de memória do contêiner. Não foi identificado destino persistente
  privado aprovado nem validada sua quota. Capacidade aparente de disco não
  elimina os limites de formato/memória e a necessidade de espaço para pacote,
  temporários, restauração e margem de crescimento.

## Gravadores e serviços

Identificação por código; execução atual tratada separadamente.

| Gravador/entrada | Destinos e efeito |
| --- | --- |
| API `scripts/serve_bi_factory_api.py` (padrão 8505) | Catálogo via `bi_factory_catalog.OPERATIONS`; herda Handler do editor. Escreve produtos/pastas/biblioteca/projetos, layouts e metadados. Docstring “read-only” está desatualizada: POST e rotas herdadas gravam. |
| Editor `prototypes/editor-visual/server.py` (padrão 8510) | `information_product_registry.py`: registry/folders; `_write_json`: layouts/metadata. Pode coexistir com API e Streamlit sobre os mesmos JSON. |
| Streamlit `app/main.py` (8502 documentada no devcontainer) | `SQLiteAnalysisRepository`: inicialização/migração, análises, qualidade, semântica, prepared e transformações. `_repository()` também marca gerações interrompidas. Abrir a UI pode gravar, mesmo sem edição manual. |
| Componentes Streamlit de catálogo/dashboard | `information_product_registry.py` e `dashboard_project_designer_view.py`: registry, folders, produtos, published; sincronização de componentes em gravações separadas. |
| Prepared/transformação/MVP | `core/prepared/generation.py`, `core/transformation/engine.py`, `core/bi_mvp/*`: CSV, linhagem, relatórios e staged; metadados persistidos separadamente pelo repositório SQLite. |
| CLI e scripts de execução/teste real | `run_bi_mvp.py`, `audit_bi_mvp.py`, `run_real_prepared_dataset_test.py`, `run_real_quality_gate_hardening_test.py` podem gravar banco/artefatos reais; **não executados**. |
| ETL fiscal/Siconfi | `siconfi_rreo_snapshot.py`, `siconfi_rreo_dashboard_data.py`, `build_fiscal_dw_sqlite.py`, `export_fiscal_dw_postgres.sql.py`: snapshots, manifestos, JSON/CSV, fiscal_dw.sqlite e SQL. **Não executados**. |
| React/Vite e sala de situação | Frontend encaminha operações para API; `serve_sala_situacao.py` lê publicações. Ausência de escrita local no frontend não impede gravações pela API. |

Nos processos visíveis não foram identificados entrypoints da API/editor,
Streamlit, Vite, ETL ou cron. Não havia escuta TCP nas portas
8502/8503/8504/8505/8506/8510 no namespace inspecionado; nenhuma requisição HTTP
foi feita. Nenhum descritor visível apontava a storage/artifacts; quatro processos
não permitiram enumeração completa de FDs. Isso é observação pontual, não prova
de quiescência, disponibilidade do BI em outro ambiente ou inexistência de
outros gravadores. Escritas JSON podem abrir/fechar rapidamente seus descritores.
Não há `/etc/crontab`, spool de crontabs nem `/run/systemd/system` visíveis;
`/etc/cron.d` contém entrada de manutenção e2scrub_all. Agendamentos externos,
outros contêineres/hosts e jobs remotos permanecem não verificados.
Nenhum serviço foi parado, iniciado, reconfigurado ou sondado por rotas com efeitos.

## Consistência SQLite e JSON

A captura exige `--writers-stopped`: declaração do operador, não bloqueio técnico.
Copia SQLite e WAL/journal para temporário privado antes da backup API e checks;
não abre SQLite operacional. Isso protege uma imagem SQLite quando a origem está
estável, **não cria transação global** entre bancos, JSON, CSV e linhagem.

`os.replace` garante troca por arquivo, não atomicidade de um conjunto. Publicação
pode substituir projeto e depois registry; prepared renomeia CSV e linhagem em
etapas e só depois persiste metadados. Concorrência entre API/editor/Streamlit
pode produzir referências divergentes ou atualização perdida. Inventário
SHA-256 antes/depois recusa alterações detectadas, mas não comprova ausência de
operação intermediária revertida nem corrige inconsistência já existente.
Integridade física/FK dos snapshots não valida relações semânticas JSON–SQLite.

O código atual não oferece barreira global de escrita que mantenha leitura
operacional. Portanto, o procedimento antigo de parar todos os gravadores não
satisfaz automaticamente um ensaio sem indisponibilidade. Sem aprovação de janela
ou mecanismo de suspensão somente de escritas comprovado, não declarar
`--writers-stopped` e não realizar captura real com o BI gravando.

## Procedimento proposto — não executado

1. **Condições de entrada:** resolver limite/formato sem perda, validar origens
   externas e PostgreSQL se aplicável; definir responsável, custódia de chave
   externa recuperável, retenção, RPO/RTO e destino privado persistente com quota
   e temporários protegidos. Usar código deste SHA ou versão corrigida e testada;
   ambiente OSS isolado (`requirements-backup.txt`: cryptography 46.0.7,
   Apache-2.0 OR BSD-3-Clause; Python PSF-2.0). Não instalar na aplicação.
2. **Disponibilidade:** mapear os serviços efetivos no ambiente que atende o BI,
   usuários e todos os agendadores. Projetar/testar primeiro em fixture uma
   barreira comum de escrita, impedindo novas mutações, drenando requisições e
   ETL em andamento e mantendo consultas disponíveis. Não basta bloquear POST:
   incluir PUT/DELETE, Streamlit, startup/migração, CLI e filesystem externo.
   O mecanismo não existe hoje. Se a única opção for parar serviços, negociar
   nova autorização/janela; não executar sob a restrição atual de continuidade.
3. **Captura coordenada:** com a barreira comprovada e todas as origens estáveis,
   conferir inventário, ausência de gerações parciais e espaço livre. Capturar
   integralmente pelo mecanismo aprovado e corrigido; se houver vários pacotes,
   todos sob a mesma barreira, identificados como um único conjunto, com mapa
   privado de origem/destino e sem colisões de nomes. `--source` alternativo
   também restaura sob `storage/`: manter raízes em destinos isolados distintos.
   Nunca declarar pausa apenas porque não há FDs abertos. Não forçar checkpoint,
   VACUUM, migração ou reparo sobre a origem. Registrar duração e SHA do cifrado,
   nunca conteúdo. Se falhar, rejeitar o conjunto incompleto.
4. **Retomada:** registrar resultado da captura, liberar a barreira de escrita e
   comprovar consultas e mutações normais por protocolo operacional aprovado,
   sem testes destrutivos em produtos reais. Definir tempo máximo e abortar a
   janela ao atingi-lo. A verificação/restauração demorada ocorre após retomada.
5. **Verificação offline:** autenticação GCM, manifesto exato, hashes/tamanhos,
   `integrity_check` e `foreign_key_check` nas cópias. Conferir cobertura das
   origens, entradas, volumes e conjunto de pacotes. Erro reprova o conjunto;
   não promover nem sobrescrever origem. Guardar evidência resumida privada.
6. **Restauração isolada:** destino novo externo ao checkout, privado, quota
   suficiente; chave separada. Restaurar somente após verificação. Para teste
   funcional, usar checkout separado no SHA registrado e contêiner isolado,
   mapear TODAS as raízes para a cópia, substituir caminhos absolutos apenas
   nessa cópia, bloquear acesso à produção/rede externa e usar portas locais
   distintas. Nunca iniciar o app contra a cópia sem revisar caminhos: startup
   pode migrar/gravar e referências absolutas podem alcançar a origem.
7. **Validação semântica e aceite:** conferir na cópia vínculos entre registry,
   pastas, projetos, layouts, metadata, biblioteca, prepared/linhagem e SQLite;
   detectar órfãos, versões conflitantes e caminhos inexistentes. Checar produtos,
   dashboards e ECharts na UI isolada, sem publicar conteúdo. Medir RPO real e
   RTO, conferir custódia recuperável da chave e documentar PASS/FAIL/BLOCKED.
   Testes sintéticos não substituem esse aceite.
8. **Rollback operacional:** o ensaio não promove a cópia nem altera a origem.
   Falha na captura: cancelar somente a tarefa de captura, registrar/rejeitar
   artefato incompleto e liberar a barreira pelo procedimento aprovado; preservar
   bancos e arquivos originais. Falha na cópia: isolar a restauração rejeitada,
   encerrar somente o ambiente de teste, sem reset/restauração sobre produção.
   Se a retomada de escrita falhar, acionar responsável e runbook de recuperação
   do mecanismo de barreira, mantendo a origem intacta. Uma recuperação real
   de desastre/cutover exige missão e autorização separadas.

## Bateria consolidada e pendências

- **PASS:** `/tmp/seppe-backup-venv/bin/python -m pytest tests/test_secure_backup.py -q`:
  **20 passed em 0,97 s**, apenas fixtures sintéticas temporárias.
- **PASS:** mesmo ambiente, `python -m pip check`: sem requisitos quebrados.
- **PASS:** conferência final `git diff --check` (registrada após documentação).
- Inventário por metadados e assinatura SQLite concluído; não houve hash integral
  de origem, teste de integridade real, ensaio de captura/restauração ou E2E real.
- Busca inicial de código incluiu `app.py` inexistente e retornou código 2;
  complementada pela leitura de `app/main.py` e buscas nos diretórios existentes,
  sem impacto na bateria de testes. Nenhum resultado omitido como PASS.

**Bloqueios para liberar o ensaio:** (1) volume incompatível com limite/formato;
(2) ausência de barreira de escrita validada que preserve disponibilidade;
(3) cobertura de origens externas e referências persistidas não comprovada;
(4) destino/custódia/quotas, responsáveis e critérios RPO/RTO ainda indefinidos.
Privacidade do remoto permanece não verificada e envio continua fora do escopo;
um ensaio estritamente offline não depende de publicar em remoto.

**Decisão: BLOQUEADO.** É possível prosseguir com desenho e testes sintéticos das
correções, preservando todos os arquivos. A aprovação de código na Missão 2
não equivale a aptidão operacional. Não aumentar o limite, remover linhagem,
fracionar dados com perda ou parar o BI implicitamente para contornar bloqueios.
