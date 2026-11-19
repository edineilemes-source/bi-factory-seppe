# Laboratório BI Factory — ECharts X / Y / Z / Cabeçalho (porta 8507)

## Intenção e isolamento
Este laboratório **não substitui** a aplicação de apresentação da porta **8506**.
Ele não modifica o Editor Visual atual, os gráficos atuais, os produtos e o repositório de dados.
A porta **8507** disponibiliza uma experiência separada para validar outra
arquitetura de construção de gráficos.

- Interface: `experiments/echarts-axes-8507/`
- Servidor: `scripts/serve_echarts_axes_8507.py`
- Rascunhos da 8507: `storage/labs/echarts-axes-8507/state.json`
- Dados: leitura da API já existente em `http://127.0.0.1:8505/api/fiscal`
- Estabilidade: o instalador salva snapshot da implementação atual antes de
  criar os arquivos do laboratório; não encerra nem reinicia processos da 8506.

## Regra 1 — quem define os dados?
**ECharts** é o contrato de dados de cada visualização:
- **X** e **Y**: Ano, Bimestre, Valor (variável numérica virtual) ou Medida
  (identidade da medida). Eixos de Valor podem ser invertidos, por exemplo
  X=Valor e Y=Bimestre.
- **Z**: medida (séries/legenda), valor (rótulos numéricos) ou sem rótulo.
- **Cabeçalho**: contextualiza Ano, Bimestre, Medida ou nenhum.
- **Medidas permitidas**: subconjunto explícito das sete medidas da fonte RREO.
- **Escopo de Ano e de Bimestre**: cada um pode ser `fixed`,
  `filterable` ou `all`.

**Editor Visual** apenas organiza texto, imagem, gráfico, KPI e os componentes de
filtro no canvas. Seus menus da esquerda não possuem combo de Ano ou Bimestre.
Um filtro é colocado no Editor Visual, mas recebe opções apenas dos gráficos
que autorizam variar aquela dimensão.

## Regra 2 — gráfico fixo é imutável pelo painel
Um gráfico cujo contrato tenha
`ano.mode="fixed"`, `ano.fixed=2025` e
`measures=["receita_realizada_acumulada"]`:

- Nunca mostra 2026 por atuação de um filtro global Ano;
- Nunca mostra Despesa por atuação de um seletor global de medidas;
- Permanece fixo se outro gráfico do mesmo painel autorizar 2022–2026;
- Pode exibir bimestres distintos de 2025 **somente conforme o próprio
  contrato de Bimestre** (fixo, filtrável ou todos).

Um componente de filtro sem gráficos autorizados exibe uma mensagem explicativa
em vez de oferecer opções enganosas.

## Regra 3 — sem dados inventados
O RREO carregado possui somente dimensões **Ano** e **Bimestre**; as medidas
incluem Receita realizada, Despesa empenhada, liquidada, paga e três medidas
derivadas já existentes. Há **28 períodos oficiais** na carga confirmada em
19/11/2026: 2022–2025 completos e 2026 até o 4º bimestre.

**Mês, Dia, Unidade Gestora, Fonte, GPF e Elemento de Despesa** não podem
aparecer como dimensões funcionais a partir desta fonte agregada. Para
suportá-las será necessária uma nova base detalhada e catálogo de campos.
No futuro, papéis visuais X/Y/Z/Cabeçalho devem permanecer independentes do
catálogo de dimensões de cada fonte.

RREO contém acumulados: ao agrupar Ano o laboratório utiliza o último
bimestre disponível, e nunca a soma dos bimestres.

## Como testar
1. Execute `python scripts/instalar_lab_echarts_8507.py` após buscar a branch.
2. No Codespaces, encaminhe a porta 8507 com visibilidade **Private**.
3. No **Editor Visual**, clique em **Montar painel fiscal de exemplo**.
4. Veja o indicador **Receita de 2025 · fixa** e os gráficos de execução e
   evolução filtráveis.
5. Altere o filtro Ano para 2026: os gráficos autorizados devem mudar,
   enquanto o indicador de Receita de 2025 deve continuar em 2025.
6. Clique em um gráfico e em **Editar X, Y, Z e Cabeçalho no ECharts**.
7. Configure X=Valor, Y=Bimestre, Z=Medida, Cabeçalho=Ano, Ano fixo 2025,
   medidas apenas Receita, e depois **Aplicar e voltar**.
8. Use **Salvar rascunho 8507**; a gravação fica só no laboratório.
9. Reabra a 8507 para verificar a persistência. Confirme que a 8506 permanece
   disponível e sem alterações.
10. Execute `node scripts/test_echarts_axes_8507.js` para testar as
    invariantes de filtragem e os eixos.

## Limites da prova de conceito
- É uma experiência isolada, não um substituto integral do motor de
  publicações, pastas e cadastro da 8506.
- Há canvas com reordenação, larguras e alturas configuráveis e rascunho
  persistente no laboratório, mas não migra nem edita automaticamente
  produtos existentes.
- As bibliotecas ECharts são carregadas por CDN, como no estúdio atual. A
  biblioteca Apache ECharts tem licença Apache-2.0.
- Ainda é necessário testar a interação real no navegador do Codespaces.
