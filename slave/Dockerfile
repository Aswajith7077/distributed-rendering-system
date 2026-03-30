FROM blenderkit/headless-blender:blender-5.2

# Add blender directory to PATH so 'blender' resolves without hardcoding
ENV PATH="/home/headless/blender:$PATH"

# Install python + venv tools
RUN apt-get update && apt-get install -y python3 python3-venv python3-pip
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:/home/headless/blender:$PATH"

WORKDIR /app

RUN blender --version

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]