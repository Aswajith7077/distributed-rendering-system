FROM python:3.12-slim

# Install python + venv tools
RUN apt-get update && apt-get install -y python3 python3-venv python3-pip ffmpeg
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app

COPY requirements.txt .

# Install dependencies inside venv
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]