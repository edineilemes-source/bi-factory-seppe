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
python -m pytest
```

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

## Próximos passos

As próximas sprints poderão evoluir o diagnóstico e os contratos do Módulo 01.
Integrações externas, persistência e modelagem serão introduzidas apenas quando
entrarem formalmente no escopo.
