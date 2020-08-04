# Copyright 2018 Google LLC.
# SPDX-License-Identifier: Apache-2.0

FROM alpine:3.10

COPY requirements.txt /

RUN \
  apk update && \
  apk add linux-headers build-base libstdc++ python python-dev py2-pip py2-curl && \
  /usr/bin/pip install --upgrade pip && \
  /usr/bin/pip install -r requirements.txt && \
  apk del build-base python-dev

COPY main.py run.sh /
RUN chmod 755 /main.py /run.sh

ENV MON_CRONSPEC "*/2 * * * *"
ENV MON_HOSTSFILE "# no extra hosts to add from MON_HOSTSFILE variable"
ENV CRONTAB /etc/crontabs/root
ENV LOGFILE /var/log/latency.log

CMD \
  echo "$MON_HOSTSFILE" >> /etc/hosts && \
  echo "$MON_CRONSPEC	/run.sh >>$LOGFILE 2>&1" > $CRONTAB && \
  crond -L /var/log/cron.log && \
  touch $LOGFILE && \
  tail -F $LOGFILE