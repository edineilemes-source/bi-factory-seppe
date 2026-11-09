# BI Factory SEPPE — Interface unificada (8504 + editor 8510)

Branch: `feat/unificar-8504-8510`. Esta integração preserva a interface React da porta 8504 e incorpora o editor GridStack + ECharts do protótipo 8510, sem exigir um terceiro servidor.

## Inicialização no Codespaces

Terminal 1 (API):

```bash
cd /workspaces/bi-factory-seppe
python3 -u scripts/serve_bi_factory_api.py --port 8505
```

Terminal 2 (React):

```bash
cd /workspaces/bi-factory-seppe/web/bi_factory
npm run dev
```

Abrir somente a porta **8504** no navegador. Manter ambas as portas privadas. A porta 8510 não é necessária.

## Fluxo

1. Abrir Produtos, escolher Todos os produtos, Sem pasta ou uma pasta.
2. Novo produto: cadastrar e abrir automaticamente a ficha com o editor visual integrado.
3. Editar produto: atualizar metadados e criar/alterar layout GridStack/ECharts no mesmo local.
4. Criar pasta/subpasta via Nova pasta; arrastar produtos para pastas ou Sem pasta.
5. O editor GridStack persiste em `storage/information_products/layouts/<id>.json` usando o mesmo identificador do catálogo; o canvas Fabric.js anterior permanece disponível.

## Limites e validação

- Código integrado no repositório, **ainda não validado em navegador/Codespaces**.
- Os formatos antigos Fabric.js e GridStack são preservados separadamente; não há migração automática de layouts.
- A rota de edição usa o registro existente e grava metadados complementares em `storage/information_products/metadata`.
- Não foi feita alteração em produtos publicados, nem merge para main.
- Validar: `python3 -m py_compile scripts/serve_bi_factory_api.py prototypes/editor-visual/server.py`, `cd web/bi_factory && npm run build`, abrir 8504 e testar criar/editar/salvar/reabrir produto e mover pasta.
