# Player de Inglês

Um player de áudio que **toca sozinho e nunca fica sem faixa**. Enquanto você
ouve, ele já está produzindo a próxima aula.

```bash
cd ~/Downloads/gerador-licoes
./licoes
```

Janela única, maximizada. Play/pause, avançar, voltar, seek e volume.

---

## Os três modos

| Modo | O que toca | De onde vem |
|---|---|---|
| **AULAS** | Aula atrás de aula, sem fim | Currículo gerado na hora |
| **LIVROS** | Audiobook, ou aula de 4 passos feita do livro | Arquivos que você selecionar |
| **MP3** | Arquivos que já existem | Seu disco |

Escolha o modo, clique em **INICIAR**, e não encoste mais. A playlist anda
sozinha e continua sendo abastecida conforme o modo escolhido.

### Modo AULAS

O currículo tem **11 tópicos × 3 temas**, na mesma ordem do vídeo original:
Simple Present → Present Continuous → Simple Past → Present Perfect →
going to → will → can → should.

Cada aula vira uma faixa no padrão de 4 passos:

> inglês devagar → português → inglês na velocidade real → português

O gerador mantém uma **folga** de aulas prontas à frente (padrão: 2). Quando
você começa a ouvir a penúltima, ele já está fazendo a próxima.

### Modo LIVROS

Duas opções por rádio:

- **Audiobook (só inglês)** — narra o texto direto, sem tradução. Para quem já
  entende e quer volume de escuta.
- **Virar aula (4 passos)** — filtra as frases curtas, traduz e monta a lição.

Aceita `.epub` `.txt` `.srt` `.vtt`. O livro é quebrado em faixas do tamanho
que você escolher.

### Modo MP3

Adiciona arquivos ou uma pasta inteira. Serve para o MP3 do vídeo original —
já está em `~/Downloads/`.

---

## Por que o currículo não usa IA de fora

Testei os endpoints de LLM gratuitos e anônimos. O Pollinations, que era o
mais usado, passou a exigir pagamento. Nenhum outro se sustentou.

Então a geração é **por estrutura**, não por modelo de linguagem: um tópico
gramatical combinado com um banco de verbos e complementos. É exatamente o
que o vídeo faz — uma estrutura, muitas trocas de verbo.

A vantagem é que **funciona offline e a tradução sai correta**, porque o
português vem de um conjugador (`conjugacao.py`), não de tradução automática.

A primeira versão errava: gerava *"Eles entra na reunião"*. O conjugador
cobre as seis pessoas, presente e passado, com tabela de irregulares.

---

## Cache

Aula já gerada é reaproveitada. O nome do arquivo é o hash do conteúdo mais
a configuração de voz, então:

| | Tempo |
|---|---|
| Primeira geração (12 frases) | ~20 s |
| Mesma aula de novo | **0,00 s** |

Fica em `aulas/`, com o roteiro `.json` ao lado do `.mp3` para conferir.
O rodapé mostra quanto espaço está ocupado.

---

## Arquivos

| Arquivo | O que é |
|---|---|
| `app.py` | Janela única — player e os três modos |
| `player.py` | Motor de reprodução: fila, pause, seek, avanço automático |
| `biblioteca.py` | Gera aulas à frente e guarda em disco |
| `curriculo.py` | Banco de estruturas gramaticais e vocabulário |
| `conjugacao.py` | Conjugador de português |
| `nucleo.py` | Extração de texto, tradução e síntese de voz |
| `cli.py` | **Utilitário manual de apoio**, pela linha de comando |
| `licoes` | Lançador |

### O utilitário manual

Continua existindo para caso pontual — montar uma lição específica à mão:

```bash
./licoes extrair  legenda.srt  frases.json  4 9
./licoes traduzir frases.json
./licoes gerar    frases.json  licao.mp3
```

---

## Serviços usados

**Voz — `edge-tts`.** Vozes neurais da Microsoft, sem chave. 47 em inglês,
5 em português. Escolhido por qualidade: `gTTS` soa robótico e não controla
velocidade, `Piper` tem entonação chapada.

**Tradução — só no modo LIVROS.** Google gtx → MyMemory → Lingva, em cadeia
de reserva. Sem chave. O modo AULAS não precisa: a tradução já vem pronta.

**Reprodução — `just_playback`.** `pygame` não compila no Python 3.14.

---

## Desempenho

Síntese roda com 6 chamadas simultâneas (`CONCORRENCIA` em `nucleo.py`).

| | Por frase |
|---|---|
| Sequencial | 6,8 s |
| Paralelo | **1,2 s** |

Acima de 6 simultâneas o serviço recusa. Cada síntese tem 3 tentativas.

---

## Material legal para o modo LIVROS

| Fonte | O que tem |
|---|---|
| [Project Gutenberg](https://www.gutenberg.org/) | 75k+ em domínio público |
| [Standard Ebooks](https://standardebooks.org/) | Os mesmos, revisados |
| [mxt0/epub-CC](https://github.com/mxt0/epub-CC) | Domínio público brasileiro |
| [EbookFoundation/free-programming-books](https://github.com/EbookFoundation/free-programming-books) | Técnicos, licença livre |

Boa parte das coleções de epub no GitHub é cópia não autorizada de obra com
direito autoral vigente. As quatro acima são limpas.

**Aviso sobre romance:** medido aqui, prosa literária tem 18–21 palavras por
frase, contra 5 do vídeo original. Filtrando *Alice* inteiro sobram 8%, e o
que sobra é narrativa. Legenda `.srt` rende muito mais — diálogo é curto.

---

## Se quebrar

| Sintoma | Causa |
|---|---|
| Playlist parou de crescer | Gerador desligado — clique em INICIAR |
| Voz falha no meio | Serviço recusou. Baixe `CONCORRENCIA` em `nucleo.py` |
| Tradução falha (modo livros) | Sem rede, ou cota do MyMemory por IP |
| `ffmpeg not found` | `sudo apt install ffmpeg` |
| Janela não abre | `sudo apt install python3-tk` |
