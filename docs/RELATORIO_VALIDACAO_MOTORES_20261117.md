# Relatório de testes — Recuperação dos motores BI Factory

Data: 2026-11-17  
Marco de referência preservado: `751e292d4b06f41d79a3e7a1fc18b82e34c0ebcc`  
Branch de integração: `feat/integracao-react-pipeline-legado-20261117`.

## Objetivo
Reutilizar o pipeline Python antigo na interface React atual e executar uma bateria abrangente e **isolada** de testes de ingestão, profiling, decisões/perguntas semânticas, qualidade, preparação, grão, dimensional, star, DDL, ETL, transformação, dry run, persistência, PostgreSQL e grande volume, sem tocar em produtos e dados operacionais do Codespaces.

## Evidências dos testes automatizados

Workflow: `.github/workflows/react-legacy-pipeline.yml`.  
Execução **com todos os três jobs principais verdes**: [GitHub Actions #44186453294](https://github.com/edineilemes-source/bi-factory-seppe/actions/runs/44186453294).

| Bateria | Resultado confirmado | Observação |
|---|---|---|
| Legado Python e integração React (pytest) | **417 aprovados, 5 ignorados** | 10 excluídos deliberadamente dessa job (1 slow + 9 PostgreSQL), testados em jobs separados; os cinco skips precisam ser discriminados na homologação |
| Integração HTTP unitária/sintética | **3 testes unittest aprovados** | Upload, persistência, questionário, validações de arquivo em SQLite temporário (esses casos também entram na coleta pytest, não somar duas vezes) |
| Volume alto / proteção de memória | **1 aprovado** | Teste marcado slow |
| PostgreSQL 16 descartável | **9 aprovados** | Esquema isolado, PK/FK, rollback, reconstrução/reexecução, valores de precisão e invariantes |
| Build React + novo workspace | **Aprovado** | Constrói o React com Conhecimento, Entrada de Dados e Modelagem reutilizando backend Python |
| Navegador Chromium / porta 8506 | **Teste adicional criado; consultar workflow subsequente** | `tests/e2e/test_unified_react_workspace.py`; não considerar homologado até CI verde |

Assim, na execução principal auditada, **427 testes pytest aprovados e 5 ignorados**, sem falhas, considerando a soma dos jobs não sobrepostos. Não confundir isso com aprovação de operações sobre a fonte real PMCG. O teste originalmente falho por ausência da planilha `storage/originals/rela de pagos PMCG 10 ago 2026.xlsx` foi ajustado para ser ignorado *somente quando a fonte operacional não existir*, preservando a verificação de imutabilidade quando ela existir.

### Diagnóstico e correções descobertas
1. Testes de backup precisavam de `cryptography`, já declarado em `requirements-backup.txt`. A CI agora instala os dois requirements, sem alterar as versões do projeto.
2. Um teste antigo tentava ler a planilha real da PMCG antes de verificar se estava disponível; condicional de skip corrigida.
3. Primeira execução PostgreSQL falhou em rollback/cleanup porque parte dos testes herda a variável `PGPASSWORD`, enquanto a workflow oferecia apenas `TEST_POSTGRES_PASSWORD`. Testes PostgreSQL passaram após fornecer a variável contratada.
4. Teste de navegador configurado separadamente em runner Ubuntu 24.04 porque o Chromium da versão Playwright 1.58.0 não instala em runner Ubuntu 26.04; não falsear PASS até resultado confirmado.
5. `scripts/run_golden_database_dry_run_test.py` apenas imprime texto PASS; **não conta como evidência de teste**. As provas reais do PostgreSQL são os pytest da suíte `tests/golden_database_dry_run`.

## Integração React / Python existente na branch
- `scripts/bi_factory_analytics_adapter.py` expõe motores legados com upload sintético/tabular, `SQLiteAnalysisRepository`, conhecimento semântico, respostas e qualidade preliminar. Armazena original fora do Git em `storage/working/react_analytics/<analysis_id>`.
- `scripts/serve_bi_factory_api.py` acrescenta rotas `/api/analytics/capabilities`, `/api/analytics/upload`, `/api/analytics/answer` e `/api/analytics/analysis/<id>`.
- `web/bi_factory/src/DataWorkspace.jsx` apresenta entrada tabular, análise de campos, perguntas e status das etapas de modelagem dentro da interface React.
- `web/bi_factory/src/main.jsx` somente injeta o workspace nos menus Conhecimento / Entrada de Dados / Modelagem. Não altera as funcionalidades Produtos/Editor Visual.
- `tests/test_react_analytics_http.py` testa as rotas HTTP diretamente em loopback, com dados e SQLite sintéticos.
- Grão, dimensional, star, DDL, ETL, PostgreSQL e transformações **já têm motores antigos e testes**, mas o React apenas mostra o status; **não foram expostos como operações completas** nessa primeira integração. Não anunciar como integração funcional final.

## Limites e segurança
- Testes foram executados nos runners GitHub Actions com arquivos sintéticos, não sobre as bases reais do Codespaces.
- O upload HTTP inicial tem limite de 8 MiB e suporta XLSX, XLSM e CSV; conectores de PDF normativo, bancos e APIs ainda precisam ser construídos.
- O banco SQLite de análises antigo é reutilizado; a integração não executa migração destrutiva.
- Editor Visual congelado permanece no commit original e não foi alterado pela branch de integração.
- A branch de trabalho **não foi implantada no Codespaces**; a versão visual do navegador deve ser verificada após implantação controlada.
- Metadados/segredos de produção não devem ser versionados.

## Próximo passo de homologação
1. Exigir workflow da última revisão completamente verde, inclusive Chromium/E2E e teste real HTTP.
2. Aplicar somente os arquivos auditados no **mesmo Codespaces** via procedimento sem reset, sem limpeza e com backup; reiniciar apenas a API 8505, manter React 8506.
3. Verificar a mesma URL no navegador e preservar a branch marco até homologação humana.
4. Em seguida, integrar por etapas as ações reais de Prepared, Grão, Modelagem e demais motores no React.
