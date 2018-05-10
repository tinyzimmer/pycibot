##  CI/CD Slack Bot

#####     Tested in Python 3.6.3 but should work in 3.4+
#####     No Windows, just no. you can use docker

TODO: update docs...everywhere

Features:

 * Pluggable Bot for use in slack channels
 * Intuitive Slack client API for easy customization

Usage:

 * `pip install -r requirements.txt` # and any other dependancies you need
 * `cp config.yml.sample config.yml` # edit fields as required
 * `python slackbot.py -d`

Alternatively, use docker:

 * `cp config.yml.sample config.yml` # edit fields as required
 * `docker build .`
 * `docker run <imagename>`

Available Plugins (but write more!):

 * example - dumps a user's slack profile, kind of annoying, don't use it
 * chatterbot - if no other plugins catch a command will return a response from the chatterbot corpus
 * excuses - responds with a random excuse from the BOFH series
 * gitlab - provides a handful of gitlab automations/integrations
 * jenkins - same as for gitlab but with jenkins
 * gitlab-jenkins-bridge - loads gitlab/jenkins interfaces without their threads to provide cross-functionality

Documentation for configuring the plugins will come. For now just look at the `__init__` in the plugins to find needed values.

config.yml:

```yaml
# required configurations
slack_token: xxxx-xxxxxxxxxxxxx-xxxxxxxxxxxxxxxxxxxxxxxx
bot_name: my-new-bot
command_trigger: '!'

# name of folders inside ./plugins that contain a plugin.py and loadable object (see below)
# load as many as you want but keep in mind they will be processing all events in parallel
enabled_plugins:
  - example
  - gitlab

# Optional configurations for plugins
... # better docs coming, see sample config
```

Plugins are autoloaded from the plugins directory at runtime and must contain a file called 'plugin.py' and a loadable SlackBotPlugin object with an on_recv() method that accepts three arguments. The arguments passed to the method respectively are:

 * channel: The channel that is being interacted with
 * user: A dictionary containing slack user attributes of sender
 * words: a list containing the contents of the message delimited by spaces

If a string or a list is returned from the on_recv() method it will automatically be outputted to the channel.

See plugins/example but here's some code anyway! :+1:

```python
from lib.builtins import BasePlugin

class SlackBotPlugin(BasePlugin):

    hooks = ['mycommand'] # will get reigstered to self.client.registered_hooks
                        # useful if you don't want to step on other plugins toes
    help_pages = [  # optional help pages for your command that get loaded by builtin help plugin
                {'mycommand': 'mycommand - i do something'}
            ]
    trigger_phrases = ['some trigger phrase'] # optional phrases to trigger your plugin

    def on_trigger(self, channel, user, words):
        trigger = self.get_trigger(words) # retrieves what the trigger was or None
        if trigger:
            return "I was triggered by %s" % trigger
    
    def on_recv(self, channel, user, words):
    	return "Hey! I just heard % say something in %s!" % (user['real_name'], channel)
```

##### Useful Methods Provided by "self.client" in "BasePlugin"

Just what I have so far

```python
client.config # dictionary of items in config.yml
client.client # raw SlackClient object
client.running # Boolean representing if the client has been signaled to shutdown, useful for threading
client.name # name of the bot
client._get_users() # returns a list of all readable user objects
client._get_my_id() # returns the user ID for the current bot
client.sanitize_handle(handle) # When parsing a user's @mention this will return a string formatted with just the user_id
client.get_user_profile(user_id) # retrieve the profile of a user by ID
client.send_channel_message(channel, message) # self explanatory, useful to send messages at different points in callback
client.send_channel_file(channel, title, filetype, content) # create a snippet in the channel. filetype can be language for syntax hilighting
client.get_help_page(command) # returns the help page for a given command

# There is also a builtin sqlite database that may later be convereted to mysql or something, code works the same no matter what
client.db # the database session object
client.db.session # SQLAlchemy session object for queries, etc. see example gitlab plugin

# Only call these functions once during your bootstrap. If you need to reload the database while running, reload the plugin as shown below.
#TODO: These don't work, there needs to be an easier way to create tables. see gitlab plugin for current work around
client.db.cycle_database() # deletes and recreates all tables
client.db.ensure_table_defs() # ensure table definitions but leave data in tact
```

See the gitlab plugin for some examples of defining tables and interacting with them. I will document better later.


##### Builtin chat commands
```
@bot list # list loaded commands
@bot help # 'man' like functionality
@bot source # retrieve source url
@bot shutdown # shuts the bot down
@bot reload config # reloads the config.yml
@bot reload users # reloads knowledge of slack users
@bot reload plugins # reloads all plugins. use for database changes
@bot greet # greets a user
```
