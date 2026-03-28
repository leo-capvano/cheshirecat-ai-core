import re


# Common stopwords to strip from FTS queries (multilingual basics)
_STOPWORDS = frozenset(
    {
        # English
        "a",
        "an",
        "the",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "could",
        "should",
        "may",
        "might",
        "shall",
        "can",
        "of",
        "in",
        "to",
        "for",
        "with",
        "on",
        "at",
        "by",
        "from",
        "as",
        "into",
        "about",
        "between",
        "through",
        "during",
        "before",
        "after",
        "and",
        "but",
        "or",
        "nor",
        "not",
        "so",
        "yet",
        "both",
        "either",
        "neither",
        "it",
        "its",
        "this",
        "that",
        "these",
        "those",
        "i",
        "me",
        "my",
        "we",
        "our",
        "you",
        "your",
        "he",
        "him",
        "his",
        "she",
        "her",
        "they",
        "them",
        "their",
        "what",
        "which",
        "who",
        "whom",
        "how",
        "when",
        "where",
        "why",
        # Italian
        "il",
        "lo",
        "la",
        "le",
        "gli",
        "un",
        "uno",
        "una",
        "di",
        "del",
        "dello",
        "della",
        "dei",
        "degli",
        "delle",
        "da",
        "dal",
        "dallo",
        "dalla",
        "dai",
        "dagli",
        "dalle",
        "su",
        "sul",
        "sullo",
        "sulla",
        "sui",
        "sugli",
        "sulle",
        "per",
        "con",
        "tra",
        "fra",
        "che",
        "chi",
        "cui",
        "non",
        "è",
        "sono",
        "come",
        "mi",
        "ti",
        "si",
        "ci",
        "vi",
        "ne",
    }
)

_MIN_WORD_LENGTH = 2
# match alphanumeric words including accented chars
_WORD_RE = re.compile(r"[a-zA-Z0-9\u00C0-\u024F]+")
# match quoted phrases (websearch_to_tsquery treats these as consecutive-word searches)
_QUOTED_RE = re.compile(r'"([^"]+)"')


def extract_fts_keywords_from(text: str) -> str:
    """Extract keywords from natural language text for use with websearch_to_tsquery.

    Quoted phrases (e.g. ``"machine learning"``) are preserved intact so that
    ``websearch_to_tsquery`` applies a consecutive-word (phrase) search for them.
    Unquoted text is split into individual words, filtered for stopwords and
    minimum length, then everything is joined with ``OR``.

    Examples::

        >>> extract_fts_keywords_from('come funziona qdrant')
        'funziona OR qdrant'
        >>> extract_fts_keywords_from('"machine learning" models')
        '"machine learning" OR models'
        >>> extract_fts_keywords_from('"red queen" is the best')
        '"red queen" OR best'
        >>> extract_fts_keywords_from('"red" is the best "in the world" as always')
        '"red" "in the world" OR best OR always'

    Args:
        text: Natural language input (e.g. a user's chat message).

    Returns:
        A string ready for ``websearch_to_tsquery``, or an empty string
        if no keywords remain.
    """
    if not text:
        return ""

    # 1. Extract and preserve quoted phrases
    exact_search_keywords: list[str] = []
    for phrase in _QUOTED_RE.findall(text):
        stripped = phrase.strip()
        if stripped:
            exact_search_keywords.append(f'"{stripped}"')

    # 2. Remove quoted segments, then process remaining text as individual words
    search_keywords: list[str] = []
    remaining = _QUOTED_RE.sub("", text)
    words = _WORD_RE.findall(remaining)
    search_keywords.extend(w for w in words if len(w) > _MIN_WORD_LENGTH and w.lower() not in _STOPWORDS)

    keywords_in_or = " OR ".join(search_keywords)
    keywords_in_and = " ".join(exact_search_keywords)
    return " ".join(filter(None, [f"({keywords_in_or})", keywords_in_and]))


if __name__ == "__main__":
    f = extract_fts_keywords_from

    # -- Empty / blank input --
    assert f("") == "", f"empty string: {f('')!r}"
    assert f("   ") == "()", f"whitespace only: {f('   ')!r}"
    assert f("!@#$%^&*()") == "()", f"special chars only: {f('!@#$%^&*()')!r}"

    # -- All stopwords / all short words --
    assert f("is the are") == "()", f"only stopwords: {f('is the are')!r}"
    assert f("a I") == "()", f"only short words: {f('a I')!r}"
    assert f("THE Is ARE") == "()", f"stopwords case-insensitive: {f('THE Is ARE')!r}"

    # -- Single keyword --
    assert f("qdrant") == "(qdrant)", f"single keyword: {f('qdrant')!r}"

    # -- Unquoted text with stopwords --
    assert f("This is a test") == "(test)", f"one keyword among stopwords: {f('This is a test')!r}"
    assert (
        f("come funziona qdrant") == "(funziona OR qdrant)"
    ), f"Italian stopword filtered: {f('come funziona qdrant')!r}"
    assert (
        f("This is a test phrase for extracting keywords, including stopwords and short words like a and is")
        == "(test OR phrase OR extracting OR keywords OR including OR stopwords OR short OR words OR like)"
    )

    # -- Quoted phrases --
    assert f('"This is a test"') == '() "This is a test"', "only quoted phrase"
    assert f('"machine learning"') == '() "machine learning"', "single quoted phrase"
    assert f('"foo bar" "baz qux"') == '() "foo bar" "baz qux"', "multiple quoted, no unquoted"

    # -- Mixed quoted + unquoted --
    assert f('"machine learning" models') == '(models) "machine learning"', "quoted + unquoted"
    assert f('"red queen" is the best') == '(best) "red queen"', "quoted + stopwords + keyword"
    assert (
        f('"red" is the best "in the world" as always') == '(best OR always) "red" "in the world"'
    ), "multiple quoted + unquoted"
    assert f('descrivimi il controllo "XYZ"') == '(descrivimi OR controllo) "XYZ"', "Italian + alphanumeric quoted"
    assert (
        f('This is a "test phrase" for extracting keywords, including stopwords and short words like "a" and "is".')
        == '(extracting OR keywords OR including OR stopwords OR short OR words OR like) "test phrase" "a" "is"'
    )

    # -- Accented characters --
    assert f("café résumé naïve") == "(café OR résumé OR naïve)", f"accented: {f('café résumé naïve')!r}"

    # -- Numbers and alphanumeric --
    assert f("test123 42 a") == "(test123)", f"numbers: {f('test123 42 a')!r}"
    assert f("100 200 300") == "(100 OR 200 OR 300)", f"three-digit numbers: {f('100 200 300')!r}"

    # -- Unbalanced quotes (not matched by regex, treated as plain text) --
    assert f('he said "hello') == "(said OR hello)", "unbalanced quote"

    print("All tests passed!")
