#!/usr/bin/env python3
"""Conjugador de português — só o que a lição precisa.

Cobre presente, pretérito perfeito, gerúndio e particípio nas seis pessoas
que aparecem nas frases. Regulares saem por regra; o resto vem da tabela.

Sem isso a lição gera "Eles entra na reunião" — erro que passa despercebido
porque a frase em inglês fica certa.
"""
from __future__ import annotations

PESSOAS = ("eu", "voce", "ele", "ela", "nos", "eles")

# irregulares e os que a regra erraria (ortografia: -car, -gar, -guir…)
IRREGULARES = {
    "ler": {
        "presente": ("leio", "lê", "lê", "lê", "lemos", "leem"),
        "passado": ("li", "leu", "leu", "leu", "lemos", "leram"),
        "gerundio": "lendo", "participio": "lido",
    },
    "dirigir": {
        "presente": ("dirijo", "dirige", "dirige", "dirige", "dirigimos", "dirigem"),
        "passado": ("dirigi", "dirigiu", "dirigiu", "dirigiu", "dirigimos", "dirigiram"),
        "gerundio": "dirigindo", "participio": "dirigido",
    },
    "verificar": {
        "presente": ("verifico", "verifica", "verifica", "verifica", "verificamos", "verificam"),
        "passado": ("verifiquei", "verificou", "verificou", "verificou", "verificamos", "verificaram"),
        "gerundio": "verificando", "participio": "verificado",
    },
    "ligar": {
        "presente": ("ligo", "liga", "liga", "liga", "ligamos", "ligam"),
        "passado": ("liguei", "ligou", "ligou", "ligou", "ligamos", "ligaram"),
        "gerundio": "ligando", "participio": "ligado",
    },
    "comer": {
        "presente": ("como", "come", "come", "come", "comemos", "comem"),
        "passado": ("comi", "comeu", "comeu", "comeu", "comemos", "comeram"),
        "gerundio": "comendo", "participio": "comido",
    },
    "beber": {
        "presente": ("bebo", "bebe", "bebe", "bebe", "bebemos", "bebem"),
        "passado": ("bebi", "bebeu", "bebeu", "bebeu", "bebemos", "beberam"),
        "gerundio": "bebendo", "participio": "bebido",
    },
    "subir": {
        "presente": ("subo", "sobe", "sobe", "sobe", "subimos", "sobem"),
        "passado": ("subi", "subiu", "subiu", "subiu", "subimos", "subiram"),
        "gerundio": "subindo", "participio": "subido",
    },
    "sair": {
        "presente": ("saio", "sai", "sai", "sai", "saímos", "saem"),
        "passado": ("saí", "saiu", "saiu", "saiu", "saímos", "saíram"),
        "gerundio": "saindo", "participio": "saído",
    },
}

_TERM = {
    "ar": {"presente": ("o", "a", "a", "a", "amos", "am"),
           "passado": ("ei", "ou", "ou", "ou", "amos", "aram"),
           "gerundio": "ando", "participio": "ado"},
    "er": {"presente": ("o", "e", "e", "e", "emos", "em"),
           "passado": ("i", "eu", "eu", "eu", "emos", "eram"),
           "gerundio": "endo", "participio": "ido"},
    "ir": {"presente": ("o", "e", "e", "e", "imos", "em"),
           "passado": ("i", "iu", "iu", "iu", "imos", "iram"),
           "gerundio": "indo", "participio": "ido"},
}


def _idx(pessoa: str) -> int:
    return PESSOAS.index(pessoa)


def conjugar(infinitivo: str, tempo: str, pessoa: str = "eu") -> str:
    """tempo: presente | passado | gerundio | participio"""
    inf = infinitivo.lower().strip()
    tabela = IRREGULARES.get(inf)
    if tabela:
        v = tabela[tempo]
        return v if isinstance(v, str) else v[_idx(pessoa)]

    term = inf[-2:]
    if term not in _TERM:
        raise ValueError(f"não sei conjugar {infinitivo!r}")
    raiz, regra = inf[:-2], _TERM[term]
    v = regra[tempo]
    return raiz + (v if isinstance(v, str) else v[_idx(pessoa)])


# auxiliares que aparecem nas estruturas
AUX = {
    "estar": {"eu": "estou", "voce": "está", "ele": "está", "ela": "está",
              "nos": "estamos", "eles": "estão"},
    "ter": {"eu": "tenho", "voce": "tem", "ele": "tem", "ela": "tem",
            "nos": "temos", "eles": "têm"},
    "ir": {"eu": "vou", "voce": "vai", "ele": "vai", "ela": "vai",
           "nos": "vamos", "eles": "vão"},
    "poder": {"eu": "posso", "voce": "pode", "ele": "pode", "ela": "pode",
              "nos": "podemos", "eles": "podem"},
    "dever": {"eu": "deveria", "voce": "deveria", "ele": "deveria",
              "ela": "deveria", "nos": "deveríamos", "eles": "deveriam"},
}


if __name__ == "__main__":
    for inf in ("trabalhar", "entrar", "ler", "subir", "comer", "dirigir"):
        pres = "/".join(conjugar(inf, "presente", p) for p in PESSOAS)
        pas = "/".join(conjugar(inf, "passado", p) for p in PESSOAS)
        print(f"{inf:<11} presente: {pres}")
        print(f"{'':<11} passado : {pas}")
