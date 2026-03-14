@echo off
setlocal

set CONTAINER_NAME=pm-app
docker rm -f %CONTAINER_NAME%
