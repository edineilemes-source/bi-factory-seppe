# Inventário técnico e plano de recuperação — BI Factory SEPPE

**Data:** 2026-11-17  
**Referência imutável do inventário:** `751e292d4b06f41d79a3e7a1fc18b82e34c0ebcc`  
**Branch de origem:** `marco/editor-visual-homologado-20261116`  
**Escopo:** Conhecimento, Entrada de Dados, Modelagem, ligação com Produtos e Publicações.  
**Método:** leitura da árvore GitHub do commit do marco (360 itens no tree recursivo, sem truncamento), leitura de código, scripts, README e documentos de sprint. **Não foram executados testes nem consultados os arquivos operacionais do Codespaces nesta fase.** Não confundir existência de código e testes com execução aprovada na versão atual.

## 1. Resultado principal

O projeto já dispõe de um pipeline Python/Streamlit modular e relativamente extenso para ingestão de planilhas, profiling, validação semântica, qualidade, preparação, descoberta/validação humana do grão, descoberta dimensional, contrato estrela, DDL, plano ETL, transformação e dry run, além de um caminho MVP independente de artefatos preparado para PostgreSQL e saídas SQL/Metabase. Os módulos estão versionados no marco homologado. A interface React da porta 8506, porém, concentra a execução em Projetos, prévia fiscal, Produtos e Publicações; a experiência de Conhecimento/Entrada de Dados/Modelagem **não está integrada** ao frontend homologado. A prioridade é integrar o legado com contratos de API, sem reescrever ou apagar os motores existentes.

## 2. Mapa de reaproveitamento

| Área | Código/artefato encontrado | Estado verificável | Lacuna |
|---|---|---|---|
| Conhecimento e questionário semântico | `core/semantic/decision_engine.py`, `question_generator.py`, `validation_service.py`, `knowledge.py`, `knowledge_migration.py`, `core/persistence/sqlite_repository.py` | Motor de decisões AUTO_ACCEPT/CONFIRM/ASK/DEFERRED, perguntas com opção “Não sei”, persistência e reutilização condicionada à compatibilidade de evidências | Não é pesquisa de legislação por IA; não indexa normativos PDF como conhecimento de negócio; não há fluxo React correspondente |
| Entrada de dados tabulares | `core/ingestion/file_loader.py`, `core/profiling/*`, `app/components/profiling_view.py` | Suporte observado XLSX/XLSM/CSV, leitura em memória, amostragem determinística, chunks, detecção de cabeçalho/campos | Não há importador genérico de PDF/XML/API/SQL no mesmo contrato; não há upload genérico no React 8506 |
| Qualidade | `core/quality/{engine,gate,models,export}.py` | Regras determinísticas e qualidade contextual; distinção entre ausência física e obrigatoriedade de negócio | Integrar validação ao pipeline da interface atual; revisar resultados nas fontes reais |
| Preparação e linhagem | `core/prepared/*`, `core/transformation/*` | Prepared Dataset versionado, `source_row_id`, fingerprint e transformação preservando origem, descritos no README | Expor fluxo por API, armazenamentos/filas para fontes grandes e validação operacional |
| Grão e perguntas | `core/grain/*`, `app/components/grain_discovery_view.py` | Grão separado de chave técnica e validação humana obrigatória | Não assumir grão PMCG homologado; expor dúvidas na central de pendências |
| Fatos e dimensões | `core/dimensional/*`, `core/star/*`, `core/ddl/*`, `core/etl/*` | Candidatos dimensionais, contrato estrela, DDL, plano ETL e validações | Generalizar o catálogo corporativo, relacionamentos entre fontes e integração a produtos |
| Teste de carga | `core/database_dry_run/*`, `scripts/start_test_postgres.sh` | Adapters, engine e relatório de dry run | Validar ambiente PostgreSQL atual, sem tocar em bases operacionais |
| Trilha MVP de despesas | `core/bi_mvp/{audit,artifacts,modeling,workflow,ddl,etl,metabase}.py`, `app/components/bi_mvp_view.py` | Recupera análise por ID e gera modelo/DDL/SQL Metabase com aprovação humana e carga PostgreSQL | É especializado no domínio de despesas; generalizar via contratos semânticos e não copiar regras fixas para qualquer negócio |
| Fiscal/SICONFI | `core/siconfi/*`, `core/business/*`, `scripts/siconfi_*.py` | Cliente/normalização/snapshots fiscais e modelos de receitas/despesas | Reaproveitar como conector especializado, não como núcleo universal |
| Editor Visual e Produtos | `web/bi_factory/src/main.jsx`, `prototypes/editor-visual/*`, `scripts/serve_bi_factory_api.py` | Marco homologado do código, build e verificações HTTP aprovados na sua criação; editor congelado | Conectar catálogo de medidas/dimensões com ECharts sem reescrever editor |
| Publicações | `web/sala_situacao/*`, `scripts/serve_sala_situacao.py`, inventário `published.json` na API | Artefatos/rotas de publicação encontrados | Biblioteca multi-formato, metadados, versões, acesso e histórico por produto não confirmados |

