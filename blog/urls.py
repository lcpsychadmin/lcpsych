from django.urls import path

from .views import (
    ManagePostsView,
    PostDetailView,
    PostCreateView,
    PostEditView,
    PostAIGenerateView,
    PostAITrendsView,
    PostDeleteView,
    PublicPostListView,
)

app_name = 'blog'

urlpatterns = [
    path('', PublicPostListView.as_view(), name='list'),
    path('manage/', ManagePostsView.as_view(), name='manage'),
    path('create/', PostCreateView.as_view(), name='create'),
    path('manage/<int:pk>/edit/', PostEditView.as_view(), name='edit'),
    path('manage/<int:pk>/delete/', PostDeleteView.as_view(), name='delete'),
    path('generate/', PostAIGenerateView.as_view(), name='generate'),
    path('ideas/', PostAITrendsView.as_view(), name='ideas'),
    path('<slug:slug>/', PostDetailView.as_view(), name='detail'),
]
