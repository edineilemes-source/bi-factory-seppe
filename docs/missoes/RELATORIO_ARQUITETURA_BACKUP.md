# Missão 4 — Arquitetura de backup e recuperação SEPPE

Data: 2026-11-10 UTC. **Conclusão: BLOQUEADO para produção.** Arquitetura,
política e preparação offline entregues; execução operacional deliberadamente
ausente. Não foi implantado um serviço de backup nem garantida recuperação real.

## Evidências e escopo

Lidos AGENTS.md, ESTADO_ATUAL.md, DIARIO_TECNICO.md e os três relatórios
BACKUP_SEGURO, AUDITORIA_BACKUP e PREVALIDACAO_BACKUP; inspecionados utilitário
anterior, catálogo/API, repositório SQLite, requisitos e configuração de ambiente.
Branch confirmada: `feat/unificar-8504-8510`. SHA local e upstream armazenado:
`b61f7fde3b63bb58e43c9eb3c3914cf117f76e1a`; divergência 0/0.
Sem fetch ou consulta viva ao GitHub. Terminal local acessível nesta execução.
Os dois documentos de continuidade já estavam modificados; suas entradas foram
preservadas e esta missão acrescenta registros. Não rastreados preservados.

O inventário da Missão 3 registrou cerca de 2,465 GiB, incluindo um arquivo
individual próximo de 2 GiB; não foi refeito nem lido conteúdo operacional aqui.
O limite de 256 MiB do utilitário anterior permanece, sem aumento artificial.
Nenhum banco foi aberto nesta missão, nenhum serviço alterado/interrompido,
backup operacional, transferência remota, exclusão, staging Git, commit ou push.

## Classes e cobertura

| Classe | Conteúdo e autoridade | Tratamento |
| --- | --- | --- |
| A | Código, módulos, arquitetura, documentação, migrações, esquemas declarativos e configuração pública versionada | Git completo, espelho privado independente e bundles históricos cifrados |
| B | Produtos, pastas, layouts, biblioteca, metadados, publicações e configuração operacional sem segredos | Mesmo conjunto consistente que C, via staging privado e Restic |
| C | SQLite, originais, relatórios, prepared, linhagem e staged; configurações de esquemas efetivas no banco | Preservação integral por padrão, incremental deduplicado |
| D | node_modules, dist e caches reconhecidos, reconstruíveis após validação de versões | Sem exclusão automática; preservar até comprovar reconstrução |

`config/backup/policy.json` define regras por prefixo, priorizando o mais
específico. Desconhecidos em storage são C; fora das raízes são UNCLASSIFIED,
exigindo decisão explícita. Nome real-test, .bak ou extensão grande não autoriza
exclusão. Código A é selecionado por refs Git auditadas, não por adivinhar extensão.
Um esquema pode ter definição em A e estado efetivo em B/C; ambos são necessários.

Inventário completo futuro deve cobrir todas as raízes externas, caminhos
substituídos por argumentos/configuração, arquivos não rastreados relevantes,
submódulos, objetos LFS e PostgreSQL se efetivamente usado. Git bundle não inclui
LFS externo, dados não rastreados, reflogs ou objetos inalcançáveis. Não se declara
que essas fontes foram cobertas. D permanece fora de qualquer limpeza nesta missão.

Segredos são uma categoria de custódia separada, nunca conteúdo de snapshot:
revisão por nome é somente triagem, não detector suficiente de conteúdo. O
classificador recusa nomes usuais de chaves/ambiente e exige REVIEW_SECRET.
Mesmo um JSON comum pode conter credenciais: revisão de conteúdo privada,
allowlist e validação do histórico Git são pré-condições ainda não implementadas.
Não empacotar checkout inteiro, `.git/config`, ambiente, credenciais de provedores
ou configurações privadas. Configurações públicas têm templates sem valores;
credenciais são reprovisionadas de cofre separado, com recuperação independente.
Se histórico Git contiver segredo, bloquear espelhamento; revogar o segredo e
planejar remediação separada sem reescrever/apagar o histórico nesta missão.

## Código: Git e independência

Git continua sendo controle de versões; espelho não substitui retenção histórica.
O planejador prepara `clone --mirror --no-hardlinks` para um destino novo,
`fsck --full`, bundle `--all` e verificação do bundle. Não executa comandos.
O clone deve originar-se de repositório auditado completo, sem shallow/partial;
comparar inventário privado de refs/OIDs antes/depois e registrar SHA do código
associado ao conjunto B+C. Conferir branches locais, remotas, tags e notes;
uma cópia somente do GitHub pode perder commits/branches ainda exclusivamente locais.

