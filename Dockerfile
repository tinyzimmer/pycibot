FROM amazonlinux

# Install latest patches
RUN yum -y update

# Install python compilation dependancies
RUN yum -y install wget gcc xz zlib zlib-devel openssl openssl-devel sqlite sqlite-devel

# Download and install python 3.6.3 source
RUN wget https://www.python.org/ftp/python/3.6.3/Python-3.6.3.tar.xz
RUN tar xf Python-3.6.3.tar.xz
RUN cd ./Python-3.6.3 && ./configure
RUN cd ./Python-3.6.3 && make
RUN cd ./Python-3.6.3 && make install

# Install bot depends
RUN pip3.6 install slackclient pyyaml sqlalchemy

# Copy src
COPY ./ /opt/slackbot

# Install requirements for plugins
RUN chmod +x /opt/slackbot/docker_helpers/install_plugin_reqs.sh
RUN /opt/slackbot/docker_helpers/install_plugin_reqs.sh

CMD python3.6 /opt/slackbot/slackbot.py -d
