# Anker

Anker is a bridge between [anki](https://apps.ankiweb.net/index.html) and [telegram messenger](https://telegram.org) to help you learn languages.
Using Anker, you can create flashcards directly into your ankiweb account.

# Highlights:

* **Privacy-oriented**:
  Anker doesn't store your credentials, password, or email.
* **Offline translations**:
  Anker uses several open-source offline translation tools. Say "nein" to google translate.
* **Easy to self-host**:
  Anker [is shipped](https://github.com/szobov/anker/blob/master/Dockerfile) with a [Docker](https://www.docker.com) image.

# Usage

I encourage you to [run your instance](#running-your-own-anker) of Anker, but you can try to find mine in the telegram search.

Once you have access to the bot, you can do the following:

1. Authorize to ankiweb
2. Choose a deck or create one
3. Set the translation languages
4. Send it a word and choose a translation
5. Synchronize a collection in the Anki app
6. Enjoy learning

# Running your own Anker

1. First, you must feel the missing information in the [run.sh.template](https://github.com/szobov/anker/blob/master/run.sh.template) file. Please, read the instructions in the comments.
2. Rename the *run.sh.template* file to `run.sh`.
3. Build a docker image using `docker build -t Anker.` and run the container using `docker run -d --name Anker anker`.

# Differences from other similar projects

* [AnkiConnect](https://web.archive.org/web/20230401044849/https://ankiweb.net/shared/info/2055492159) is a plugin for the Anki desktop program. You must have an Anki desktop local installation and a one-to-one connection between your Anki desktop and your ankiweb account. On the other hand, Anker doesn't require anything from you except an account on Anki web and telegram. Anker allows many users login into their accounts using one Anker instance.
* [ankigenbot](https://github.com/damaru2/ankigenbot) - ankigenbot is very similar to Anker but different in the following:
    1. ankigenbot uses online translation services. Anker uses offline ones.
    2. ankigenbot uses [chromiumdriver](https://pypi.org/project/chromedriver-py/) to access ankiweb (therefore requires more CPU and Memory). Anker uses a very thin [http-client](https://github.com/szobov/anker/blob/master/anker/anki_api.py) instead.
    3. ankigenbot store user credentials [localy](https://github.com/damaru2/ankigenbot/blob/master/src/database.py#L40-L41). Anker doesn't store it locally.
    4. ankigenbot is shipped as a source code, and you must [install all dependencies locally](https://github.com/damaru2/ankigenbot#installation) to self-host it. Anker is shipped with Dockerfile and requires little effort to set up locally.
