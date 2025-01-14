# Django imports
from django.contrib.auth.models import User
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.geos import Point
from django.db.models import Count, Q
from django.utils import timezone

# Rest Framework imports
from rest_framework import generics, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

# Local imports
from .models import (
    CheckIn,
    FriendRequest,
    UserProfile,
    Venue,
    VenueRating
)
from .serializers import (
    CheckInSerializer,
    FriendRequestSerializer,
    UserProfileSerializer,
    UserSerializer,
    VenueRatingSerializer,
    VenueSerializer
)

class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = [permissions.AllowAny]
    serializer_class = UserSerializer

    def perform_create(self, serializer):
        user = serializer.save()
        UserProfile.objects.create(user=user)

class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = UserSerializer

class UserProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user.profile

class FriendRequestListCreateView(generics.ListCreateAPIView):
    serializer_class = FriendRequestSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return FriendRequest.objects.filter(
            models.Q(sender=user) | models.Q(receiver=user)
        )

    def perform_create(self, serializer):
        serializer.save(sender=self.request.user)

class FriendRequestViewSet(viewsets.ModelViewSet):
    serializer_class = FriendRequestSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = FriendRequest.objects.all()

    def get_queryset(self):
        user = self.request.user
        return FriendRequest.objects.filter(
            models.Q(sender=user) | models.Q(receiver=user)
        )

    @action(detail=True, methods=['POST'])
    def accept(self, request, pk=None):
        friend_request = self.get_object()
        
        if request.user != friend_request.receiver:
            return Response(
                {"error": "Only the receiver can accept friend requests"},
                status=status.HTTP_403_FORBIDDEN
            )
            
        if friend_request.status != 'pending':
            return Response(
                {"error": "Only pending requests can be accepted"},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        friend_request.accept()
        return Response({"status": "Friend request accepted"})

    @action(detail=True, methods=['POST'])
    def reject(self, request, pk=None):
        friend_request = self.get_object()
        reason = request.data.get('reason', '')
        
        if request.user != friend_request.receiver:
            return Response(
                {"error": "Only the receiver can reject friend requests"},
                status=status.HTTP_403_FORBIDDEN
            )
            
        if friend_request.status != 'pending':
            return Response(
                {"error": "Only pending requests can be rejected"},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        friend_request.reject(reason=reason)
        return Response({"status": "Friend request rejected"})

    @action(detail=True, methods=['POST'])
    def cancel(self, request, pk=None):
        friend_request = self.get_object()
        
        if request.user != friend_request.sender:
            return Response(
                {"error": "Only the sender can cancel friend requests"},
                status=status.HTTP_403_FORBIDDEN
            )
            
        if friend_request.status != 'pending':
            return Response(
                {"error": "Only pending requests can be canceled"},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        friend_request.cancel()
        return Response({"status": "Friend request canceled"})

class UserFriendsView(generics.RetrieveAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_object(self):
        return self.request.user.userprofile

class VenueListView(generics.ListCreateAPIView):
    serializer_class = VenueSerializer
    permission_classes = [permissions.AllowAny]
    filterset_fields = ['category']
    
    def get_queryset(self):
        queryset = Venue.objects.all()
        
        lat = self.request.query_params.get('latitude')
        lng = self.request.query_params.get('longitude')
        radius = float(self.request.query_params.get('radius', 5000))
        
        if lat and lng:
            user_location = Point(float(lng), float(lat), srid=4326)
            queryset = queryset.annotate(
                distance=Distance('location', user_location)
            ).filter(distance__lte=radius)
            
            # Optimize query with indexing
            queryset = queryset.select_related('location')\
                              .prefetch_related('ratings')\
                              .order_by('distance')
        
        return queryset

class VenueDetailView(generics.RetrieveUpdateAPIView):
    queryset = Venue.objects.all()
    serializer_class = VenueSerializer
    permission_classes = [permissions.AllowAny]

    def get_current_vibe(self, request, *args, **kwargs):
        venue = self.get_object()
        recent_checkins = CheckIn.objects.filter(
            venue=venue,
            timestamp__gte=timezone.now() - timezone.timedelta(hours=2)
        )
        
        if not recent_checkins.exists():
            return Response({
                'vibe': 'Unknown',
                'checkins_count': 0
            })
            
        vibe_counts = recent_checkins.values('vibe_rating').annotate(
            count=Count('id')
        ).order_by('-count')
        
        return Response({
            'vibe': vibe_counts[0]['vibe_rating'],
            'checkins_count': recent_checkins.count()
        })

class CheckInListView(generics.ListCreateAPIView):
    serializer_class = CheckInSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Get check-ins from the user and their friends
        user_profile = self.request.user.profile
        friend_ids = user_profile.friends.values_list('id', flat=True)
        
        return CheckIn.objects.filter(
            Q(user=self.request.user) | Q(user_id__in=friend_ids)
        ).order_by('-timestamp')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

class CheckInDetailView(generics.RetrieveDestroyAPIView):
    serializer_class = CheckInSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return CheckIn.objects.filter(user=self.request.user)

class VenueRatingView(generics.ListCreateAPIView):
    serializer_class = VenueRatingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        venue_id = self.request.query_params.get('venue_id')
        if venue_id:
            return VenueRating.objects.filter(venue_id=venue_id)
        return VenueRating.objects.none()

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

class NearbyFriendsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        lat = request.query_params.get('latitude')
        lng = request.query_params.get('longitude')
        radius = request.query_params.get('radius', 1000)  # Default 1km radius

        if not (lat and lng):
            return Response(
                {'error': 'Location parameters required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        user_location = Point(float(lng), float(lat), srid=4326)
        friend_ids = request.user.profile.friends.values_list('id', flat=True)

        nearby_friends = CheckIn.objects.filter(
            user_id__in=friend_ids,
            timestamp__gte=timezone.now() - timezone.timedelta(hours=3)
        ).annotate(
            distance=Distance('venue__location', user_location)
        ).filter(distance__lte=radius).select_related('user', 'venue')

        return Response({
            'nearby_friends': CheckInSerializer(nearby_friends, many=True).data
        })

class MeetupPingViewSet(viewsets.ModelViewSet):
    serializer_class = MeetupPingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return MeetupPing.objects.filter(
            Q(sender=user) | Q(receiver=user)
        ).select_related('sender', 'receiver', 'venue')

    def perform_create(self, serializer):
        serializer.save(sender=self.request.user)

    @action(detail=True, methods=['POST'])
    def accept(self, request, pk=None):
        ping = self.get_object()
        
        if request.user != ping.receiver:
            return Response(
                {"error": "Only the receiver can accept pings"},
                status=status.HTTP_403_FORBIDDEN
            )
            
        if ping.status != 'pending':
            return Response(
                {"error": "Only pending pings can be accepted"},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        if ping.is_expired:
            ping.mark_expired()
            return Response(
                {"error": "This ping has expired"},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        ping.status = 'accepted'
        ping.response_message = request.data.get('message', '')
        ping.save()
        
        return Response({
            "status": "Ping accepted",
            "data": MeetupPingSerializer(ping).data
        })

    @action(detail=True, methods=['POST'])
    def decline(self, request, pk=None):
        ping = self.get_object()
        
        if request.user != ping.receiver:
            return Response(
                {"error": "Only the receiver can decline pings"},
                status=status.HTTP_403_FORBIDDEN
            )
            
        if ping.status != 'pending':
            return Response(
                {"error": "Only pending pings can be declined"},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        ping.status = 'declined'
        ping.response_message = request.data.get('message', '')
        ping.save()
        
        return Response({
            "status": "Ping declined",
            "data": MeetupPingSerializer(ping).data
        })