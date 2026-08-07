from pydantic import BaseModel
from typing import Optional


class GameRequest(BaseModel):
    app_id: int


class PlaytimeBuckets(BaseModel):
    under_1h: float
    one_to_10h: float
    over_10h: float


class ReviewInfo(BaseModel):
    total: int
    positive: int
    negative: int
    score: float
    recent_total: int
    recent_positive: int
    recent_negative: int
    recent_score: float
    trend: str


class SentimentAnalysis(BaseModel):
    compound_score: float
    top_keywords: list[dict]
    sentiment_distribution: dict


class GenreBenchmark(BaseModel):
    genre: str
    median_playtime_hours: float
    avg_review_score: float
    avg_ccu: int
    avg_total_reviews: int
    avg_achievement_completion: float


class PMFScores(BaseModel):
    engagement: float
    satisfaction: float
    market_traction: float
    overall: int


class Recommendation(BaseModel):
    category: str
    signal: str
    detail: str


class PMFReport(BaseModel):
    app_id: int
    game_name: str
    pmf_score: int
    pmf_label: str
    scores: PMFScores
    playtime: PlaytimeBuckets
    median_playtime_minutes: int
    reviews: ReviewInfo
    sentiment: SentimentAnalysis
    ccu_peak: int
    ccu_current: int
    estimated_owners: Optional[str] = None
    achievement_completion_avg: float
    genres: list[str]
    genre_benchmark: GenreBenchmark
    recommendations: list[Recommendation]


class SurveyResponse(BaseModel):
    game_name: str
    response: str


class SurveyResult(BaseModel):
    total_responses: int
    very_disappointed: int
    somewhat_disappointed: int
    not_disappointed: int
    very_disappointed_pct: float
    pmf_achieved: bool
