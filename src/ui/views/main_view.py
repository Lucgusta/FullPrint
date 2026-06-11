"""Tela principal do MVP."""
from __future__ import annotations

import threading
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

import customtkinter as ctk

from ...config.settings import Settings
from ...core.agrupador import EtiquetaAgrupador
from ...core.gerador import GeradorLoteZPL
from ...core.parser import ShopeeZPLParser
from ...core.sku_catalog import SKUCatalog
from ...services.printer import ZebraPrinterService
from ...services.spooler_worker import PrintJob, PrintQueueManager
from ...utils.logger import get_logger

log = get_logger("ui.main")

# Limites defensivos: o gargalo histórico foi criar um widget CTk por linha do
# preview. Treeview aguenta milhares, mas mantemos o teto para o caso de algum
# arquivo absurdo (centenas de milhares).
MAX_PREVIEW_ROWS = 5000
MAX_LOG_LINES = 500


class MainView(ctk.CTkFrame):
    def __init__(
        self,
        master,
        settings: Settings,
        printer_service: ZebraPrinterService,
        worker: PrintQueueManager,
    ) -> None:
        super().__init__(master)
        self.settings = settings
        self.printer_service = printer_service
        self.worker = worker

        # Catalogo persistente: SKU numerico Shopee -> Seller SKU manual.
        # Constroi-se ao longo do uso: duplo-clique numa linha do preview salva.
        cache_path = Path(settings.printer_dev_output_dir).parent / "sku_catalog.json"
        self.catalog = SKUCatalog(cache_path)

        self.parser = ShopeeZPLParser(
            encoding_primario=settings.printer_encoding,
            progress_callback=lambda msg: self.after(0, self._progresso_parse, msg),
            catalog=self.catalog,
        )
        self.agrupador = EtiquetaAgrupador()
        self.gerador = GeradorLoteZPL(settings.templates_dir)

        self._arquivo_atual: Path | None = None
        self._etiquetas_atuais: list = []
        self._grupos_atuais = None
        self._modo_preview = "Por SKU"
        self._busy = False
        self._log_lines = 0

        self._build_layout()
        self._popular_impressoras()
        self._popular_modelos()
        self.log_status("info", "Aplicacao iniciada.")

    # ------------------------------------------------------------------ layout
    def _build_layout(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)
        self.grid_rowconfigure(2, weight=1)

        topo = ctk.CTkFrame(self, corner_radius=8)
        topo.grid(row=0, column=0, columnspan=2, sticky="ew", padx=12, pady=(12, 6))
        topo.grid_columnconfigure(1, weight=1)
        topo.grid_columnconfigure(3, weight=1)

        ctk.CTkLabel(topo, text="Impressora:").grid(row=0, column=0, padx=(12, 6), pady=10, sticky="w")
        self.cb_impressora = ctk.CTkComboBox(topo, values=["(carregando...)"], width=300)
        self.cb_impressora.grid(row=0, column=1, padx=6, pady=10, sticky="ew")

        ctk.CTkLabel(topo, text="Modelo etiqueta:").grid(row=0, column=2, padx=(18, 6), pady=10, sticky="w")
        self.cb_modelo = ctk.CTkComboBox(topo, values=["(carregando...)"], width=240)
        self.cb_modelo.grid(row=0, column=3, padx=(6, 12), pady=10, sticky="ew")

        anexo = ctk.CTkFrame(self, corner_radius=8)
        anexo.grid(row=1, column=0, columnspan=2, sticky="ew", padx=12, pady=6)
        anexo.grid_columnconfigure(1, weight=1)

        self.btn_anexar = ctk.CTkButton(anexo, text="Anexar arquivo TXT...", command=self._on_anexar, width=200)
        self.btn_anexar.grid(row=0, column=0, padx=12, pady=10)

        self.lbl_arquivo = ctk.CTkLabel(anexo, text="Nenhum arquivo selecionado.", anchor="w")
        self.lbl_arquivo.grid(row=0, column=1, padx=6, pady=10, sticky="ew")

        self.btn_processar = ctk.CTkButton(
            anexo, text="Processar", command=self._on_processar, width=120, state="disabled"
        )
        self.btn_processar.grid(row=0, column=2, padx=12, pady=10)

        preview = ctk.CTkFrame(self, corner_radius=8)
        preview.grid(row=2, column=0, sticky="nsew", padx=(12, 6), pady=6)
        preview.grid_columnconfigure(0, weight=1)
        preview.grid_rowconfigure(1, weight=1)

        cabecalho_preview = ctk.CTkFrame(preview, fg_color="transparent")
        cabecalho_preview.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 0))
        cabecalho_preview.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            cabecalho_preview, text="Preview", font=ctk.CTkFont(weight="bold")
        ).grid(row=0, column=0, sticky="w")
        self.toggle_modo = ctk.CTkSegmentedButton(
            cabecalho_preview,
            values=["Por SKU", "Individual"],
            command=self._on_trocar_modo,
            width=240,
        )
        self.toggle_modo.set("Por SKU")
        self.toggle_modo.grid(row=0, column=1, sticky="e")

        self._build_preview_tree(preview)

        log_frame = ctk.CTkFrame(self, corner_radius=8, width=320)
        log_frame.grid(row=2, column=1, sticky="nsew", padx=(6, 12), pady=6)
        log_frame.grid_propagate(False)
        log_frame.grid_columnconfigure(0, weight=1)
        log_frame.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(log_frame, text="Log de impressao", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, sticky="w", padx=12, pady=(10, 0)
        )
        self.log_box = ctk.CTkTextbox(log_frame, width=300, state="disabled", wrap="word")
        self.log_box.grid(row=1, column=0, sticky="nsew", padx=12, pady=10)

        rodape = ctk.CTkFrame(self, corner_radius=8)
        rodape.grid(row=3, column=0, columnspan=2, sticky="ew", padx=12, pady=(6, 12))
        rodape.grid_columnconfigure(0, weight=1)

        self.lbl_resumo = ctk.CTkLabel(rodape, text="Aguardando arquivo.", anchor="w")
        self.lbl_resumo.grid(row=0, column=0, padx=12, pady=10, sticky="ew")

        self.btn_imprimir = ctk.CTkButton(
            rodape,
            text="Imprimir Lote",
            command=self._on_imprimir,
            width=200,
            height=44,
            font=ctk.CTkFont(size=15, weight="bold"),
            state="disabled",
        )
        self.btn_imprimir.grid(row=0, column=1, padx=12, pady=10)

    def _build_preview_tree(self, parent: ctk.CTkFrame) -> None:
        """Treeview ttk nativo: muito mais leve que centenas de CTkLabel."""
        style = ttk.Style()
        # Tenta tema escuro compatível com CTk dark; cai para o default se indisponível.
        try:
            style.theme_use("clam")
        except Exception:  # noqa: BLE001
            pass
        bg = "#2b2b2b"
        fg = "#e6e6e6"
        sel_bg = "#1f6aa5"
        style.configure(
            "Preview.Treeview",
            background=bg,
            fieldbackground=bg,
            foreground=fg,
            rowheight=24,
            borderwidth=0,
        )
        style.configure(
            "Preview.Treeview.Heading",
            background="#1f1f1f",
            foreground=fg,
            relief="flat",
        )
        style.map(
            "Preview.Treeview",
            background=[("selected", sel_bg)],
            foreground=[("selected", "white")],
        )

        container = ctk.CTkFrame(parent, fg_color="transparent")
        container.grid(row=1, column=0, sticky="nsew", padx=12, pady=10)
        container.grid_columnconfigure(0, weight=1)
        container.grid_rowconfigure(0, weight=1)

        self.tree = ttk.Treeview(
            container,
            columns=("idx", "seller", "sku", "descricao", "qtd"),
            show="headings",
            style="Preview.Treeview",
            selectmode="browse",
        )
        self.tree.heading("idx", text="#")
        self.tree.heading("seller", text="Seller SKU")
        self.tree.heading("sku", text="SKU Shopee")
        self.tree.heading("descricao", text="Descricao")
        self.tree.heading("qtd", text="Qtd")
        self.tree.column("idx", width=50, anchor="e", stretch=False)
        self.tree.column("seller", width=170, anchor="w", stretch=False)
        self.tree.column("sku", width=180, anchor="w", stretch=False)
        self.tree.column("descricao", anchor="w")
        self.tree.column("qtd", width=60, anchor="e", stretch=False)

        # Duplo-clique numa linha abre dialog pra editar/cadastrar o Seller SKU
        self.tree.bind("<Double-Button-1>", self._on_editar_seller_sku)

        vsb = ttk.Scrollbar(container, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")

    # ----------------------------------------------------------------- helpers
    def _popular_impressoras(self) -> None:
        impressoras = self.printer_service.listar_impressoras()
        if not impressoras:
            impressoras = ["(nenhuma encontrada)"]
        self.cb_impressora.configure(values=impressoras)
        padrao = self.printer_service.impressora_padrao() or self.settings.printer_default
        if padrao and padrao in impressoras:
            self.cb_impressora.set(padrao)
        else:
            self.cb_impressora.set(impressoras[0])

    def _popular_modelos(self) -> None:
        modelos = [m.nome for m in self.settings.label_models] or ["(nenhum)"]
        self.cb_modelo.configure(values=modelos)
        self.cb_modelo.set(modelos[0])

    def log_status(self, level: str, mensagem: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        prefixo = {"info": "[i]", "ok": "[OK]", "erro": "[X]", "aviso": "[!]"}.get(level, "[ ]")
        linha = f"{ts} {prefixo} {mensagem}\n"
        self.log_box.configure(state="normal")
        self.log_box.insert("end", linha)
        self._log_lines += 1
        # Rotaciona o buffer para impedir crescimento ilimitado.
        if self._log_lines > MAX_LOG_LINES:
            excedente = self._log_lines - MAX_LOG_LINES
            self.log_box.delete("1.0", f"{excedente + 1}.0")
            self._log_lines = MAX_LOG_LINES
        self.log_box.see("end")
        self.log_box.configure(state="disabled")
        log.log({"erro": 40, "aviso": 30, "ok": 20, "info": 20}.get(level, 20), mensagem)

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        estado_processar = "disabled" if busy or not self._arquivo_atual else "normal"
        estado_anexar = "disabled" if busy else "normal"
        estado_imprimir = "disabled" if busy or not self._grupos_atuais else "normal"
        self.btn_processar.configure(state=estado_processar)
        self.btn_anexar.configure(state=estado_anexar)
        self.btn_imprimir.configure(state=estado_imprimir)

    # ------------------------------------------------------------------- acoes
    def _on_trocar_modo(self, valor: str) -> None:
        self._modo_preview = valor
        if self._grupos_atuais is not None:
            self._renderizar_preview()

    def _on_anexar(self) -> None:
        if self._busy:
            return
        diretorio_inicial = str(self.settings.default_input_dir) if self.settings.default_input_dir.exists() else None
        caminho = filedialog.askopenfilename(
            title="Selecione o arquivo TXT/ZPL da Shopee",
            initialdir=diretorio_inicial,
            filetypes=[("Arquivos ZPL/TXT", "*.txt *.zpl"), ("Todos", "*.*")],
        )
        if not caminho:
            return
        self._arquivo_atual = Path(caminho)
        self._etiquetas_atuais = []
        self._grupos_atuais = None
        self.lbl_arquivo.configure(text=str(self._arquivo_atual))
        self.btn_processar.configure(state="normal")
        self.btn_imprimir.configure(state="disabled")
        self.log_status("info", f"Arquivo selecionado: {self._arquivo_atual.name}")

    def _progresso_parse(self, mensagem: str) -> None:
        self.lbl_resumo.configure(text=mensagem)

    def _on_processar(self) -> None:
        if self._busy or not self._arquivo_atual:
            return
        arquivo = self._arquivo_atual
        self._set_busy(True)
        self.lbl_resumo.configure(text=f"Processando {arquivo.name}...")
        self.log_status("info", f"Iniciando parse: {arquivo.name}")

        def worker() -> None:
            try:
                etiquetas = self.parser.parse_file(arquivo)
                grupos = self.agrupador.agrupar_por_sku(etiquetas) if etiquetas else None
                self.after(0, self._on_processar_concluido, etiquetas, grupos, None)
            except Exception as exc:  # noqa: BLE001
                log.exception("Erro no parse")
                self.after(0, self._on_processar_concluido, None, None, exc)

        threading.Thread(target=worker, name="ParseWorker", daemon=True).start()

    def _on_processar_concluido(self, etiquetas, grupos, erro) -> None:
        self._set_busy(False)
        if erro is not None:
            messagebox.showerror("Erro ao processar arquivo", str(erro))
            self.log_status("erro", f"Falha no parse: {erro}")
            self.lbl_resumo.configure(text="Falha ao processar arquivo.")
            return
        if not etiquetas:
            self.log_status("aviso", "Nenhum bloco ^XA..^XZ encontrado no arquivo.")
            messagebox.showwarning("Nada encontrado", "Nenhuma etiqueta ZPL foi detectada no arquivo.")
            self.lbl_resumo.configure(text="Arquivo sem etiquetas ZPL.")
            return

        self._etiquetas_atuais = etiquetas
        self._grupos_atuais = grupos
        self._renderizar_preview()

        blocos = sum(g.qtd for g in grupos.values())
        stickers = sum(g.total_stickers for g in grupos.values())
        nome = self._arquivo_atual.name if self._arquivo_atual else "?"
        if stickers != blocos:
            resumo = (
                f"{len(grupos)} SKUs  |  {blocos} etiquetas  |  "
                f"{stickers} stickers  |  Arquivo: {nome}"
            )
        else:
            resumo = f"{len(grupos)} SKUs  |  {blocos} etiquetas  |  Arquivo: {nome}"
        self.lbl_resumo.configure(text=resumo)
        self.btn_imprimir.configure(state="normal")
        self.log_status(
            "ok",
            f"Processado: {len(grupos)} SKUs / {blocos} etiquetas / {stickers} stickers.",
        )

    def _seller_label(self, sku: str, fallback_ocr: str = "") -> str:
        """Cache manual tem prioridade; cai pra OCR (sugestao); senao '?'."""
        manual = self.catalog.get(sku)
        if manual:
            return manual  # confiavel
        if fallback_ocr:
            return f"~{fallback_ocr}"  # ~prefixo = sugestao do OCR
        return "?"

    def _renderizar_preview(self) -> None:
        # Limpa em bloco — Treeview lida com isso sem o custo dos widgets CTk.
        self.tree.delete(*self.tree.get_children())
        if self._modo_preview == "Individual":
            itens = self._etiquetas_atuais
            total = len(itens)
            exibir = min(total, MAX_PREVIEW_ROWS)
            for i, et in enumerate(itens[:exibir], start=1):
                seller = self._seller_label(et.sku, et.metadados.get("seller_ocr", ""))
                self.tree.insert(
                    "",
                    "end",
                    iid=f"sku::{et.sku}::{i}",
                    values=(f"{i:03d}", seller, et.sku, et.descricao, 1),
                )
            unidade = "stickers"
        else:
            grupos = self._grupos_atuais or {}
            itens = list(grupos.values())
            total = len(itens)
            exibir = min(total, MAX_PREVIEW_ROWS)
            # Procura OCR do 1o sticker daquele SKU para usar como sugestao
            seller_ocr_por_sku: dict[str, str] = {}
            for et in self._etiquetas_atuais:
                if et.sku not in seller_ocr_por_sku:
                    seller_ocr_por_sku[et.sku] = et.metadados.get("seller_ocr", "")
            for i, grupo in enumerate(itens[:exibir], start=1):
                seller = self._seller_label(grupo.sku, seller_ocr_por_sku.get(grupo.sku, ""))
                self.tree.insert(
                    "",
                    "end",
                    iid=f"sku::{grupo.sku}",
                    values=(f"{i:03d}", seller, grupo.sku, grupo.descricao, grupo.qtd),
                )
            unidade = "SKUs"
        if total > exibir:
            self.log_status(
                "aviso",
                f"Preview limitado a {exibir} de {total} {unidade} (lote inteiro sera impresso).",
            )

    def _on_editar_seller_sku(self, _event) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        iid = sel[0]
        if not iid.startswith("sku::"):
            return
        sku_numerico = iid.split("::")[1]
        atual = self.catalog.get(sku_numerico) or ""
        novo = simpledialog.askstring(
            "Seller SKU",
            f"SKU Shopee:\n  {sku_numerico}\n\nSeller SKU (vazio remove o mapeamento):",
            initialvalue=atual,
            parent=self,
        )
        if novo is None:
            return  # cancelou
        novo = novo.strip().upper()
        self.catalog.set(sku_numerico, novo)
        # Atualiza tambem as EtiquetaZPL em memoria pra refletir agora.
        for et in self._etiquetas_atuais:
            if et.sku == sku_numerico:
                et.seller_sku = novo
        # Re-renderiza preview pra mostrar o novo valor na coluna.
        self._renderizar_preview()
        self.log_status(
            "ok",
            f"Seller SKU '{novo}' salvo para {sku_numerico} (catalogo: {self.catalog.total()} mapeamentos).",
        )

    def _on_imprimir(self) -> None:
        if self._busy or not self._etiquetas_atuais:
            return
        impressora = self.cb_impressora.get()
        if not impressora or impressora.startswith("("):
            messagebox.showwarning("Impressora", "Selecione uma impressora valida.")
            return
        lote_id = datetime.now().strftime("%Y%m%d%H%M%S")
        etiquetas = self._etiquetas_atuais
        gerador = self.gerador

        # Builder lazy: a montagem do ZPL acontece dentro da thread do worker.
        # Ordem original do arquivo, sem agrupar e sem separador.
        def builder() -> str:
            return gerador.gerar_zpl_ordem_original(etiquetas, lote_id=lote_id)

        job = PrintJob(
            printer_name=impressora,
            job_name=f"Lote-{lote_id}",
            builder=builder,
        )
        self.worker.submit(job)
        self.log_status("info", f"Lote {lote_id} enviado para fila de impressao.")
