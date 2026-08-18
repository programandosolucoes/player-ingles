#!/usr/bin/env python3
"""Player de Inglês — janela única, maximizada.

Três modos, um player só:

  AULAS   — o currículo gera aula atrás de aula, sem fim, e a playlist toca
  LIVROS  — audiobook ou aula de 4 passos feita do livro selecionado
  MP3     — toca arquivos que já existem no disco

Em qualquer modo a playlist anda sozinha e continua sendo abastecida
enquanto você ouve.
"""
from __future__ import annotations

import os
import threading
import time
import traceback

import FreeSimpleGUI as sg

import biblioteca
import curriculo
import nucleo
import player as pl

sg.theme("DarkGrey13")

FUNDO = "#12161c"
CARTAO = "#1b222c"
DESTAQUE = "#2e7d32"
AZUL = "#1f6aa5"

MODOS = ["AULAS — geradas sem parar", "LIVROS — audiobook ou aula", "MP3 — arquivos do disco"]
TIPOS_LIVRO = (("Livros e textos", "*.epub *.txt *.srt *.vtt"), ("Todos", "*.*"))
TIPOS_MP3 = (("Áudio", "*.mp3 *.m4a *.wav *.ogg *.flac"), ("Todos", "*.*"))


class App:
    def __init__(self):
        self.player = pl.Player(ao_mudar=self._faixa_mudou)
        self.lib = biblioteca.Biblioteca(ao_pronta=self._aula_pronta,
                                         ao_status=self._status_thread)
        self.janela: sg.Window | None = None
        self.livros: list[str] = []
        self.log: list[str] = []
        self.gerando_livro = False
        self._ultimo_titulo = ""
        self._seek_em = 0.0

    # ------------------------------------------------------------ layout

    def montar(self) -> sg.Window:
        vozes_en, vozes_pt = nucleo.listar_vozes()
        v_en = "en-US-AndrewMultilingualNeural"
        v_pt = "pt-BR-AntonioNeural"

        cab = [[
            sg.Text("PLAYER DE INGLÊS", font=("Any", 20, "bold"), text_color="#7fb3ff"),
            sg.Text("·", font=("Any", 20), text_color="#3a4553"),
            sg.Text("a playlist toca e se regenera sozinha",
                    font=("Any", 11), text_color="#8a97a8"),
            sg.Push(),
            sg.Text("", key="-ESPACO-", font=("Any", 10), text_color="#8a97a8"),
        ]]

        # ---- coluna esquerda: modo e fonte
        modo = [
            [sg.Text("MODO DE OPERAÇÃO", font=("Any", 10, "bold"), text_color="#7fb3ff")],
            [sg.Combo(MODOS, default_value=MODOS[0], key="-MODO-", readonly=True,
                      size=(34, 1), enable_events=True, font=("Any", 11))],
        ]

        painel_aulas = [
            [sg.Text("Frases por aula"),
             sg.Spin([6, 8, 10, 12, 15, 20, 25, 30], initial_value=12, size=(4, 1),
                     key="-QTD-"),
             sg.Text("   Folga"),
             sg.Spin([1, 2, 3, 4, 5], initial_value=2, size=(3, 1), key="-FOLGA-",
                     tooltip="Quantas aulas manter prontas à frente")],
            [sg.Text(f"{len(curriculo.TOPICOS)} tópicos × {len(curriculo.TEMAS)} temas",
                     text_color="#8a97a8", font=("Any", 9))],
            [sg.Text("Próxima no currículo: —", key="-POS-", text_color="#8a97a8",
                     font=("Any", 9))],
        ]

        painel_livros = [
            [sg.Listbox([], size=(38, 5), key="-LIVROS-", no_scrollbar=False,
                        background_color=CARTAO, text_color="#d7dde5")],
            [sg.Input(key="-ADDLIVRO-", visible=False, enable_events=True),
             sg.FilesBrowse("Adicionar livros…", file_types=TIPOS_LIVRO,
                            target="-ADDLIVRO-", size=(16, 1)),
             sg.Button("Remover", key="-DELLIVRO-", size=(9, 1))],
            [sg.Radio("Audiobook (só inglês)", "LIVRO", key="-LIVRO_AB-",
                      default=True, enable_events=True)],
            [sg.Radio("Virar aula (4 passos)", "LIVRO", key="-LIVRO_AULA-",
                      enable_events=True)],
            [sg.Text("Palavras por frase"),
             sg.Spin(list(range(3, 21)), initial_value=4, size=(3, 1), key="-LMIN-"),
             sg.Text("a"),
             sg.Spin(list(range(4, 31)), initial_value=12, size=(3, 1), key="-LMAX-")],
        ]

        painel_mp3 = [
            [sg.Input(key="-ADDMP3-", visible=False, enable_events=True),
             sg.FilesBrowse("Adicionar arquivos…", file_types=TIPOS_MP3,
                            target="-ADDMP3-", size=(18, 1)),
             sg.Input(key="-ADDPASTA-", visible=False, enable_events=True),
             sg.FolderBrowse("Pasta inteira…", target="-ADDPASTA-", size=(14, 1))],
            [sg.Text("Os arquivos entram direto na playlist.",
                     text_color="#8a97a8", font=("Any", 9))],
        ]

        voz = [
            [sg.Text("Voz inglês", size=(11, 1)),
             sg.Combo(vozes_en, default_value=v_en if v_en in vozes_en else vozes_en[0],
                      key="-VOZEN-", readonly=True, size=(30, 1))],
            [sg.Text("Voz português", size=(11, 1)),
             sg.Combo(vozes_pt, default_value=v_pt if v_pt in vozes_pt else vozes_pt[0],
                      key="-VOZPT-", readonly=True, size=(30, 1))],
            [sg.Text("Inglês devagar", size=(11, 1)),
             sg.Combo(["-40%", "-30%", "-25%", "-20%", "-10%", "+0%"],
                      default_value="-30%", key="-LENTO-", readonly=True, size=(7, 1)),
             sg.Text("Pausa"),
             sg.Spin([round(x * 0.1, 1) for x in range(0, 21)], initial_value=0.6,
                     size=(4, 1), key="-PAUSA-")],
        ]

        esquerda = [
            [sg.Frame("", modo, background_color=FUNDO, border_width=0, expand_x=True)],
            [sg.pin(sg.Frame("Aulas", painel_aulas, key="-P_AULAS-", expand_x=True))],
            [sg.pin(sg.Frame("Livros selecionados", painel_livros, key="-P_LIVROS-",
                             visible=False, expand_x=True))],
            [sg.pin(sg.Frame("Arquivos", painel_mp3, key="-P_MP3-",
                             visible=False, expand_x=True))],
            [sg.Frame("Voz", voz, expand_x=True)],
            [sg.Button("▶  INICIAR", key="-INICIAR-", size=(17, 2),
                       button_color=("white", DESTAQUE), font=("Any", 12, "bold")),
             sg.Button("■  PARAR", key="-PARARGER-", size=(13, 2),
                       button_color=("white", "#8a3a2a"), font=("Any", 12, "bold"))],
        ]

        # ---- coluna direita: playlist
        direita = [
            [sg.Text("PLAYLIST", font=("Any", 10, "bold"), text_color="#7fb3ff"),
             sg.Push(),
             sg.Text("", key="-CONTA-", text_color="#8a97a8", font=("Any", 9))],
            [sg.Table(values=[], headings=["", "Faixa", "Origem"],
                      col_widths=[3, 62, 9], auto_size_columns=False,
                      justification="left", num_rows=17, key="-PLAY-",
                      enable_events=True, expand_x=True, expand_y=True,
                      background_color=CARTAO, alternating_row_color="#222a35",
                      text_color="#d7dde5", header_background_color="#2a3340",
                      selected_row_colors=("white", AZUL),
                      select_mode=sg.TABLE_SELECT_MODE_BROWSE)],
            [sg.Button("Tocar selecionada", key="-TOCARSEL-"),
             sg.Button("Remover", key="-REMOVER-"),
             sg.Button("Limpar playlist", key="-LIMPAR-"),
             sg.Push(),
             sg.Checkbox("repetir do início no fim", default=True, key="-REPETIR-",
                         enable_events=True)],
        ]

        # ---- rodapé: transporte
        transporte = [
            [sg.Text("—", key="-AGORA-", font=("Any", 14, "bold"),
                     text_color="#d7dde5", expand_x=True)],
            [sg.Text("0:00", key="-POSICAO-", size=(6, 1), font=("Any", 10)),
             sg.Slider((0, 1000), 0, orientation="h", key="-SEEK-", expand_x=True,
                       disable_number_display=True, enable_events=True,
                       trough_color="#2a3340", size=(10, 16)),
             sg.Text("0:00", key="-DURACAO-", size=(6, 1), font=("Any", 10))],
            [sg.Button("⏮", key="-ANT-", size=(5, 1), font=("Any", 14)),
             sg.Button("▶  PLAY", key="-PLAYPAUSE-", size=(14, 1),
                       font=("Any", 13, "bold"), button_color=("white", DESTAQUE)),
             sg.Button("⏭", key="-PROX-", size=(5, 1), font=("Any", 14)),
             sg.Text("   Volume"),
             sg.Slider((0, 100), 90, orientation="h", key="-VOL-", size=(16, 14),
                       disable_number_display=True, enable_events=True,
                       trough_color="#2a3340"),
             sg.Push(),
             sg.Text("", key="-GERSTATUS-", text_color="#9ad29a", font=("Any", 10))],
        ]

        layout = [
            cab,
            [sg.HorizontalSeparator()],
            [sg.Column(esquerda, vertical_alignment="top", pad=(6, 6)),
             sg.VerticalSeparator(),
             sg.Column(direita, expand_x=True, expand_y=True, pad=(6, 6))],
            [sg.Frame("", transporte, expand_x=True, border_width=0,
                      background_color=FUNDO)],
            [sg.Multiline("", key="-LOG-", size=(100, 4), disabled=True,
                          background_color="#0d1116", text_color="#8a97a8",
                          font=("Monospace", 9), expand_x=True, no_scrollbar=False)],
        ]

        janela = sg.Window("Player de Inglês", layout, finalize=True,
                           resizable=False, background_color=FUNDO,
                           return_keyboard_events=False)
        janela.maximize()
        return janela

    # ------------------------------------------------------- callbacks

    def _faixa_mudou(self, faixa: pl.Faixa, i: int) -> None:
        if self.janela:
            self.janela.write_event_value("-MUDOU-", (faixa.titulo, i))

    def _aula_pronta(self, faixa: pl.Faixa) -> None:
        if self.janela:
            self.janela.write_event_value("-NOVA-", faixa)

    def _status_thread(self, txt: str) -> None:
        if self.janela:
            self.janela.write_event_value("-GER-", txt)

    def _registrar(self, txt: str) -> None:
        self.log.append(txt)
        del self.log[:-200]

    # ------------------------------------------------------ modo/fonte

    def _modo(self, valores) -> int:
        return MODOS.index(valores["-MODO-"])

    def _trocar_painel(self, idx: int) -> None:
        self.janela["-P_AULAS-"].update(visible=idx == 0)
        self.janela["-P_LIVROS-"].update(visible=idx == 1)
        self.janela["-P_MP3-"].update(visible=idx == 2)

    def _faltando(self) -> int:
        """Faixas de aula ainda não tocadas — o gerador usa para saber se corre."""
        with self.player._lock:
            return sum(1 for i, f in enumerate(self.player.fila)
                       if i > self.player.indice and f.origem in ("aula", "livro"))

    # --------------------------------------------------------- ações

    def _iniciar(self, val) -> None:
        idx = self._modo(val)
        self.lib.voz_en = val["-VOZEN-"]
        self.lib.voz_pt = val["-VOZPT-"]
        self.lib.lento = val["-LENTO-"]
        self.lib.pausa = float(val["-PAUSA-"])
        self.lib.frases_por_aula = int(val["-QTD-"])
        self.lib.folga = int(val["-FOLGA-"])

        if idx == 0:
            self.lib.iniciar_auto(self._faltando)
            self._registrar("Gerador de aulas ligado — a playlist não vai secar.")
            existentes = biblioteca.Biblioteca.em_disco()
            if existentes and not self.player.fila:
                self.player.enfileirar(existentes, tocar_agora=True)
                self._registrar(f"{len(existentes)} aulas de sessões anteriores na fila.")
        elif idx == 1:
            if not self.livros:
                self._registrar("Nenhum livro selecionado. Use 'Adicionar livros…'.")
                return
            self._iniciar_livros(val)
        else:
            if not self.player.fila:
                self._registrar("Playlist vazia. Use 'Adicionar arquivos…'.")
                return
            self.player.tocar()

    def _iniciar_livros(self, val) -> None:
        if self.gerando_livro:
            self._registrar("Já estou processando os livros.")
            return
        self.gerando_livro = True
        audiobook = bool(val["-LIVRO_AB-"])
        lmin, lmax = int(val["-LMIN-"]), int(val["-LMAX-"])
        cfg = dict(voz_en=val["-VOZEN-"], voz_pt=val["-VOZPT-"],
                   lento=val["-LENTO-"], pausa=float(val["-PAUSA-"]))
        livros = list(self.livros)
        por_faixa = int(val["-QTD-"])

        def trabalho():
            try:
                for caminho in livros:
                    nome = os.path.splitext(os.path.basename(caminho))[0]
                    self._status_thread(f"Lendo {nome}…")
                    brutas = nucleo.de_arquivo(caminho)
                    frases = nucleo.filtrar(brutas, lmin, lmax)
                    if not frases:
                        self._status_thread(f"{nome}: nada passou no filtro.")
                        continue
                    self._status_thread(f"{nome}: {len(frases)} frases de {len(brutas)}")

                    for bloco in range(0, len(frases), por_faixa):
                        pedaco = frases[bloco:bloco + por_faixa]
                        rotulo = f"{nome} — parte {bloco // por_faixa + 1}"
                        destino = os.path.join(
                            biblioteca.PASTA,
                            f"livro_{abs(hash(rotulo)) % 10**10}.mp3")

                        if os.path.exists(destino) and os.path.getsize(destino) > 2000:
                            self._aula_pronta(pl.Faixa(destino, rotulo, "livro"))
                            continue

                        if audiobook:
                            itens = [{"en": f, "pt": ""} for f in pedaco]
                            self._status_thread(f"Narrando {rotulo}…")
                            nucleo.gerar_audiobook(itens, destino,
                                                   voz_en=cfg["voz_en"],
                                                   pausa=cfg["pausa"])
                        else:
                            itens = []
                            for n, f in enumerate(pedaco, 1):
                                try:
                                    ptx, _ = nucleo.traduzir(f)
                                except Exception:
                                    ptx = ""
                                if ptx:
                                    itens.append({"en": f, "pt": ptx})
                                self._status_thread(
                                    f"{rotulo}: traduzindo {n}/{len(pedaco)}")
                            if not itens:
                                continue
                            nucleo.gerar_mp3(itens, destino, **cfg)

                        self._aula_pronta(pl.Faixa(destino, rotulo, "livro"))
                self._status_thread("Livros processados.")
            except Exception as e:
                self._status_thread(f"Erro nos livros: {type(e).__name__}: {e}")
                self._registrar(traceback.format_exc()[-400:])
            finally:
                self.gerando_livro = False

        threading.Thread(target=trabalho, daemon=True).start()
        self._registrar(f"Processando {len(livros)} livro(s) em segundo plano.")

    # ------------------------------------------------------- desenhar

    def _pintar(self, val) -> None:
        """Redesenha a janela inteira — estado do player, playlist e rodapé."""
        j = self.janela
        p = self.player

        atual = p.atual
        titulo = atual.titulo if atual else "—"
        j["-AGORA-"].update(titulo)
        j["-PLAYPAUSE-"].update("⏸  PAUSE" if p.tocando else "▶  PLAY",
                                button_color=("white", "#8a6a2a" if p.tocando else DESTAQUE))

        dur, pos = p.duracao, p.posicao
        j["-POSICAO-"].update(pl.mmss(pos))
        j["-DURACAO-"].update(pl.mmss(dur))
        # não mexe no slider por 1,2s depois que o usuário arrastou,
        # senão o valor volta sozinho no meio do gesto
        if dur > 0 and time.time() - self._seek_em > 1.2:
            j["-SEEK-"].update(int(1000 * pos / dur))

        linhas = []
        with p._lock:
            for i, f in enumerate(p.fila):
                marca = "▶" if i == p.indice else ""
                linhas.append([marca, f.titulo, f.origem])
            idx_atual = p.indice
        j["-PLAY-"].update(values=linhas)
        j["-CONTA-"].update(f"{len(linhas)} faixas · tocando {idx_atual + 1 if idx_atual >= 0 else 0}")
        j["-POS-"].update(f"Próxima no currículo: {self.lib.proxima_posicao + 1}")
        j["-ESPACO-"].update(f"cache: {biblioteca.Biblioteca.espaco_usado()}")
        j["-LIVROS-"].update([os.path.basename(x) for x in self.livros])
        j["-LOG-"].update("\n".join(self.log[-40:]))

    # --------------------------------------------------------- laço

    def rodar(self) -> None:
        self.janela = self.montar()
        self._registrar("Pronto. Escolha o modo e clique em INICIAR.")
        self._pintar({})
        ultimo_titulo = ""

        while True:
            ev, val = self.janela.read(timeout=350)
            if ev in (sg.WIN_CLOSED, None):
                break

            try:
                if ev == "-MODO-":
                    self._trocar_painel(self._modo(val))

                elif ev == "-INICIAR-":
                    self._iniciar(val)

                elif ev == "-PARARGER-":
                    self.lib.parar_auto()
                    self._registrar("Gerador desligado. A playlist atual continua.")

                elif ev == "-PLAYPAUSE-":
                    self.player.alternar()

                elif ev == "-PROX-":
                    self.player.proxima()

                elif ev == "-ANT-":
                    self.player.anterior()

                elif ev == "-SEEK-":
                    self._seek_em = time.time()
                    dur = self.player.duracao
                    if dur > 0:
                        self.player.buscar(dur * float(val["-SEEK-"]) / 1000.0)

                elif ev == "-VOL-":
                    self.player.set_volume(float(val["-VOL-"]) / 100.0)

                elif ev == "-REPETIR-":
                    self.player.repetir_fila = bool(val["-REPETIR-"])

                elif ev == "-TOCARSEL-":
                    sel = val.get("-PLAY-") or []
                    if sel:
                        self.player.tocar_indice(sel[0])

                elif ev == "-PLAY-":
                    sel = val.get("-PLAY-") or []
                    if sel:
                        self.player.tocar_indice(sel[0])

                elif ev == "-REMOVER-":
                    sel = val.get("-PLAY-") or []
                    if sel:
                        self.player.remover(sel[0])

                elif ev == "-LIMPAR-":
                    self.player.limpar()
                    self._registrar("Playlist limpa.")

                elif ev == "-ADDLIVRO-" and val["-ADDLIVRO-"]:
                    novos = [x for x in val["-ADDLIVRO-"].split(";") if x]
                    self.livros += [x for x in novos if x not in self.livros]
                    self.janela["-ADDLIVRO-"].update("")
                    self._registrar(f"{len(novos)} livro(s) adicionado(s).")

                elif ev == "-DELLIVRO-":
                    sel = val.get("-LIVROS-") or []
                    if sel:
                        self.livros = [x for x in self.livros
                                       if os.path.basename(x) != sel[0]]

                elif ev == "-ADDMP3-" and val["-ADDMP3-"]:
                    arquivos = [x for x in val["-ADDMP3-"].split(";") if x]
                    self.player.enfileirar(
                        [pl.Faixa(a, os.path.basename(a), "mp3") for a in arquivos],
                        tocar_agora=True)
                    self.janela["-ADDMP3-"].update("")
                    self._registrar(f"{len(arquivos)} arquivo(s) na playlist.")

                elif ev == "-ADDPASTA-" and val["-ADDPASTA-"]:
                    pasta = val["-ADDPASTA-"]
                    achados = sorted(
                        os.path.join(pasta, f) for f in os.listdir(pasta)
                        if f.lower().endswith((".mp3", ".m4a", ".wav", ".ogg", ".flac")))
                    self.player.enfileirar(
                        [pl.Faixa(a, os.path.basename(a), "mp3") for a in achados],
                        tocar_agora=True)
                    self.janela["-ADDPASTA-"].update("")
                    self._registrar(f"{len(achados)} arquivo(s) da pasta.")

                # ---- eventos das threads
                elif ev == "-NOVA-":
                    faixa = val[ev]
                    self.player.enfileirar([faixa], tocar_agora=True)
                    self._registrar(f"+ {faixa.titulo}")

                elif ev == "-GER-":
                    self.janela["-GERSTATUS-"].update(val[ev])

                elif ev == "-MUDOU-":
                    titulo, i = val[ev]
                    if titulo != ultimo_titulo:
                        self._registrar(f"♪ {titulo}")
                        ultimo_titulo = titulo

                self._pintar(val)

            except Exception as e:
                self._registrar(f"ERRO {type(e).__name__}: {e}")

        self.lib.parar_auto()
        self.player.encerrar()
        self.janela.close()


if __name__ == "__main__":
    App().rodar()
