FROM tchabaud/alpine-base

RUN apk --update add ffmpeg python3 \
    && pip3 install -U youtube-dl python-telegram-bot

ADD ./main.py /opt/main.py

RUN chmod a+x /opt/main.py

USER docker
ENTRYPOINT [ "/opt/main.py" ]