Preparar provedor/conta administrativa independente do primário, privado,
privilégios mínimos, MFA e credenciais fora do checkout. Endereço não definido
nem acessado nesta missão. Não há comando de push no planejador. Antes de envio
futuro, confirmar privacidade, quota, titular e autorização. Não copiar hooks,
credential helpers ou configuração local com segredos. Não usar hardlinks para
independência física. Bundles também precisam criptografia e custódia de chave.

Atualização futura: criar espelho de geração nova ou atualizar cópia dedicada
somente após preservar bundle imutável anterior; comparar refs, sem propagar
deleções automaticamente. Um mirror atualizado pode refletir apagamentos e
force pushes, portanto manter gerações diárias/semanais/mensais recuperáveis.
Ref snapshots e manifests privados identificam versões anteriores por SHA.

## Restic e dados de vários gigabytes

Escolha proposta: Restic, licença **BSD-2-Clause**, versão candidata **0.19.1**
observada na documentação oficial. Não instalado. Fixar versão e verificar
checksum/assinatura do binário e suas dependências antes de homologação.
O projeto documenta deduplicação/incrementais e autenticação dos dados por
AES-256-CTR + Poly1305-AES; não confundir com AES-GCM do utilitário anterior.
Referências: [projeto/licença](https://github.com/restic/restic),
[formato criptográfico](https://restic.readthedocs.io/en/v0.18.0/design.html),
[backup](https://restic.readthedocs.io/en/stable/040_backup.html).

Restic recebe arquivos de staging diretamente, sem ZIP monolítico nem leitura
integral em memória pelo wrapper. Arquivos de múltiplos GiB são requisito de
homologação real, não resultado comprovado aqui. Evitar cifrar cada arquivo ou
ZIP antes do Restic, o que prejudicaria deduplicação; usar volume de staging
cifrado, privado e com swap/dumps controlados. Destino Restic privado cifrado,
fora do checkout, inicialmente local persistente; cópia offsite independente
é fase posterior, sem autorização de envio nesta missão.

O plano fornece argumentos separados para init formato 2, backup, snapshots,
check completo, recuperação e retenção em dry-run. Localização do repositório e
senha vêm de arquivos externos distintos; somente placeholders são emitidos.
Não executar a saída com eval. Backup tem CWD no staging selado e caminho `.`
para estabilidade do agrupamento; deve conter todas as raízes B+C, mapeadas sem
colisões, e manifesto privado com geração, refs Git, hashes e versões de esquema.
Falha ou código de retorno não zero, incluindo captura parcial do Restic, reprova
o conjunto e gera alerta. Não promover captura incompleta como ponto recuperável.

## Consistência: requisito ainda bloqueante

API/editor, Streamlit, ETL, prepared, CLI e gravadores externos devem compartilhar
uma barreira de escrita. É necessário impedir novas mutações, drenar trabalhos
em andamento e congelar conjuntamente SQLite, JSON, CSV e linhagem. Não basta
observar ausência de processos ou bloquear POST. Leitura/startup pode gravar.
Nenhuma barreira foi implementada nos módulos funcionais nem serviço interrompido.

Fluxo projetado: obter mutex exclusivo da tarefa; verificar capacidade e todos
os gravadores; adquirir barreira validada; criar staging privado novo e geração;
copiar arquivos estáveis por streaming e bancos com WAL/journal associado para
cópias privadas; usar backup API SQLite nessas cópias e executar integrity_check
e foreign_key_check; conferir referências JSON–bancos–artefatos; registrar
manifesto e selar staging; liberar barreira em finally, inclusive em falha.
WAL/journal só deixam de integrar a imagem restaurável após snapshot válido;
nunca excluir os da origem. SQLite backup sozinho não cria transação entre
bancos/arquivos. Não copiar banco vivo ignorando WAL nem usar immutable sobre
origem ativa. Hash antes/depois complementa barreira, não prova consistência.

Após liberar escritas, Restic captura somente staging selado, verifica snapshot
e restaura isoladamente. Prazo máximo de barreira e recuperação da liberação
precisam ser testados. Se barreira com disponibilidade não for viável, negociar
janela em outra missão; não declarar escritores pausados sem evidência.
O produtor de staging/runner é **pendente**, não parte executável desta entrega.

## Retenção, capacidade e objetivos propostos

- Captura A após mudanças publicadas e checkpoint diário; B+C diário às 02:00 UTC.
- Reter 14 diários, 8 semanais, 12 mensais por conjunto; união de pontos escolhidos,
  não promessa de exatamente 34 snapshots. Preservar último conjunto comprovado.
- `forget` preparado somente com `--dry-run`, filtrado por host/tag e agrupamento
  explícito. Remoção efetiva/prune exige revisão futura, validação de recuperação
  e política aprovada. Nenhuma exclusão programada.
- RPO proposto A: até 24 h de mudanças auditadas; B+C: 24 h desde geração coerente.
  Commits locais não espelhados e mudanças não versionadas continuam em risco.
  RTO proposto A: 2 h; recuperação completa B+C e validação: 8 h.
  São metas a aceitar e medir; não SLAs demonstrados nem garantia de perda máxima.
- Planejar 12 meses: L = volume lógico projetado, U = blocos únicos alterados/dia.
  Repositório conservador inicial: L + 366×U + 30% de margem, sem assumir ganho
  de compressão; medir e revisar mensalmente. Reservar separadamente staging,
  cópias SQLite e restauração: pelo menos 3×L mais espaço de bancos/journals,
  overhead e margem. Alerta de quota em 70%, crítico em 85%; impedir nova captura
  antes de esgotar disco. Não limpar automaticamente para contornar quota.
- Responsável proposto: operador de infraestrutura para captura/alertas;
  custodiante separado para recuperação de senha; mantenedor BI para aceite
  semântico. Pessoas, destino, orçamento e armazenamento imutável são pendentes.

Senha forte gerada em cofre, cópia de recuperação separada e ensaio de acesso sem
credencial do host original. Cifrar não impede exclusão pelo administrador do
destino: prever offline/append-only/object lock, credenciais separadas para
retenção e cópia independente. Rotação de senha não neutraliza automaticamente
chaves já comprometidas: considerar novo repositório e recaptura aprovada.

## Recuperação completa e versões anteriores

1. Escolher geração validada e IDs completos explícitos, também para versão
   anterior; registrar SHA Git, ID Restic, hashes, versão de ferramenta e esquema
   em inventário privado. Não usar `latest` automaticamente em desastre.
2. Disponibilizar máquina isolada, armazenamento privado e cofre recuperável;
   negar acesso à produção e à rede externa do app. Rodar check completo do
   repositório antes de restauração; hash de manifesto não substitui autenticação.
3. Verificar bundle, clonar para checkout novo, rodar fsck e conferir refs/OIDs;
   selecionar SHA vinculado à geração. Recuperar submódulos/LFS caso existam.
   Não promover espelho como diretório de trabalho nem executar hooks não revistos.
4. Preparar Python 3.12 em venv; instalar requirements.txt e requisitos opcionais
   necessários. Node/npm compatíveis com engines do package-lock, `npm ci` em
   web/bi_factory, depois `npm run build`. Comandos são procedimento futuro,
   não executados nesta missão. Arquivar versões/licenças e pacotes aprovados
   para independência dos registries. Node não está fixado: homologação pendente;
   Python tem transitivas não totalmente travadas: reconstrução exata pendente.
5. Restaurar B+C com ID completo para destino **novo**, externo ao checkout,
   produção, staging e repositório Restic; `restore --verify`. O helper
   restore_target rejeita destinos existentes, links e sobreposição com raízes
   protegidas fornecidas; não executa restauração. Futuro runner deve reservar
   destino exclusivamente em pai privado e revalidar imediatamente antes de
   executar, pois checagem prévia sozinha tem janela de corrida.
6. Conferir hashes/conjunto exato do manifesto, SQLite integrity/FK nas cópias,
   vínculos de registry/pastas/layouts/projetos/biblioteca/prepared/linhagem,
   esquemas e completude de raízes. Reprovisionar segredos pelo cofre e ajustar
   caminhos absolutos exclusivamente na cópia. Dados PostgreSQL, se usados,
   exigem procedimento consistente próprio com ferramentas PostgreSQL homologadas.
7. Somente após isolamento comprovado, subir API (`serve_bi_factory_api.py`,
   porta local 8505), UI Vite (padrão 8504) ou Streamlit conforme perfil necessário,
   em portas privadas e ambiente isolado; conferir proxy. Startup pode migrar
   SQLite: guardar imagem restaurada intacta e testar sobre cópia descartável.
   Validar produtos, layouts, gráficos ECharts e persistência com fixtures.
8. Medir tempos e perda temporal. Aceite do responsável antes de cutover real.
   Falha: preservar origem e evidência, manter cópia rejeitada isolada, selecionar
   geração anterior. Sem restauração sobre produção ou limpeza automática.

Referências: [recuperação Restic](https://restic.readthedocs.io/en/stable/050_restore.html),
[verificação de repositório](https://restic.readthedocs.io/en/stable/045_working_with_repos.html),
[Git mirror](https://git-scm.com/docs/git-clone),
[Git bundle](https://git-scm.com/docs/git-bundle).

## Agendamento e plano periódico

`ops/backup/schedule.cron.disabled` contém apenas comentários, UTC, sem instalação.
Runner referenciado é placeholder inexistente e não deve ser ativado. Antes da
ativação: mutex, barreira e timeout, staging, custódia, limites, supervisão de
falhas, liberação garantida e alertas sem caminhos/conteúdo sensível em logs.

Diariamente: conferir captura íntegra e idade do último ponto, código de saída,
quota e integridade dos metadados; alertar imediatamente falha/ausência de ponto.
Semanalmente: `check --read-data` e recuperação isolada de conjunto representativo,
incluindo SQLite/WAL sintético, JSON relacionados e arquivo multigiB real sintético.
Mensalmente: reconstrução completa desde ambiente vazio, versão anterior e chave
de recuperação alternativa, validação semântica e mensuração RPO/RTO.
Trimestralmente: simular perda do primário, revogar credenciais do host de teste,
restaurar por cópia independente e revisar retenção/licenças/advisories.
Falha em qualquer gate impede promoção/expurgo. Evidências privadas sem dumps.

## Arquivos e testes desta entrega

Novos: `config/backup/policy.json`, `scripts/backup_architecture.py`,
`ops/backup/schedule.cron.disabled`, `tests/test_backup_architecture.py` e este
relatório. Atualizados: `docs/ESTADO_ATUAL.md` e `docs/DIARIO_TECNICO.md`.
Nenhuma dependência adicionada ou módulo BI alterado. Utilitário anterior mantido.

Bateria consolidada executada em ambiente isolado já existente:
`python -m pytest tests/test_secure_backup.py tests/test_backup_architecture.py -q`:
**PASS — 47 testes em 4,35 s** (20 anteriores + 27 novos).
`python -m pip check`: **PASS**. CLI do planejador: **PASS**, somente JSON local
com placeholders. `git diff --check`: **PASS**, repetido na entrega final.

Testes novos: precedência/limites das classes, preservação de desconhecidos,
triagem de nomes secretos, caminhos inválidos, flags fail-closed, plano sem
execução/prune, retenção dry-run, refs Git completas, ID explícito, destinos
existentes/sobrepostos e alias por link, SHA streaming. Simulação de leitura
de 4.097 blocos de 1 MiB (>4 GiB) com memória limitada; **não** mede vazão/disco
nem comprova capacidade Restic. Não houve execução Git nem criação de commits
nos testes novos. Os testes anteriores exercitam criptografia/SQLite sintéticos.

Licenças: novo script usa somente biblioteca padrão Python, **PSF-2.0**;
pytest 8.4.1 **MIT** no ambiente de testes; Git **GPL-2.0-only** como ferramenta
externa; Restic candidato **BSD-2-Clause**. Dependências anteriores mantidas:
cryptography 46.0.7 **Apache-2.0 OR BSD-3-Clause**, cffi **MIT-0**, pycparser
**BSD-3-Clause**, conforme auditoria anterior. Não há nova instalação nem
revalidação exaustiva de vulnerabilidades/transitivas nesta missão.

## Bloqueios para produção e decisão

1. Implementar/homologar barreira global, produtor de staging consistente e runner.
2. Completar inventário externo e revisão privada de segredos, inclusive histórico.
3. Instalar/verificar Restic em ambiente de homologação e ensaiar captura,
   corrupção, senha errada, restauração e versões anteriores com multigiB sintético.
4. Confirmar destinos privados independentes, imutabilidade, capacidade, custódia,
   responsáveis e aceite das metas de retenção/RPO/RTO.
5. Homologar reconstrução completa, lock/transitivas/Node, referências absolutas,
   validação semântica e PostgreSQL se aplicável; medir tempos reais.

**Conclusão: BLOQUEADO.** A preparação offline passa nos testes direcionados,
mas ausência de consistência global comprovada e de ensaio Restic impede
afirmar recuperação completa. Essas dependências não podem ser contornadas
com backup vivo, exclusão de arquivos grandes ou interrupção de serviços nesta
missão. A próxima etapa é homologação sintética do executor e da barreira;
nenhuma autorização de envio, operação real ou commit/push está implícita.
