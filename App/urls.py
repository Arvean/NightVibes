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
    MeetupPingViewSet,
    DeviceTokenViewSet,
    NotificationViewSet
)

# The following URLs will be automatically generated:
# - GET /api/pings/ - List all pings for the current user
# - POST /api/pings/ - Create a new ping
# - GET /api/pings/{id}/ - Retrieve a specific ping
# - PUT /api/pings/{id}/ - Update a ping
# - DELETE /api/pings/{id}/ - Delete a ping
# - POST /api/pings/{id}/accept/ - Accept a ping
# - POST /api/pings/{id}/decline/ - Decline a ping

# Add VenueDetailView to the router
router = DefaultRouter()
router.register(r'friend-requests', FriendRequestViewSet, basename='friend-request')
router.register(r'pings', MeetupPingViewSet, basename='ping')
router.register(r'venues', VenueDetailView, basename='venue')
router.register(r'device-tokens', DeviceTokenViewSet, basename='device-token')
router.register(r'notifications', NotificationViewSet, basename='notification')

urlpatterns = [
    # Include router URLs
    path('api/', include(router.urls)),
    
    # Authentication URLs
    path('api/auth/register/', RegisterView.as_view(), name='register'),
    path('api/auth/login/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # User and Profile URLs
    path('api/profile/', UserProfileView.as_view(), name='user-profile'),
    path('api/friends/', UserFriendsView.as_view(), name='user-friends'),
    path('api/friends/nearby/', NearbyFriendsView.as_view(), name='nearby-friends'),
    path('api/friend-requests/list/', FriendRequestListCreateView.as_view(), name='friend-request-list-create'),

    # Check-in URLs
    path('api/checkins/', CheckInListView.as_view(), name='checkin-list'),
    path('api/checkins/<int:pk>/', CheckInDetailView.as_view(), name='checkin-detail'),
    
    # Rating URLs
    path('api/ratings/', VenueRatingView.as_view(), name='venue-ratings'),

]