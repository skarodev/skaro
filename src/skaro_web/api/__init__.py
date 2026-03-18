"""Skaro Web API — router registry."""

from skaro_web.api.analytics import router as analytics_router
from skaro_web.api.architecture import router as architecture_router
from skaro_web.api.autopilot import router as autopilot_router
from skaro_web.api.config import router as config_router
from skaro_web.api.constitution import router as constitution_router
from skaro_web.api.devplan import router as devplan_router
from skaro_web.api.feature import router as feature_router
from skaro_web.api.files import router as files_router
from skaro_web.api.git import router as git_router
from skaro_web.api.import_project import router as import_router
from skaro_web.api.review import router as review_router
from skaro_web.api.skills import router as skills_router
from skaro_web.api.status import router as status_router
from skaro_web.api.tasks import router as tasks_router

all_routers = [
    analytics_router,
    status_router,
    constitution_router,
    architecture_router,
    devplan_router,
    import_router,
    tasks_router,
    feature_router,
    review_router,
    config_router,
    git_router,
    autopilot_router,
    files_router,
    skills_router,
]

__all__ = ["all_routers"]
