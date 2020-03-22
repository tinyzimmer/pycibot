IMAGE_TAG ?= slackbot:latest

build:
	docker build . -t ${IMAGE_TAG}

run:
	docker run -it --rm \
		-v `pwd`/pv:/opt/slackbot/pv \
		-v `pwd`/config.yml:/opt/slackbot/config.yml \
		-e SLACK_BOT_CONFIG=/opt/slackbot/config.yml \
		${IMAGE_TAG}

run_mock:
	docker run -it --rm \
		-v `pwd`/pv:/opt/slackbot/pv \
		-v `pwd`/config.yml:/opt/slackbot/config.yml \
		-e SLACK_BOT_CONFIG=/opt/slackbot/config.yml \
		${IMAGE_TAG} -m

clean:
	docker images --filter 'dangling=true' -q | xargs docker rmi || echo
