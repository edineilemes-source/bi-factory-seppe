# Projeto-first: entrada do BI Factory e Conhecimento

**Data:** 17/11/2026  
**Problema observado:** área Conhecimento abria uma tela com entrada de UUID sem contexto de negócio. O sistema possuía projeto PMCG fixo e não oferecia criação de projetos na interface.

## Implementação na branch feat/onboarding-projetos-conhecimento-20261117
- Página inicial explica o produto, mostra projetos e oferece **Novo projeto**.
- Cadastro de projeto: nome, tema, objetivo, organização, abrangência e descrição.
- Projeto PMCG é recuperado virtualmente e não sobrescrito.
- Abrir projeto conduz diretamente ao primeiro passo do Conhecimento, não a um ID de análise.
- Conhecimento oferece seleção de assuntos e fontes de pesquisa (legislação, normas, manuais, sites oficiais e métodos), definição do tema, abrangência, upload de documentos PDF/DOCX/TXT e inventário de documentos.
- Documentos originais armazenados por projeto em `storage/working/projects/<id>/originals`, fora do Git, com SHA-256 e metadados; 12 MB limite inicial.
- Solicitações de pesquisa ficam no acervo com status **Aguardando integração com serviço de pesquisa IA**. **Não há motor de pesquisa legal ou extração semântica de PDFs implantado nesta entrega.** Não simular resultados de IA.
- Projetos novos têm estado e análise recente separados; produtos PMCG não são exibidos em projetos novos. A estrutura de pastas do editor antigo não foi migrada.
- API /api/projects GET/POST, /api/projects/<id> GET/PATCH, /knowledge GET, /research POST, /documents POST.
- Testes sintéticos de HTTP, rejeição de uploads indevidos, isolamento entre projetos, navegação Chromium e regressão dos motores existentes.
- Editor Visual do marco `751e292d4b06f41d79a3e7a1fc18b82e34c0ebcc` não foi modificado; arquivos e registros de produtos anteriores não foram migrados ou limpos.
- A aplicação frontend permanece React 8506 com Python 8505 interno; não se reativa a interface Streamlit.

## Limites atuais
- Projeto por **ambiente de trabalho**; login multiusuário e catálogo por conta dependem de autenticação ainda inexistente.
- Consulta remota à legislação por IA, verificação de vigência, interpretação de documentos e geração de conceitos são próximas entregas, não capacidades prontas.
- Isolamento visual de produtos por projeto utiliza o campo existente `project`, que representa nome de projeto; migração a IDs estáveis precisa de atenção futura. Pastas herdadas não são compartilhadas com novos projetos.
- A versão implantada no Codespaces no início deste trabalho é a anterior. Há script protegido para aplicar a atualização na mesma branch local sem sobrescrever arquivos divergentes: `scripts/implantar_onboarding_projetos_codespaces.py`.
