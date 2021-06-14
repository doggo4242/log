FROM alpine:edge
RUN mkdir -p /etc/log
ADD config /etc/log
RUN apk update
RUN apk --no-cache upgrade
RUN apk --no-cache add python3 py3-pip gcc python3-dev musl-dev libffi-dev g++
RUN python3 -m pip install --no-cache-dir wheel
RUN python3 -m pip install --upgrade --no-cache-dir pip
RUN python3 -m pip install --no-cache-dir -r /etc/log/requirements.txt
RUN apk del gcc python3-dev musl-dev g++
ARG token
ENV LOG_TOKEN ${token}
COPY main.py /usr/local/bin/log
COPY log_cogs /usr/local/bin/log_cogs
ENTRYPOINT ["log"]
