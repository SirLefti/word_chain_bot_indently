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
__DEFAULT_SIZE = CorporaSize.Size_300K.value
# English uses simple-wikipedia corpus
# Icelandic has no 300K corpus, use 100K instead
__LANGUAGE_SOURCES: dict[Language, str] = ComputedDefaultDict(lambda k: f'https://downloads.wortschatz-leipzig.de/corpora/{k.value.code_long}_wikipedia_2021_{__DEFAULT_SIZE}.tar.gz', {
    Language.ENGLISH: f'https://downloads.wortschatz-leipzig.de/corpora/eng-simple_wikipedia_2021_{__DEFAULT_SIZE}.tar.gz',
    Language.ICELANDIC: 'https://downloads.wortschatz-leipzig.de/corpora/isl_wikipedia_2021_100K.tar.gz'
})


def has_uppercase_beyond_first(word: str) -> bool:
    """
    Detects if the word has uppercase characters beyond the first character. It must be used on the raw corpus, not on
    a processed lowercased version of the corpus. Ordinary capitalized words are accepted (sentence starts, proper
    names, German nouns).

    This rejects:

    * abbreviations (e.g. NGO)
    * plurals of abbreviations that do not satisfy ``word.isupper()`` (e.g. NGOs)
    * internal capitals in brand names, surnames or unit symbols (e.g. iPhone, McLaren, kWh; they are not proper words)
    * abbreviations in combinations (e.g. CD-Player)

    As a side effect, it also rejects:

    * combined capitalized words (e.g. American-Samoa; but the first parts are usually not rare on their own, rejecting
      it is acceptable)
    * German short forms with single character followed by hyphen (e.g. U-Boot; rejecting is acceptable because ``x-``
      are irrelevant in hard mode, since words do not end with hyphens, and the first character is usually frequent
      enough on its own that rejecting does not hurt the metric in any significant way)
    * Capitalized Dutch digraphs (e.g. IJs; they usually appear also in a lowercased version, rejecting them does
      not hurt the characters metric in any significant way)
    """
    return any(c.isupper() for c in word[1:])


def accepted_words(words: list[str], language: Language) -> set[str]:
    """
    Filters corpus words down to those usable for the given language and lowercases them.
    """
    regex = re.compile(language.value.allowed_word_regex)
    return {word.lower() for word in words
            if regex.match(word.lower()) and not has_uppercase_beyond_first(word)}


def generate_token_scores(words: set[str], game_modes: set[GameMode]) -> dict[int, dict[str, float]]:
    scores: dict[int, dict[str, float]] = dict()

    for game_mode in game_modes:
        token_width = int(game_mode.value)
        min_word_length = token_width + 1
        token_occurrences: defaultdict[str, int] = defaultdict(lambda: 0)
        single_tokens = set(string.ascii_lowercase)
        valid_words = [word.lower() for word in words if len(word) >= min_word_length]

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
    words_with_more_than_one_occurrence = [word for (word, occurrences) in extracted_words.items() if occurrences > 1]
    words = accepted_words(words_with_more_than_one_occurrence, language)
    result = generate_token_scores(words, {game_mode for game_mode in GameMode})
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
