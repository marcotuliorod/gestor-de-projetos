from django.urls import path

from .views import BoardView, SnapshotHistoryView

urlpatterns = [
    path("board/", BoardView.as_view(), name="board"),
    path("snapshots/", SnapshotHistoryView.as_view(), name="snapshot-history"),
]