## 3. Conhecimento: encontrado versus solicitado

**Existente**: classificação de papel semântico de campos, detector de conflitos, perguntas contextualizadas, registros SQLite (`semantic_questions`, `semantic_answers`, `semantic_knowledge`) e política de reuso que reavalia compatibilidade. O histórico humano pode reutilizar papéis validados sem tomar equivalência apenas pelo nome do campo.

**Não encontrado no commit do marco**: serviço funcional de busca de legislação em fontes oficiais, indexação de PDFs normativos, armazenamento com citação de artigo/página/vigência, controle de revisão/revogação e RAG verificado. `core/ai/` contém apenas `__init__.py` e `core/metadata/` e `core/modeling/` também apenas `__init__.py`. Isso é ausência de módulo específico nessas pastas, não prova de que não existam protótipos externos ao commit.

**Próxima implementação recomendada**: fonte documental com proveniência e versões; pesquisa oficial assistida; upload seguro; extração; chunking; referência/citação; extração de conceitos/regras; fila de dúvidas; aprovação humana. Não usar inferências de IA como normas oficiais.

## 4. Entrada de Dados

`core/ingestion/file_loader.py`: aceita `.xlsx`, `.xlsm`, `.csv`; limite padrão de amostra 10 mil linhas; permite leitura completa e iteração em lotes. `core/profiling/` gera perfil por aba/campo, detecta cabeçalho, nomes duplicados, nulos, distribuição e alertas. `app/main.py` possui upload e controle de análises no Streamlit legado.

A interface React atual mostra um inventário/preview fiscal e **não** substitui essa ingestão genérica. Contratos para PDF de dados tabulares, XML, JSON, SQL, autenticação de conectores e APIs deverão ser especificados, não assumidos já operacionais.

## 5. Modelagem e recuperações prioritárias

Sequência de motor já encontrada:
`ingestion → profiling → semantic validation/questions → quality → prepared dataset → grain discovery/approval → dimensional discovery → star schema contract → DDL → ETL plan → transformation → database dry run`.

`app/main.py` importa as views dessas etapas e utiliza estágio persistido. `core/bi_mvp/workflow.py` oferece caminho paralelo por artefatos persistidos, independente de carregar a planilha inteira na sessão.

O documento `docs/sprint-4.4.8.md` relata análise de **181.476 linhas, 38 campos** e **36 registros** de conhecimento semântico à época. Observa que a granularidade real PMCG foi classificada como **INSUFFICIENT_EVIDENCE**, sem grão humano validado; portanto nenhuma aprovação real de modelo ou carga PostgreSQL da PMCG pode ser presumida. Testes com PostgreSQL citados no documento são sintéticos. Propostas de `fato_despesa_registro` e dimensões são candidatas, não modelo institucional certificado.

