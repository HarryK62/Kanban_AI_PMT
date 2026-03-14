# Scripts Agent Notes

This directory contains helper scripts for starting and stopping the local Dockerized app.

## Current scripts

- `start-mac.sh`
- `stop-mac.sh`
- `start-linux.sh`
- `stop-linux.sh`
- `start-windows.bat`
- `stop-windows.bat`

## Behavior

- Start scripts build the Docker image and run the container as `pm-app` on port `8000`.
- Stop scripts remove the `pm-app` container if it exists.
