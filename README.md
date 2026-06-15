# Shopee ZPL Spooler

Automação de impressão de etiquetas ZPL da Shopee Full em impressoras Zebra (ZD220). Lê o arquivo `.txt` exportado da Shopee e imprime conforme o **modelo de etiqueta** configurado:

- **Fiel (10x15 Shopee)**: envia o arquivo **byte a byte** para a impressora (pass-through) — sai idêntico ao original. Para quem usa a bobina padrão da Shopee.
- **Composto (bobina própria)**: re-monta as etiquetas no tamanho/layout da sua bobina (ex.: 50x25mm, 2 colunas). Cada sticker (QR + texto) é recortado do bitmap original (pixels idênticos, **sem OCR**) e reposicionado, com **1 bloco de impressão por linha** — corrige impressão fora do padrão e etiquetas faltando em bobinas menores.

> **Status**: v0.3.x. Modelos de etiqueta configuráveis pelo usuário; preview mostra a etiqueta exatamente como vai sair.

## Funcionalidades

- Interface gráfica em **CustomTkinter** (tema dark).
- Seleção de impressora (lista as locais do Windows via `win32print`).
- Anexar arquivo TXT/ZPL via diálogo.
- **Impressão pass-through**: os bytes originais do arquivo vão direto para a impressora (RAW), sem decode/re-encode — fidelidade garantida por construção.
- Preview por SKU ou individual: SKU Shopee lido do **QR code** de cada sticker (pyzbar), quantidade por SKU, e **imagem real do sticker** (recortada do bitmap GRF) ao selecionar uma linha.
- **Seller SKU via catálogo manual**: duplo-clique numa linha cadastra o mapeamento SKU Shopee → Seller SKU (persistido em `data/sku_catalog.json`).
- Impressão em **thread separada** (worker daemon + fila).
- **Modo DEV** (Linux/macOS, ou win32print indisponível): grava o ZPL em `data/dev_output/` ao invés de mandar para impressora — útil para desenvolvimento.
- Log de impressão em painel lateral e arquivo rotacionado (`logs/spooler.log`).

## Estrutura

```text
shopee_zpl_spooler/
├── src/
│   ├── main.py
│   ├── config/{settings.py, config.yaml}
│   ├── core/{parser.py, agrupador.py, grf_decoder.py, sku_catalog.py,
│   │         label_models.py, label_renderer.py}
│   ├── services/{printer.py, spooler_worker.py, updater.py}
│   ├── database/     # Fase 2
│   ├── ui/{app.py, views/main_view.py}
│   └── utils/{logger.py, zpl_utils.py, runtime.py}
├── tests/{test_parser.py, smoke_pipeline.py, smoke_grf.py, render_grf.py}
├── logs/  data/
├── requirements.txt
└── README.md
```

## Instalação nas máquinas dos operadores (produção)

**Não use `git` nas máquinas de produção.** A distribuição é por instalador:

1. Baixe o `FullPrintSetup.exe` da página de **[Releases](https://github.com/LeandroBossiniSoleira/FullPrint/releases/latest)**.
2. Execute. Ele instala em `%LOCALAPPDATA%\FullPrint` (não pede admin) e cria atalho no Menu Iniciar e na Área de Trabalho — zero configuração manual.
3. Pronto. **A partir daí o app se atualiza sozinho**: ao abrir, verifica se há versão nova no GitHub, baixa em segundo plano e aplica a atualização (silenciosa) quando o app é fechado.

> A primeira instalação precisa ser feita pelo `FullPrintSetup.exe` (não por `git clone`), porque o auto-update reinstala por cima dele.

## Instalação para desenvolvimento

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

pip install -r requirements.txt
```

`pywin32` instala apenas no Windows (marker em `requirements.txt`). Em outras plataformas, o serviço cai para **modo DEV** automaticamente. No Linux, o pyzbar precisa do `libzbar0` do sistema (`apt install libzbar0`). Rodando do código-fonte o auto-update fica desativado (só age no `.exe` instalado).

## Execução

```bash
python -m src.main
# ou
python src/main.py
```

## Testes

```bash
python -m unittest discover tests
# Smoke com um TXT real da Shopee Full (valida o pass-through byte a byte):
python tests/smoke_grf.py /caminho/arquivo_shopee.txt
# Calibração visual dos crops de sticker (gera PNGs em data/dev_output/):
python tests/render_grf.py /caminho/arquivo_shopee.txt
```

## Configuração

Edite `src/config/config.yaml`:

- `printer.default_name`: impressora padrão (deixe vazio para usar a do Windows).
- `printer.dev_mode: true`: força modo DEV mesmo no Windows (não imprime, grava arquivo).
- `paths.default_input_dir`: pasta inicial do diálogo de anexar arquivo.

Os **modelos de etiqueta** são gerenciados pela própria interface (botão "Configurar...") e salvos em `data/label_models.json` — dimensões da bobina, colunas, margens e tamanho do QR. Use "Imprimir teste" para calibrar o alinhamento na bobina real.

## Como lançar uma nova versão

O build do instalador é **automático** via GitHub Actions (`.github/workflows/release.yml`).

1. Ajuste `src/version.py` se quiser (o CI sobrescreve com a tag de qualquer forma).
2. Crie e publique a tag:
   ```bash
   git tag v1.2.0
   git push origin v1.2.0
   ```
3. O CI (runner Windows) roda os testes + PyInstaller + compila o Inno Setup e **publica o `FullPrintSetup.exe` no Release** correspondente.
4. As máquinas dos operadores detectam a versão nova no próximo start e se atualizam sozinhas.

> Use [versionamento semântico](https://semver.org/lang/pt-BR/) nas tags (`vMAJOR.MINOR.PATCH`). A tag **precisa** ser maior que a versão instalada para o auto-update disparar.

Peças do pipeline:

| Arquivo | Função |
|---|---|
| `src/version.py` | Fonte única da versão (injetada pela tag no build). |
| `src/services/updater.py` | Verifica/baixa/aplica updates via GitHub Releases. |
| `packaging/FullPrint.spec` | Empacotamento PyInstaller (gera o `.exe`). |
| `packaging/installer.iss` | Instalador Inno Setup (bundle + atalhos). |
| `.github/workflows/release.yml` | CI: testa, compila e publica a cada tag `v*`. |

## Próximos passos (Fase 2)

- Persistência em SQLite (lotes + reimpressão).
- Refatorar parser sob `MarketplaceParser` para suportar Mercado Livre Full.
- Barra de progresso real no worker.
- Agrupamento opcional por SKU na impressão (reordenar folhas inteiras + separadora), mantendo os trios ZPL originais intactos.
