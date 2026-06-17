FROM python:3.12-slim

WORKDIR /app

RUN pip install --upgrade pip

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ffmpeg latexmk poppler-utils \
    texlive-science texlive-latex-extra \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://nodejs.org/dist/v22.19.0/node-v22.19.0-linux-x64.tar.gz \
    | tar -xz -C /usr/local --strip-components=1

RUN npm install -g @earendil-works/pi-coding-agent && \
    npm install -g pi-subagents

COPY . .
COPY config/pi-models.json /root/.pi/agent/models.json

RUN mkdir -p workspaces

ENV PYTHONPATH=/app

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]