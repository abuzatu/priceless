#!/bin/bash

MY_IP=$(hostname -I | awk '{print $1}')
echo "hostname=$(hostname)"
echo "MY_IP=${MY_IP}"
if [ $(hostname) = "vps" ]; then
    echo "Hostname is vps"
    URL_STEM="${MY_IP}"
else
    echo "Hostname is not vps, assume it is local"
    URL_STEM="localhost"
fi
echo "URL_STEM=${URL_STEM}"

PYTHONPATH=${PWD}/src URL_STEM=${URL_STEM} poetry run streamlit run `echo "${@:1}"` \
    # the echo part file name taken from the command line as input
    # port for streamlit
    --server.port 8508 \
    # extra
    --server.enableXsrfProtection false \
    --server.enableCORS false

