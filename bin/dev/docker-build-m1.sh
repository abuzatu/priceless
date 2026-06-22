#!/bin/bash
: "${PROJECT_NAME:=priceless}"

docker build --platform linux/amd64 --no-cache -t $PROJECT_NAME:latest .
