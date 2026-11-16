# Recuperação operacional — 2026-11-16

- Aplicação e Produtos acessíveis no navegador autenticado: https://fluffy-spoon-p77j7gpqjgp374qx-8506.app.github.dev/
- Porta 8506 confirmada Private no painel Ports. Sem mudança para acesso público.
- Consulta sem autenticação retornou 401/tunnel. Após login Google e confirmação de dispositivo GitHub, pf-signin completou e a aplicação abriu. Isso não prova causa única de todos os 404 históricos.
- Codespaces ativo fluffy-spoon-p77j7gpqjgp374qx, branch local teste/cadastro-filtros-20261113, HEAD 051f1c1, quatro commits locais e alterações anteriores preservados. Sem checkout/reset/rebase.
- main.jsx anterior conferido pelo blob d79d3acb9fdb66d425c5595fb4d0b3a3b4d8bfaf, exatamente a correção 4ccbce8. Instalado main.jsx da referência ba06f86f51e6b2f0c83b21e098d36d3d9c597d81, blob da298ea2e7db9d48d99f7f9012c69615a08bf757. Backup anterior em .git/recovery-main-20261116-163335/main.jsx.
- Fonte canônica fix/recuperacao-homologacao-20261116, PR #16. Implantação local no working tree; scripts/devcontainer modificados anteriormente não substituídos. Não afirmar sincronização integral.

## Evidências executadas

| Verificação | Resultado |
|---|---|
| Cinco testes E2E Chromium + API em fixture isolada | PASS, Actions 43906062599 / job 133435093946, 19,505 s |
| Quatro verificações HTTP/API em fixture local: criação, edição/reabertura, layout/preservação, disco | PASS |
| Build e sintaxe no CI | PASS |
| Build React no Codespaces | PASS, 5,94 s |
| bash -n e git diff --check no Codespaces | PASS |
| Página principal e Produtos pelo endereço privado | PASS |
| Reabertura de produto existente com prévia, layout e filtros | PASS |
| Novo produto fecha ficha anterior, #product-details ausente, Nome vazio | PASS |
| Nome obrigatório e cancelar sem alteração do catálogo | PASS |
| Recuperação automática do frontend pelo monitor existente | PASS; PID 350 substituído por 28353; API PID 152 preservada |
| Hashes de 11 JSONs do catálogo/layouts antes e após recuperação | PASS, iguais |
| Reinício completo do Codespaces | BLOCKED, não ensaiado |
| Rebuild do devcontainer | BLOCKED, não ensaiado |
| Instalação persistente do agente de patches | BLOCKED pela revisão automática |

Nenhum produto operacional criado/apagado para testes. Dados operacionais preservados. Hashes não substituem backup operacional. Um aviso createRoot ocorreu durante HMR da atualização; não observado novamente após recarga. Erros de extensão do navegador são distintos da aplicação.

## Automação

Monitor PID 93 e agente de abertura já estavam ativos. Agente de patches observado em /tmp/bi_factory_patch_agent.py; não implica persistência após rebuild. Recuperação do frontend existente foi comprovada, sem instalar novo monitor.

A revisão automática rejeitou instalar scripts/bi_factory_patch_agent.py e modificar autostart para execução persistente, por risco de executar agente obtido remotamente sem autorização específica. Operação não aplicada nem contornada; somente a correção de main.jsx foi implantada separadamente.

Próxima ação: autorização específica para instalação persistente do agente restrito e sua chamada pelo monitor, com inspeção do código e restrições atuais preservadas (branch permitida, SHA completo, somente main.jsx, working tree limpo no alvo, git apply --check; sem comandos arbitrários, reset ou sobrescrita). Em seguida, ensaiar reinício e rebuild com preservação de dados.

Registros equivalentes foram acrescentados em docs/ESTADO_ATUAL.md, docs/DIARIO_TECNICO.md e no relatório no Codespaces.
