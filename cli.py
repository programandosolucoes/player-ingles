#!/usr/bin/env python3
"""Mesmo motor do app, pela linha de comando.

  cli.py extrair  entrada.(txt|epub|srt|vtt)  saida.json [min] [max]
  cli.py traduzir arquivo.json
  cli.py gerar    arquivo.json  saida.mp3
  cli.py tudo     entrada.srt   saida.mp3
"""
import json
import sys

import nucleo


def _ler(p):
    frases, _ = nucleo.abrir_projeto(p)
    return frases


def _gravar(p, frases):
    nucleo.salvar_projeto(p, frases, {})


def extrair(entrada, saida, minimo=4, maximo=9):
    brutas = nucleo.de_arquivo(entrada)
    cand = nucleo.filtrar(brutas, int(minimo), int(maximo))
    _gravar(saida, [{"en": c, "pt": ""} for c in cand])
    print(f"{len(brutas)} frases -> {len(cand)} aproveitadas -> {saida}")
    return cand


def traduzir(arquivo):
    frases = _ler(arquivo)
    pend = [f for f in frases if not f["pt"]]
    for n, f in enumerate(pend, 1):
        try:
            f["pt"], prov = nucleo.traduzir(f["en"])
        except Exception as e:
            prov = f"FALHOU {type(e).__name__}"
        print(f"  [{n}/{len(pend)}] {prov}: {f['pt'][:60]}")
    _gravar(arquivo, frases)
    print(f"{len(pend)} traduzidas -> {arquivo}")


def gerar(arquivo, saida):
    nucleo.gerar_mp3(_ler(arquivo), saida,
                     progresso=lambda i, t, f: print(f"  {i}/{t} {f[:50]}"))
    print(f"pronto: {saida}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    cmd, a = sys.argv[1], sys.argv[2:]
    if cmd == "extrair":
        extrair(*a)
    elif cmd == "traduzir":
        traduzir(*a)
    elif cmd == "gerar":
        gerar(*a)
    elif cmd == "tudo":
        entrada, saida = a[0], a[1]
        tmp = saida + ".json"
        extrair(entrada, tmp)
        traduzir(tmp)
        gerar(tmp, saida)
    else:
        print(__doc__)
        sys.exit(1)
