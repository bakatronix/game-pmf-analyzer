from app.data.benchmarks import get_benchmark_for_genres


def clamp(value: float, low: float = 0, high: float = 100) -> float:
    return max(low, min(high, value))


def compute_pmf_score(
    game_name: str,
    genres: list[str],
    median_playtime_minutes: int,
    review_score: float,
    recent_review_score: float,
    total_reviews: int,
    recent_reviews_total: int,
    compound_sentiment: float,
    positive_sentiment_pct: float,
    achievement_avg: float,
    ccu_peak: int,
    ccu_current: int,
    estimated_owners_str: str,
    playtime_buckets: dict,
) -> dict:
    benchmark = get_benchmark_for_genres(genres)
    bm_playtime_hours = benchmark["median_playtime_hours"]
    bm_review_score = benchmark["avg_review_score"]
    bm_ccu = benchmark["avg_ccu"]
    bm_total_reviews = benchmark["avg_total_reviews"]
    bm_achievement = benchmark["avg_achievement_completion"]

    median_hours = median_playtime_minutes / 60.0

    playtime_ratio = median_hours / bm_playtime_hours if bm_playtime_hours > 0 else 1.0
    engagement_playtime = clamp(playtime_ratio * 50)

    under_1h_pct = playtime_buckets.get("under_1h", 0)
    if under_1h_pct > 40:
        engagement_playtime *= 0.5
    elif under_1h_pct > 25:
        engagement_playtime *= 0.75

    engagement_achievements = clamp(achievement_avg / bm_achievement * 30) if bm_achievement > 0 else 15

    over_10h_pct = playtime_buckets.get("over_10h", 0)
    review_depth = clamp(over_10h_pct * 0.4, 0, 20)
    if median_hours > bm_playtime_hours * 1.5:
        review_depth = 20

    engagement = clamp(engagement_playtime + engagement_achievements + review_depth)
    engagement = round(engagement, 1)

    review_score_norm = clamp(review_score / bm_review_score * 40) if bm_review_score > 0 else 20
    if review_score >= 95:
        review_score_norm = 40
    elif review_score >= 90:
        review_score_norm = 36
    elif review_score >= 85:
        review_score_norm = 32
    elif review_score >= 80:
        review_score_norm = 28
    elif review_score >= 70:
        review_score_norm = 20
    else:
        review_score_norm = clamp(review_score / 100 * 25)

    diff = recent_review_score - review_score
    if diff >= 5:
        trend_score = 30
        trend_text = "rising"
    elif diff >= 2:
        trend_score = 25
        trend_text = "improving"
    elif diff >= -2:
        trend_score = 15
        trend_text = "stable"
    elif diff >= -5:
        trend_score = 10
        trend_text = "declining"
    else:
        trend_score = 0
        trend_text = "falling"

    sentiment_score = clamp((compound_sentiment + 1) / 2 * 30)
    if positive_sentiment_pct > 70:
        sentiment_score = clamp(sentiment_score + 5, 0, 30)

    satisfaction = clamp(review_score_norm + trend_score + sentiment_score)
    satisfaction = round(satisfaction, 1)

    review_volume_score = clamp(total_reviews / bm_total_reviews * 40) if bm_total_reviews > 0 else 0
    if total_reviews > 10000:
        review_volume_score = 40
    elif total_reviews > 5000:
        review_volume_score = 35
    elif total_reviews > 1000:
        review_volume_score = 25
    elif total_reviews > 100:
        review_volume_score = 15
    else:
        review_volume_score = 5

    recent_review_ratio = recent_reviews_total / max(total_reviews, 1)
    if total_reviews < 50:
        velocity_score = clamp(recent_reviews_total * 2 / 100 * 30)
    else:
        velocity_benchmark = 0.05
        velocity_score = clamp((recent_review_ratio / velocity_benchmark) * 30)

    dominance = ccu_peak / bm_ccu if bm_ccu > 0 else 0
    ccu_score = clamp(dominance * 30)
    if ccu_peak > 10000:
        ccu_score = 30
    elif ccu_peak > 5000:
        ccu_score = 25
    elif ccu_peak > 1000:
        ccu_score = 20
    elif ccu_peak > 100:
        ccu_score = 10

    market_traction = clamp(review_volume_score + velocity_score + ccu_score)
    market_traction = round(market_traction, 1)

    overall = round(engagement * 0.40 + satisfaction * 0.35 + market_traction * 0.25)

    if overall >= 75:
        label = "PMF Achieved"
    elif overall >= 50:
        label = "Early Traction"
    else:
        label = "Pre-PMF"

    recommendations = _generate_recommendations(
        game_name, genres, median_hours, bm_playtime_hours,
        review_score, trend_text, compound_sentiment,
        achievement_avg, bm_achievement,
        total_reviews, ccu_peak, bm_ccu,
        under_1h_pct, over_10h_pct,
        engagement, satisfaction, market_traction,
    )

    return {
        "app_id": 0,
        "game_name": game_name,
        "pmf_score": overall,
        "pmf_label": label,
        "scores": {
            "engagement": engagement,
            "satisfaction": satisfaction,
            "market_traction": market_traction,
            "overall": overall,
        },
        "genres": genres,
        "genre_benchmark": benchmark,
        "recommendations": recommendations,
    }


