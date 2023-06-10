from __future__ import annotations

import dataclasses
import enum
import functools
import itertools
import logging
import typing as _t

import argostranslate.package
import argostranslate.translate

from huggingface_hub import list_models
from transformers import MarianMTModel, MarianTokenizer

import wn as wordnet
from spellchecker import SpellChecker

logger = logging.getLogger(__name__)

wordnet.config.allow_multithreading = True

MARIAM_MODEL_ORG = "Helsinki-NLP"
MARIAM_MODEL_PREFIX = f"{MARIAM_MODEL_ORG}/opus-mt-"


@functools.lru_cache(maxsize=1)
def get_wordnet_mapping() -> dict[str, str]:
    return {"en": "oewn:2021", "de": "odenet:1.4", "fi": "omw-fi:1.4"}


# TODO: make readable languages names
@functools.lru_cache(maxsize=1)
def get_available_languages() -> tuple[str, ...]:
    return tuple(get_wordnet_mapping().keys())


@functools.lru_cache
def get_wordnet_name_from_language_code(language_code: str) -> str:
    mapping = get_wordnet_mapping()
    assert language_code in mapping, language_code
    return mapping[language_code]


def spell_check(language: str, text: str) -> str:
    spell_checker = SpellChecker(language=language)

    def _(word: str) -> str:
        match len(spell_checker.unknown([word])):
            case 0:
                return word
            case _:
                return spell_checker.correction(word) or word

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


@functools.lru_cache
def _get_mariam_model_and_tokenizer(
    from_lang: str, to_lang: str
) -> tuple[MarianMTModel, MarianTokenizer]:
    model_name = f"{MARIAM_MODEL_PREFIX}{from_lang}-{to_lang}"
    tokenizer = MarianTokenizer.from_pretrained(model_name)
    model = MarianMTModel.from_pretrained(model_name)
    return model, tokenizer


def init_mariam_translate(languages: tuple[str, ...]) -> None:
    model_list = list_models()
    model_ids = [
        x.modelId for x in model_list if x.modelId.startswith(MARIAM_MODEL_ORG)
    ]
    language_mappings = {tuple(x.split("/")[1].split("-")[-2:]): x for x in model_ids}

    for language_from, language_to in itertools.permutations(languages, r=2):
        model_name = language_mappings.get((language_from, language_to))
        if model_name:
            _get_mariam_model_and_tokenizer(language_from, language_to)

        model_to_fallback = language_mappings.get(
            (language_from, ARGOS_FALLBACK_LANGUAGE)
        )
        model_from_fallback = language_mappings.get(
            (ARGOS_FALLBACK_LANGUAGE, language_to)
        )
        if model_from_fallback and model_to_fallback:
            _get_mariam_model_and_tokenizer(language_from, ARGOS_FALLBACK_LANGUAGE)
            _get_mariam_model_and_tokenizer(ARGOS_FALLBACK_LANGUAGE, language_to)


@functools.lru_cache
def get_mariam_translation(from_language: str, to_language: str, text: str) -> str:
    model, tokenizer = _get_mariam_model_and_tokenizer(from_language, to_language)
    translated = model.generate(**tokenizer(text, return_tensors="pt", padding=True))
    return " ".join(tokenizer.decode(t, skip_special_tokens=True) for t in translated)


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


def get_wordnet_translation(from_language: str, to_language: str, text: str):
    possible_words = wordnet.words(text, lang=from_language)
    if len(possible_words) == 0:
        return None
    # TODO: process several possible words
    word = possible_words[0]
    translation_results = word.translate(lang=to_language)
    translations: list[str] = []
    for translation in itertools.chain(*translation_results.values()):
        translations.append(translation.lemma())
    if len(translations) == 0:
        return None
    return TranslationResult(
        word=text,
        from_language=from_language,
        to_language=to_language,
        possible_translations=tuple(translations),
        part_of_speech=WordNetPartOfSpeech(word.pos),
    )


def get_translations(
    from_language: str, to_language: str, input_text: str
) -> _t.Optional[TranslationResult]:
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

    mariam_translation = get_mariam_translation(from_language, to_language, text)
    possible_translations: tuple[str, ...] = (mariam_translation,)

    argos_translation = get_argostranslate(from_language, to_language)
    if argos_translation:
        possible_translations = (
            argos_translation.translate_function(text) + possible_translations
        )

    wordnet_translation = get_wordnet_translation(from_language, to_language, text)

    if wordnet_translation is None:
        return TranslationResult(
            word=text,
            from_language=from_language,
            to_language=to_language,
            possible_translations=possible_translations,
            part_of_speech=None,
        )
    else:
        return dataclasses.replace(
            wordnet_translation,
            possible_translations=(
                wordnet_translation.possible_translations + possible_translations
            ),
        )


def format_translation_result_iterator(
    translation: TranslationResult,
) -> _t.Iterator[str]:
    for possible_translation in translation.possible_translations:
        if translation.part_of_speech:
            yield f"({translation.part_of_speech.value}) {possible_translation}"
        else:
            yield possible_translation


def initialize_translation_packages():
    langueges = ("en", "de", "fi")
    init_wordnet_lexicons(languages=langueges)
    init_argostranslate(languages=langueges)
    init_mariam_translate(languages=langueges)


def main():
    initialize_translation_packages()
    print(get_translations("de", "en", "Beruf"))


if __name__ == "__main__":
    logging.basicConfig()
    logging.getLogger().setLevel(logging.DEBUG)
    main()
