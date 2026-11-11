# Publicação Hostinger — Etapa 1 (preparação)
Data: 2026-11-11
Estado: **pacote de frontend; não publicado**.

## O que foi automatizado
O workflow `.github/workflows/hostinger-build-preview.yml` executa `npm ci`, `npm run build`, valida `dist/index.html` e publica o artefato `bi-factory-frontend-static` no GitHub Actions. É um pacote estático verificável para implantação, **não** uma implantação na Hostinger.

## Limitação comprovada no código
`web/bi_factory/src/main.jsx` usa `/api/overview` e operações de gravação em `/api/products`; `scripts/serve_bi_factory_api.py` implementa rotas HTTP Python e integra `prototypes/editor-visual/server.py`. O `vite.config.js` faz proxy dessas rotas no desenvolvimento. A hospedagem estática **não** executa essa API e não inclui automaticamente o editor servido pela API. Publicar somente `dist/` geraria uma aplicação incompleta. **Não publicar o pacote como produto funcional.**

## Condições para implantação funcional
1. Confirmar por documentação/conta quais runtimes backend o plano Hostinger Business oferece. Não assumir suporte a Python persistente.
2. Selecionar backend Python persistente autorizado e protegido, com domínio HTTPS e persistência independente, **ou** migrar backend mediante decisão explícita e testes completos.
3. Criar proxy HTTPS para `/api`, `/visual-editor` e `/echarts-studio.html`, evitando CORS e exposição pública não autenticada de operações mutáveis.
4. Configurar conexão GitHub-Hostinger para site **novo**, sem alterar BeUpFree/UpPulse, com branch e diretório corretos.
5. Validar autenticação, isolamento dos dados, backup/restauração, E2E de salvar e reabrir produto, e rollback antes de publicar.
6. Nenhum token, senha, credencial FTP, chave SSH ou dado operacional deve ser colocado no repositório.

## Critério de aceite
A URL HTTPS deve carregar frontend, API, editor e ECharts, permitir criar e reabrir um produto **sintético isolado**, sem Codespaces ativo. CI verde de frontend sozinho **não** satisfaz esse critério.
