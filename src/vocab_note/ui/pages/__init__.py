"""사이드바로 전환되는 본문 페이지들. 각 페이지는 서비스 함수만 호출합니다."""

from .quiz_page import QuizPage
from .review_page import ReviewPage
from .settings_page import SettingsPage
from .stats_page import StatsPage

__all__ = ["QuizPage", "ReviewPage", "SettingsPage", "StatsPage"]
