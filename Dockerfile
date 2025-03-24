FROM docker:dind

ENV PYTHONUNBUFFERED=1
RUN apk add --update --no-cache python3 py3-pip && ln -sf python3 /usr/bin/python

COPY . /src/

WORKDIR /src

RUN pip install --break-system-packages -r requirements.txt