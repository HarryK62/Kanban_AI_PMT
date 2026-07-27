@echo off
setlocal

set ROOT_DIR=%~dp0..
set CONTAINER_NAME=pm-app

if not exist "%ROOT_DIR%\.env" (
  echo Missing %ROOT_DIR%\.env
  echo Create it from .env.example before starting the app.
  exit /b 1
)

pushd "%ROOT_DIR%"
docker rm -f %CONTAINER_NAME% >nul 2>nul
docker compose up --build --detach
if errorlevel 1 (
  popd
  exit /b 1
)
popd

echo App is starting at http://localhost:8000
