#!/usr/bin/env python3
"""Banco de aulas — gera frases de lição sem depender de rede.

Cada tópico gramatical é uma função que combina um sujeito com um verbo.
O português sai do conjugador, não de tradução automática, então a frase
vem correta e de graça.

É assim que o vídeo original funciona: uma estrutura, muitas trocas de
verbo e complemento. A variação vem da combinação.
"""
from __future__ import annotations

import hashlib
import itertools
import random

from conjugacao import AUX, conjugar

# ------------------------------------------------------------------ vocabulário
# (base_en, 3ps_en, passado_en, particípio_en, gerúndio_en, infinitivo_pt,
#  complemento_en, complemento_pt)

VERBOS = {
    "trabalho": [
        ("check", "checks", "checked", "checked", "checking", "verificar", "the logs", "os logs"),
        ("send", "sends", "sent", "sent", "sending", "mandar", "the report", "o relatório"),
        ("fix", "fixes", "fixed", "fixed", "fixing", "consertar", "the bug", "o defeito"),
        ("join", "joins", "joined", "joined", "joining", "entrar", "the meeting", "na reunião"),
        ("review", "reviews", "reviewed", "reviewed", "reviewing", "revisar", "the code", "o código"),
        ("answer", "answers", "answered", "answered", "answering", "responder", "the client", "o cliente"),
        ("test", "tests", "tested", "tested", "testing", "testar", "everything", "tudo"),
        ("call", "calls", "called", "called", "calling", "ligar", "the support", "para o suporte"),
    ],
    "rotina": [
        ("work", "works", "worked", "worked", "working", "trabalhar", "from home", "de casa"),
        ("study", "studies", "studied", "studied", "studying", "estudar", "every day", "todos os dias"),
        ("drive", "drives", "drove", "driven", "driving", "dirigir", "to work", "para o trabalho"),
        ("cook", "cooks", "cooked", "cooked", "cooking", "cozinhar", "on weekends", "nos fins de semana"),
        ("read", "reads", "read", "read", "reading", "ler", "before bed", "antes de dormir"),
        ("run", "runs", "ran", "run", "running", "correr", "in the morning", "de manhã"),
        ("leave", "leaves", "left", "left", "leaving", "sair", "at six", "às seis"),
        ("train", "trains", "trained", "trained", "training", "treinar", "twice a week", "duas vezes por semana"),
    ],
    "casa": [
        ("clean", "cleans", "cleaned", "cleaned", "cleaning", "limpar", "the kitchen", "a cozinha"),
        ("watch", "watches", "watched", "watched", "watching", "assistir", "TV at night", "TV à noite"),
        ("drink", "drinks", "drank", "drunk", "drinking", "beber", "coffee", "café"),
        ("eat", "eats", "ate", "eaten", "eating", "comer", "lunch at noon", "almoço ao meio-dia"),
        ("buy", "buys", "bought", "bought", "buying", "comprar", "groceries", "as compras"),
        ("organize", "organizes", "organized", "organized", "organizing", "organizar", "the house", "a casa"),
    ],
}

# (en, pt, chave_de_pessoa, é_terceira_do_singular?)
SUJEITOS = [
    ("I", "Eu", "eu", False),
    ("You", "Você", "voce", False),
    ("He", "Ele", "ele", True),
    ("She", "Ela", "ela", True),
    ("We", "Nós", "nos", False),
    ("They", "Eles", "eles", False),
]


# ------------------------------------------------------------------ estruturas

def _sp_afirmativa(s, v):
    en, pt, p, terceira = s
    b, b3, _, _, _, inf, ce, cp = v
    return (f"{en} {b3 if terceira else b} {ce}.",
            f"{pt} {conjugar(inf, 'presente', p)} {cp}.")


def _sp_negativa(s, v):
    en, pt, p, terceira = s
    b, _, _, _, _, inf, ce, cp = v
    aux = "doesn't" if terceira else "don't"
    return (f"{en} {aux} {b} {ce}.",
            f"{pt} não {conjugar(inf, 'presente', p)} {cp}.")


def _sp_pergunta(s, v):
    en, pt, p, terceira = s
    b, _, _, _, _, inf, ce, cp = v
    aux = "Does" if terceira else "Do"
    return (f"{aux} {en.lower()} {b} {ce}?",
            f"{pt} {conjugar(inf, 'presente', p)} {cp}?")


def _presente_continuo(s, v):
    en, pt, p, _ = s
    _, _, _, _, ing, inf, ce, cp = v
    return (f"{en} {_be(en)} {ing} {ce}.",
            f"{pt} {AUX['estar'][p]} {conjugar(inf, 'gerundio')} {cp}.")


