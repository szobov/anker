# Anker

Anker is a bridge between [anki](https://apps.ankiweb.net/index.html) and [telegram](https://telegram.org) messenger to help you learn languages.
Using Anker you can create a flashcards directly into your ankiweb account.

# Running your own Anker

1. First you need to feel missing information into the [run.sh.template](https://github.com/szobov/anker/blob/master/run.sh.template) file. Please, read the instructions in the comments.
2. Rename the *run.sh.template* file to `run.sh`.
3. Build docker image using `docker build -t anker .` and run the container using `docker run -d --name anker anker`.

# Usage

I highly encourage you to [run your own instance](#running-your-own-anker) of Anker, but you can try find mine in the telegram search.

Once you have an access to the bot you can do the following:

1. Authorize to ankiweb
2. Choose a deck or create one
3. Set the translation languages
4. Send it a word and choose a translation
5. Synchronize a collection in anki app
6. Enjoy learning


# Highlights:

* Privacy-oriented: Anker doesn't store your credentials, neither password or email.
* Offline translations: Anker uses several open-source offline translation tools. Say "nein" to google translate.
* Easy to host: Anker is shipped as a [Docker](https://www.docker.com).

# Differences from other similar projects

* [AnkiConnect](https://web.archive.org/web/20230401044849/https://ankiweb.net/shared/info/2055492159) - AnkiConnect is a plugin for Anki that allows you to control Anki with external programs. Anker is a standalone bot that uses AnkiConnect to communicate with Anki.
* [ankigenbot](https://github.com/damaru2/ankigenbot) - ankigenbot is very similar to Anker, but differes in following:
1. ankigenbot uses online translation services. Anker uses offline ones.
2. ankigenbot uses chromiumdriver to access ankiweb. Anker uses a very thin http-client instead.
3. ankigenbot store user credentials localy. Anker doesn't store it localy.






