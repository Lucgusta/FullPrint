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

## Instalação nas máquinas dos operadores (produção)

**Não use `git` nas máquinas de produção.** A distribuição é por instalador:

1. Baixe o `FullPrintSetup.exe` da página de **[Releases](https://github.com/LeandroBossiniSoleira/FullPrint/releases/latest)**.
2. Execute. Ele instala em `%LOCALAPPDATA%\FullPrint` (não pede admin), cria atalho no Menu Iniciar e na Área de Trabalho, e **já inclui o Tesseract OCR** — zero configuração manual.
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

`pywin32` instala apenas no Windows (marker em `requirements.txt`). Em outras plataformas, o serviço cai para **modo DEV** automaticamente. Rodando do código-fonte o auto-update fica desativado (só age no `.exe` instalado).

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

## Como lançar uma nova versão

O build do instalador é **automático** via GitHub Actions (`.github/workflows/release.yml`).

1. Ajuste `src/version.py` se quiser (o CI sobrescreve com a tag de qualquer forma).
2. Crie e publique a tag:
   ```bash
   git tag v1.2.0
   git push origin v1.2.0
   ```
3. O CI (runner Windows) roda PyInstaller + embute o Tesseract + compila o Inno Setup e **publica o `FullPrintSetup.exe` no Release** correspondente.
4. As máquinas dos operadores detectam a versão nova no próximo start e se atualizam sozinhas.

> Use [versionamento semântico](https://semver.org/lang/pt-BR/) nas tags (`vMAJOR.MINOR.PATCH`). A tag **precisa** ser maior que a versão instalada para o auto-update disparar.

Peças do pipeline:

| Arquivo | Função |
|---|---|
| `src/version.py` | Fonte única da versão (injetada pela tag no build). |
| `src/services/updater.py` | Verifica/baixa/aplica updates via GitHub Releases. |
| `packaging/FullPrint.spec` | Empacotamento PyInstaller (gera o `.exe`). |
| `packaging/installer.iss` | Instalador Inno Setup (bundle + Tesseract + atalhos). |
| `.github/workflows/release.yml` | CI: compila e publica a cada tag `v*`. |

## Próximos passos (Fase 2)

- Persistência em SQLite (lotes + reimpressão).
- Refatorar parser sob `MarketplaceParser` para suportar Mercado Livre Full.
- Barra de progresso real no worker.
- Tabela com edição de quantidade antes de imprimir.
