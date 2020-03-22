FROM alpine as builder

# Install python build dependancies
RUN apk add --update sqlite sqlite-dev python3 python3-dev build-base

# Install bot depends
COPY ./requirements.txt /opt/build/requirements.txt
RUN python3 -m venv /opt/build/venv && \
    /opt/build/venv/bin/pip3 install cython && \
    /opt/build/venv/bin/pip3 install -r /opt/build/requirements.txt

# Build artifact image
FROM alpine

# Install core deps and setup bot user
RUN apk add --update python3 sqlite libstdc++ && adduser -h /opt/slackbot -u 1000 -D slackbot

# Copy the venv over
COPY --from=builder /opt/build/venv /opt/slackbot/venv

# Switch user
USER slackbot
WORKDIR /opt/slackbot

# Copy src
COPY . /opt/slackbot

ENTRYPOINT ["/opt/slackbot/venv/bin/python3", "/opt/slackbot/slackbot.py"]
