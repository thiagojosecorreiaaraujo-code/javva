FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ .

# O Claude Code embutido no SDK grava estado em ~/.claude: precisa de HOME
# gravavel e de usuario NAO-root.
RUN useradd --create-home --home-dir /home/javva javva \
 && mkdir -p /tmp/javva /home/javva/.claude /home/javva/sessoes \
 && chown -R javva /tmp/javva /home/javva
USER javva
ENV HOME=/home/javva \
    CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1 \
    DISABLE_TELEMETRY=1 \
    DISABLE_AUTOUPDATER=1

EXPOSE 8787
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8787/api/hello', timeout=4).status == 200 else 1)"

# Ping do WebSocket bem espacado: o cliente (PowerShell) so responde ping
# enquanto esta lendo o socket, e a pessoa pode ficar minutos pensando no
# proximo comando.
CMD ["uvicorn", "javva:app", "--host", "0.0.0.0", "--port", "8787", \
     "--ws-ping-interval", "3600", "--ws-ping-timeout", "3600", \
     "--timeout-keep-alive", "75"]
