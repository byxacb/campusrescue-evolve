FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir functions-framework==3.8.0 google-cloud-aiplatform>=1.161.0
COPY main.py .
CMD ["functions-framework", "--target=main", "--port=8080", "--signature-type=http"]
