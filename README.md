# Viral Cuts Bot v2

Aplicacao local para transformar videos longos em cortes verticais com legenda, board estilo Trello e processamento em segundo plano.

## O que o projeto faz

- Cria jobs em background para nao travar a requisicao HTTP.
- Aceita video por `upload`, `URL` ou caminho local.
- Usa Whisper para transcricao em portugues.
- Escolhe momentos com um motor de selecao por contexto.
- Gera momentos verticais individuais com legenda e thumbnail.
- Junta os melhores momentos em um video final vertical pronto para TikTok.
- Permite escolher se o video final tera legenda ou nao.
- Organiza os clips em um board Kanban.
- Permite editar titulo, caption, hashtags, observacoes, status e coluna.
- Permite baixar original HQ, corte, legenda e excluir clips.

## Motor de cortes

O projeto agora usa uma camada de analise local para evitar cortes sem sentido.

Em vez de olhar apenas um segmento isolado, o sistema:

- avalia janelas com varias falas consecutivas
- procura gancho de abertura
- mede continuidade de assunto
- procura payoff ou fechamento coerente
- aplica pesos diferentes para `viral`, `engracado`, `chocante` e `informativo`
- penaliza trechos que parecem comeco ou fim incompleto

Depois da selecao, o sistema gera os momentos individuais e monta um unico video final curto com eles.
O resultado da analise entra no campo de observacoes do card para facilitar revisao manual.

## Arquitetura atual

### Backend

- `app/main.py`
  API FastAPI, fila de jobs, endpoints do board, upload e downloads.
- `app/storage.py`
  Persistencia em SQLite (`data/state.db`).
- `app/services/source_service.py`
  Ingestao local e por URL com `yt-dlp`.
- `app/services/transcript_service.py`
  Transcricao com Whisper.
- `app/services/scoring_service.py`
  Selecao inteligente de momentos por contexto.
- `app/services/ffmpeg_service.py`
  Extracao de audio, corte vertical, burn de legenda, thumbnail e montagem do compilado final.

### Frontend

- `app/templates/index.html`
  Estrutura da pagina.
- `app/static/app.css`
  Visual do workspace, jobs, board e modal de edicao.
- `app/static/app.js`
  Polling, renderizacao dos cards, upload, drag and drop e edicao manual.

## Requisitos

- Python 3.11+
- FFmpeg

Observacao:

- O projeto ja procura um FFmpeg local em `.tools/ffmpeg/bin/ffmpeg.exe`.
- Se esse binario existir, ele sera usado automaticamente.

## Instalacao

### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Linux/macOS

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Rodando o projeto

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Abra:

```text
http://127.0.0.1:8000
```

## Como testar

### Opcao 1: upload direto

1. Abra a pagina.
2. Em `Tipo de fonte`, escolha `Upload direto`.
3. Selecione um video.
4. Escolha o tipo de corte.
5. Clique em `Criar job`.

### Opcao 2: URL

1. Em `Tipo de fonte`, escolha `URL`.
2. Cole uma URL suportada.
3. Clique em `Criar job`.

### Opcao 3: arquivo local

1. Em `Tipo de fonte`, escolha `Arquivo local`.
2. Informe o caminho completo do video.
3. Clique em `Criar job`.

## Status exibidos no job

Os jobs mostram etapas como:

- `Na fila`
- `Preparando fonte`
- `Extraindo audio`
- `Transcrevendo`
- `Analisando contexto`
- `Gerando cortes`
- `Legendando`
- `Criando thumbnail`
- `Concluido`
- `Erro`

## Estrutura de dados

### Jobs

Cada job representa um processamento de entrada.

Campos principais:

- origem
- tipo de corte
- status
- etapa atual
- quantidade de clips gerados
- video final compilado

### Clips

Cada clip representa um corte final ligado a um job.

Campos principais:

- titulo
- caption
- hashtags
- observacoes
- status de publicacao
- coluna do board

## Pastas importantes

- `data/downloads`
  videos originais ingeridos
- `data/audio`
  audios extraidos
- `data/transcripts`
  transcricoes JSON
- `data/clips`
  momentos individuais
- `data/exports`
  videos finais compilados por job
- `data/subtitles`
  legendas `.srt`
- `data/thumbs`
  thumbnails
- `data/state.db`
  banco SQLite

## Limitacoes atuais

- A publicacao real ainda depende da implementacao do servico final da plataforma alvo.
- O polling de status e feito por requisicoes periodicas, nao websocket.
- Para varias maquinas acessarem o mesmo acervo com seguranca, o ideal e migrar para um banco central e storage compartilhado.

## Proximos passos sugeridos

- IA com modelo externo opcional para revisao semantica ainda mais forte
- websocket para status em tempo real
- autenticacao e usuarios
- banco central para acesso multi-maquina
