# Sprint 4.4.8 — entrega e reprodução

Status: implementação do caminho MVP disponível; BI PMCG **não concluído**. Não existe validação humana de grão para a análise real. Nenhum modelo PMCG foi aprovado e nenhuma linha PMCG foi carregada no PostgreSQL nesta execução. Os testes PostgreSQL usam dados sintéticos e aprovação exclusivamente de fixtures.

## Auditoria antes das edições

Branch `codespace-working`. O worktree já continha muitas alterações, inclusive `core/bi_mvp`, Grain v2.1, CLI e testes da sprint. Foram inspecionados código, contratos, testes, SQLite e CSV antes das edições. Cópias dos arquivos preexistentes trabalhados foram guardadas em `/tmp/s448-before`. Não houve reset, checkout, remoção de alterações, commit ou push.

Prepared reutilizado: `8d60c32c-2363-4f48-80be-d108f8bcae80`, versão 2; análise `ca5cf2d7-98d8-4404-a5cd-916eda0810db`; 181.476 linhas, 38 campos originais. CSV: `storage/working/prepared/prepared-ca5cf2d7-98d8-4404-a5cd-916eda0810db-v2-8d60c32c.csv`. SHA-256: `6dbddc11e6e75eb4f0f29a18c2d0ce27362a749a6e05600d20764930723ae56a`.

Catálogo consultado: `semantic_knowledge` no SQLite, 36 registros. `core/metadata`, `core/modeling`, `database/migrations` e `database/seeds` não contêm catálogo físico de entidades. Não foi criado um catálogo corporativo paralelo. Cada proposta salva um snapshot do conhecimento existente, e as dimensões locais continuam candidatas a futura conformação.

Há correções/confirmações humanas de Credor, Elemento de Despesa, Evento Pagamento, Fonte, GPF Descriçao, Grupo de Despesa, Item Elemento Despesa, documentos e UGs. Os papéis de tempo e medidas incluem aceitação automática; isso **não** confirma evento, aditividade ou chave de negócio. Os dez campos de retenção estão vazios, com papel UNKNOWN; não geram dimensões.

| Campo/grupo | Linhas preenchidas | Uso proposto, sujeito à aprovação |
|---|---:|---|
| Ano, Mês, Dia | 181.476 cada | Componentes temporais originais |
| UG Sigla | 181.476 | Unidade gestora |
| UG Empenho, UG Liquidação | 35.982 cada | Papéis de unidade distintos, preservados |
| Credor | 90.324 | Código textual; nenhum nome inventado |
| Elemento de Despesa | 14.384 | Classificação |
| Item Elemento Despesa, Grupo de Despesa | 181.476 cada | Classificação |
| Fonte, GPF Descriçao | 179.895 cada | Fonte de recurso |
| Evento Pagamento | 35.982 | Evento presente na fonte; não representa todas as linhas |
| Nº Empenho | 168.826 | Documento preservado |
| Nº Liquidação | 39.959 | Documento preservado |
| Nº Reserva | 19.023 | Documento preservado |
| Nº Estorno | 610 | Documento de subconjunto, não chave global |
| Ano do Empenho | 91.116 | Escopo temporal original do empenho |
| Total Pago, Liquidado, Empenhado, Devolvido, Estornado | 181.476 cada | Medidas separadas |

Números de documentos não são considerados globalmente únicos. Ano do Empenho, UGs e documentos ficam disponíveis no fato/lineage; não se deduz identificação de negócio por concatenação automática. A dimensão unidade usa a tupla completa dos atributos observados para não escolher arbitrariamente uma UG Empenho/Liquidação quando UG Sigla se repete. Isso é uma identidade técnica de combinação, não uma entidade corporativa certificada.

Dependências legadas preservadas: Dimensional calcula cardinalidades sobre `dataset.rows`; Star usa Prepared e contratos dimensionais; ETL Plan usa Prepared; Transformation gera coleções de linhas/staging; DDL usa Star validado na sessão; Dry Run depende do resultado Transformation. A trilha `core/bi_mvp` fornece o caminho independente por artefatos, sem reescrever esses módulos ou reconstruir seus objetos completos.

## Grain

O v1 dividia distintos pelas 610 linhas completas e descrevia a unicidade como se fosse global. Nº Estorno possui 583 distintos, 27 repetições, unicidade condicional 95,57%, cobertura apenas 0,3361%; a confiança histórica era 85,9319%.

O motor `artifact-grain-v2.2` separa unicidade condicional, cobertura, suporte, consistência entre duas partições da fonte e papel semântico. Compatibilidade de processo exige validação humana; sinais lexicais continuam hipóteses. Cobertura abaixo do limiar configurado impede recomendação global; suporte zero implica confiança zero. Não se infere estabilidade temporal de uma única planilha.

