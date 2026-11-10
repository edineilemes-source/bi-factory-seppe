# Missão 5 — Homologação sintética do backup incremental

Data: 2026-11-10 UTC. **Decisão: APROVADO para o escopo sintético desta missão.
BLOQUEADO para produção.** Restic foi executado de verdade: backup incremental,
verificação completa e restauração de arquivo acima de 2 GiB comprovados.
A aprovação não ativa execução, remoto, agenda ou captura operacional.

## Estado e arquivos

Lidos AGENTS.md, ESTADO_ATUAL.md, DIARIO_TECNICO.md, os quatro relatórios
anteriores, scripts/secure_backup.py, scripts/backup_architecture.py, política
e testes direcionados. Terminal local acessível em /workspaces/bi-factory-seppe.
Branch confirmada: `feat/unificar-8504-8510`. HEAD e upstream armazenado:
`b09fffaf2b341b71b3c2f10f7840f79448080312`, divergência 0/0. Sem fetch ou
consulta viva ao GitHub do projeto; isso não comprova sincronização remota atual.

Criados:

- `scripts/homologate_backup_synthetic.py`: laboratório reproduzível Linux,
  executável apenas por solicitação explícita, sem argumento de origem operacional.
- `docs/missoes/RELATORIO_HOMOLOGACAO_BACKUP.md`: este relatório.

Alterados: `docs/ESTADO_ATUAL.md` e `docs/DIARIO_TECNICO.md`, por acréscimo.
Não alterados: módulos BI, utilitário anterior (limite 256 MiB), planejador,
política e template de cron. `execution_enabled`, `remote_enabled` e
`schedule_enabled` continuam **false**. A grafia efetiva da primeira chave é
`execution_enabled`; nenhuma chave alternativa foi introduzida.

Não rastreados preexistentes preservados: .vite/, FETCH_HEAD, cópia .bak do
editor, storage/dashboard_projects/, storage/information_products/, dist/ e
node_modules/ da UI. Nenhum conteúdo operacional foi aberto/copiado nesta missão.
Nenhum staging, commit ou push neste repositório. Os únicos commits de teste
foram criados no repositório Git inteiramente sintético privado exigido na tarefa 7.

## Ferramenta, licença e integridade

Restic **0.19.1**, compilado com **go1.26.4**, linux/amd64. Binário oficial
baixado para `/tmp/seppe-m5-tool-opyb7gmx/restic`, sem instalação global ou serviço.
Licença **BSD-2-Clause** confirmada no LICENSE da tag exata v0.19.1, conservado
no mesmo diretório privado. Apenas download público de ferramenta/metadados;
nenhum envio de dados, acesso ao destino de backup ou rede durante os ensaios.

| Evidência | SHA-256 |
| --- | --- |
| restic_0.19.1_linux_amd64.bz2 | `f415415624dcc452f2a02b8c33641791a8c6d6d3b65bbb3543fcf9a25151585c` |
| Binário descomprimido executado | `20d4142678d0d95ec11a4759def1b73fd9190abc9ca19e4b62d067c0b387e639` |
| LICENSE da tag | `6f08a01a9fab5b24e139a09f15cc24a73087c7bc09e3bacf099fdf2d767bf897` |

