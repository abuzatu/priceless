#!/bin/bash
: "${PROJECT_NAME:=priceless}"

docker build --no-cache -t $PROJECT_NAME:latest .
