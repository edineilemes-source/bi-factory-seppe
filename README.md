# BI Factory SEPPE

Aplicação web para criação de relatórios analíticos a partir de documentos,
planilhas e outras fontes de dados. A plataforma será responsável por apoiar o
diagnóstico técnico e semântico, a construção de metadados, a identificação de
entidades e relacionamentos, a avaliação da qualidade dos dados, a geração de
modelos dimensionais e, futuramente, a publicação de dashboards.

## Sprint 1

Esta sprint implementa o Módulo 01 — Ingestão e Profiling. A aplicação recebe
arquivos XLSX, XLSM e CSV, identifica sua estrutura, gera perfis dos campos,
registra alertas estruturais e permite baixar o diagnóstico completo em JSON.

O processamento é local e em memória. Os arquivos enviados não são alterados
nem persistidos, e o profiling limita a leitura a uma amostra de até 10.000
linhas por aba quando aplicável. Nesta etapa não há banco de dados, integrações
com IA, ETL, modelos dimensionais, dashboards, autenticação ou API.

## Estrutura principal

- `app/`: interface Streamlit, páginas e componentes visuais.
- `core/ingestion/`: leitura segura das fontes tabulares suportadas.
- `core/profiling/`: modelos, heurísticas e geração do diagnóstico técnico.
- `core/`: módulos reservados para metadados, qualidade, modelagem e IA.
- `database/`: espaço reservado para migrações e dados iniciais futuros.
- `storage/`: áreas locais para arquivos originais, de trabalho e relatórios.
- `tests/`: testes automatizados.
- `.devcontainer/`: configuração do ambiente no GitHub Codespaces.

## Desenvolvimento local

O projeto requer Python 3.12.

Crie e ative um ambiente virtual:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
```

No Windows PowerShell, a ativação pode ser feita com:

```powershell
.venv\Scripts\Activate.ps1
```

Instale as dependências:

```bash
python -m pip install -r requirements.txt
```

Execute os testes:

```bash
./test-bi-factory.sh
```

Antes de considerar uma sprint concluída, execute `./test-bi-factory.sh`. O
resultado esperado é a aprovação dos testes smoke, regression, acceptance, do
Golden Semantic Test, da suíte completa e da verificação `git diff --check`.

### Regra de regressão semântica

Todo erro semântico relevante descoberto manualmente deve seguir este fluxo:

1. reproduzir o erro no Golden Semantic Test ou em um teste de regressão;
2. confirmar que o novo teste falha;
3. corrigir a implementação;
4. confirmar que o teste passa;
5. manter o caso permanentemente na suíte.

O Golden Dataset é pequeno, determinístico, versionável, não contém dados
pessoais ou confidenciais e não depende da planilha usada na validação
exploratória.

Inicie a aplicação:

```bash
streamlit run streamlit_app.py
```

## GitHub Codespaces

Ao criar o Codespace, as dependências serão instaladas automaticamente. Inicie
o Streamlit com o comando acima e abra a porta `8501` na aba **Ports**. A porta
aparecerá com o nome **BI Factory Streamlit**.

## Diagnóstico gerado

O resultado inclui contexto do projeto, metadados do arquivo, totais
aproximados, inventário de abas, hipótese de papel de cada aba, perfil dos
campos e alertas estruturais. As classificações são heurísticas preliminares e
devem ser validadas por uma pessoa responsável pelo domínio dos dados.

## Qualidade contextual

Completude física e qualidade de completude de negócio são métricas distintas.
Todo campo começa com obrigatoriedade e aplicabilidade `UNKNOWN`; ausência só é
penalizada como defeito quando a política é `REQUIRED + APPLICABLE`. Campos sem
evidência cuja decisão semântica é `DEFERRED_NO_EVIDENCE` são `NOT_EVALUATED`:
seu score é N/A e suas células não entram no denominador.

O score contextual é determinístico:

`100 - min(100, 100 * weighted_quality_defects / eligible_cells)`

Os pesos permanecem INFO=0,25, WARNING=0,5, ERROR=1 e CRITICAL=2. Ausências
neutras continuam nas métricas físicas de missing, placeholder e observed
completeness, mas não compõem `weighted_quality_defects`. O relatório apresenta
separadamente Quality Score e Observed Completeness.

## Próximos passos

As próximas sprints poderão evoluir o diagnóstico e os contratos do Módulo 01.
Integrações externas, persistência e modelagem serão introduzidas apenas quando
entrarem formalmente no escopo.
# Motor de qualidade (Sprint 2.1)

Após a validação semântica, o motor determinístico analisa a amostra carregada sem
alterar valores de origem. Findings semelhantes são agrupados e limitados a cinco
exemplos. O relatório e candidatos de reconciliação permanecem vinculados ao
`analysis_id` no SQLite; reabrir uma análise não dispara recálculo.

O score é explicável: `100 - min(100, 100 × células afetadas ponderadas / células
analisadas)`, com pesos INFO 0,25, WARNING 0,5, ERROR 1 e CRITICAL 2. O relatório
detalhado é a fonte principal. A checagem `REFERENTIAL_CANDIDATE_ISSUE` possui
contrato, mas fica explicitamente não implementada até existirem relacionamentos
declarados; inferir integridade referencial antes disso produziria falsos positivos.
# Prepared Dataset (Sprint 2.2)

O fluxo de preparação consome a fonte completa e produz somente valores efetivos
(`validated > normalized > source`), sem alterar valores de origem, excluir linhas
ou remover campos vazios/deferred. Cada linha recebe um `source_row_id` técnico e
determinístico; toda alteração segura gera um `TransformationRecord`.

Cada geração recebe UUID e versão novos. O fingerprint SHA-256 considera schema,
linhas efetivas e versão do ruleset, mas ignora UUIDs e timestamps, permitindo
verificar reprodutibilidade. O SQLite guarda metadados, schema, transformações e
localização opcional do artefato — nunca 181 mil linhas célula a célula. O CSV
baixável contém apenas valores efetivos e a identidade técnica da linha; a
auditoria detalhada fica no relatório JSON separado.

## Grain Discovery & Validation (Sprint 2.3)

O Grain Engine consome exclusivamente o Prepared Dataset completo. Ele gera um
número limitado e configurável de candidatos a grão usando papéis semânticos
efetivos, cardinalidade, combinações de identificadores, constraints e issues de
qualidade. Chaves técnicas e `source_row_id` nunca participam do business grain.

Processo, evento, grão e business key são contratos distintos. Dependências
funcionais são registradas como apenas observadas na carga atual, e medidas
repetidas geram alertas conservadores de risco de dupla contagem. Nenhuma
hipótese é autoaceita: somente uma confirmação ou descrição manual persistida
produz o Effective Grain e o status `READY_FOR_DIMENSIONAL_MODELING`.

Relatórios de descoberta e definições validadas são imutáveis e versionados por
Prepared Dataset. Uma nova versão preparada exige nova descoberta/validação e
não herda silenciosamente o grão anterior.
