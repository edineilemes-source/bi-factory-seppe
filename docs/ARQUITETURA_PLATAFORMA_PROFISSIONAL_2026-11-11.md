# Plano de arquitetura profissional — BI Factory SEPPE
Data: 2026-11-11
Status: proposta técnica versionada, **não implantada**.
Branch base: feat/unificar-8504-8510.

## Problema comprovado
No Codespaces, a aplicação React na 8506, /api/overview, /visual-editor/index.html e /echarts-studio.html responderam HTTP 200. A URL externa apresentou 404 no navegador e HTTP 401 em curl sem sessão autenticada. A causa específica do 404 externo não foi comprovada. Não atribuir falha ao código sem evidência.

## Decisão arquitetural
Codespaces é IDE efêmera, não hospedagem de homologação/produção. GitHub é fonte de código, não armazenamento operacional. Criar ambientes independentes e persistentes para homologação e produção; não publicar via encaminhamento de porta do Codespaces.

## Componentes
- Fonte: GitHub, branches de feature, PR, revisão e proteção de branch.
- CI: GitHub Actions para lint/build, testes de API, integração, E2E Chromium/Playwright, auditoria de dependências e licenças; evidências e logs como artifacts.
- Empacotamento: frontend React/Vite compilado e servido como estático; API Python como serviço separado; roteamento /api, /visual-editor e /echarts-studio no mesmo domínio via proxy reverso.
- Runtime: preferencialmente containers OCI com imagens versionadas por SHA e health/readiness checks, reinício automático, limites de recursos e logs centralizados.
- Persistência: volumes persistentes e isolados por ambiente; não usar /tmp, filesystem do Codespaces ou GitHub Actions para dados operacionais. Avaliar evolução do catálogo JSON para banco transacional com migração auditada; não fazer migração nesta fase.
- Segurança: HTTPS, autenticação, RBAC, segredos em cofre/secret manager, acesso restrito, auditoria, dependências OSS com licenças identificadas; nunca publicar porta de terminal.
- Operação: backup automatizado e teste de restauração, métricas, alertas, rollback de release, runbook e SLO a definir.
- Agente/MCP opcional: execução de operações allowlisted, com autenticação curta, auditoria e aprovação para deploy ou alterações de dados; não expor shell irrestrito nem credenciais em Git.

## Fases e critérios de aceite
0. **Preservação**: inventário do Codespaces, git status/commits locais, diretórios não rastreados e datasets; backup verificável e teste de restauração. Bloqueio: sem backup, sem migração.
1. **Reprodutibilidade**: levantar app completa de commit fixo em ambiente limpo, incluindo datasets sintéticos; testes integrados de editor, ECharts e persistência; saída com relatório.
2. **Empacotamento**: frontend estático + API e proxy; healthchecks; configuração por variáveis, sem portas hardcoded para navegação; pipeline de build reproduzível.
3. **Homologação**: provisionar serviço persistente com DNS/HTTPS e dados isolados, deploy automatizado e rollback. Aceite: URL acessível de navegador autorizado sem túnel Codespaces, teste E2E passando.
4. **Produção**: após aceite explícito, política de backup/restore, controle de acesso, observabilidade e plano de migração de dados. Sem promoção automática.
5. **Agente operacional**: integração MCP autenticada para logs, diagnóstico, testes e deploy restrito; ações mutáveis sujeitas a política de aprovação.

## Portões de qualidade
- Falha em build/testes bloqueia deploy.
- Testes de catálogo devem usar fixture isolada; não alterar storage operacional.
- Não fazer merge, rebase, reset, limpeza de untracked ou migração automática.
- Verificar divergência local/remota antes de incorporar branches existentes.
- Licenças OSS verificadas para cada nova dependência.
- Exigir teste de restauração antes de produção.

## Decisões pendentes
- Provedor e custo de hospedagem (avaliar infraestrutura institucional, VPS gerenciada ou PaaS; não assumir autorização para dados públicos sensíveis).
- Classificação dos dados, LGPD e requisitos institucionais.
- Inventário real de armazenamento e tamanho dos datasets.
- RTO/RPO, disponibilidade, autenticação e DNS.
- Forma de conectar o agente operacional sem expor o ambiente.

## Estado
Este documento registra a direção. Nenhum servidor, túnel, deploy, credencial ou dado operacional foi alterado por este commit.
