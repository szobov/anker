from __future__ import annotations

import dataclasses
import enum
import functools
import itertools
import logging
import typing as _t

import argostranslate.package
import argostranslate.translate
import wn as wordnet
from spellchecker import SpellChecker

logger = logging.getLogger(__name__)


@functools.lru_cache
def get_wordnet_name_from_language_code(language_code: str) -> str:
    mapping = {"en": "oewn:2021", "de": "odenet:1.4", "fi": "omw-fi:1.4"}
    assert language_code in mapping, language_code
    return mapping[language_code]


def spell_check(language: str, text: str) -> str:
    spell_checker = SpellChecker(language=language)

    def _(word: str) -> str:
        match len(spell_checker.unknown([word])):
            case 0:
                return word
            case _:
                return spell_checker.correction(word)

    return " ".join(map(_, text.split()))


def init_wordnet_lexicons(languages: tuple[str, ...]):
    logger.info(
        msg={"languages": languages, "comment": "initialize wordnet files and database"}
    )
    for language in languages:
        wordnet_name = get_wordnet_name_from_language_code(language)
        path = wordnet.download(wordnet_name, progress_handler=None)
        logger.debug(
            msg={
                "languages": languages,
                "wordnet_path": path,
                "comment": "wordnet is initialized",
            }
        )
        assert path.exists()


TranslateFunctionT = _t.Callable[[str], tuple[str, ...]]


@dataclasses.dataclass(frozen=True)
class ArgosTranslate:
    language_from: str
    language_to: str
    translate_function: TranslateFunctionT


ARGOS_FALLBACK_LANGUAGE = "en"


@functools.lru_cache
def _argos_get_new_translation(
    language_from: str,
    language_to: str,
) -> TranslateFunctionT:
    installed_languages = argostranslate.translate.get_installed_languages()
    from_lang = next(filter(lambda l: l.code == language_from, installed_languages))
    to_lang = next(filter(lambda l: l.code == language_to, installed_languages))
    translation = from_lang.get_translation(to_lang)
    return lambda w: (translation.translate(w),)


@functools.lru_cache(maxsize=1)
def _get_argos_package_mappings() -> dict[
    tuple[str, str], argostranslate.package.Package
]:
    argostranslate.package.update_package_index()
    return {
        (package.from_code, package.to_code): package
        for package in argostranslate.package.get_available_packages()
    }


def _install_argos_package(argos_package: argostranslate.package.Package):
    logger.info(
        msg={
            "comment": "install argostranslate language package",
            "from": argos_package.from_code,
            "to": argos_package.to_code,
        }
    )
    argostranslate.package.install_from_path(argos_package.download())
    logger.info(
        msg={
            "comment": "argostranslate language package is installed",
            "from": argos_package.from_code,
            "to": argos_package.to_code,
        }
    )


def init_argostranslate(languages: tuple[str, ...]) -> None:
    argos_package_mappings = _get_argos_package_mappings()

    for language_from, language_to in itertools.permutations(languages, r=2):
        argos_language = argos_package_mappings.get((language_from, language_to))
        if argos_language:
            _install_argos_package(argos_language)
            continue

        argos_language_to_fallback = argos_package_mappings.get(
            (language_from, ARGOS_FALLBACK_LANGUAGE)
        )
        argos_language_from_fallback = argos_package_mappings.get(
            (ARGOS_FALLBACK_LANGUAGE, language_to)
        )
        if argos_language_from_fallback and argos_language_to_fallback:
            _install_argos_package(argos_language_to_fallback)
            _install_argos_package(argos_language_from_fallback)


@functools.lru_cache
def get_argostranslate(
    language_from: str, language_to: str
) -> _t.Optional[ArgosTranslate]:
    argos_package_mappings = _get_argos_package_mappings()
    argos_language = argos_package_mappings.get((language_from, language_to))
    translate_function: _t.Optional[TranslateFunctionT]
    if argos_language:
        translate_function = _argos_get_new_translation(language_from, language_to)
    else:
        argos_language_to_fallback = argos_package_mappings.get(
            (language_from, ARGOS_FALLBACK_LANGUAGE)
        )
        argos_language_from_fallback = argos_package_mappings.get(
            (ARGOS_FALLBACK_LANGUAGE, language_to)
        )
        if argos_language_from_fallback and argos_language_to_fallback:
            translation_function_to_fallback = _argos_get_new_translation(
                language_from, ARGOS_FALLBACK_LANGUAGE
            )
            translation_function_from_fallback = _argos_get_new_translation(
                ARGOS_FALLBACK_LANGUAGE, language_to
            )
            translate_function = lambda w: translation_function_from_fallback(
                translation_function_to_fallback(w)[0]
            )
    if translate_function:
        return ArgosTranslate(language_from, language_to, translate_function)
    return None


@enum.unique
class WordNetPartOfSpeech(enum.Enum):
    ADJ = "a"
    ADJ_SAT = "s"
    ADV = "r"
    NOUN = "n"
    VERB = "v"

    @classmethod
    def get_description(
        cls: _t.Type[WordNetPartOfSpeech], part_of_speech: str
    ) -> str | None:
        match part_of_speech:
            case cls.ADJ:
                return "adjective"
            case cls.ADJ_SAT:
                return "adjective"
            case cls.ADV:
                return "adverb"
            case cls.NOUN:
                return "noun"
            case cls.VERB:
                return "verb"
            case _:
                return None


@dataclasses.dataclass(frozen=True)
class TranslationResult:
    word: str
    from_language: str
    to_language: str
    possible_translations: tuple[str, ...]
    part_of_speech: _t.Optional[WordNetPartOfSpeech]


def get_wordnet_translation(from_language: str, to_languge: str, text: str):
    possible_words = wordnet.words(text, lang=from_language)
    if len(possible_words) == 0:
        return None
    # TODO: process several possible words
    word = possible_words[0]
    translation_results = word.translate(lang=to_languge)
    translations: list[str] = []
    for translation in translation_results.values():
        translations.append(translation.lemma())
    if len(translations) == 0:
        return None
    return TranslationResult(
        word=text,
        from_language=from_language,
        to_language=to_languge,
        possible_translations=tuple(translations),
        part_of_speech=WordNetPartOfSpeech(word.pos)
    )


def get_translations(from_language: str, to_languge: str, input_text: str):
    if False:
        # TODO: pyspellcheck is not working properly
        text = spell_check(from_language, input_text)
        if input_text != text:
            logger.debug(
                msg={
                    "comment": "text was corrected",
                    "original": input_text,
                    "corrected": text,
                    "lang": from_language,
                }
            )
    else:
        text = input_text
    if (result := get_wordnet_translation(from_language, to_languge, text)) is not None:
        return result

    argos_translation = get_argostranslate(from_language, to_languge)
    if argos_translation:
        return TranslationResult(
            word=text,
            from_language=from_language,
            to_language=to_languge,
            possible_translations=argos_translation.translate_function(text),
            part_of_speech=None
        )


def main():
    langueges = ("en", "de", "fi")
    init_wordnet_lexicons(languages=langueges)
    init_argostranslate(languages=langueges)
    print(get_translations("de", "fi", "die Katze"))


if __name__ == "__main__":
    logging.basicConfig()
    logging.getLogger().setLevel(logging.DEBUG)
    main()
