import string

import pytest

from consts import GameMode
from language import Language


### ENGLISH

@pytest.mark.parametrize("token", list(string.ascii_lowercase), ids=lambda c: f'token_{c}')
def test_en_normal_mode(token: str):
    language = Language.ENGLISH
    mode = GameMode.NORMAL

    assert language.value.score_threshold[mode] <= language.value.first_token_scores[mode][token], f'failed for {token=}'


@pytest.mark.parametrize("token", [
    "en", "an", "es", "ey", "ow", "um", "ry", "ay"
], ids=lambda c: f'token_{c}')
def test_en_hard_mode_expect_valid(token: str):
    language = Language.ENGLISH
    mode = GameMode.HARD

    assert language.value.score_threshold[mode] <= language.value.first_token_scores[mode][token], f'failed for {token=}'

@pytest.mark.parametrize("token", [
    "nd", "ns", "ld", "ss", "ds", "ls", "ms", "ys", "ws", "ck", "ht", "rm", "lt", "ft", "ie", "ng"
], ids=lambda c: f'token_{c}')
def test_en_hard_mode_expect_invalid(token: str):
    language = Language.ENGLISH
    mode = GameMode.HARD

    assert language.value.score_threshold[mode] > language.value.first_token_scores[mode][token], f'failed for {token=}'


### GERMAN

@pytest.mark.parametrize("token", list(string.ascii_lowercase) + ['ä', 'ö', 'ü'], ids=lambda c: f'token_{c}')
def test_de_normal_mode(token: str):
    language = Language.GERMAN
    mode = GameMode.NORMAL

    assert language.value.score_threshold[mode] <= language.value.first_token_scores[mode][token], f'failed for {token=}'


@pytest.mark.parametrize("token", ["ß"], ids=lambda c: f'token_{c}')
def test_de_normal_mode_expect_invalid(token: str):
    language = Language.GERMAN
    mode = GameMode.NORMAL

    assert language.value.score_threshold[mode] > language.value.first_token_scores[mode][token], f'failed for {token=}'


@pytest.mark.parametrize("token", [
    "en", "an", "es", "it", "uf", "us", "ig", "ut", "om", "eg"
], ids=lambda c: f'token_{c}')
def test_de_hard_mode_expect_valid(token: str):
    language = Language.GERMAN
    mode = GameMode.HARD

    assert language.value.score_threshold[mode] <= language.value.first_token_scores[mode][token], f'failed for {token=}'

@pytest.mark.parametrize("token", [
    "ie", "nd", "ss", "nt", "ns", "tz", "hl", "rg", "ms", "hs", "ff", "rb", "ld", "ür", "eß", "ng", "hr", "gs"
], ids=lambda c: f'token_{c}')
def test_de_hard_mode_expect_invalid(token: str):
    language = Language.GERMAN
    mode = GameMode.HARD

    assert language.value.score_threshold[mode] > language.value.first_token_scores[mode][token], f'failed for {token=}'
