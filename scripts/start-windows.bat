@echo off
setlocal

set ROOT_DIR=%~dp0..
set IMAGE_NAME=pm-app
set CONTAINER_NAME=pm-app

if not exist "%ROOT_DIR%\.env" (
  echo Missing %ROOT_DIR%\.env
  echo Create it from .env.example before starting the app.
  exit /b 1
)

docker build -t %IMAGE_NAME% "%ROOT_DIR%"
docker rm -f %CONTAINER_NAME% >nul 2>nul
docker run --detach --name %CONTAINER_NAME% --env-file "%ROOT_DIR%\.env" --publish 8000:8000 %IMAGE_NAME%

echo App is starting at http://localhost:8000