def _generate_recommendations(
    game_name, genres, median_hours, bm_hours,
    review_score, trend_text, compound_sentiment,
    achievement_avg, bm_achievement,
    total_reviews, ccu_peak, bm_ccu,
    under_1h_pct, over_10h_pct,
    engagement, satisfaction, market_traction,
) -> list[dict]:
    recs = []

    if median_hours < bm_hours * 0.5 and median_hours > 0:
        recs.append({
            "category": "Engagement",
            "signal": "Low Median Playtime",
            "detail": f"Median playtime ({median_hours:.1f}h) is well below the {genres[0] if genres else 'genre'} benchmark ({bm_hours:.1f}h). Consider adding deeper progression, replayable modes, or post-game content.",
        })

    if under_1h_pct > 30:
        recs.append({
            "category": "Engagement",
            "signal": "High Early Drop-Off",
            "detail": f"{under_1h_pct:.0f}% of reviewers played under 1 hour. The first-time user experience may need improvement — consider a stronger tutorial, hook, or opening sequence.",
        })

    if over_10h_pct > 50:
        recs.append({
            "category": "Engagement",
            "signal": "Strong Deep Engagement",
            "detail": f"{over_10h_pct:.0f}% of players are investing 10+ hours. This is a powerful PMF signal — focus marketing on depth and replayability.",
        })

    if achievement_avg < bm_achievement * 0.5:
        recs.append({
            "category": "Engagement",
            "signal": "Low Achievement Completion",
            "detail": f"Average achievement completion ({achievement_avg:.1f}%) is below the genre benchmark ({bm_achievement:.1f}%). Consider rebalancing achievement difficulty or adding milestone-based achievements.",
        })

    if review_score < 70:
        recs.append({
            "category": "Satisfaction",
            "signal": "Low Review Score",
            "detail": f"Review score ({review_score:.0f}%) is below 70%. Prioritize bug fixes, performance improvements, and addressing the most common complaints from reviews.",
        })

    if trend_text in ("declining", "falling"):
        recs.append({
            "category": "Satisfaction",
            "signal": "Review Score Declining",
            "detail": "Recent reviews are trending downward. Investigate recent updates, community feedback, or potential review bombing. Swift communication can help stabilize sentiment.",
        })
    elif trend_text == "rising":
        recs.append({
            "category": "Satisfaction",
            "signal": "Review Score Rising",
            "detail": "Recent reviews are improving — whatever you changed is working. Amplify the positive momentum with patch note visibility and community engagement.",
        })

    if compound_sentiment < -0.1:
        recs.append({
            "category": "Satisfaction",
            "signal": "Negative Review Sentiment",
            "detail": "Review sentiment is predominantly negative. Read through the most common complaints and prioritize the top 3 issues in your next update.",
        })
    elif compound_sentiment > 0.3:
        recs.append({
            "category": "Satisfaction",
            "signal": "Strong Positive Sentiment",
            "detail": "Players love your game. Encourage them to leave Steam reviews and share with friends — organic word-of-mouth is your strongest growth lever right now.",
        })

    if total_reviews < 50:
        recs.append({
            "category": "Market Traction",
            "signal": "Low Review Volume",
            "detail": "Fewer than 50 reviews makes it hard to gauge PMF. Focus on discovery: participate in Steam festivals, reach out to content creators, and optimize your store page.",
        })

    if ccu_peak < 50:
        recs.append({
            "category": "Market Traction",
            "signal": "Low Concurrent Players",
            "detail": "Concurrent player counts are very low. Consider a free weekend, bundle deals, or a major content update to re-engage and attract players.",
        })

    if total_reviews > 500 and review_score >= 85:
        recs.append({
            "category": "Market Traction",
            "signal": "Strong Market Validation",
            "detail": "High review volume with a strong score indicates market traction. Consider DLC, localization, or platform expansion to grow your audience further.",
        })

    engagement_ok = engagement >= 50
    satisfaction_ok = satisfaction >= 50
    traction_ok = market_traction >= 50

    if engagement_ok and satisfaction_ok and traction_ok:
        recs.insert(0, {
            "category": "Overall",
            "signal": "Strong PMF Across All Lenses",
            "detail": "Your game is performing well across engagement, satisfaction, and market traction. Focus on scaling what works and expanding your reach.",
        })

    return recs
