# Auditoria técnica — acesso ao BI Factory (11/11/2026)

## Escopo e fontes
- Inspeção do código do GitHub na base `feat/unificar-8504-8510`.
- Registros de terminal fornecidos pelo usuário em 11/11: `curl http://127.0.0.1:8504/` retornou 200; `curl -I https://<codespace>-8504.app.github.dev/` retornou 401 e posteriormente 302 para `github.dev/pf-signin`. O navegador Chrome exibiu 404 em 8504 e 8506.
- Histórico de 9 e 10/11: Vite pendurado sem resposta (9/11), erro de proxy `ECONNREFUSED 127.0.0.1:8505` (10/11), sintaxe JS do editor reportada em teste antigo.
- Execução automatizada GitHub Actions 43051179108 em ambiente isolado Ubuntu 24.04, Node 22, Chromium Playwright, script `scripts/audit_ports_browser.cjs`. **Não é acesso ao Codespaces do usuário.**

## Resultados observados em CI
- PASS: sintaxe de scripts inline do editor visual e do ECharts Studio.
- PASS: HTTP 200 nas portas 8504 e 8506, módulo React `/src/main.jsx`, API via proxy `/api/overview`, editor via proxy `/visual-editor/index.html`, ECharts via proxy `/echarts-studio.html`, editor via API 8505 e servidor de produtos 8510.
- PASS: Chromium abriu React nas portas 8504 e 8506; `#root` não vazio, título `BI Factory | SEPPE`, nenhum erro de console; abriu editor visual e ECharts Studio sem erros JS reportados. `AUDIT_FAILURES 0`.
- LIMITAÇÃO: CI usa cópia limpa do GitHub, dados de teste/arquivos presentes no checkout e ambiente Linux separado. Não confirma o estado local do Codespaces, autenticação do túnel GitHub, os cookies do Chrome do usuário, persistência de produtos reais ou o fluxo completo de inserção de gráfico.

## Mapa de portas
- 8502: Streamlit; independente do Vite.
- 8503: Sala de Situação; independente do Vite.
- 8504: Vite React; proxy de `/api`, `/visual-editor`, `/echarts-studio.html` para 8505.
- 8505: API Python; serve endpoints e arquivos do editor; é dependência direta do frontend.
- 8506: segundo Vite React com `--port 8506 --strictPort`; usa os mesmos proxies para 8505, sem copiar dados.
- 8510: servidor Python de produtos; usa `127.0.0.1` (loopback), não é diretamente acessível por túnel externo; a integração via 8505 é o caminho previsto.

## Diagnóstico diferencial
1. **Bloqueio externo comprovado no momento da coleta**: a URL `app.github.dev` devolveu 401/302 para `github.dev/pf-signin`, antes de chegar ao Vite. O HTTP 200 após `curl -L` é da página de login, NÃO da aplicação. O 404 visto no Chrome não identifica por si só qual etapa do fluxo de autenticação falhou.
2. **Falhas internas históricas comprovadas**: Vite sem resposta e API 8505 indisponível ocorreram em dias anteriores; podem se repetir e exigem health checks e gerência de processos. Não explicam o 302 de autenticação atual.
3. **Código atual testado em ambiente limpo**: a UI, o editor e o ECharts abrem nas duas portas em Chromium. Portanto, não há evidência de erro de sintaxe atual impedindo a abertura básica. Isso NÃO elimina bugs funcionais de gráficos e produtos.
4. **Sincronização GitHub/Codespaces**: o usuário relatou arquivos locais modificados e não rastreados. O GitHub Actions não confirma que o Codespaces esteja na mesma revisão. Não usar reset/clean nem sobrescrever storage.
5. **Portas auxiliares VS Code**: as portas altas observadas podem pertencer a extensões e ao editor. Não há evidência de que causem o 404. Não matar indiscriminadamente.
6. **Segurança**: o servidor 8510 declara não possuir autenticação; manter portas privadas e evitar expor dados reais em Public.

## Próximas correções técnicas recomendadas
- Adicionar verificação integrada de saúde dos serviços antes de abrir a UI, distinguindo 200 local, 500/502 proxy e 302/401 túnel.
- Tratar falhas da API 8505 na UI com mensagem explícita e logs, sem tela branca.
- Verificar ciclo completo ECharts: criar, inserir, salvar, reabrir, visualizar, editar; usar fixtures isoladas sem dados reais.
- Resolver o acesso `pf-signin` no próprio ambiente Codespaces/GitHub; este ponto não pode ser corrigido no Vite e não é reproduzível no runner de CI.
- Não confundir porta interna ativa com túnel autenticado e não declarar homologação externa sem teste real.

## Alterações de auditoria
- Branch `audit/portas-navegador-20261111`, sem merge e sem alteração dos dados operacionais.
- Arquivos `scripts/audit_ports_browser.cjs`, `.github/workflows/audit-ports-browser.yml`.
- GitHub Actions: https://github.com/edineilemes-source/bi-factory-seppe/actions/runs/43051179108 — PASS.
