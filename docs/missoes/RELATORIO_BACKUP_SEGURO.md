# Relatório — backup seguro e recuperação

Data: 2026-11-10 (UTC). Branch local confirmada: `feat/unificar-8504-8510`.
SHA de base: `60e34d8f7e23b58b5142eb59ad18ba1ab6df9e3c`.
Referência remota local: mesmo SHA, divergência 0/0; sem fetch, sem consulta
atual ao servidor GitHub. Entrega em arquivos locais, sem commit/push.

## Resultado e escopo

Implementado utilitário independente `scripts/secure_backup.py`, sem mudanças
na aplicação, APIs, catálogo ou editor. Inclui toda a árvore `storage` por padrão:
SQLite, produtos, dashboards, layouts, metadados, biblioteca compartilhada,
publicações, originais, dados preparados, fontes oficiais e relatórios. Inclui
arquivos ocultos e diretórios vazios. Não inclui código, dependências, arquivos
fora da origem, configuração de ambiente ou segredos externos. Bancos em caminhos
personalizados fora de `storage` exigem uma captura separada com `--source`.
Não se presume que esses caminhos tenham dados no ambiente de destino.

**Nenhum backup operacional foi executado.** Testes usaram dados sintéticos em
áreas temporárias. Não houve restauração operacional, envio, acesso ao repositório
de backup, parada de serviços, exclusão ou sobrescrita de dados existentes.

## Consistência e formato

- Pré-condição obrigatória: todos os gravadores devem permanecer parados durante
  a captura (API, editor standalone, Streamlit, ETL, importadores e tarefas externas).
  `--writers-stopped` declara essa condição; o utilitário não suspende processos
  nem consegue provar que um gravador externo foi pausado.
- Inventário SHA-256 da origem antes/depois; alteração detectada recusa a captura.
  Isso complementa a pausa, não substitui uma transação entre arquivos e bancos.
- Bancos detectados pelo cabeçalho SQLite ou extensões `.db`, `.sqlite`, `.sqlite3`.
  O arquivo e journals WAL/rollback são copiados para temporário privado; SHM é
  reconstruído apenas nessa cópia. A API `sqlite3.Connection.backup` gera o
  snapshot dessa cópia. Nenhuma conexão SQLite abre o banco operacional.
- `PRAGMA integrity_check` e `foreign_key_check` no snapshot e na verificação.
  Journals correspondentes não integram o pacote restaurável: seus dados
  confirmados já estão no snapshot. Bancos inválidos ou referências inválidas
  interrompem a operação. Timeout de 30 s por operação de backup SQLite.
- ZIP sem compressão, manifesto interno versionado com caminho relativo, tipo,
  tamanho e SHA-256 de cada entrada. Manifesto e conteúdo ficam criptografados.
- AES-256-GCM: chave aleatória de 32 bytes, nonce aleatório de 12 bytes por pacote,
  tag de autenticação de 128 bits; cabeçalho versionado autenticado como AAD.
  Chave errada ou qualquer adulteração autenticada impedem a restauração.
- Artefato cifrado recebe SHA-256 separado no resultado e no plano de transferência.
  O hash público serve à conferência; a autenticidade vem do GCM.
- Restauração autentica e verifica todo o conteúdo antes de criar o destino.
  Rejeita caminhos absolutos, traversal, tipos inválidos, entradas extras e
  duplicadas, divergência no manifesto, links e arquivos especiais na origem.
  Não usa extração ZIP automática.
- Destino deve ser inexistente e externo à árvore do projeto; pais precisam
  existir. A API Python permite especificar `protected_root` em testes, enquanto
  a CLI protege sempre o projeto. Não existe comando de promoção para produção.
  Arquivos são criados exclusivamente (0600), diretórios privados (0700).
  Falha de gravação limpa somente o novo diretório criado pela própria chamada.
