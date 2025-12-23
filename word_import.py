import argparse
import asyncio
import re

from sqlalchemy.sql.expression import insert

from character_frequency import __CACHE_DIRECTORY, __LANGUAGE_SOURCES
from language import Language
from main import word_chain_bot
from model import WordCacheModel
from wortschatz import extract_words


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-l', '--language', type=str, help='ISO-639-1 language code', required=True)

    args = parser.parse_args()
    language = Language.from_language_code(args.language)

    words = await extract_words(__LANGUAGE_SOURCES[language], __CACHE_DIRECTORY)
    regex = re.compile(language.value.allowed_word_regex)
    accepted_words = [word.lower() for word in words if regex.match(word.lower()) and not word.isupper()]
    total_words = len(accepted_words)

    async with word_chain_bot.db_connection(locked=True) as connection:
        for index, word in enumerate(accepted_words):
            statement = insert(WordCacheModel).values(
                word=word,
                language=language.value.code
            ).prefix_with('OR IGNORE')
            await connection.execute(statement)
            if index % 100 == 0:
                print(f'({(index/total_words):.2%}) {index}/{total_words}')
        await connection.commit()
    print(f'finished importing {total_words} words')

if __name__ == '__main__':
    asyncio.run(main())
