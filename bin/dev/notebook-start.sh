#!/bin/bash
: "${PROJECT_NAME:=priceless}"

MY_IP=$(hostname -I | awk '{print $1}')
if [ $(hostname) = "vps" ]; then
    echo "Hostname is vps"
    URL_STEM="${MY_IP}"
else
    echo "Hostname is not vps, assume it is local"
    URL_STEM="localhost"
fi
echo "URL_STEM=${URL_STEM}"

docker exec -i -t  ${PROJECT_NAME} \
  poetry run dotenv run jupyter notebook \
  --ip="*" \
  --port=1342 \
  --NotebookApp.token=''  \
  --NotebookApp.custom_display_url=http://${URL_STEM}:1342
