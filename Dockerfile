FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements-core.txt requirements-web.txt ./
RUN pip install --no-cache-dir --disable-pip-version-check -r requirements-web.txt \
    && useradd --create-home --uid 10001 appuser
COPY exam_formatter ./exam_formatter
COPY templates/master_exam.docx ./templates/master_exam.docx
USER appuser
EXPOSE 8000
CMD ["uvicorn", "exam_formatter.web.app:app", "--host", "0.0.0.0", "--port", "8000"]
