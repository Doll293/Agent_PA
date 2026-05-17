FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8501

CMD ["streamlit", "run", "mail_manager/streamlit_app.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.fileWatcherType=none"]
