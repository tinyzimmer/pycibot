#!/bin/bash

for i in $(ls /opt/slackbot/plugins); do
    if [[ -f "/opt/slackbot/plugins/${i}/requirements.txt" ]]; then
        pip3.6 install -r "/opt/slackbot/plugins/${i}/requirements.txt"
    fi
done