- Chaves e backups não sobrescrevem arquivos existentes. Chave não é aceita
  como argumento em texto: somente caminho para arquivo regular privado.

## Arquivos da entrega

| Arquivo | Mudança |
| --- | --- |
| `scripts/secure_backup.py` | CLI e funções de geração de chave, captura, verificação, recuperação isolada e preparação local |
| `requirements-backup.txt` | Dependência opcional isolada: cryptography 46.0.6 |
| `tests/test_secure_backup.py` | 17 testes sintéticos direcionados |
| `.gitignore` | Proteção adicional para `*.sepbackup` e `*.seppekey` |
| `docs/missoes/RELATORIO_BACKUP_SEGURO.md` | Este relatório e procedimento |
| `docs/ESTADO_ATUAL.md` | Estado confirmado e limitações da entrega |
| `docs/DIARIO_TECNICO.md` | Registro técnico com SHA e resultados |

Arquivos não rastreados anteriores preservados: `.vite/`, `FETCH_HEAD`, cópia
`.bak` do editor, diretórios de produtos e dashboards, build e node_modules da UI.
Não se confundem com arquivos novos desta entrega.

## Procedimento local

Exemplo com caminhos ilustrativos; não foi executado contra dados reais.
Use disco privado e persistente, fora do checkout. A pasta deve existir e ser
restrita ao operador. Não guardar chaves no repositório, no pacote nem no mesmo
local de retenção dos backups. Manter cópia de recuperação da chave em cofre
separado. Perder a chave torna o backup irrecuperável.

```bash
python -m venv /tmp/seppe-backup-env
/tmp/seppe-backup-env/bin/pip install -r requirements-backup.txt
# Substitua os caminhos abaixo pelo armazenamento privado aprovado.
/tmp/seppe-backup-env/bin/python scripts/secure_backup.py keygen --key-file /local-privado/chave.seppekey
# Pausar todos os gravadores ANTES do create; mantê-los parados até terminar.
/tmp/seppe-backup-env/bin/python scripts/secure_backup.py create --key-file /local-privado/chave.seppekey --backup /local-privado/captura.sepbackup --writers-stopped
# Encerrado o create com sucesso, os gravadores podem ser retomados.
/tmp/seppe-backup-env/bin/python scripts/secure_backup.py verify --key-file /local-privado/chave.seppekey --backup /local-privado/captura.sepbackup
/tmp/seppe-backup-env/bin/python scripts/secure_backup.py restore --key-file /local-privado/chave.seppekey --backup /local-privado/captura.sepbackup --destination /local-privado/recuperacao-nova
/tmp/seppe-backup-env/bin/python scripts/secure_backup.py prepare-transfer --key-file /local-privado/chave.seppekey --backup /local-privado/captura.sepbackup --destination /local-privado/entrega-nova
```

A restauração produz `recuperacao-nova/storage/` e `manifest.json` privado.
Inspecionar semanticamente os produtos e layouts na cópia antes de qualquer
promoção, que exige procedimento separado. Não apontar serviços operacionais
para a cópia durante a validação inicial. CLI retorna JSON resumido no sucesso,
código 1 e erro sem conteúdo/caminhos no fracasso.

## Integração preparada, envio desabilitado

`prepare-transfer` verifica o pacote e cria exclusivamente `snapshot.sepbackup`
e `transfer-plan.json` com SHA-256 do cifrado, destino lógico
`edineilemes-source/bi-factory-seppe-backup` e `upload_enabled: false`.
Não copia chave nem manifesto em claro para a entrega. Não executa Git, HTTP,
clone, commit ou push. Não instala workflow nem agenda upload. A existência,
privacidade, permissões, limites e retenção do repositório remoto permanecem
não verificados. A ativação futura requer verificação desses itens e autorização
explícita para envio; a ferramenta entregue não contém comando de upload.

## Testes e evidências consolidadas

