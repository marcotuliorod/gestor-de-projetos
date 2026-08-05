from rest_framework.routers import DefaultRouter

from .views import TaskRunViewSet

router = DefaultRouter()
router.register(r"task-runs", TaskRunViewSet, basename="task-run")

urlpatterns = router.urls
