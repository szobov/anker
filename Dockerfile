FROM python:3.10-slim

COPY requirements.txt /app/requirements.txt
WORKDIR /app/
RUN apt-get update && apt-get install -y libzbar0 protobuf-compiler && python -m pip install -U pip && pip install -r requirements.txt

COPY anker/card_generation/translation.py /app/anker/card_generation/translation.py
WORKDIR /app/anker/card_generation/
RUN python -c 'import translation; translation.initialize_translation_packages()'

WORKDIR /app/
COPY . .

RUN protoc --python_out=. ./anker/anki_proto/*.proto

CMD ["bash", "run.sh"]
