Write-Host "Starting Redis and MinIO via Docker..." -ForegroundColor Cyan
docker-compose up -d redis minio

Write-Host "Waiting for infrastructure to be ready..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

Write-Host "Starting Gateway (Port 8000)..." -ForegroundColor Green
Start-Process -FilePath ".\.venv\Scripts\uvicorn.exe" -ArgumentList "main:app --port 8000" -WorkingDirectory "gateway" -WindowStyle Normal

Write-Host "Starting Slave Worker 1 (Port 8001)..." -ForegroundColor Green
Start-Process -FilePath ".\.venv\Scripts\uvicorn.exe" -ArgumentList "main:app --port 8001" -WorkingDirectory "slave" -WindowStyle Normal

Write-Host "Starting Slave Worker 2 (Port 8002)..." -ForegroundColor Green
Start-Process -FilePath ".\.venv\Scripts\uvicorn.exe" -ArgumentList "main:app --port 8002" -WorkingDirectory "slave" -WindowStyle Normal

Write-Host "All local services started in separate windows!" -ForegroundColor Cyan
Write-Host "Close those windows to stop the services."
