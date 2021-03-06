
Adafruit Adabot
============

.. image :: https://img.shields.io/discord/327254708534116352.svg
    :target: https://discord.gg/nBQh6qu
    :alt: Discord

AdaBot is a friendly helper bot that works across the web to make people's
lives better. It focuses on those contributing to Adafruit's variety of
projects including CircuitPython.

Setup
=======

Here are the instructions for one time setup. Its simpler to start once
everything is installed.

Debian/Ubuntu Dependencies
+++++++++++++++++++++++++++

.. code-block:: shell

    sudo apt-get update # make sure you have the latest packages
    sudo apt-get upgrade # make sure already installed packages are latest
    sudo apt-get install git python3 python3-venv python3-pip screen

Adabot
++++++++++

Once the dependencies are installed, now clone the git repo into your home directory.

.. code-block:: shell

    git clone https://github.com/adafruit/adabot.git
    cd adabot

First, set up a virtual environment and install the deps.

.. code-block:: shell

  python3 -m venv .env
  source .env/bin/activate
  pip install -r requirements.txt

Secrets!
+++++++++

Adabot needs a few secrets to do her work. Never, ever check these into source
control!

They are stored as environment variables in ``env.sh``.

So, copy the example ``template-env.sh``, edit it and save it as ``env.sh``.

.. code-block:: shell

    cp template-env.sh env.sh
    nano env.sh

Do CTRL-X to exit and press Y to save the file before exiting.

Git
+++++++++

Adabot can automatically commit information so git must know an email and name
for the author.

.. code-block:: shell

    git config --global user.email "<adabot's email>"
    git config --global user.name "Adafruit Adabot"
    git config --global credential.helper 'store --file ~/.adabot-git-
credentials'
    git push

The git push won't actually push anything but it prompt for the bot's username
and password. These will be stored in the ~/.adabot-git-credentials file which
makes this not very secure. Make sure your OAUTH token has only the permissions
it needs in case it ends up in someone else's hands.

Usage Example
=============

To run Adabot we'll use screen to manage all of the individual pieces. Luckily,
we have a screenrc file that manages starting everything up.

.. code-block:: shell

    screen -c adabot.screenrc

This command will return back to your prompt with something like
``[detached from 10866.pts-0.raspberrypi]``. This means that Rosie is now
running within screen session behind the scenes. You can view output of it by
attaching to the screen with:

.. code-block:: shell

    screen -r

Once reattached you can stop everything by CTRL-Cing repeatedly or detach again
with CTRL-A then D. If any errors occur, a sleep command will be run so you can
view the output before screen shuts down.

To run the library statistics and validation script you must be inside this cloned
adabot directory and run the following command:

.. code-block:: shell

    python3 -m adabot.circuitpython_libraries

Ensure you have set BOTH the Github access token and Travis token environment
variables beforehand--see the template-env.sh for the name and where to get tokens.

Contributing
============

Contributions are welcome! Please read our `Code of Conduct
<https://github.com/adafruit/Adafruit_CircuitPython_adabot/blob/master/CODE_OF_CONDUCT.md>`_
before contributing to help this project stay welcoming.
