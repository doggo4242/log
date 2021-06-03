FROM alpine:edge
RUN mkdir /etc/log
RUN apk update
RUN apk --no-cache upgrade
RUN apk --no-cache add python3 gcc python3-dev musl-dev
RUN python3 -m pip install --upgrade --no-cache-dir pip
RUN python3 -m pip install --no-cache-dir -r /etc/log/requirements.txt
RUN apk del gcc python3-dev musl-dev
ARG token
ENV TOKEN ${token}
COPY logs.py /usr/local/bin/logs.py
ENTRYPOINT ["python3 logs.py"]
