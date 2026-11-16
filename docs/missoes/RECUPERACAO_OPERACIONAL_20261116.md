# Recuperação operacional — 2026-11-16

## Resultado confirmado
- Aplicação acessível no navegador autenticado: https://fluffy-spoon-p77j7gpqjgp374qx-8506.app.github.dev/
- Página principal e Produtos carregaram; porta 8506 Private confirmada no painel Ports. Nenhuma porta tornada pública.
- Antes do login, consulta externa retornou 401 com www-authenticate: tunnel. Após Google + confirmação do GitHub, o fluxo pf-signin concluiu e a UI abriu. Não há prova suficiente para atribuir todos os 404 históricos a uma causa única.
- Codespaces ativo: fluffy-spoon-p77j7gpqjgp374qx. Branch local preservada teste/cadastro-filtros-20261113, HEAD 051f1c1, quatro commits locais anteriores preservados. Scripts/devcontainer já tinham alterações locais; não substituídos.
- main.jsx anterior conferido pelo blob d79d3acb9fdb66d425c5595fb4d0b3a3b4d8bfaf, igual à correção 4ccbce8. Instalado main.jsx da referência ba06f86f51e6b2f0c83b21e098d36d3d9c597d81, blob da298ea2e7db9d48d99f7f9012c69615a08bf757. Backup do arquivo anterior em .git/recovery-main-20261116-163335/main.jsx. Sem checkout/reset/rebase ou merge.
- Fonte canônica: branch fix/recuperacao-homologacao-20261116, PR #16. A aplicação local permanece com mudanças no working tree; não afirmar sincronização integral de todas as branches/scripts.

## Testes
- PASS: cinco testes E2E Chromium + API reais em fixture isolada (Actions run 43906062599, job 133435093946; 5 testes em 19,505 s).
- PASS: quatro verificações HTTP/API em fixture local: cadastros distintos, edição/reabertura, layout preservando primeiro produto, gravação em disco.
- PASS: build/sintaxe no CI; build React no Codespaces em 5,94 s; bash -n e git diff --check.
- PASS externo: produto existente reaberto com layout e filtros; Novo produto remove #product-details (contagem zero), Nome vazio; validação de nome; cancelar retorna ao catálogo com os mesmos dois itens (inclui legado). Nenhum produto operacional criado ou apagado para testar.
- PASS recuperação: parada controlada apenas do frontend PID 350; monitor já existente PID 93 restabeleceu Vite PID 28353; API PID 152 permaneceu ativa. Reabertura externa e Produtos confirmados após recuperação.
- PASS integridade: hashes de 11 JSONs em storage/information_products iguais antes/depois da recuperação. Isso não substitui backup operacional nem prova estado de bancos externos.
- Log de createRoot duplicado observado durante HMR da atualização; tela recarregada. Não houve nova ocorrência observada após recarga/recuperação. Erros de chrome-extension são externos à aplicação.
- BLOCKED: reinício completo do Codespaces e rebuild do devcontainer não ensaiados nesta entrega.

## Automação e pendência
- Já ativos: monitor, agente de abertura e agente de patch em /tmp/bi_factory_patch_agent.py. A existência do processo não comprova sua sobrevivência ao rebuild.
- Revisão automática rejeitou instalar o agente de patches no caminho versionado e modificar autostart para execução persistente, por risco de executar agente obtido remotamente sem autorização específica. Operação não aplicada nem contornada. Correção do cadastro foi implantada separadamente.
- Exige decisão específica: autorizar instalação de scripts/bi_factory_patch_agent.py e sua inicialização pelo monitor, com inspeção do código e restrições atuais preservadas (branch permitida, SHA completo, somente main.jsx, arquivo limpo, git apply --check; sem comando arbitrário, reset ou sobrescrita).
- Próximo passo após autorização: consolidar instalação persistente dos agentes, ensaiar reinício e rebuild com preservação de dados; não ampliar o escopo funcional.
