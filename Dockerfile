FROM python:3.10-slim
WORKDIR /app
COPY . /app
RUN pip install --upgrade pip && \
    pip install fastapi uvicorn openai pandas python-dotenv
EXPOSE 5000
CMD ["uvicorn", "fastapi_app:app", "--host", "0.0.0.0", "--port", "5000"]
