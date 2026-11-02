FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt runtime.txt ./
COPY scripts/guess_core.py scripts/serve_guess.py scripts/
COPY web web
COPY data/wujiang_database.json data/zhanfa_database.json data/
COPY data/figure data/figure

ENV HOST=0.0.0.0
ENV PORT=8770
ENV PYTHONUNBUFFERED=1
EXPOSE 8770

CMD ["python", "scripts/serve_guess.py"]