Ambiente de teste isolado: `/tmp/seppe-backup-venv`, Python 3.12.
Bateria: `/tmp/seppe-backup-venv/bin/python -m pytest tests/test_secure_backup.py -q`.
**PASS: 17 testes.** `pip check`: **PASS**, sem dependências quebradas.
`git diff --check`: **PASS**. Conferência final repetida após ajustes de limites.

Cobertura: recuperação integral; SQLite com WAL aberto e dados confirmados;
SHA-256 e integridade SQLite; preservação byte a byte da origem; diretórios
vazios; corrupção de cabeçalho/cifrado e truncamento; chave incorreta; manifesto
com hash errado; entrada extra e traversal mesmo em payload autenticado;
SQLite inválido com hash correto; recusa de sobrescrita e destino operacional;
exigência de pausa; rejeição de links; mudança concorrente detectada; permissões
de chave; preparação local sem envio; limites; falha de I/O com limpeza isolada;
nonces independentes; ciclo completo CLI e códigos de saída.

A primeira execução detectou alteração no SHM por conexão SQLite somente leitura
(11 falhas, 3 sucessos). Corrigido para trabalhar exclusivamente sobre cópias
privadas; execução seguinte passou os 14 testes iniciais, depois ampliada para 17.
Não foram executados testes E2E de UI, integração com GitHub, nem ensaio real de
recuperação operacional. Nenhum módulo funcional existente foi alterado.

## Dependências e referências

Dependência de produção opcional: `cryptography 46.0.6`, Apache-2.0 OR BSD-3-Clause.
Transitivas observadas: `cffi 2.1.1`, MIT-0; `pycparser 3.12`, BSD-3-Clause.
Licenças confirmadas pelos metadados dos pacotes instalados. Biblioteca padrão
Python: PSF-2.0. pytest 8.4.1 (MIT) somente para testes.
Documentação primária: [AEAD cryptography](https://cryptography.io/en/stable/hazmat/primitives/aead/)
(AESGCM, nonce e InvalidTag); [SQLite Online Backup](https://www.sqlite.org/backup.html).

## Riscos e pendências

1. Pausa externa é indispensável para consistência entre múltiplos bancos/JSON.
   Detecção antes/depois não garante ausência de alterações transitórias revertidas.
2. Limite deliberado: 256 MiB de origem/payload e 10.000 entradas; várias cópias
   residem em memória. Volume maior é recusado; exige formato streaming futuro.
3. SQLite temporário fica em diretório 0700; arquivos ZIP/manifesto ficam em memória.
   Temporários são removidos ao sair normalmente, mas interrupção abrupta, swap,
   dumps ou acesso privilegiado podem expor plaintext. Usar máquina/disco confiável
   e temporário privado cifrado/tmpfs conforme política local. Não há secure erase.
4. Ferramenta pressupõe diretórios sob controle do operador, sem usuário hostil
   trocando links durante a execução. Não constitui isolamento contra o mesmo UID/root.
5. Não preserva ACLs, proprietário, timestamps, hard links ou permissões originais:
   restauração usa permissões privadas. Caminhos absolutos persistidos dentro de
   SQLite/JSON não são reescritos; validação da cópia precisa avaliar portabilidade.
6. Não inclui código/configurações externos à origem. Inventariar bancos adicionais
   e dependências reais antes do primeiro backup operacional. Não embutir segredos
   em `storage`; todo conteúdo dessa árvore é capturado e deve ser tratado como sensível.
7. Sem política automática de retenção, rotação de chaves, agendamento, prevenção
   de replay ou monitoração; definir RPO/RTO e ensaiar recuperação antes de uso regular.
8. Em encerramento abrupto pode restar artefato incompleto ou restauração parcial
   isolada; verificação deve preceder uso. Nenhum dado operacional é substituído.
9. Não há evidência de sincronização atual com GitHub nem de envio; SHA registrado
   é a base, pois commit/push foram expressamente proibidos.
