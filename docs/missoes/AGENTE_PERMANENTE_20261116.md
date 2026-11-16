# Agente permanente — 2026-11-16

Autorizacao especifica do usuario recebida para instalar scripts/bi_factory_patch_agent.py e configurar inicializacao automatica. Instalado da referencia e9843578bccfd478bda748271f17097d971e965d, com copia dos arquivos anteriores em .git/agent-install-20261116-164708.

Alteracoes: agente sai de /tmp para scripts; estado de issues processadas em .git/bi-factory-agent-apply-processed.json; singleton por flock; monitor usa .git/bi-factory-monitor.lock e fecha descritor 9 antes de iniciar subprocessos de longa duracao; GitHub CLI configurado como feature do devcontainer, preservando Node e hooks existentes. Restricoes anteriores de autor, branch, SHA completo, caminho permitido, arquivo limpo e git apply --check mantidas. Nenhuma porta tornada publica.

PASS: nove testes de guardas/monitor localmente, no GitHub Actions (run 43911070572, job 133452788705) e no Codespaces (0,133 s). PASS: cinco E2E de cadastro em Actions 43911070390; build/editor em 43911070440.
PASS: inicializacao idempotente (duas chamadas, uma instancia), parada controlada do agente e recuperacao 33953 -> 35149, estado persistido.
PASS: parada completa observada pela pagina Codespace is stopped e reinicio pelo botao Restart codespace. Sem comandos manuais para iniciar servicos apos retomada: hooks executaram automaticamente. Processos depois: monitor 100, patch 207, abertura 203, API 120, Vite 133. Nao houve heranca do arquivo de lock do monitor pelos servicos. Node pode reutilizar o numero 9 para seus proprios descritores; a verificacao final compara o destino do descritor, nao somente sua existencia.
PASS: main.jsx preservado e hashes de 11 JSONs de catalogo/layouts iguais antes e depois; estado passou de 1 para 2 issues, preservando anterior.
PASS: issue sintetica #17 recebida apos reinicio e rejeitada por formato nao autorizado antes de aplicar patch. Issue encerrada como teste aprovado; nenhum dado operacional alterado.
PASS: aplicacao externa voltou e carregou o catalogo no mesmo endereco privado https://fluffy-spoon-p77j7gpqjgp374qx-8506.app.github.dev/

Limitacao: rebuild completo do devcontainer nao executado; nao declarar validacao desse cenario. Arquivos/ciclo de vida preparados, com feature GitHub CLI, mas reinstalacao de dependencias no rebuild ainda exige ensaio. Branch local teste/cadastro-filtros-20261113 e quatro commits anteriores preservados; mudancas locais continuam no working tree. Fonte canonica no PR #16 / fix/recuperacao-homologacao-20261116.