Novo relatório real: versão 4, ID `e41f7e91-4838-4917-a1a6-0f6a9e142115`, classificação `INSUFFICIENT_EVIDENCE`, sem candidato global recomendado. O v1 `b3d38cd3-e37f-4dfd-94bd-4b98ba049885` e v2/v3 foram preservados. A interface exibe evidências, cobertura, contraindicações, até cinco exemplos e as opções de descrição manual, registro de origem e “Não sei”. Esta última bloqueia o modelo e revoga uma definição efetiva anterior.

Hipótese pendente: **um registro de despesa/pagamento conforme a granularidade original da fonte**, preservando todas as linhas e usando chave substituta técnica. Validar esta hipótese não valida a soma de medidas.

## Modelo e carga implementados

Após validação humana do grão, a proposta contempla `fato_despesa_registro` e dimensões `dim_tempo`, `dim_unidade_gestora`, `dim_credor`, `dim_natureza_despesa`, `dim_fonte_recurso`, `dim_evento_pagamento`, somente com campos presentes e preenchidos. Todos usam chaves substitutas. Dimensões inteiramente vazias são omitidas. Nulos dentro de dimensões existentes representam combinações desconhecidas, sem atributos inventados.

`source_values` JSONB preserva todos os campos do registro, inclusive os que não viram coluna dimensional. Lineage inclui análise, Prepared ID/versão, documento, aba, número da linha e `source_row_id`. Códigos são TEXT, inclusive zeros à esquerda e representações como `573.0` já presentes no Prepared.

Medidas usam **NUMERIC sem escala fixa**, pois o Prepared contém resíduos decimais como `344.3499999999999`. NUMERIC(20,4) alteraria valores sem autorização. A soma Python usa Decimal com precisão ajustada, sem arredondamento por contexto. Nenhuma exclusão de estornos, deduplicação de negócio ou correção financeira é aplicada.

A carga usa COPY em chunks de 2.000 linhas, tabelas temporárias no PostgreSQL, uma transação de dados e reconciliação antes do commit. O registro `bi_load_run` é criado antes da transação e atualizado para FAILED em falhas tratáveis; falha abrupta do processo pode deixar RUNNING, sem publicar a transação parcial. Uma reexecução usa novo run e chave única `(analysis_id, prepared_version, source_row_id)`, inserindo apenas linhas ainda ausentes. Reexecutar lê o CSV para verificar contagens e totais, sem duplicar fatos.

`bi_model_contract` vincula o schema a um contrato imutável. Modelo/Prepared/versão/hash incompatíveis falham explicitamente. **Nesta trilha MVP, outro modelo ou versão exige outro schema**; migração de schema compartilhado e conformação entre análises ficam para evolução. Modelos são PROPOSED por padrão, aprovados explicitamente e persistidos com checksum; nova decisão cria nova versão.

## Metabase

São geradas `vw_despesa_detalhe`, `vw_despesa_executivo`, `vw_despesa_mensal` e views `vw_despesa_por_*` para dimensões disponíveis. Contagem sempre disponível; somente medidas com `additive_confirmed=true` entram nas agregações. Análise e Prepared version permanecem nas chaves dos agrupamentos. Não há indicador que some diferentes estágios.

O arquivo `dashboard-vN-SCHEMA.md` gerado junto ao SQL contém configuração da conexão, cartões, filtros compartilhados, ordem de meses e detalhamento. As views mensais preservam os componentes originais; meses textuais precisam de ordenação calendário no Metabase. Perguntas baseadas na view detalhe permitem filtros Ano/Mês/Dia e dimensões, sem inventar uma data de pagamento.

Não foi configurada conexão ou dashboard real no Metabase. A alternativa SQL e instruções reproduzíveis foi implementada.

## Reprodução

1. Abra Streamlit diretamente em `/?mvp=1`, informe o Analysis ID e revise o Grain. Esta rota ocorre antes da ingestão de arquivos. O estado de sessão não precisa conter PreparedDataset nem workbook.
2. Confirme o grão ou registre “Não sei”. Depois gere a proposta, revise os mapeamentos e selecione apenas medidas cuja soma entre linhas foi confirmada. Aprove o modelo explicitamente.
3. Configure `BI_MVP_POSTGRES_DSN` no ambiente e execute a carga pelo botão ou CLI. Não inclua credenciais em arquivos de relatório.

Auditoria independente, sem aprovação nem XLSX:

```bash
python scripts/audit_bi_mvp.py ca5cf2d7-98d8-4404-a5cd-916eda0810db \
  --prepared-id 8d60c32c-2363-4f48-80be-d108f8bcae80 --prepared-version 2
```

