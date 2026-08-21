import asyncio
import json
import logging
import os
import re
import string
from collections import defaultdict
from itertools import product
from pathlib import Path
from typing import Callable

from consts import GameMode
from language import LANGUAGES_DIRECTORY, Language
from wortschatz import CorporaSize, extract_words


class ComputedDefaultDict(defaultdict):

    def __init__(self, default_factory: Callable, initial_values: dict | None):
        super().__init__(default_factory, initial_values if initial_values else {})

    def __missing__(self, key):
        self[key] = value = self.default_factory(key)
        return value


__LOGGER = logging.getLogger(__name__)
__CACHE_DIRECTORY = LANGUAGES_DIRECTORY / Path('cache')
__DEFAULT_SIZE = CorporaSize.Size_30K.value
__LANGUAGE_SOURCES: dict[Language, str] = ComputedDefaultDict(lambda k: f'https://downloads.wortschatz-leipzig.de/corpora/{k.value.code_long}_wikipedia_2021_{__DEFAULT_SIZE}.tar.gz', {
    Language.ENGLISH: f'https://downloads.wortschatz-leipzig.de/corpora/eng-simple_wikipedia_2021_{__DEFAULT_SIZE}.tar.gz'
})


def has_uppercase_beyond_first(word: str) -> bool:
    """
    Detects abbreviations, initialisms and brand spellings by checking for capital letters past the first
    character. Regularly capitalized compounds like `U-Boot` are covered on purpose.
    """
    return any(c.isupper() for c in word[1:])


def accepted_words(words: list[str], language: Language) -> set[str]:
    """
    Filters corpus words down to those usable for the given language and lowercases them.
    """
    regex = re.compile(language.value.allowed_word_regex)
    return [word.lower() for word in words
            if regex.match(word.lower()) and not has_uppercase_beyond_first(word)]


def generate_token_scores(words: list[str], game_modes: list[GameMode]) -> dict[int, dict[str, float]]:
    scores: dict[int, dict[str, float]] = dict()

    for game_mode in game_modes:
        token_width = int(game_mode.value)
        token_occurrences: defaultdict[str, int] = defaultdict(lambda: 0)
        single_tokens = set(string.ascii_lowercase)
        valid_words = [word.lower() for word in words if len(word) >= token_width]

        for word in valid_words:
            start_token = word[:token_width]
            token_occurrences[start_token] += 1
            single_tokens.update(set([c for c in word]))

        tokens = [''.join(c) for c in product(*[single_tokens for _ in range(token_width)])]
        total_words = len(valid_words)
        total_tokens = len(tokens)

        scores[token_width] = {token: token_occurrences[token] / total_words * total_tokens for token in tokens}

    return scores

async def run_for_language(language: Language):
    __LOGGER.info(f'analyzing for {language.value.code}')
    extracted_words = await extract_words(__LANGUAGE_SOURCES[language], __CACHE_DIRECTORY)
    words = accepted_words(extracted_words, language)
    result = generate_token_scores(words, [game_mode for game_mode in GameMode])
    with open(LANGUAGES_DIRECTORY / f'scores_{language.value.code}.json', 'w', encoding='utf-8') as export_file:
        json.dump(result, export_file, indent=4, sort_keys=True, ensure_ascii=False)
        __LOGGER.info(f'analyzed and exported for {language.value.code}')


async def main():
    if not os.path.exists(LANGUAGES_DIRECTORY):
        os.mkdir(LANGUAGES_DIRECTORY)
    if not os.path.exists(__CACHE_DIRECTORY):
        os.mkdir(__CACHE_DIRECTORY)

    for l in Language:
        await run_for_language(l)

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