As regras `core/bi_mvp/modeling.py` contêm referências específicas à despesa (medidas como Pago, Liquidado, Empenhado). Devem permanecer como **perfil de domínio**; não tornar o motor universal dependente desses nomes. Adoção do modelo genérico requer mapeamento de granularidade, aditividade, chaves e conformidade entre fontes.

## 6. Testes recuperados e como validar

A árvore inclui **90 arquivos sob `tests/`** (incluindo arquivos `__init__.py`, fixtures e dados de referência), com diretórios de smoke, regression, acceptance, golden semantic, quality, prepared, grain, dimensional, star schema, DDL, ETL, transformation, dry run, integrações e regressões específicas. O `test-bi-factory.sh` executa a bateria por estágios e coleta a suíte pytest.

**Não executar contra a base operacional sem confirmar isolamento**. Próxima validação controlada: inventariar fixtures e dependências; criar ambiente de teste; `pytest --collect-only`; rodar golden e unitários em base temporária; segregar PostgreSQL `postgres_integration`; registrar testes executados/aprovados/falhos e tempo. A referência de “mais de 100 testes” deve ser confirmada pela coleta; o inventário de arquivos não prova número de casos pytest.

## 7. Integração com a interface homologada

`web/bi_factory/src/main.jsx` apresenta opções no menu (Conhecimento, Entrada de dados, Modelagem, Produtos, Publicações), mas o código identificado no marco só oferece tela de Prévia Fiscal para Entrada de Dados e placeholder genérico para módulos sem implementação frontend. `scripts/serve_bi_factory_api.py` expõe principalmente o catálogo e o material fiscal; o app Streamlit tem o pipeline analítico mais completo. O caminho preferencial é uma camada API/adaptador que delegue aos serviços `core/*`, com estados de análise, tarefas assíncronas, erros e progressos, sem duas implementações concorrentes da semântica.

**Não tocar no Editor Visual congelado antes de definir o contrato de entrega de dimensões/medidas**.

## 8. Riscos e dados a preservar

- Branch de referência do Editor Visual: `marco/editor-visual-homologado-20261116`, SHA `751e292d4b06f41d79a3e7a1fc18b82e34c0ebcc`. Este inventário vive em branch **separada**, sem modificar o marco.
- `storage/` tem conteúdos operacionais ignorados ou não rastreados: não mover, limpar, reindexar ou versionar dumps por engano. A árvore Git não representa necessariamente as bases que estão no Codespaces.
- O SQLite de análise, os datasets preparados e relatórios citados na Sprint 4.4.8 **não foram inspecionados no ambiente atual**; referências históricas não demonstram disponibilidade operacional hoje.
- Algumas evidências estão em documentação histórica e podem divergir do código em execução; validar as rotas e serviços existentes antes de alterar módulos.
- Não marcar módulos como “prontos para usuário” apenas porque existem funções e testes versionados.

## 9. Próximo ciclo de trabalho, sem novo desenho do zero

1. Teste controlado do pipeline legado sobre fixtures, recuperando contagem real de testes e problemas. Não exige entrar com dados operacionais.
2. Levantamento de contratos de funções, persistência e requisitos de API (propor adaptadores, não reescrita).
3. Protótipo do Conhecimento na interface atual, com origem documental, pesquisa assistida e upload de normas; reaproveitar `core/semantic/*`.
4. Expor upload tabular/perfilamento para Entrada de Dados; ligar respostas de dúvidas às evidências do Conhecimento.
5. Expor pipeline de modelagem e catálogo de fatos, dimensões e medidas ao Charts/ECharts, mantendo o Editor Visual congelado.
6. Validar uma segunda área de negócio distinta da despesa (estoque, condomínio ou folha) para comprovar generalidade.

**Status:** Inventário estático do GitHub realizado. Integração, execução da bateria e verificação de dados do Codespaces continuam pendentes; não há autorização neste documento para mutação operacional.
