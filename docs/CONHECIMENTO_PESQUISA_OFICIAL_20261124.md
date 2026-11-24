# Pesquisa oficial de legislação e manuais — módulo Conhecimento

**Data:** 24/11/2026. **Projeto:** BI Factory SEPPE. **Situação:** código publicado em branch isolada; implantação e validação HTTP no Codespaces ainda não confirmadas.

## Objetivo

Na ficha do projeto, seção **Conhecimento**, o operador informa um tema e uma abrangência, escolhe tipos documentais, consulta portais oficiais, analisa os resultados com URL de origem e seleciona explicitamente até dez documentos para incorporar ao acervo. O sistema só baixa PDFs depois da aprovação.

### Fontes iniciais realmente reconhecidas

- [Tesouro Nacional — MCASP](https://www.gov.br/tesouronacional/pt-br/contabilidade-e-custos/manuais/manual-de-contabilidade-aplicada-ao-setor-publico-mcasp-1). **11ª edição**, válida desde o exercício 2025.
- [Tesouro Nacional — MDF](https://www.gov.br/tesouronacional/pt-br/contabilidade-e-custos/manuais/manual-de-demonstrativos-fiscais-mdf). **15ª edição vigente para 2026**, com versão atualizada em 23/9/2026; **16ª edição válida a partir de 2027**, publicada em 3/11/2026.
- [Siconfi — instruções e guias de preenchimento](https://siconfi.tesouro.gov.br/siconfi/pages/public/conteudo/conteudo.jsf?id=42): RREO, RGF e DCA.
- [Siconfi — documentação e tabelas](https://siconfi.tesouro.gov.br/siconfi/pages/public/conteudo/conteudo.jsf?id=46903).
- [Tesouro Nacional — PCASP](https://www.gov.br/tesouronacional/pt-br/contabilidade-e-custos/federacao/plano-de-contas-aplicado-ao-setor-publico-pcasp-1).
- [Planalto — Lei 4.320/1964, texto compilado](https://www.planalto.gov.br/ccivil_03/leis/l4320compilado.htm), especialmente receita, empenho, liquidação, pagamento e balanços.
- [Planalto — Lei Complementar 101/2000, LRF](https://www.planalto.gov.br/ccivil_03/leis/lcp/lcp101.htm), responsabilidade fiscal, RREO e RGF.
- [Manual público completo Siconfi, em PDF](https://manualsiconfi.tesouro.gov.br/manual_completo.pdf).

**Limite deliberado:** descoberta inicial a partir dessas páginas oficiais, seus links e termos associados. Não é um motor de busca exaustivo de todos os diários oficiais, tribunais ou portais municipais; não afirmar cobertura integral. PDFs com endereço indeterminável não são inventados. Links inoperantes aparecem nas advertências.

## Interação

1. Selecione **Projetos → Conhecimento**; informe **Tema ou assunto**, por exemplo: *empenho, liquidação, receita orçamentária, resultado orçamentário, prestação de contas, RREO, RGF, DCA*. Existem atalhos.
2. Pressione **Pesquisar fontes oficiais**. A pesquisa percorre portais reais e retorna título, URL, órgão, categoria, indicação de PDF e edição/vigência quando identificável.
3. Clique nos links para conferir a procedência. Marque os PDFs ou referências desejados (até dez por rodada).
4. Pressione **Aprovar e incorporar**. Os PDFs são baixados apenas neste momento; as páginas HTML ficam como referências, não como documentos falsamente marcados PDF.
5. O resultado fica no **Acervo de conhecimento** do projeto, com hash SHA-256, URL, data de pesquisa, aprovação, origem e botão para baixar a cópia. É possível reabrir buscas anteriores.

## Persistência e confiança

- Base do projeto: `storage/working/projects/<id>/knowledge.json`.
- Pesquisas: `storage/working/projects/<id>/discoveries/<uuid>.json`.
- PDFs originais aprovados: `storage/working/projects/<id>/originals/<SHA256>.pdf` (até 25 MiB cada).
- Resultados e documentos de um projeto não são associados a outro, e o PDF não é versionado automaticamente no Git remoto.
- Downloads somente HTTPS, hospedagens oficiais `.gov.br` e `.leg.br`, redirecionamentos igualmente validados, limite de tamanho, assinatura `%PDF-`, nomes por SHA-256, gravação atômica com permissão restrita, verificação de duplicados.
- A base não altera as medidas, o catálogo fiscal, os dados RREO nem as pastas de produtos.

## IA gratuita opcional

A pesquisa funciona **sem chave de API ou pagamentos**, com rastreabilidade nos portais oficiais. Se o Codespaces já possuir o servidor **Ollama** (licença MIT), definir:

```bash
export BI_KNOWLEDGE_OLLAMA_MODEL=qwen2.5:1.5b
export BI_KNOWLEDGE_OLLAMA_URL=http://127.0.0.1:11434
```

O modelo Qwen2.5 1.5B é Apache 2.0; não instalamos nem baixamos modelos automaticamente. O processo precisa estar em execução **antes** da inicialização da API 8505 para que o ambiente seja herdado. A IA só sugere termos de pesquisa; os resultados são sempre obtidos em portais reais. Sem Ollama, o sistema opera normalmente. A disponibilidade do plano gratuito da API Gemini varia; não há conexão automática com API externa, e nenhuma chave é armazenada no Git.

## Verificação

- Testes de segurança, isolamento, aprovação e PDF: `python3 scripts/test_knowledge_official.py`.
- Compilação do frontend: `cd web/bi_factory && npm run build`.
- CI: `.github/workflows/bi-knowledge-official.yml`, com execução offline e build.
- Instalação local: `scripts/instalar_conhecimento_oficial.py` via `git show` após `git fetch origin`. Não troca de branch, não mexe na 8507 experimental nem altera o editor.
- Pendente: teste real HTTPS nos portais a partir do Codespaces, confirmação de downloads efetivos e homologação da interface pelo operador.

## Relação com modelagem

Esta base é a **fundamentação jurídica e contábil** das medidas: distinguir receita prevista/realizada, despesa empenhada/liquidada/paga, classificação fiscal, demonstrativos RREO/RGF/DCA e balanços. O vínculo automático entre cada regra extraída e cada medida do modelo ainda é uma etapa futura. O sistema não inventa interpretações de normas; toda regra terá de indicar a fonte primária e a edição aplicável.
