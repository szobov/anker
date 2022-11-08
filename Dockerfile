FROM python:3.10-slim

COPY requirements.txt /app/requirements.txt
WORKDIR /app/
RUN python -m pip install -U pip && pip install -r requirements.txt

COPY anker/card_generation/translation.py /app/anker/card_generation/translation.py
WORKDIR /app/anker/card_generation/
RUN python -c 'import translation; translation.initialize_translation_packages()'

WORKDIR /app/
COPY . .

CMD ["bash", "run.sh"]
