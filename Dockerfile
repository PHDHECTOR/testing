FROM python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 RERIMSS_REPORTS_DIR=/app/dist RERIMSS_STATE_DIR=/data
WORKDIR /app
COPY vendor/wheels /wheels
RUN pip install --no-cache-dir --no-index --find-links=/wheels --require-hashes -r /wheels/requirements.lock && groupadd --gid 10001 rerimss && useradd --uid 10001 --gid rerimss --no-create-home rerimss && mkdir -p /data && chown rerimss:rerimss /data && rm -rf /wheels
COPY --chown=rerimss:rerimss app ./app
COPY --chown=rerimss:rerimss dist/public/index.html ./dist/public/index.html
COPY --chown=rerimss:rerimss dist/private/index.html ./dist/private/index.html
USER rerimss
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/healthz',timeout=3).read()"
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "2", "--threads", "4", "--timeout", "120", "--worker-tmp-dir", "/tmp", "--access-logfile", "-", "--error-logfile", "-", "app.wsgi:app"]
