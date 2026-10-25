FROM python:3.12-slim
WORKDIR /srv
COPY pyproject.toml README.md requirements.txt ./
COPY app ./app
RUN pip install --no-cache-dir -r requirements.txt && pip install --no-cache-dir --no-deps .
RUN useradd -m gateway
USER gateway
EXPOSE 8000
HEALTHCHECK CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/')" || exit 1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
