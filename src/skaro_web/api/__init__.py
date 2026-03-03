"""Skaro Web API — router registry."""

from skaro_web.api.architecture import router as architecture_router
from skaro_web.api.config import router as config_router
from skaro_web.api.constitution import router as constitution_router
from skaro_web.api.devplan import router as devplan_router
from skaro_web.api.import_project import router as import_router
from skaro_web.api.status import router as status_router
from skaro_web.api.tasks import router as tasks_router

all_routers = [
    status_router,
    constitution_router,
    architecture_router,
    devplan_router,
    import_router,
    tasks_router,
    config_router,
]

__all__ = ["all_routers"]
