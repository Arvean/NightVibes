from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    RegisterView,
    CustomTokenObtainPairView,
    UserProfileView,
    FriendRequestViewSet,
    UserFriendsView,
    FriendRequestListCreateView,
    VenueListView,
    VenueDetailView,
    CheckInListView,
    CheckInDetailView,
    VenueRatingView,
    NearbyFriendsView,
)

router = DefaultRouter()
router.register(r'friend-requests', FriendRequestViewSet, basename='friend-request')
router.register(r'pings', MeetupPingViewSet, basename='ping')

# The following URLs will be automatically generated:
# - GET /api/pings/ - List all pings for the current user
# - POST /api/pings/ - Create a new ping
# - GET /api/pings/{id}/ - Retrieve a specific ping
# - PUT /api/pings/{id}/ - Update a ping
# - DELETE /api/pings/{id}/ - Delete a ping
# - POST /api/pings/{id}/accept/ - Accept a ping
# - POST /api/pings/{id}/decline/ - Decline a ping

app_name = 'nightvibes'

urlpatterns = [
    path('api/', include(router.urls)),
    path('api/friends/', UserFriendsView.as_view(), name='user-friends'),
    
    # Authentication URLs
    path('api/auth/register/', RegisterView.as_view(), name='register'),
    path('api/auth/login/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # User and Profile URLs
    path('api/profiles/', UserProfileListView.as_view(), name='profile-list'),
    path('api/profiles/<int:pk>/', UserProfileDetailView.as_view(), name='profile-detail'),
    path('api/friend-requests/', FriendRequestListView.as_view(), name='friend-request-list'),
    path('api/friend-requests/<int:pk>/', FriendRequestDetailView.as_view(), name='friend-request-detail'),
    path('api/friends/nearby/', NearbyFriendsView.as_view(), name='nearby-friends'),

    # Venue URLs
    path('api/venues/', VenueListView.as_view(), name='venue-list'),
    path('api/venues/<int:pk>/', VenueDetailView.as_view(), name='venue-detail'),
    path('api/venues/<int:pk>/current-vibe/', 
         VenueDetailView.as_view({'get': 'current_vibe'}), name='venue-current-vibe'),
    
    # Check-in URLs
    path('api/checkins/', CheckInListView.as_view(), name='checkin-list'),
    path('api/checkins/<int:pk>/', CheckInDetailView.as_view(), name='checkin-detail'),
    
    # Rating URLs
    path('api/ratings/', VenueRatingView.as_view(), name='venue-ratings'),

]