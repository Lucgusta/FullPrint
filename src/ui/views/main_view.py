"""Tela principal do MVP."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from ...config.settings import Settings
from ...core.agrupador import EtiquetaAgrupador
from ...core.gerador import GeradorLoteZPL
from ...core.parser import ShopeeZPLParser
from ...services.printer import ZebraPrinterService
from ...services.spooler_worker import PrintJob, PrintQueueManager
from ...utils.logger import get_logger

log = get_logger("ui.main")


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

        self.parser = ShopeeZPLParser(encoding_primario=settings.printer_encoding)
        self.agrupador = EtiquetaAgrupador()
        self.gerador = GeradorLoteZPL(settings.templates_dir)

        self._arquivo_atual: Path | None = None
        self._grupos_atuais = None

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

        ctk.CTkLabel(preview, text="Preview do agrupamento", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, sticky="w", padx=12, pady=(10, 0)
        )
        self.preview_frame = ctk.CTkScrollableFrame(preview, label_text="SKU  |  Descricao  |  Qtd")
        self.preview_frame.grid(row=1, column=0, sticky="nsew", padx=12, pady=10)

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
        self.log_box.see("end")
        self.log_box.configure(state="disabled")
        log.log({"erro": 40, "aviso": 30, "ok": 20, "info": 20}.get(level, 20), mensagem)

    # ------------------------------------------------------------------- acoes
    def _on_anexar(self) -> None:
        diretorio_inicial = str(self.settings.default_input_dir) if self.settings.default_input_dir.exists() else None
        caminho = filedialog.askopenfilename(
            title="Selecione o arquivo TXT/ZPL da Shopee",
            initialdir=diretorio_inicial,
            filetypes=[("Arquivos ZPL/TXT", "*.txt *.zpl"), ("Todos", "*.*")],
        )
        if not caminho:
            return
        self._arquivo_atual = Path(caminho)
        self.lbl_arquivo.configure(text=str(self._arquivo_atual))
        self.btn_processar.configure(state="normal")
        self.btn_imprimir.configure(state="disabled")
        self.log_status("info", f"Arquivo selecionado: {self._arquivo_atual.name}")

    def _on_processar(self) -> None:
        if not self._arquivo_atual:
            return
        try:
            etiquetas = self.parser.parse_file(self._arquivo_atual)
        except Exception as exc:  # noqa: BLE001
            log.exception("Erro no parse")
            messagebox.showerror("Erro ao processar arquivo", str(exc))
            self.log_status("erro", f"Falha no parse: {exc}")
            return

        if not etiquetas:
            self.log_status("aviso", "Nenhum bloco ^XA..^XZ encontrado no arquivo.")
            messagebox.showwarning("Nada encontrado", "Nenhuma etiqueta ZPL foi detectada no arquivo.")
            return

        grupos = self.agrupador.agrupar_por_sku(etiquetas)
        self._grupos_atuais = grupos
        self._renderizar_preview(grupos)

        total = sum(g.qtd for g in grupos.values())
        self.lbl_resumo.configure(
            text=f"{len(grupos)} SKUs unicos  |  {total} etiquetas  |  Arquivo: {self._arquivo_atual.name}"
        )
        self.btn_imprimir.configure(state="normal")
        self.log_status("ok", f"Processado: {len(grupos)} SKUs / {total} etiquetas.")

    def _renderizar_preview(self, grupos) -> None:
        for widget in self.preview_frame.winfo_children():
            widget.destroy()
        for i, grupo in enumerate(grupos.values()):
            cor = ("gray85", "gray20") if i % 2 == 0 else ("gray90", "gray25")
            linha = ctk.CTkFrame(self.preview_frame, fg_color=cor, corner_radius=4)
            linha.grid(row=i, column=0, sticky="ew", padx=2, pady=1)
            linha.grid_columnconfigure(1, weight=1)
            ctk.CTkLabel(linha, text=grupo.sku, width=140, anchor="w").grid(row=0, column=0, padx=8, pady=4, sticky="w")
            ctk.CTkLabel(linha, text=grupo.descricao, anchor="w").grid(row=0, column=1, padx=8, pady=4, sticky="ew")
            ctk.CTkLabel(linha, text=f"x{grupo.qtd}", width=60, anchor="e").grid(row=0, column=2, padx=8, pady=4, sticky="e")

    def _on_imprimir(self) -> None:
        if not self._grupos_atuais:
            return
        impressora = self.cb_impressora.get()
        if not impressora or impressora.startswith("("):
            messagebox.showwarning("Impressora", "Selecione uma impressora valida.")
            return
        lote_id = datetime.now().strftime("%Y%m%d%H%M%S")
        zpl_final = self.gerador.gerar_zpl_final(self._grupos_atuais, lote_id=lote_id)
        job = PrintJob(
            zpl_content=zpl_final,
            printer_name=impressora,
            job_name=f"Lote-{lote_id}",
        )
        self.worker.submit(job)
        self.log_status("info", f"Lote {lote_id} enviado para fila de impressao.")
