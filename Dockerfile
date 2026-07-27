FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir fastapi uvicorn

COPY mock_report_api.py .

EXPOSE 9000

CMD ["uvicorn", "mock_report_api:app", "--host", "0.0.0.0", "--port", "9000"]