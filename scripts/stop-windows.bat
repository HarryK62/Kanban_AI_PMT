@echo off
setlocal

set ROOT_DIR=%~dp0..
set CONTAINER_NAME=pm-app
pushd "%ROOT_DIR%"
docker compose down
docker rm -f %CONTAINER_NAME% >nul 2>nul
popd
