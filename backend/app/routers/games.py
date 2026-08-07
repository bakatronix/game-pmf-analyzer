from fastapi import APIRouter, HTTPException
from app.models.schemas import GameRequest, PMFReport, SurveyResponse, SurveyResult
from app.services.steam import (
    get_game_name, get_genres, get_reviews, get_player_count,
    get_achievement_percentages, get_estimated_owners,
    get_playtime_breakdown_from_reviews, get_ccu_history,
)
from app.services.sentiment import analyze_reviews
from app.services.pmf_scorer import compute_pmf_score

router = APIRouter(prefix="/api", tags=["games"])

surveys_store: dict[str, list[str]] = {}


@router.post("/analyze", response_model=dict)
async def analyze_game(req: GameRequest):
    app_id = req.app_id

    try:
        game_name = await get_game_name(app_id)
        genres = await get_genres(app_id)

        reviews_data = await get_reviews(app_id)
        all_reviews = reviews_data.get("reviews", [])
        recent_reviews = reviews_data.get("recent_reviews", [])

        playtime = await get_playtime_breakdown_from_reviews(all_reviews)
        median_minutes = playtime.get("median_minutes", 0)

        total_reviews = reviews_data.get("total", 0)
        positive = reviews_data.get("positive", 0)
        negative = reviews_data.get("negative", 0)
        review_score = (positive / total_reviews * 100) if total_reviews > 0 else 0

        recent_total = reviews_data.get("recent_total", 0)
        recent_positive = reviews_data.get("recent_positive", 0)
        recent_review_score = (recent_positive / recent_total * 100) if recent_total > 0 else review_score

        sentiment = analyze_reviews(all_reviews)

        achievements = await get_achievement_percentages(app_id)
        achievement_list = achievements.get("achievements", [])
        achievement_avg = (sum(float(a.get("percent", 0)) for a in achievement_list) /
                           max(len(achievement_list), 1))

        ccu = await get_ccu_history(app_id)
        ccu_peak = ccu.get("peak", 0)
        ccu_current = ccu.get("current", 0)

        estimated_owners = await get_estimated_owners(app_id)

        if recent_review_score > review_score + 5:
            trend = "rising"
        elif recent_review_score > review_score + 1:
            trend = "improving"
        elif recent_review_score >= review_score - 1:
            trend = "stable"
        elif recent_review_score >= review_score - 5:
            trend = "declining"
        else:
            trend = "falling"

        review_info = {
            "total": total_reviews,
            "positive": positive,
            "negative": negative,
            "score": round(review_score, 1),
            "recent_total": recent_total,
            "recent_positive": recent_positive,
            "recent_negative": reviews_data.get("recent_negative", 0),
            "recent_score": round(recent_review_score, 1),
            "trend": trend,
        }

        pmf_result = compute_pmf_score(
            game_name=game_name,
            genres=genres,
            median_playtime_minutes=median_minutes,
            review_score=review_score,
            recent_review_score=recent_review_score,
            total_reviews=total_reviews,
            recent_reviews_total=recent_total,
            compound_sentiment=sentiment["compound_score"],
            positive_sentiment_pct=sentiment["sentiment_distribution"]["positive"],
            achievement_avg=achievement_avg,
            ccu_peak=ccu_peak,
            ccu_current=ccu_current,
            estimated_owners_str=estimated_owners,
            playtime_buckets=playtime,
        )

        return {
            "app_id": app_id,
            "game_name": game_name,
            "pmf_score": pmf_result["pmf_score"],
            "pmf_label": pmf_result["pmf_label"],
            "scores": pmf_result["scores"],
            "playtime": {
                "under_1h": playtime.get("under_1h", 0),
                "one_to_10h": playtime.get("one_to_10h", 0),
                "over_10h": playtime.get("over_10h", 0),
            },
            "median_playtime_minutes": median_minutes,
            "reviews": review_info,
            "sentiment": {
                "compound_score": sentiment["compound_score"],
                "top_keywords": sentiment["top_keywords"],
                "sentiment_distribution": sentiment["sentiment_distribution"],
            },
            "ccu_peak": ccu_peak,
            "ccu_current": ccu_current,
            "estimated_owners": estimated_owners,
            "achievement_completion_avg": round(achievement_avg, 1),
            "genres": genres,
            "genre_benchmark": pmf_result["genre_benchmark"],
            "recommendations": pmf_result["recommendations"],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.get("/survey/{game_name}", response_model=dict)
async def get_survey_link(game_name: str):
    return {
        "game_name": game_name,
        "survey_link": f"/survey/{game_name}",
        "question": "How would you feel if you could no longer play this game?",
        "options": ["Very disappointed", "Somewhat disappointed", "Not disappointed"],
    }


@router.post("/survey/{game_name}/respond", response_model=dict)
async def submit_survey(game_name: str, resp: SurveyResponse):
    if game_name not in surveys_store:
        surveys_store[game_name] = []
    surveys_store[game_name].append(resp.response)
    return {"message": "Response recorded", "total": len(surveys_store[game_name])}


@router.get("/survey/{game_name}/results", response_model=SurveyResult)
async def get_survey_results(game_name: str):
    responses = surveys_store.get(game_name, [])
    total = len(responses)
    if total == 0:
        return SurveyResult(
            total_responses=0,
            very_disappointed=0,
            somewhat_disappointed=0,
            not_disappointed=0,
            very_disappointed_pct=0,
            pmf_achieved=False,
        )

    very = sum(1 for r in responses if r.lower().startswith("very"))
    somewhat = sum(1 for r in responses if r.lower().startswith("somewhat"))
    not_d = sum(1 for r in responses if r.lower().startswith("not"))

    pct = round(very / total * 100, 1)
    return SurveyResult(
        total_responses=total,
        very_disappointed=very,
        somewhat_disappointed=somewhat,
        not_disappointed=not_d,
        very_disappointed_pct=pct,
        pmf_achieved=pct >= 40,
    )
