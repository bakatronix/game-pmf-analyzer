GENRE_BENCHMARKS = {
    "Action": {
        "median_playtime_hours": 12.0,
        "avg_review_score": 82.0,
        "avg_ccu": 1200,
        "avg_total_reviews": 5000,
        "avg_achievement_completion": 35.0,
    },
    "Adventure": {
        "median_playtime_hours": 8.0,
        "avg_review_score": 85.0,
        "avg_ccu": 600,
        "avg_total_reviews": 3000,
        "avg_achievement_completion": 40.0,
    },
    "RPG": {
        "median_playtime_hours": 25.0,
        "avg_review_score": 83.0,
        "avg_ccu": 1500,
        "avg_total_reviews": 8000,
        "avg_achievement_completion": 30.0,
    },
    "Strategy": {
        "median_playtime_hours": 20.0,
        "avg_review_score": 80.0,
        "avg_ccu": 800,
        "avg_total_reviews": 4000,
        "avg_achievement_completion": 28.0,
    },
    "Simulation": {
        "median_playtime_hours": 18.0,
        "avg_review_score": 81.0,
        "avg_ccu": 700,
        "avg_total_reviews": 3500,
        "avg_achievement_completion": 32.0,
    },
    "Racing": {
        "median_playtime_hours": 6.0,
        "avg_review_score": 79.0,
        "avg_ccu": 300,
        "avg_total_reviews": 1500,
        "avg_achievement_completion": 38.0,
    },
    "Sports": {
        "median_playtime_hours": 10.0,
        "avg_review_score": 78.0,
        "avg_ccu": 400,
        "avg_total_reviews": 2000,
        "avg_achievement_completion": 36.0,
    },
    "Casual": {
        "median_playtime_hours": 4.0,
        "avg_review_score": 84.0,
        "avg_ccu": 500,
        "avg_total_reviews": 2500,
        "avg_achievement_completion": 45.0,
    },
    "Roguelike": {
        "median_playtime_hours": 30.0,
        "avg_review_score": 85.0,
        "avg_ccu": 1000,
        "avg_total_reviews": 6000,
        "avg_achievement_completion": 25.0,
    },
    "Horror": {
        "median_playtime_hours": 5.0,
        "avg_review_score": 82.0,
        "avg_ccu": 350,
        "avg_total_reviews": 2000,
        "avg_achievement_completion": 42.0,
    },
    "Puzzle": {
        "median_playtime_hours": 5.0,
        "avg_review_score": 86.0,
        "avg_ccu": 200,
        "avg_total_reviews": 1500,
        "avg_achievement_completion": 44.0,
    },
    "Platformer": {
        "median_playtime_hours": 6.0,
        "avg_review_score": 83.0,
        "avg_ccu": 400,
        "avg_total_reviews": 2000,
        "avg_achievement_completion": 40.0,
    },
    "FPS": {
        "median_playtime_hours": 15.0,
        "avg_review_score": 80.0,
        "avg_ccu": 2000,
        "avg_total_reviews": 10000,
        "avg_achievement_completion": 33.0,
    },
    "Indie": {
        "median_playtime_hours": 6.0,
        "avg_review_score": 84.0,
        "avg_ccu": 500,
        "avg_total_reviews": 2500,
        "avg_achievement_completion": 38.0,
    },
    "Default": {
        "median_playtime_hours": 10.0,
        "avg_review_score": 82.0,
        "avg_ccu": 600,
        "avg_total_reviews": 3000,
        "avg_achievement_completion": 36.0,
    },
}


def get_benchmark_for_genres(genres: list[str]) -> dict:
    for genre in genres:
        if genre in GENRE_BENCHMARKS:
            b = GENRE_BENCHMARKS[genre]
            return {
                "genre": genre,
                "median_playtime_hours": b["median_playtime_hours"],
                "avg_review_score": b["avg_review_score"],
                "avg_ccu": b["avg_ccu"],
                "avg_total_reviews": b["avg_total_reviews"],
                "avg_achievement_completion": b["avg_achievement_completion"],
            }
    b = GENRE_BENCHMARKS["Default"]
    return {
        "genre": "Indie (default)",
        "median_playtime_hours": b["median_playtime_hours"],
        "avg_review_score": b["avg_review_score"],
        "avg_ccu": b["avg_ccu"],
        "avg_total_reviews": b["avg_total_reviews"],
        "avg_achievement_completion": b["avg_achievement_completion"],
    }
