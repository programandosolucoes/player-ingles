#!/usr/bin/env python3
"""Produz aulas à frente do que está tocando e guarda em disco.

O player nunca pode ficar sem faixa. Uma thread fica gerando enquanto o
usuário ouve, mantendo uma folga configurável de aulas prontas.

MP3 já gerado é reaproveitado: o nome do arquivo é o hash do conteúdo da
aula, então mesma aula = mesmo arquivo = geração instantânea na segunda vez.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
import time

import curriculo
import nucleo
from player import Faixa

PASTA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "aulas")
os.makedirs(PASTA, exist_ok=True)


def _chave(aula: dict, voz_en: str, voz_pt: str, lento: str, pausa: float) -> str:
    corpo = json.dumps(
        {"f": aula["frases"], "en": voz_en, "pt": voz_pt, "l": lento, "p": pausa},
        ensure_ascii=False, sort_keys=True)
    return hashlib.sha1(corpo.encode()).hexdigest()[:16]


class Biblioteca:
    """Fábrica de faixas.

    ao_pronta(faixa)  — chamada quando uma aula fica pronta
    ao_status(texto)  — progresso legível
    """

    def __init__(self, ao_pronta=None, ao_status=None):
        self.ao_pronta = ao_pronta
        self.ao_status = ao_status
        self.voz_en = "en-US-AndrewMultilingualNeural"
        self.voz_pt = "pt-BR-AntonioNeural"
        self.lento = "-30%"
        self.pausa = 0.6
        self.frases_por_aula = 12
        self.folga = 2            # quantas aulas prontas manter à frente
        self._n = 0               # posição no currículo
        self._parar = threading.Event()
        self._rodando = False
        self._thread: threading.Thread | None = None
        self._pendentes = 0

    # ---------------------------------------------------------- geração

    def _msg(self, txt: str) -> None:
        if self.ao_status:
            self.ao_status(txt)

    def gerar_uma(self, n: int | None = None) -> Faixa | None:
        """Gera (ou reaproveita) a aula de índice n do currículo."""
        n = self._n if n is None else n
        topico = n % len(curriculo.TOPICOS)
        tema = curriculo.TEMAS[(n // len(curriculo.TOPICOS)) % len(curriculo.TEMAS)]
        aula = curriculo.montar_aula(topico, tema, self.frases_por_aula,
                                     semente=f"auto|{n}")

        chave = _chave(aula, self.voz_en, self.voz_pt, self.lento, self.pausa)
        destino = os.path.join(PASTA, f"{chave}.mp3")
        rotulo = f"Aula {n + 1:03d} — {aula['titulo']}"

        if os.path.exists(destino) and os.path.getsize(destino) > 2000:
            self._msg(f"Reaproveitada: {rotulo}")
            return Faixa(destino, rotulo, "aula")

        self._msg(f"Gerando: {rotulo}")
        try:
            nucleo.gerar_mp3(
                aula["frases"], destino,
                voz_en=self.voz_en, voz_pt=self.voz_pt,
                lento=self.lento, pausa=self.pausa,
                progresso=lambda i, t, f: self._msg(
                    f"Gerando {rotulo} — {i}/{t}"),
                cancelado=lambda: self._parar.is_set())
        except InterruptedError:
            return None
        except Exception as e:
            self._msg(f"Falhou {rotulo}: {type(e).__name__}")
            return None

        # roteiro ao lado do áudio, para conferir depois
        with open(destino.replace(".mp3", ".json"), "w", encoding="utf-8") as fh:
            json.dump(aula, fh, ensure_ascii=False, indent=1)

        self._msg(f"Pronta: {rotulo}")
        return Faixa(destino, rotulo, "aula")

    # -------------------------------------------------------- automático

    def iniciar_auto(self, faltando) -> None:
        """faltando() -> quantas faixas de aula ainda não tocadas existem na fila."""
        if self._rodando:
            return
        self._parar.clear()
        self._rodando = True

        def laco():
            while not self._parar.is_set():
                try:
                    if faltando() < self.folga:
                        faixa = self.gerar_uma()
                        self._n += 1
                        if faixa and self.ao_pronta and not self._parar.is_set():
                            self.ao_pronta(faixa)
                    else:
                        time.sleep(1.0)
                except Exception as e:
                    self._msg(f"Erro no gerador: {type(e).__name__}")
                    time.sleep(3.0)
            self._rodando = False

        self._thread = threading.Thread(target=laco, daemon=True)
        self._thread.start()

    def parar_auto(self) -> None:
        self._parar.set()

    @property
    def rodando(self) -> bool:
        return self._rodando

    @property
    def proxima_posicao(self) -> int:
        return self._n

    def reiniciar_curriculo(self) -> None:
        self._n = 0

    # ------------------------------------------------------------ disco

    @staticmethod
    def em_disco() -> list[Faixa]:
        """Aulas já geradas em sessões anteriores."""
        saida = []
        for nome in sorted(os.listdir(PASTA)):
            if not nome.endswith(".mp3"):
                continue
            caminho = os.path.join(PASTA, nome)
            roteiro = caminho.replace(".mp3", ".json")
            titulo = nome
            if os.path.exists(roteiro):
                try:
                    with open(roteiro, encoding="utf-8") as fh:
                        titulo = json.load(fh).get("titulo", nome)
                except Exception:
                    pass
            saida.append(Faixa(caminho, titulo, "aula"))
        return saida

    @staticmethod
    def espaco_usado() -> str:
        total = sum(os.path.getsize(os.path.join(PASTA, f))
                    for f in os.listdir(PASTA)
                    if os.path.isfile(os.path.join(PASTA, f)))
        return f"{total / 1_048_576:.0f} MB"
