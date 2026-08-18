#!/usr/bin/env python3
"""Núcleo do gerador de lições — sem interface.

Faz três coisas:
  1. Extrai frases de texto/EPUB/SRT
  2. Traduz via API gratuita e anônima (sem chave)
  3. Gera o MP3 no padrão de 4 passos

Tudo que precisa de rede usa serviço público sem cadastro.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
import tempfile
import urllib.parse

import requests

# ---------------------------------------------------------------- extração

_FIM_FRASE = re.compile(r"(?<=[.!?])\s+")
_LIXO = re.compile(r"[_\[\]<>{}\\|]|\d{2,}")
_CAPITULO = re.compile(r"\b(CHAPTER|CAPÍTULO|PART|BOOK|VOLUME)\b", re.I)


def _limpar(txt: str) -> str:
    return re.sub(r"\s+", " ", txt).strip()


def de_texto(txt: str) -> list[str]:
    return [f.strip() for f in _FIM_FRASE.split(_limpar(txt)) if f.strip()]


def de_srt(caminho: str) -> list[str]:
    """Legenda .srt/.vtt — descarta índices e marcas de tempo."""
    with open(caminho, encoding="utf-8", errors="ignore") as fh:
        bruto = fh.read()
    linhas = []
    for l in bruto.splitlines():
        l = l.strip()
        if not l or "-->" in l or l.isdigit() or l.upper().startswith("WEBVTT"):
            continue
        linhas.append(re.sub(r"<[^>]+>", "", l))
    return de_texto(" ".join(linhas))


def de_epub(caminho: str) -> list[str]:
    from bs4 import BeautifulSoup
    from ebooklib import ITEM_DOCUMENT, epub

    livro = epub.read_epub(caminho)
    pedacos = [
        BeautifulSoup(it.get_content(), "html.parser").get_text(" ")
        for it in livro.get_items()
        if it.get_type() == ITEM_DOCUMENT
    ]
    return de_texto(" ".join(pedacos))


def de_arquivo(caminho: str) -> list[str]:
    ext = os.path.splitext(caminho)[1].lower()
    if ext == ".epub":
        return de_epub(caminho)
    if ext in (".srt", ".vtt"):
        return de_srt(caminho)
    with open(caminho, encoding="utf-8", errors="ignore") as fh:
        return de_texto(fh.read())


def filtrar(frases: list[str], minimo=4, maximo=9, so_dialogo=False) -> list[str]:
    """Peneira o que serve para o padrão de 4 passos.

    Frase de lição é curta e começa com maiúscula. Sumário, cabeçalho de
    capítulo e linha com número não servem.
    """
    saida, vistas = [], set()
    for f in frases:
        n = len(f.split())
        if not (minimo <= n <= maximo):
            continue
        if not re.match(r"^[A-Z\"“']", f):
            continue
        if _LIXO.search(f) or _CAPITULO.search(f):
            continue
        if so_dialogo and not re.search(r"[\"“”']", f):
            continue
        chave = f.lower()
        if chave in vistas:
            continue
        vistas.add(chave)
        saida.append(f)
    return saida


# ---------------------------------------------------------------- tradução

class ErroTraducao(RuntimeError):
    pass


def _google_gtx(texto: str, de="en", para="pt") -> str:
    r = requests.get(
        "https://translate.googleapis.com/translate_a/single",
        params={"client": "gtx", "sl": de, "tl": para, "dt": "t", "q": texto},
        timeout=20,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    r.raise_for_status()
    return "".join(p[0] for p in r.json()[0] if p and p[0])


def _mymemory(texto: str, de="en", para="pt-BR") -> str:
    r = requests.get(
        "https://api.mymemory.translated.net/get",
        params={"q": texto, "langpair": f"{de}|{para}"},
        timeout=20,
    )
    r.raise_for_status()
    dados = r.json()
    if dados.get("responseStatus") not in (200, "200"):
        raise ErroTraducao(str(dados.get("responseDetails"))[:120])
    return dados["responseData"]["translatedText"]


def _lingva(texto: str, de="en", para="pt") -> str:
    for host in ("lingva.ml", "translate.plausibility.cloud"):
        try:
            r = requests.get(
                f"https://{host}/api/v1/{de}/{para}/{urllib.parse.quote(texto)}",
                timeout=20,
            )
            r.raise_for_status()
            return r.json()["translation"]
        except Exception:
            continue
    raise ErroTraducao("nenhuma instância Lingva respondeu")


PROVEDORES = {
    "Google (gtx)": _google_gtx,
    "MyMemory": _mymemory,
    "Lingva": _lingva,
}
ORDEM_PADRAO = ["Google (gtx)", "MyMemory", "Lingva"]


def traduzir(texto: str, ordem: list[str] | None = None) -> tuple[str, str]:
    """Tenta os provedores em ordem. Devolve (tradução, provedor usado).

    Cair para o próximo é o comportamento normal, não exceção: serviço
    público sem chave cai e volta o tempo todo.
    """
    erros = []
    for nome in ordem or ORDEM_PADRAO:
        fn = PROVEDORES.get(nome)
        if not fn:
            continue
        try:
            out = (fn(texto) or "").strip()
            if out and out.lower() != texto.lower():
                return out, nome
            erros.append(f"{nome}: devolveu vazio/igual")
        except Exception as e:
            erros.append(f"{nome}: {type(e).__name__}")
    raise ErroTraducao(" | ".join(erros))


# ---------------------------------------------------------------- voz / TTS

VOZES_EN = [
    "en-US-AndrewMultilingualNeural",
    "en-US-BrianMultilingualNeural",
    "en-US-EmmaMultilingualNeural",
    "en-US-AvaMultilingualNeural",
    "en-US-GuyNeural",
    "en-US-JennyNeural",
    "en-GB-RyanNeural",
    "en-GB-SoniaNeural",
]
VOZES_PT = [
    "pt-BR-AntonioNeural",
    "pt-BR-FranciscaNeural",
    "pt-BR-ThalitaMultilingualNeural",
]


def listar_vozes() -> tuple[list[str], list[str]]:
    """Busca a lista viva no serviço. Cai para a lista fixa se não houver rede."""
    try:
        import edge_tts

        todas = asyncio.run(edge_tts.list_voices())
        en = sorted(v["ShortName"] for v in todas if v["Locale"].startswith("en-"))
        pt = sorted(v["ShortName"] for v in todas if v["Locale"].startswith("pt-"))
        return (en or VOZES_EN, pt or VOZES_PT)
    except Exception:
        return (VOZES_EN, VOZES_PT)


# ---------------------------------------------------------------- áudio

CONCORRENCIA = 6   # sínteses simultâneas — acima disso o serviço recusa


def _ffmpeg(args: list[str]) -> None:
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", *args], check=True)


async def _falar(texto: str, voz: str, rate: str, destino: str) -> None:
    import edge_tts

    await edge_tts.Communicate(texto, voz, rate=rate).save(destino)


def gerar_mp3(
    frases: list[dict],
    saida: str,
    voz_en=VOZES_EN[0],
    voz_pt=VOZES_PT[0],
    lento="-30%",
    pausa=0.6,
    repetir_pt_no_fim=True,
    progresso=None,
    cancelado=None,
) -> str:
    """Monta o MP3 no padrão: EN devagar -> PT -> EN normal -> [PT].

    progresso(i, total, frase) é chamado a cada frase.
    cancelado() -> True aborta.
    """
    frases = [f for f in frases if f.get("en") and f.get("pt")]
    if not frases:
        raise ValueError("nenhuma frase com inglês E português preenchidos")

    tmp = tempfile.mkdtemp(prefix="licao_")
    silencio = os.path.join(tmp, "sil.mp3")
    _ffmpeg(["-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
             "-t", str(pausa), "-q:a", "9", silencio])

    async def montar():
        # Monta o roteiro inteiro primeiro, depois sintetiza em paralelo.
        # Sequencial dava ~7s por frase; o gargalo é a ida e volta na rede,
        # não a CPU. Com 6 em voo o tempo cai para ~1,5s por frase.
        roteiro = []
        for i, f in enumerate(frases):
            passos = [
                (f["en"], voz_en, lento),
                (f["pt"], voz_pt, "+0%"),
                (f["en"], voz_en, "+0%"),
            ]
            if repetir_pt_no_fim:
                passos.append((f["pt"], voz_pt, "+0%"))
            for j, (txt, voz, rate) in enumerate(passos):
                roteiro.append((i, os.path.join(tmp, f"{i:05d}_{j}.mp3"), txt, voz, rate))

        limite = asyncio.Semaphore(CONCORRENCIA)
        feitas = [0]
        total_frases = len(frases)

        async def um(i, destino, txt, voz, rate):
            if cancelado and cancelado():
                raise InterruptedError
            async with limite:
                if cancelado and cancelado():
                    raise InterruptedError
                ultimo = None
                for tentativa in range(3):
                    try:
                        await _falar(txt, voz, rate, destino)
                        break
                    except Exception as e:      # serviço público cai; tenta de novo
                        ultimo = e
                        await asyncio.sleep(1.5 * (tentativa + 1))
                else:
                    raise RuntimeError(f"TTS falhou em {txt[:40]!r}: {ultimo}")
            if progresso and destino.endswith("_0.mp3"):
                feitas[0] += 1
                progresso(feitas[0], total_frases, txt)

        try:
            await asyncio.gather(*(um(*r) for r in roteiro))
        except InterruptedError:
            return None

        partes = []
        for _, destino, *_ in roteiro:
            partes += [destino, silencio]
        return partes

    partes = asyncio.run(montar())
    if partes is None:
        raise InterruptedError("cancelado pelo usuário")

    lista = os.path.join(tmp, "lista.txt")
    with open(lista, "w", encoding="utf-8") as fh:
        for p in partes:
            fh.write("file '%s'\n" % p.replace("'", r"'\''"))
    _ffmpeg(["-y", "-f", "concat", "-safe", "0", "-i", lista,
             "-acodec", "libmp3lame", "-q:a", "5", saida])
    return saida


# ---------------------------------------------------------------- projeto

def salvar_projeto(caminho: str, frases: list[dict], config: dict) -> None:
    with open(caminho, "w", encoding="utf-8") as fh:
        json.dump({"config": config, "frases": frases}, fh,
                  ensure_ascii=False, indent=1)


def abrir_projeto(caminho: str) -> tuple[list[dict], dict]:
    with open(caminho, encoding="utf-8") as fh:
        dados = json.load(fh)
    if isinstance(dados, list):          # formato antigo: só a lista
        return dados, {}
    return dados.get("frases", []), dados.get("config", {})


def gerar_audiobook(
    frases: list[dict],
    saida: str,
    voz_en=VOZES_EN[0],
    pausa=0.4,
    progresso=None,
    cancelado=None,
) -> str:
    """Narra o texto em inglês, direto, sem tradução e sem repetição.

    É o modo audiobook: serve para quem já entende e quer volume de escuta,
    não para quem está montando vocabulário.
    """
    itens = [f for f in frases if f.get("en")]
    if not itens:
        raise ValueError("nenhuma frase para narrar")

    tmp = tempfile.mkdtemp(prefix="audiobook_")
    silencio = os.path.join(tmp, "sil.mp3")
    _ffmpeg(["-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
             "-t", str(pausa), "-q:a", "9", silencio])

    async def montar():
        limite = asyncio.Semaphore(CONCORRENCIA)
        feitas = [0]

        async def um(i, destino, txt):
            if cancelado and cancelado():
                raise InterruptedError
            async with limite:
                ultimo = None
                for tentativa in range(3):
                    try:
                        await _falar(txt, voz_en, "+0%", destino)
                        break
                    except Exception as e:
                        ultimo = e
                        await asyncio.sleep(1.5 * (tentativa + 1))
                else:
                    raise RuntimeError(f"TTS falhou: {ultimo}")
            feitas[0] += 1
            if progresso:
                progresso(feitas[0], len(itens), txt)

        alvos = [(i, os.path.join(tmp, f"{i:05d}.mp3"), f["en"])
                 for i, f in enumerate(itens)]
        try:
            await asyncio.gather(*(um(*a) for a in alvos))
        except InterruptedError:
            return None
        partes = []
        for _, destino, _ in alvos:
            partes += [destino, silencio]
        return partes

    partes = asyncio.run(montar())
    if partes is None:
        raise InterruptedError("cancelado pelo usuário")

    lista = os.path.join(tmp, "lista.txt")
    with open(lista, "w", encoding="utf-8") as fh:
        for p in partes:
            fh.write("file '%s'\n" % p.replace("'", r"'\''"))
    _ffmpeg(["-y", "-f", "concat", "-safe", "0", "-i", lista,
             "-acodec", "libmp3lame", "-q:a", "5", saida])
    return saida
