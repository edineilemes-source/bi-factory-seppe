"""Views expose only explicitly confirmed additive measures as executive totals."""
from core.bi_mvp.ddl import identifier
from core.bi_mvp.models import MVPModel


def generate_metabase_sql(model: MVPModel, *, schema: str = "bi") -> str:
    s = identifier(schema)
    joins, columns = [], ["f.*"]
    for dim in model.dimensions:
        alias = "d_" + dim.name
        joins.append(f'LEFT JOIN "{s}"."dim_{dim.name}" {alias} USING ("{dim.name}_sk")')
        columns.extend(f'{alias}."{model.source_fields[x]}" AS "{dim.name}_{model.source_fields[x]}"'
                       for x in dim.source_fields)
    detailed = ",\n  ".join(columns)
    statements = [f'''CREATE OR REPLACE VIEW "{s}".vw_despesa_detalhe AS
SELECT {detailed}
FROM "{s}"."{model.fact_name}" f
{' '.join(joins)};''']
    totals = ['COUNT(*) AS quantidade_registros'] + [
        f'SUM("{m.name}") AS "{m.name}"' for m in model.measures if m.additive_confirmed]
    groups = [("executivo", [])]
    for dim in model.dimensions:
        attrs = dim.source_fields
        if dim.name == "tempo":
            attrs = [x for x in ("Ano", "Mês") if x in attrs]
        groups.append(("mensal" if dim.name == "tempo" else "por_" + dim.name,
                       [dim.name + "_" + model.source_fields[x] for x in attrs]))
    for name, attributes in groups:
        keys = ['analysis_id', 'prepared_version'] + [f'"{x}"' for x in attributes]
        statements.append(f'''CREATE OR REPLACE VIEW "{s}"."vw_despesa_{name}" AS
SELECT {', '.join(keys + totals)}
FROM "{s}".vw_despesa_detalhe
GROUP BY {', '.join(keys)};''')
    return '\n\n'.join(statements) + '\n'


def dashboard_instructions(model: MVPModel, *, schema: str = "bi") -> str:
    s = identifier(schema)
    return f'''# Dashboard de despesas — MVP

Modelo {model.model_id}, versão {model.version}; análise {model.analysis_id}, Prepared v{model.prepared_version}.

1. Configure a conexão PostgreSQL no Metabase e sincronize o schema `{s}`.
2. Crie cartões sobre `vw_despesa_executivo` (registros e cada medida confirmada separadamente).
3. Use `vw_despesa_mensal` quando houver Ano/Mês. Os componentes originais são textos; configure ordenação calendário de meses jan a dez, sem ordenar alfabeticamente.
4. Crie barras usando as views `vw_despesa_por_*` disponíveis (unidade, credor, natureza, fonte, evento).
5. Para filtros compartilhados, crie perguntas no construtor sobre `vw_despesa_detalhe`: vincule Ano/Mês/Dia e dimensões disponíveis. Sempre filtre análise e versão.
6. Adicione uma tabela detalhada com `despesa_registro_sk`, identificadores, medidas individuais e `source_values`. Ela preserva todos os campos, `sheet_name`, `source_row_number` e `source_row_id` para investigação.

Somente medidas com `additive_confirmed=true` aparecem nas agregações. Nenhuma soma entre estágios é gerada. A confirmação de grão não confirma aditividade de uma medida.

SQL reproduzível para o cartão de registros:

```sql
SELECT * FROM "{s}".vw_despesa_executivo
WHERE analysis_id = '{model.analysis_id}' AND prepared_version = {model.prepared_version};
```

SQL de detalhamento (ligar filtros de campo no Metabase às colunas reais):

```sql
SELECT * FROM "{s}".vw_despesa_detalhe
WHERE analysis_id = '{model.analysis_id}' AND prepared_version = {model.prepared_version}
ORDER BY source_row_number LIMIT 100;
```

A geração destes arquivos não configura conexão, cartões ou dashboard automaticamente no Metabase.
'''