Após validar o grão, gerar proposta pela CLI:

```bash
python scripts/run_bi_mvp.py ca5cf2d7-98d8-4404-a5cd-916eda0810db \
  --prepared-id 8d60c32c-2363-4f48-80be-d108f8bcae80 --prepared-version 2
```

Aprovação explícita usa `--approve-model`; apenas se confirmado pelo responsável, acrescente `--additive-measure 'Total Pago'`. O caminho versionado é impresso. Não executar essas opções como substituto de uma decisão pendente.

Retomada exata após aprovação (substituir N pela versão aprovada e configurar a variável DSN):

```bash
python scripts/run_bi_mvp.py ca5cf2d7-98d8-4404-a5cd-916eda0810db \
  --prepared-id 8d60c32c-2363-4f48-80be-d108f8bcae80 --prepared-version 2 \
  --model storage/reports/bi_mvp/ca5cf2d7-98d8-4404-a5cd-916eda0810db/model-vN.json \
  --schema bi --chunk-size 2000
```

Sem DSN, a CLI gera os arquivos, mas não executa PostgreSQL. Sem grão validado, retorna `PENDING_HUMAN_GRAIN_VALIDATION`, comportamento verificado na análise real.

## Evidência real e pendências

Auditoria persistida em `storage/reports/bi_mvp/ca5cf2d7-98d8-4404-a5cd-916eda0810db/audit-e9d2f8a4-162d-445f-a020-b568ca01ef23.json` e Grain em `grain-report-v4.json`.

Leitura: 181.476 linhas, 91 chunks; 4,05 s. RSS da leitura: inicial 47,77 MB, máximo observado 55,56 MB, final 55,56 MB. Auditoria + novo Grain: 18,45 s; RSS inicial 45,05 MB, final 57,38 MB, máximo do processo aproximadamente 57,3 MB. RSS de chunks é amostrado, não medição contínua. `/proc` e getrusage podem divergir ligeiramente. Nenhuma materialização integral ou regeneração do Prepared foi utilizada.

Totais **técnicos da fonte**, sem validação de aditividade e **sem reconciliação real PostgreSQL**:

| Medida | Soma exata observada no Prepared |
|---|---:|
| Total Pago | 3672421912.059999970187421 |
| Liquidado | 3542585102.42 |
| Empenhado | 5878169917.2899999999 |
| Devolvido | 0.0 |
| Estornado | -98513673.80999999993020 |

Pendências: decisão humana sobre grão, mapeamentos e aditividade; carga PMCG e reconciliação real; conexão Metabase e validação dos cartões. Não declarar o BI concluído antes dessas etapas.

Commit/push: **NO**.

## Verificação final

- Suíte inicial: 320 passed, 8 skipped (PostgreSQL ainda sem configuração).
- Suíte completa final com PostgreSQL local: **337 passed, 0 skipped**, 95,53 s.
- Testes adicionais/estendidos cobrem cobertura quase nula, suporte zero, ausência de identificadores, contratos históricos, aprovação explícita, somas não confirmadas, dimensões vazias, checksums, ownership, chunks, retomada com novo repositório, revogação por “Não sei”, interface Streamlit e exemplos limitados.
- PostgreSQL: carga sintética de 23 linhas em 4 chunks; reexecução com 0 inserções e 23 linhas reconciliadas. Outro teste preserva 12 registros de negócio idênticos, com lineage distinto, zeros à esquerda e decimal de alta precisão; falha após o primeiro chunk deixa 0 fatos publicados, registra FAILED e a retomada carrega as 12 linhas.
- Tabelas/views criadas e consultadas **somente em schemas de teste**: fato, seis dimensões, `bi_load_run`, `bi_model_contract`, detalhe, executivo, mensal e agrupamentos das dimensões. Não há tabelas PMCG criadas por esta execução.
- Nova auditoria em processo independente: `audit-60361740-7ad1-4ab7-82c4-d6bb3f3b005f.json`; reutilizou Prepared v2 e Grain v4, manteve todos os totais acima, processou 181.476 linhas em 91 chunks e levou 7,05 s. RSS inicial do processo 45,21 MB, máximo observado nos chunks 56,05 MB e final 55,07 MB. A soma Decimal com precisão ajustada foi utilizada nesta execução.
- SHA-256 do Prepared v2 revalidado e inalterado. `app/main.py` comparado ao snapshot inicial: preservado todo o conteúdo anterior, com acréscimo apenas da entrada MVP.
- `git diff --check`: sem erros. Arquivos novos também verificados quanto a whitespace. Worktree preexistente preservado; nenhum commit/push.
