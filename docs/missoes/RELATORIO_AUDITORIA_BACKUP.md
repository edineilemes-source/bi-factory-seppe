# Relatório — auditoria do backup seguro

Data: 2026-11-10, UTC. Missão 2. Conclusão: **APROVADO** para publicação
exclusiva dos oito arquivos listados abaixo, após as correções desta auditoria.
A aprovação se refere ao código e à documentação; não autoriza envio de dados,
uso operacional sem ensaio, commit ou push. Nenhum desses atos foi executado.

## Estado confirmado e método

Terminal local acessível em `/workspaces/bi-factory-seppe`. Branch obrigatória
confirmada: `feat/unificar-8504-8510`. HEAD:
`e2ddc98e1d189d2c10b930c04c8eb5d2668b1ca8`.
A referência `origin/feat/unificar-8504-8510` armazenada localmente tem o mesmo
SHA; divergência 0/0. Não houve fetch nem consulta ao estado vivo do GitHub.
O SHA `60e34d8` do relatório anterior é sua base histórica, não o HEAD atual.
As alterações auditadas permanecem no working tree, sem staging nesta missão.

Leitura inicial dos registros obrigatórios, instruções locais, relatório anterior,
código completo do utilitário e dos testes, requisito opcional e diff de ignore.
Inspeção de status/histórico e triagem de conteúdo limitada aos candidatos.
Nenhum backup real, restauração operacional ou parada de serviço. Os testes
executam somente fixtures sintéticas em diretórios temporários fora do checkout.
Não houve alteração nos módulos funcionais, ECharts, produtos ou layouts.

## Arquivos revisados

- `AGENTS.md`: regras de preservação e entrega; sem alteração.
- `docs/ESTADO_ATUAL.md` e `docs/DIARIO_TECNICO.md`: continuidade e evidências.
- `docs/missoes/RELATORIO_BACKUP_SEGURO.md`: implementação e procedimento anteriores.
- `scripts/secure_backup.py`: todas as funções e CLI.
- `tests/test_secure_backup.py`: fixtures e todos os casos.
- `requirements-backup.txt`: versão, licenças e dependências instaladas.
- `.gitignore`: regras existentes e quatro linhas adicionadas na missão anterior.
- `docs/missoes/RELATORIO_AUDITORIA_BACKUP.md`: esta entrega.

## Problemas confirmados e correções

