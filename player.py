#!/usr/bin/env python3
"""Motor de reprodução — fila, play/pause, avanço automático.

Em cima do just_playback, que dá pause e seek de verdade (parar e recomeçar
do zero não serve para aula de 20 minutos).

O avanço para a próxima faixa roda numa thread própria: o player não avisa
quando termina, então alguém precisa vigiar.
"""
from __future__ import annotations

import os
import threading
import time

from just_playback import Playback


class Faixa:
    def __init__(self, caminho: str, titulo: str = "", origem: str = ""):
        self.caminho = caminho
        self.titulo = titulo or os.path.basename(caminho)
        self.origem = origem          # "aula", "livro" ou "mp3"

    def __repr__(self):
        return f"<Faixa {self.titulo!r}>"


class Player:
    """Fila com reprodução contínua.

    ao_mudar(faixa, indice) é chamado quando a faixa troca.
    """

    def __init__(self, ao_mudar=None):
        self._p = Playback()
        self.fila: list[Faixa] = []
        self.indice = -1
        self.ao_mudar = ao_mudar
        self.repetir_fila = True
        self._parar = threading.Event()
        self._lock = threading.RLock()
        self._vigia = threading.Thread(target=self._vigiar, daemon=True)
        self._vigia.start()

    # ------------------------------------------------------------- fila

    def enfileirar(self, faixas: list[Faixa], tocar_agora=False) -> None:
        with self._lock:
            vazia = not self.fila
            self.fila.extend(faixas)
        if (vazia and tocar_agora) or (tocar_agora and self.indice < 0):
            self.tocar_indice(0)

    def limpar(self) -> None:
        with self._lock:
            self.parar()
            self.fila.clear()
            self.indice = -1

    def remover(self, i: int) -> None:
        with self._lock:
            if not (0 <= i < len(self.fila)):
                return
            tocando = i == self.indice
            self.fila.pop(i)
            if i < self.indice:
                self.indice -= 1
            if tocando:
                self.indice -= 1
                self.proxima()

    @property
    def atual(self) -> Faixa | None:
        with self._lock:
            if 0 <= self.indice < len(self.fila):
                return self.fila[self.indice]
        return None

    # ---------------------------------------------------------- controle

    def tocar_indice(self, i: int) -> bool:
        with self._lock:
            if not (0 <= i < len(self.fila)):
                return False
            faixa = self.fila[i]
            if not os.path.exists(faixa.caminho):
                return False
            try:
                self._p.stop()
                self._p.load_file(faixa.caminho)
                self._p.play()
                self.indice = i
            except Exception:
                return False
        if self.ao_mudar:
            self.ao_mudar(faixa, i)
        return True

    def tocar(self) -> None:
        """Play — retoma se pausado, começa a fila se parado."""
        with self._lock:
            if self._p.active and self._p.paused:
                self._p.resume()
            elif not self._p.active and self.fila:
                self.tocar_indice(max(self.indice, 0))

    def pausar(self) -> None:
        with self._lock:
            if self._p.playing:
                self._p.pause()

    def alternar(self) -> None:
        """O botão único de play/pause."""
        with self._lock:
            if self._p.playing:
                self._p.pause()
            else:
                self.tocar()

    def parar(self) -> None:
        with self._lock:
            try:
                self._p.stop()
            except Exception:
                pass

    def proxima(self) -> bool:
        with self._lock:
            prox = self.indice + 1
            if prox >= len(self.fila):
                if not self.repetir_fila or not self.fila:
                    self.parar()
                    return False
                prox = 0
            return self.tocar_indice(prox)

    def anterior(self) -> bool:
        with self._lock:
            # menos de 3s tocando volta a faixa; depois disso, reinicia a atual
            if self.posicao > 3:
                return self.tocar_indice(self.indice)
            return self.tocar_indice(max(self.indice - 1, 0))

    def buscar(self, segundos: float) -> None:
        with self._lock:
            if self._p.active:
                self._p.seek(max(0.0, min(segundos, self.duracao)))

    # ----------------------------------------------------------- estado

    @property
    def tocando(self) -> bool:
        return bool(self._p.playing)

    @property
    def ativo(self) -> bool:
        return bool(self._p.active)

    @property
    def posicao(self) -> float:
        try:
            return float(self._p.curr_pos)
        except Exception:
            return 0.0

    @property
    def duracao(self) -> float:
        try:
            return float(self._p.duration)
        except Exception:
            return 0.0

    @property
    def volume(self) -> float:
        try:
            return float(self._p.volume)
        except Exception:
            return 1.0

    def set_volume(self, v: float) -> None:
        try:
            self._p.set_volume(max(0.0, min(1.0, v)))
        except Exception:
            pass

    # ------------------------------------------------------------ vigia

    def _vigiar(self) -> None:
        """Detecta fim de faixa e emenda a próxima."""
        while not self._parar.is_set():
            time.sleep(0.4)
            try:
                with self._lock:
                    acabou = (self.indice >= 0 and not self._p.active
                              and not self._p.paused and self.fila)
                if acabou:
                    self.proxima()
            except Exception:
                pass

    def encerrar(self) -> None:
        self._parar.set()
        self.parar()


def mmss(seg: float) -> str:
    seg = max(0, int(seg or 0))
    return f"{seg // 60:d}:{seg % 60:02d}"
