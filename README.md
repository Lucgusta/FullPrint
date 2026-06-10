# Shopee ZPL Spooler

Automação de impressão de etiquetas ZPL da Shopee Full em impressoras Zebra (ZD220). Lê o arquivo `.txt` exportado, agrupa etiquetas por SKU, insere uma **etiqueta separadora** entre os grupos e envia o lote para a impressora.

> **Status**: Fase 1 (MVP). Roadmap completo em `shopee_zpl_architecture.md`.

## Funcionalidades do MVP

- Interface gráfica em **CustomTkinter** (tema dark).
- Seleção de impressora (lista as locais do Windows via `win32print`).
- Seleção de modelo de etiqueta (10x15 padrão Shopee, 10x10, 4x3).
- Anexar arquivo TXT/ZPL via diálogo.
- Parser robusto: extrai blocos `^XA…^XZ`, identifica SKU/descrição.
- Agrupamento por SKU com preview em tela (SKU | Descrição | Qtd).
- Geração do lote com etiqueta separadora a cada SKU.
- Impressão em **thread separada** (worker daemon + fila).
- **Modo DEV** (Linux/macOS, ou win32print indisponível): grava o ZPL em `data/dev_output/` ao invés de mandar para impressora — útil para desenvolvimento.
- Log de impressão em painel lateral e arquivo rotacionado (`logs/spooler.log`).

## Estrutura

```text
shopee_zpl_spooler/
├── src/
│   ├── main.py
│   ├── config/{settings.py, config.yaml}
│   ├── core/{parser.py, agrupador.py, gerador.py, templates/separador.zpl}
│   ├── services/{printer.py, spooler_worker.py}
│   ├── database/     # Fase 2
│   ├── ui/{app.py, views/main_view.py}
│   └── utils/{logger.py, zpl_utils.py}
├── tests/test_parser.py
├── logs/  data/
├── requirements.txt
└── README.md
```

## Instalação

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

pip install -r requirements.txt
```

`pywin32` instala apenas no Windows (marker em `requirements.txt`). Em outras plataformas, o serviço cai para **modo DEV** automaticamente.

## Execução

```bash
python -m src.main
# ou
python src/main.py
```

## Testes

```bash
python -m unittest discover tests
```

## Configuração

Edite `src/config/config.yaml`:

- `printer.default_name`: impressora padrão (deixe vazio para usar a do Windows).
- `printer.dev_mode: true`: força modo DEV mesmo no Windows (não imprime, grava arquivo).
- `label_models`: lista de modelos disponíveis no dropdown.
- `paths.default_input_dir`: pasta inicial do diálogo de anexar arquivo.

## Próximos passos (Fase 2)

- Persistência em SQLite (lotes + reimpressão).
- Refatorar parser sob `MarketplaceParser` para suportar Mercado Livre Full.
- Barra de progresso real no worker.
- Tabela com edição de quantidade antes de imprimir.
