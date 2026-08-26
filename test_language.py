import string

import pytest

from consts import GameMode
from language import Language

### ENGLISH

@pytest.mark.parametrize("token", list(string.ascii_lowercase), ids=lambda c: f'token_{c}')
def test_en_normal_mode(token: str):
    language = Language.ENGLISH
    mode = GameMode.NORMAL

    assert language.value.first_token_scores[mode][token] >= language.value.score_threshold[mode], f'failed for {token=}'


@pytest.mark.parametrize("token", [
    "en", "an", "es", "ey", "ow", "um", "ry", "ay",
    # boundary, backed by common vocabulary
    "oy", "oe", "oo", "eb", "ej", "gn", "oi", "iv", "yi", "og",
], ids=lambda c: f'token_{c}')
def test_en_hard_mode_expect_valid(token: str):
    language = Language.ENGLISH
    mode = GameMode.HARD

    assert language.value.first_token_scores[mode][token] >= language.value.score_threshold[mode], f'failed for {token=}'


@pytest.mark.parametrize("token", [
    "nd", "ns", "ld", "ss", "ds", "ls", "ms", "ys", "ws", "ck", "ht", "rm", "lt", "ft", "ie", "ng",
    # boundary, backed only by proper names, so plentiful in a wikipedia corpus but not playable
    "hw", "vr", "ik", "xa", "ip", "tj", "iw", "jh", "gw", "vl", "ek", "iz", "ao", "sr", "sv", "kw",
], ids=lambda c: f'token_{c}')
def test_en_hard_mode_expect_invalid(token: str):
    language = Language.ENGLISH
    mode = GameMode.HARD

    assert language.value.first_token_scores[mode][token] < language.value.score_threshold[mode], f'failed for {token=}'


### GERMAN

@pytest.mark.parametrize("token", list(string.ascii_lowercase) + ['ä', 'ö', 'ü'], ids=lambda c: f'token_{c}')
def test_de_normal_mode(token: str):
    language = Language.GERMAN
    mode = GameMode.NORMAL

    assert language.value.first_token_scores[mode][token] >= language.value.score_threshold[mode], f'failed for {token=}'


@pytest.mark.parametrize("token", ["ß"], ids=lambda c: f'token_{c}')
def test_de_normal_mode_expect_invalid(token: str):
    language = Language.GERMAN
    mode = GameMode.NORMAL

    assert language.value.first_token_scores[mode][token] < language.value.score_threshold[mode], f'failed for {token=}'


@pytest.mark.parametrize("token", [
    "en", "an", "es", "it", "uf", "us", "ig", "ut", "om", "eg",
    # boundary, backed by common vocabulary
    "fj", "pn", "ds", "ax", "ew", "ih", "ic", "ek", "oz", "gn", "aa", "aq", "io",
    # boundary, umlaut-initial, backed by common vocabulary
    "pü", "ör", "vä", "äs", "äq", "zö", "äl", "äg", "än", "sö", "äh",
], ids=lambda c: f'token_{c}')
def test_de_hard_mode_expect_valid(token: str):
    language = Language.GERMAN
    mode = GameMode.HARD

    assert language.value.first_token_scores[mode][token] >= language.value.score_threshold[mode], f'failed for {token=}'


@pytest.mark.parametrize("token", [
    "ie", "nd", "ss", "nt", "ns", "tz", "hl", "rg", "ms", "hs", "ff", "rb", "ld", "ür", "eß", "ng", "hr", "gs",
    # boundary, backed only by proper names or archaic spellings
    "cö", "jö", "yv", "dw", "kw", "bh", "gm", "iu", "zh", "iw", "gw", "vr", "xi", "ay", "ry", "sv", "wy", "kh", "iv",
    "ky",
], ids=lambda c: f'token_{c}')
def test_de_hard_mode_expect_invalid(token: str):
    language = Language.GERMAN
    mode = GameMode.HARD

    assert language.value.first_token_scores[mode][token] < language.value.score_threshold[mode], f'failed for {token=}'
