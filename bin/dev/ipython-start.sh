#!/bin/bash
: "${PROJECT_NAME:=priceless}"

docker exec -i -t  ${PROJECT_NAME} \
    poetry run dotenv run ipython