def _be(en_sujeito: str) -> str:
    return {"I": "am", "He": "is", "She": "is"}.get(en_sujeito, "are")


def _past_afirmativa(s, v):
    en, pt, p, _ = s
    _, _, pas, _, _, inf, ce, cp = v
    return (f"{en} {pas} {ce}.", f"{pt} {conjugar(inf, 'passado', p)} {cp}.")


def _past_negativa(s, v):
    en, pt, p, _ = s
    b, _, _, _, _, inf, ce, cp = v
    return (f"{en} didn't {b} {ce}.",
            f"{pt} não {conjugar(inf, 'passado', p)} {cp}.")


def _present_perfect(s, v):
    en, pt, p, terceira = s
    _, _, _, part, _, inf, ce, cp = v
    aux = "has" if terceira else "have"
    return (f"{en} {aux} {part} {ce}.",
            f"{pt} {AUX['ter'][p]} {conjugar(inf, 'participio')} {cp}.")


def _going_to(s, v):
    en, pt, p, _ = s
    b, _, _, _, _, inf, ce, cp = v
    return (f"{en} {_be(en)} going to {b} {ce}.", f"{pt} {AUX['ir'][p]} {inf} {cp}.")


def _will(s, v):
    en, pt, p, _ = s
    b, _, _, _, _, inf, ce, cp = v
    return (f"{en} will {b} {ce}.", f"{pt} {AUX['ir'][p]} {inf} {cp}.")


def _can(s, v):
    en, pt, p, _ = s
    b, _, _, _, _, inf, ce, cp = v
    return (f"{en} can {b} {ce}.", f"{pt} {AUX['poder'][p]} {inf} {cp}.")


def _should(s, v):
    en, pt, p, _ = s
    b, _, _, _, _, inf, ce, cp = v
    return (f"{en} should {b} {ce}.", f"{pt} {AUX['dever'][p]} {inf} {cp}.")


# ordem do vídeo original: do fundamental ao avançado
TOPICOS = [
    ("Simple Present — afirmativa", _sp_afirmativa),
    ("Simple Present — negativa", _sp_negativa),
    ("Simple Present — pergunta", _sp_pergunta),
    ("Present Continuous", _presente_continuo),
    ("Simple Past — afirmativa", _past_afirmativa),
    ("Simple Past — negativa", _past_negativa),
    ("Present Perfect", _present_perfect),
    ("Futuro — going to", _going_to),
    ("Futuro — will", _will),
    ("Modal — can", _can),
    ("Modal — should", _should),
]

TEMAS = list(VERBOS.keys())


def montar_aula(topico_idx: int, tema: str, quantas=12, semente=None) -> dict:
    """Uma aula = um tópico gramatical sobre um tema de vocabulário.

    A semente torna reproduzível: mesma semente, mesma aula.
    """
    nome, fn = TOPICOS[topico_idx % len(TOPICOS)]
    banco = VERBOS[tema]
    semente = semente or f"{nome}|{tema}|{quantas}"
    rnd = random.Random(hashlib.sha1(str(semente).encode()).hexdigest())

    combos = list(itertools.product(SUJEITOS, banco))
    rnd.shuffle(combos)

    frases, vistas = [], set()
    for s, v in combos:
        if len(frases) >= quantas:
            break
        try:
            en, pt = fn(s, v)
        except (KeyError, ValueError):
            continue
        if en.lower() in vistas:
            continue
        vistas.add(en.lower())
        frases.append({"en": en, "pt": pt})

    return {"titulo": f"{nome} · {tema}", "topico": nome, "tema": tema,
            "frases": frases, "semente": str(semente)}


def sequencia(quantas=40, frases_por_aula=12, base="v1") -> list[dict]:
    """Currículo completo, em rodízio de tópico e tema."""
    return [montar_aula(n % len(TOPICOS),
                        TEMAS[(n // len(TOPICOS)) % len(TEMAS)],
                        frases_por_aula, semente=f"{base}|{n}")
            for n in range(quantas)]


def total_possivel() -> int:
    return len(TOPICOS) * len(TEMAS)


if __name__ == "__main__":
    print(f"{len(TOPICOS)} tópicos × {len(TEMAS)} temas = {total_possivel()} aulas distintas\n")
    for idx in (0, 1, 3, 4, 6, 7, 9):
        a = montar_aula(idx, "trabalho", 4)
        print(a["titulo"])
        for f in a["frases"]:
            print(f"   {f['en']:<42} {f['pt']}")
        print()
