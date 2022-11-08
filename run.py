import logging

from anker.bot.bot import main
from anker.card_generation.translation import initialize_translation_packages

logging.basicConfig(format='[%(asctime)s] %(levelname)s in %(filename)s:%(lineno)d : %(message)s')
logging.getLogger().setLevel(logging.INFO)

def initialize():
    initialize_translation_packages()


if __name__ == "__main__":
    main()