O SHA-256 do arquivo baixado foi comparado por assert ao SHA256SUMS da mesma
release via HTTPS **antes** da descompressão/execução. Não houve verificação
GPG nem compilação reproduzível; checksum e download compartilham o provedor.
Não se apresenta isso como autenticação independente da cadeia de distribuição
ou auditoria completa de advisories/licenças transitivas incorporadas ao binário.
Referências primárias: [release e checksums](https://github.com/restic/restic/releases/tag/v0.19.1),
[licença fixada](https://github.com/restic/restic/blob/v0.19.1/LICENSE).
Python padrão: PSF-2.0; Git: GPL-2.0-only. Sem nova dependência Python.
Dependências opcionais e de teste anteriores mantidas, sem atualização.

## Isolamento e recursos

Laboratório final: `/tmp/seppe-m5-lab-xif380iz`, criado por mkdtemp com modo
0700; umask 077 para descendentes. Ambiente dos subprocessos reconstruído com
allowlist, sem herdar credenciais, configuração Git global, senha Restic ou
origens do ambiente do operador. Senhas aleatórias somente em arquivos privados
do laboratório; valores não registrados. Restic usa backend local e --no-cache;
GOMAXPROCS=2, timeout de 180 s por comando. Sem serviços ou cron.

Fonte gerada: layout JSON v1/v2, 8 MiB aleatórios e arquivo esparso de
**2.164.260.864 bytes (2,015625 GiB)**. Origem grande inicialmente ocupava
4.096 bytes físicos. Validação prévia exigiu pelo menos 4 GiB livres; observados
cerca de 41 GiB disponíveis em /tmp. SHA-256 em blocos de 1 MiB; arquivo grande
foi lido de verdade pelo Restic e pelos verificadores, sem alocação integral Python.

Restauração --sparse: arquivo grande ocupou 524.288 bytes na v1 e 1.048.576 na
v2. Repositório final: 8.478.720 bytes físicos de arquivos; cópia para corrupção:
mesmo volume. Árvores restauradas: 8.916.992 e 9.441.280 bytes. Valores não
incluem blocos de diretórios. Sem remoção dos laboratórios ou de dados existentes.
A primeira tentativa ficou preservada em `/tmp/seppe-m5-lab-2blwiv1s`.
Temporários não são armazenamento durável; não adicionar esses artefatos ao Git.

## Bateria e resultados observados

Execução final: **18 verificações PASS, 36 subprocessos, 33,819 s**, incluindo
hashes, preparação e coordenação. Evidência privada detalhada (argv, retorno e
duração por subprocesso, sumários Restic e assertions):
`/tmp/seppe-m5-lab-xif380iz/evidence.json`. Não contém senhas ou dados reais.

| Ensaio | Resultado / duração do subprocesso |
| --- | --- |
| Versão e hash do executável | PASS; 0,016 s |
| Init formato 2, destino novo | PASS; 2,453 s |
| Backup inicial | PASS; 3 arquivos, 2.172.649.485 bytes processados; 2,326 s |
| Segundo backup incremental | PASS; 2 arquivos alterados, 1 inalterado; 3,705 s |
| Terceiro backup sem mudança | PASS; 3 inalterados, zero novos blobs/dados; 1,051 s |
| check --read-data | PASS; 1,013 s |
| Restore v1 explícita, --verify --sparse e hashes | PASS; 3,879 s de Restic |
| Restore v2 explícita, --verify --sparse e hashes | PASS; 3,433 s de Restic |
| Senha incorreta | Recusa esperada, código 12; 0,474 s |
| Destino de restore existente | Helper rejeitou antes de executar Restic; sentinela intacta |
| Init de repositório existente | Recusa código 1; config cifrado com hash preservado; 0,017 s |
| Repositório indisponível | Caminho inexistente, código 10; sem criar destino; 0,016 s |
| Snapshot incompleto | Arquivo sintético ausente + válido: código 3, snapshot criado, conjunto rejeitado; 0,665 s |
| Arquivo alterado durante captura | Escritor concorrente; hash antes/depois diferente; Restic retornou 0, conjunto rejeitado; 0,742 s |
| SQLite + JSON coordenados e recuperados | PASS; backup 0,710 s, restore 0,662 s |
| Concorrência multiprocesso e liberação da barreira | PASS; 40 gerações, 31 capturas coerentes; etapa 1,582 s incluindo backup/restore |
| Git bundle sintético completo | PASS; duas branches, duas tags e versões antigas conferidas |
| Corrupção / preservação do repositório original | Cópia corrompida: check código 1 em 0,742 s; original: check 0 em 0,753 s |

A tabela agrupa verificações relacionadas; os 18 registros PASS constam na
evidência. Códigos não zero esperados são sucesso dos testes de falha, não
backup aprovado. Nenhum conjunto parcial/alterado foi usado nas restaurações
aprovadas. Não há catálogo de promoção operacional implementado pelo laboratório.

Primeira tentativa: 30,274 s, interrompida na injeção de corrupção porque os packs
copiados preservaram modo somente leitura. Não foi declarada aprovada. Corrigido
para chmod 0600 **apenas no pack da cópia sintética de corrupção**; bateria
completa repetida acima. Acrescentada recuperação Restic do estágio SQLite+JSON
na versão final. Origem e repositório sintéticos íntegros preservados.

Regressão direcionada:
`/tmp/seppe-backup-venv/bin/python -m pytest tests/test_secure_backup.py tests/test_backup_architecture.py -q`
→ **47 passed em 5,47 s**. Mesmo Python, `-m pip check` → sem requisitos quebrados.
`git diff --check` → PASS na conferência final. Não executados testes de UI ou
imports/startup de aplicações, que poderiam tocar dados operacionais.

## Incremental e recuperação de versões

| Captura | Dados novos lógicos Restic | Dados novos comprimidos/empacotados |
| --- | ---: | ---: |
| Inicial | 9.715.207 bytes | 8.390.533 bytes |
| Incremental | 802.311 bytes | 1.055 bytes |
| Sem alterações | 0 | 0 |

A alteração foi localizada no meio do arquivo grande e no layout JSON. Houve
reutilização de blocos e reconhecimento do arquivo aleatório inalterado.
Volumes novos não equivalem ao tamanho total lógico da fonte; zeros repetidos
favorecem fortemente deduplicação/compressão. Estes tempos não projetam vazão,
memória máxima, capacidade ou RTO de dados operacionais incompressíveis.

Snapshots completos explicitamente restaurados:

- v1: `0ab71b3e92a4c4c0a56a3737da880eeb7294099daedd621cd5e1deba2307a124`.
- v2: `dd7d7d7d637b8b52a6f96b5b84e8a2505ff95a55e5926493490fcf52a67738a0`.
- SQLite+JSON: `6e551810112f04636bb0a1c7516b7010754b8a3dc08568808e9ec947268d5d32`.

SHA-256 do arquivo grande restaurado e respectiva origem histórica:
v1 `92490dcfe82e0600d8f90d763a575e2225e3b76eebce40dca0cbb2ebe89a1b46`;
v2 `e268c75f5f832305c8c4360f17f9f601d78320e54a2a96be59999b3ffae0d2b7`.
Conferidos também tamanho, conteúdo do layout, hash do arquivo estável e conjunto
exato de nomes. Nenhuma restauração usa latest ou sobrescreve destino existente.
O helper protege destino novo; Restic puro não fornece essa política por si só.

## Coordenação SQLite + JSON: alcance do protótipo

Processo escritor simula 40 atualizações: commit SQLite, intervalo deliberado,
e substituição atômica JSON, sob flock exclusivo comum. Captura adquire o mesmo
lock, drena escrita ativa, executa backup API SQLite para cópia nova e copia JSON.
Integridade/FK e igualdade da geração SQLite–JSON são verificadas na cópia.

Handshake entre processos expôs deliberadamente DB=1 / JSON=0 sem barreira;
a tentativa não bloqueante de obter o lock confirmou que o escritor o detinha.
Após liberação, 30 capturas concorreram com o escritor; captura final confirmou
geração 40. Estágio final passou por Restic e restore isolado, com validação de
SQLite e JSON restaurados. Exceção dentro da barreira liberou o lock, confirmado
por nova aquisição não bloqueante.

É um protótipo cooperativo **somente em fixtures**, sem integração real. flock
não impede gravadores que ignorem o protocolo. Não demonstra atomicidade após
crash entre commit e JSON, coordenação distribuída, preservação de disponibilidade
da UI, justiça do lock, prazo máximo de espera nem retomada após SIGKILL. Leituras
sem barreira podem observar o intervalo inconsistente. A futura solução precisa
gerações/manifesto, rejeição e recuperação de operações incompletas, timeout e
adesão de todos os gravadores. Restic retornar 0 não prova consistência global;
inventário antes/depois também não detecta alteração transitória revertida.

## Reconstrução Git

Repositório privado gerado do zero, sem remoto e sem copiar .git do projeto:
branches main/feature, dois commits, tag anotada v1 e leve v2. `bundle --all`,
verify, clone --mirror, fsck --full e comparação exata de refs/OIDs passaram.
Conteúdo histórico recuperado por SHA e por tag. SHA-256 do bundle sintético:
`3be40e582588c983064a60131fb488410b7471b1c4341cd41cf134134bb1bfe1`.
Identidade local fictícia; configuração global/sistema desabilitada.

Prova mecanismo Git, não reconstrução funcional do BI. Dependências, LFS,
submódulos, histórico com possíveis segredos, arquivos não rastreados e objetos
inalcançáveis não estão homologados. Bundle sintético não contém credenciais.

## Comandos e repetição segura

Preparação executada por Python urllib: consulta pública da release oficial,
download de `restic_0.19.1_linux_amd64.bz2` e `SHA256SUMS`, comparação SHA-256,
descompressão bz2, modo 0700; download do LICENSE fixado. Evidência em
`/tmp/seppe-m5-tool-opyb7gmx/verification.json` e LICENSE. Para repetir, verificar
a ferramenta novamente e reservar recursos; o laboratório sempre cria raiz nova.

```bash
python scripts/homologate_backup_synthetic.py --restic /tmp/seppe-m5-tool-opyb7gmx/restic
/tmp/seppe-backup-venv/bin/python -m pytest tests/test_secure_backup.py tests/test_backup_architecture.py -q
/tmp/seppe-backup-venv/bin/python -m pip check
git diff --check
```

O script registra cada argv sem shell/eval. Comandos Restic realmente usados:
`version`, `init --repository-version 2`, `backup --json --host synthetic --tag
mission5 -- .`, `check --read-data`, `restore ID --target NOVO --verify --sparse`,
`snapshots`, init repetido e backup com caminho sintético ausente. Repo sempre
local em raiz privada; senha via RESTIC_PASSWORD_FILE, nunca literal em argv.
Na corrupção, um byte foi invertido em pack de cópia independente criada por
copytree; original conferido novamente. Não houve prune, forget, reset ou limpeza.

## Pendências para produção e decisão

1. Integrar e homologar barreira de todos os gravadores reais, drenagem, timeout,
   recuperação de crash e consistência semântica entre múltiplos bancos/artefatos.
2. Implementar produtor de staging selado e runner operacional com catálogo de
   gerações aceitas; recusar qualquer retorno não zero e conjunto incompleto.
3. Inventariar origens externas/PostgreSQL, revisar segredos de conteúdo/histórico,
   validar dependências e reconstruir o BI completo isoladamente.
4. Aprovar destino persistente privado independente, capacidade, imutabilidade,
   custódia/recuperação de senha, retenção e responsáveis. Sem ensaio de rede.
5. Medir carga representativa, recursos e RPO/RTO operacionais, testar custódia
   independente, indisponibilidade durante operação e falhas abruptas. O teste de
   indisponibilidade aqui foi somente backend local ausente no início do comando.
6. Definir cadeia de confiança de distribuição (assinatura e chave por canal
   independente), revisão de advisories e transitivas antes da implantação.

**APROVADO: homologação sintética incremental e recuperável, com limites acima.**
**BLOQUEADO: produção e ativação.** Nenhum backup real, envio, alteração de banco
existente, parada de serviço, exclusão, cron, commit ou push do projeto realizado.
