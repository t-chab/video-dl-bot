FROM tchabaud/alpine-base

COPY requirements.txt /opt/

RUN apk --update add --virtual build-deps python3-dev gcc musl-dev \
    && apk --update add ffmpeg python3 \
    && pip3 install -U -r /opt/requirements.txt \
    && apk del build-deps

COPY ./main.py /opt/main.py

RUN chmod a+x /opt/main.py

USER docker
ENTRYPOINT [ "/opt/main.py" ]
