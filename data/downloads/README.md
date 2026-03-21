# Viral Cuts Bot v2

## 1. Instalação

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows
pip install -r requirements.txt

2. Rodar
uvicorn app.main:app --reload

Abra no navegador:

http://127.0.0.1:8000
3. Como testar
escolha Arquivo local
informe o caminho de um .mp4
clique em Processar vídeo
4. O que já faz
copia o vídeo para a pasta do projeto
extrai áudio
transcreve com Whisper
escolhe os trechos com score maior
cria cortes verticais
gera .srt
embute legenda no vídeo
gera thumbnail
cria título e caption
lista tudo na interface
5. O que falta plugar
Ingestão por URL

Implementar SourceService.ingest() para a fonte autorizada que você quiser usar.

Publicação real

Implementar PublishService.publish() com a API/plataforma que você vai usar.

2. Rodar
uvicorn app.main:app --reload

Abra no navegador:

http://127.0.0.1:8000
3. Como testar
escolha Arquivo local
informe o caminho de um .mp4
clique em Processar vídeo
4. O que já faz
copia o vídeo para a pasta do projeto
extrai áudio
transcreve com Whisper
escolhe os trechos com score maior
cria cortes verticais
gera .srt
embute legenda no vídeo
gera thumbnail
cria título e caption
lista tudo na interface
5. O que falta plugar
Ingestão por URL

Implementar SourceService.ingest() para a fonte autorizada que você quiser usar.

Publicação real

Implementar PublishService.publish() com a API/plataforma que você vai usar.