1. **Dependência com correção de segurança posterior.** O requisito fixava
   `cryptography==46.0.6`. O changelog oficial registra CVE-2026-39892
   (buffers não contíguos e possível buffer overflow), corrigido em 46.0.7.
   Atualizado exclusivamente o requisito opcional para **46.0.7**, menor patch
   corretivo da mesma série; instalado apenas no venv temporário dos testes.
   O fluxo inspecionado usa bytes contíguos, não demonstrando exploração dessa
   CVE pelo utilitário. A correção evita manter deliberadamente a versão afetada.
   Fonte: [changelog oficial](https://cryptography.io/en/46.0.7/changelog/).
2. **Captura aceitava nomes que a verificação recusava.** No Linux, arquivos
   com dois-pontos ou barra invertida podiam ser cifrados, mas o próprio
   verificador rejeitava esses caminhos, impedindo o ciclo de restauração.
   Validação compartilhada agora recusa esses nomes já no inventário, antes
   de produzir o pacote. Também rejeita o alias `.` em manifesto autenticado:
   antes passava pela verificação e falhava apenas na gravação do destino.
   Três casos adicionais de regressão cobrem essas condições.

Nenhuma reescrita do formato, algoritmo criptográfico ou módulo operacional.
O relatório anterior foi preservado como histórico, com nota de atualização.

## Segurança e criptografia

AES-256-GCM usa chave aleatória de 32 bytes, nonce aleatório de 12 bytes e tag
integral, com cabeçalho versionado autenticado como AAD. Manifesto e nomes ficam
dentro do conteúdo cifrado. Hash público do cifrado não substitui autenticação.
A biblioteca faz a verificação da tag antes do processamento do ZIP. Nonces
independentes, chave errada, corrupção de cabeçalho/cifrado e truncamento estão
cobertos por testes. Não há senha fraca, derivação caseira, rede ou upload.

Chaves são lidas de arquivo regular com permissões privadas e tamanho exato;
CLI de geração exige destino externo ao checkout. Criação exclusiva evita
sobrescrita. O operador deve manter chave externa, com custódia e cópia de
recuperação separadas; carregar uma chave previamente colocada no checkout não
é bloqueado em todos os comandos. Ignore por sufixo não protege chaves com
outros nomes e não remove arquivos já rastreados.

## SQLite, integridade e restauração

A captura copia banco e WAL/journal para temporário privado, sem abrir SQLite
sobre a origem. A API de backup SQLite trabalha nessa cópia; SHM é reconstruído
ali. Snapshot e verificação executam integrity_check e foreign_key_check.
O teste WAL mantém a conexão sintética aberta, confirma os registros restaurados
e compara inventários da origem antes/depois. Journals associados são omitidos
do pacote restaurável porque o snapshot incorpora o estado confirmado.

Manifesto versionado verifica conjunto exato de entradas, tamanhos e SHA-256;
rejeita duplicatas, traversal e tipos inválidos. Não usa extractall. Verificação
completa precede criação do destino. Destino novo e externo ao projeto,
permissões privadas e criação exclusiva protegem o ambiente operacional.
Falha de I/O limpa somente a nova árvore da chamada, testada com sentinela externa.
SHA e integridade física não demonstram correção semântica de produtos/layouts.
A pausa declarada de todos os gravadores é indispensável para consistência global;
o utilitário não comprova nem executa essa pausa.

## Proteção de dados e seleção de publicação

Leitura integral dos candidatos e busca automatizada por cabeçalhos de chave
privada, formatos conhecidos de tokens, URLs com credencial, atribuições literais
de segredos, e-mails e CPF formatado: **nenhuma ocorrência detectada**.
Candidatos são arquivos regulares de texto, sem cabeçalho SQLite. Os JSON/CSV
nos testes são exemplos sintéticos criados em tmp_path, não exportações reais.
A triagem não constitui garantia universal de ausência de dados pessoais ou
segredos, nem auditoria de todo o histórico Git ou dos arquivos operacionais.

Há arquivos não rastreados de produtos e layouts em storage, além de cache,
build, dependências, FETCH_HEAD e cópia .bak do editor. Foram identificados
por caminhos/tipos sem transcrever seu conteúdo. Estão **excluídos** da aprovação
e foram preservados. Em especial, o ignore atual não cobre todos os arquivos
operacionais; publicação ampla do working tree ou `git add .` seria inadequada.
Nenhum banco, layout real, arquivo de ambiente, chave, pacote de backup,
transfer-plan ou arquivo operacional integra a lista autorizável.

## Lista exata autorizável para publicação

1. `.gitignore`
2. `requirements-backup.txt`
3. `scripts/secure_backup.py`
4. `tests/test_secure_backup.py`
5. `docs/ESTADO_ATUAL.md`
6. `docs/DIARIO_TECNICO.md`
7. `docs/missoes/RELATORIO_BACKUP_SEGURO.md`
8. `docs/missoes/RELATORIO_AUDITORIA_BACKUP.md`

O relatório anterior já está rastreado no HEAD; sua nota integra esta seleção.
A lista não autoriza qualquer outro arquivo do checkout. Uma publicação futura
precisa conferir o diff e a seleção efetiva novamente; esta missão não a executa.

## Bateria consolidada e dependências

- Ambiente: Python 3.12; `/tmp/seppe-backup-venv`, isolado da aplicação.
- Antes dos ajustes: `python -m pytest tests/test_secure_backup.py -q`:
  **17 passed**, 0 falhas, em 0,95 s.
- Após ajustes e atualização da dependência: mesma bateria:
  **20 passed**, 0 falhas, em 1,00 s (17 originais + 3 regressões).
- `python -m pip check`: PASS antes e depois.
- `git diff --check`: PASS; repetido após a documentação final.
- Licenças confirmadas nos metadados instalados: cryptography 46.0.7,
  Apache-2.0 OR BSD-3-Clause; cffi 2.1.1, MIT-0; pycparser 3.12,
  BSD-3-Clause; pytest 8.4.1, MIT (apenas teste); biblioteca Python, PSF-2.0.
- Backend observado: OpenSSL 3.5.6. Nenhuma dependência proprietária adicionada.
- Consulta ao changelog oficial não substitui auditoria exaustiva de CVEs de
  todas as transitivas/backends; não foi executado scanner completo de advisories.

## Riscos pendentes e limites da aprovação

- Ensaio real de restauração, pausa coordenada, inventário de origens externas,
  validação semântica e portabilidade de caminhos absolutos continuam pendentes.
- Limites: 256 MiB e 10.000 entradas; conteúdo em memória, sem streaming.
  Não há limite rígido de memória/CPU de processo contra fontes hostis que mudam.
- Temporários SQLite contêm plaintext sob diretório privado. Crash, swap, dump
  ou acesso privilegiado podem expor dados; não há secure erase. Usar ambiente
  confiável e armazenamento temporário cifrado conforme política operacional.
- Diretórios devem estar sob controle do operador: há janelas de troca de links
  e alterações entre verificações. Sem isolamento contra mesmo UID/root ou
  concorrência hostil. Inventário antes/depois não detecta mudança revertida.
- Restauração não preserva ACLs, proprietário, timestamps e hard links originais.
- Custódia/rotação de chaves, retenção, RPO/RTO, capacidade, prevenção de replay
  e monitoração precisam de decisão operacional. Sem esses controles, não se
  declara prontidão operacional nem recuperação garantida de produção.
- Privacidade, permissões e estado atual do remoto de backup não verificados.
  prepare-transfer continua offline com upload_enabled=false.

**Conclusão: APROVADO**, no escopo restrito de publicação dos oito arquivos de
código/documentação listados, com os riscos registrados. Nenhum bloqueio de
publicação foi identificado nesse escopo após as correções. Operação real e
publicação efetiva continuam fora desta execução. Sem commit, push ou migração.
