---
name: abrir-openai-factory
description: Executar o fluxo de abertura e verificação do BI Factory SEPPE quando o usuário disser "Abra OpenAI Factory", "Abrir BI Factory" ou equivalente.
---

# Abrir OpenAI Factory — BI Factory SEPPE

## Alvo
- Repositório: edineilemes-source/bi-factory-seppe
- Branch: feat/unificar-8504-8510
- Codespace conhecido em 2026-11-12: fluffy-spoon-p77j7gpqjgp374qx (confirmar se ainda existe)
- API: 8505; frontend público: 8506
- Comando de inicialização: `cd /workspaces/bi-factory-seppe && bash scripts/start_bi_factory_codespaces.sh`

## Procedimento
1. Quando houver ferramenta autorizada para administrar Codespaces e executar terminal, localizar Codespace do repositório, iniciar/resumir caso esteja parado e aguardar disponibilidade. Não criar Codespace adicional automaticamente.
2. Executar o inicializador acima uma vez. Ele não deve parar serviços ativos; observar saída e logs.
3. Verificar HTTP 2xx em `/api/overview` na 8505 e em `/`, `/api/overview`, `/visual-editor/index.html`, `/echarts-studio.html` na 8506.
4. Verificar visibilidade/encaminhamento da porta 8506 no GitHub Codespaces; preferir visibilidade privada/autenticada. Nunca mudar porta para pública sem autorização.
5. Entregar link confirmado `https://<codespace-atual>-8506.app.github.dev/` e resumo conciso de status. Não afirmar que está ativo sem checagem real.
6. Se não houver ferramenta de controle do Codespaces, informar claramente a limitação e fornecer somente o comando único acima e o link do Codespace previamente conhecido, explicitando que a disponibilidade não foi verificada. Pode sugerir usar ChatGPT Work com navegador/computador quando disponível, sem prometer execução autônoma.

## Segurança
- Não executar `git pull`, merge, rebase, reset, clean, push, commits, alterações de código, backup real, migração, deploy ou exclusão para simplesmente abrir o sistema.
- Não modificar `storage/`, produtos, layouts, credenciais, `.env`, ou dados do usuário.
- Se o script falhar, analisar logs e diagnosticar sem executar comandos destrutivos.
- Sem acesso remoto real, não fingir que executou comandos nem solicitar vários comandos em sequência: no máximo um bloco consolidado.
- Distinguir verificação com servidores já ativos de partida a frio (ainda não homologada em 2026-11-12).
