# FastAPI-google-geolocation
Developed this app to process AP scan bssid's into location, latitude and longitude

# Virtual Env

In the root of the directory

    sudo apt install python3.9-venv

    python3.9 -m venv FastAPI_env

    source FastAPI_env/bin/activate

    pip install -r requirements.txt
    pip install --upgrade pip

## Run tests

In the root directory

    cd app
    pytest
    python3.9 main.py

Or in root of directory 

    python3.9 app/main.py

## Docker

To get docker up we build it first

    docker build -t aruba-geolocation-api .

Then run it with .env file

    docker run --env-file .env -it --rm -p 80:80 aruba-geolocation-api

## Pytest

Bash into Docker image

    docker run --env-file .env -it --rm -p 80:80 aruba-geolocation-api bash

Then run

    cd app
    pytest


## Helpful Commands

List images

    docker images

Remove Images

    docker rmi -f Image_id

List containers

    docker container ls --all

Remove Container

    docker container rm container_id
