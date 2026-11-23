# Editor Visual oficial da BI Factory SEPPE — versão 8507

## Fluxo do usuário

1. Abra a aplicação BI Factory SEPPE na **porta 8507** (Codespaces, visibilidade Private).
2. Entre em **Projetos → Produtos**, selecione uma pasta e abra **Novo produto** ou um produto existente.
3. Preencha os metadados da ficha normalmente: nome, tipo, pasta, descrição, responsável, técnico, origem, atualização, publicação e demais campos que já existiam.
4. Clique em **Editar visual**. Abre o editor da versão experimental 8507, agora oficial, com canvas de largura inteira, cortinas, ECharts, medidas, filtros autorizados, figuras, imagens, textos, KPIs, sobreposição e visualização com ampliação dos gráficos.
5. Clique em **Salvar produto**. A ficha vincula o layout ao ID do produto. Ao voltar, **Visualizar produto** apresenta o mesmo painel, sem ferramentas de edição.

## Infraestrutura e persistência

- **8507**: catálogo oficial React/Vite com o Editor Visual 8507 na ficha do produto. A porta 8506 deixa de ser a interface oficial e seu processo conhecido é encerrado **somente depois** de validar a 8507. O código anterior fica no Git e no backup; serviços desconhecidos não são encerrados.
- **8505**: API do catálogo e dados fiscais, com proxy do Vite.
- **Editor oficial**: `/visual-editor/official-8507/index.html?product=<uuid>&mode=edit`; usa recursos estáticos próprios versionados em `prototypes/editor-visual/official-8507/`. **Não depende** do antigo servidor de laboratório na 8507.
- **Layout novo por produto**: GET/PUT `/api/products/<uuid>/visual-8507` → `storage/information_products/visual_8507/<uuid>.json`. São aceitos somente objetos conhecidos, até 100 objetos por produto e até 12 MB por requisição.
- **Backup da versão anterior do mesmo layout**: `storage/information_products/visual_8507/previous/<uuid>.json`.
- **Layouts existentes (8506/GridStack)**: permanecem intocados em `storage/information_products/layouts/<uuid>.json`. Se ainda não houver layout oficial, o editor oferece uma conversão de leitura para os objetos existentes; os gráficos migrados exigem conferência de medidas e eixos antes do primeiro salvamento.
- **Rascunho que existia no laboratório 8507**: permanece em `storage/labs/echarts-axes-8507/state.json`; não é atribuído automaticamente a qualquer produto. O usuário pode clicar em **Importar painel de teste da 8507** dentro de um produto e, então, **Salvar produto**. Essa ação não apaga o rascunho do laboratório nem os arquivos do modelo antigo.
- **Cache local**: a chave inclui o ID do produto, para não misturar rascunhos entre produtos.
- **Dados STN/SICONFI**: as medidas e os 28 períodos homologados continuam na fonte original; a migração não altera o CSV.
- **Publicação**: confirmação e publicação continuam processos separados do salvamento de layout; nenhum novo endpoint de publicação pública foi criado.

## Compatibilidade e limites

A conversão do layout antigo é **não destrutiva** e não garante equivalência semântica integral de gráficos com configuração antiga. Quando houver mapeamentos ambíguos, o editor sinaliza a necessidade de revisão. O original não é apagado. Os gráficos criados diretamente no editor 8507 oficial têm seu próprio contrato completo (X, Y, Z, cabeçalho, medidas e escopos).

O instalador `scripts/implantar_editor_8507_oficial.py` testa a API isolada, os contratos do frontend e o build Vite antes de promover a porta 8507, faz backup dos arquivos alterados e aplica correções sem mudar a branch local. Se houver alterações locais incompatíveis, cancela antes de sobrescrever.

## Verificação

```bash
cd /workspaces/bi-factory-seppe
node scripts/test_editor_oficial_8507_integracao.js
python3 scripts/test_editor_oficial_8507_api.py
cd web/bi_factory && npm run build
```

Depois da ativação, verifique `http://127.0.0.1:8507/`, `/api/products`, `/visual-editor/official-8507/index.html` e o fluxo Novo produto → Salvar → Reabrir → Visualizar.
