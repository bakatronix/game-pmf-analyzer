import re
from collections import Counter
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

analyzer = SentimentIntensityAnalyzer()

GAMING_TERMS = {
    "addictive", "fun", "boring", "grindy", "repetitive", "polished",
    "buggy", "broken", "masterpiece", "unique", "generic", "short",
    "long", "difficult", "easy", "deep", "shallow", "beautiful",
    "ugly", "smooth", "clunky", "responsive", "laggy", "optimized",
    "unoptimized", "atmospheric", "immersive", "bland", "creative",
    "innovative", "classic", "fresh", "stale", "rewarding",
    "frustrating", "satisfying", "disappointing", "overhyped",
    "underrated", "overpriced", "worth", "refunded", "crashing",
    "performance", "story", "gameplay", "graphics", "soundtrack",
    "controls", "replayable", "content", "update", "dev", "developer",
    "early access", "unfinished", "promising", "abandoned",
}

STOP_WORDS = {"the", "a", "an", "is", "was", "are", "were", "be", "been",
              "being", "have", "has", "had", "do", "does", "did", "will",
              "would", "could", "can", "may", "might", "shall", "should",
              "i", "me", "my", "we", "our", "you", "your", "he", "she",
              "it", "its", "they", "them", "their", "this", "that", "these",
              "those", "in", "on", "at", "to", "for", "of", "with", "by",
              "from", "and", "or", "but", "not", "no", "so", "if", "than",
              "then", "just", "also", "very", "too", "really", "all", "some",
              "more", "game", "play", "like", "get", "make", "one", "time",
              "hour", "hours", "much", "even", "still", "good", "great",
              "bad", "well", "way", "people", "say", "know", "think",
              "pretty", "lot", "ok", "okay", "thing", "things", "kind",
              "sort", "yet", "quite", "decent", "imo", "imho",
              }


def extract_bigrams(text: str) -> list[str]:
    words = re.findall(r'\b[a-z]+\b', text.lower())
    words = [w for w in words if w not in STOP_WORDS and len(w) > 2]
    bigrams = []
    for i in range(len(words) - 1):
        bigram = f"{words[i]} {words[i+1]}"
        if not any(sw in bigram.split() for sw in ["the", "and", "for"]):
            bigrams.append(bigram)
    return bigrams


def analyze_reviews(reviews: list[dict]) -> dict:
    if not reviews:
        return {
            "compound_score": 0.0,
            "top_keywords": [],
            "sentiment_distribution": {"positive": 0, "neutral": 0, "negative": 0},
        }

    scores = []
    all_bigrams = []
    pos_count = 0
    neu_count = 0
    neg_count = 0

    for review in reviews:
        text = review.get("review", "")
        if not text:
            continue

        vs = analyzer.polarity_scores(text)
        compound = vs["compound"]
        scores.append(compound)

        if compound >= 0.05:
            pos_count += 1
        elif compound <= -0.05:
            neg_count += 1
        else:
            neu_count += 1

        all_bigrams.extend(extract_bigrams(text))

    avg_compound = sum(scores) / len(scores) if scores else 0.0
    total = len(scores) or 1

    bigram_counter = Counter(all_bigrams)
    top_bigrams = [{"keyword": kw, "count": c} for kw, c in bigram_counter.most_common(15)
                   if kw in GAMING_TERMS or any(t in kw for t in GAMING_TERMS)][:10]

    single_words = []
    for review in reviews:
        words = re.findall(r'\b[a-z]+\b', review.get("review", "").lower())
        single_words.extend([w for w in words if w in GAMING_TERMS and w not in STOP_WORDS])

    word_counter = Counter(single_words)
    top_words = [{"keyword": kw, "count": c}
                 for kw, c in word_counter.most_common(10)]

    combined_keywords = top_bigrams + top_words
    seen = set()
    unique_keywords = []
    for kw in combined_keywords:
        if kw["keyword"] not in seen:
            seen.add(kw["keyword"])
            unique_keywords.append(kw)

    return {
        "compound_score": round(avg_compound, 3),
        "top_keywords": unique_keywords[:12],
        "sentiment_distribution": {
            "positive": round(pos_count / total * 100, 1),
            "neutral": round(neu_count / total * 100, 1),
            "negative": round(neg_count / total * 100, 1),
        },
    }
