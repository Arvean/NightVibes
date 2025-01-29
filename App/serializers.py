from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth.models import User
from django.contrib.gis.geos import Point
from django.core.cache import cache
from django.utils import timezone
from django.db.models import Count
from .models import UserProfile, FriendRequest, Venue, CheckIn, VenueRating, MeetupPing, DeviceToken, Notification

class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    
    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'password', 'first_name', 'last_name')
        read_only_fields = ('id',)
        
    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data.get('email', ''),
            password=validated_data['password'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', '')
        )
        return user
        
    def update(self, instance, validated_data):
        # Remove password from update operation if it exists
        if 'password' in validated_data:
            password = validated_data.pop('password')
            instance.set_password(password)
        return super().update(instance, validated_data)

class UserProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    latitude = serializers.FloatField(write_only=True, required=False)
    longitude = serializers.FloatField(write_only=True, required=False)
    current_location = serializers.SerializerMethodField()

    class Meta:
        model = UserProfile
        fields = ['id', 'username', 'email', 'bio', 'location_sharing',
                 'latitude', 'longitude', 'current_location', 'profile_picture']
        read_only_fields = ['id']

    def get_current_location(self, obj):
        """Returns the current location as a lat/lng dict if sharing is enabled"""
        if obj.location_sharing and obj.location:
            return {
                'latitude': obj.location.y,
                'longitude': obj.location.x
            }
        return None

    def validate(self, data):
        """Validate location data"""
        latitude = data.pop('latitude', None)
        longitude = data.pop('longitude', None)
        
        if latitude is not None and longitude is not None:
            data['location'] = Point(longitude, latitude)
        elif (latitude is not None) != (longitude is not None):
            raise serializers.ValidationError(
                "Both latitude and longitude must be provided together"
            )
            
        return data


    def validate_profile_picture(self, value):
        if value:
            # Validate file type
            valid_types = ['image/jpeg', 'image/png', 'image/gif']
            if value.content_type not in valid_types:
                raise serializers.ValidationError(
                    "Invalid file type. Only JPEG, PNG and GIF are allowed."
                )
            
            # Validate file size (5MB limit)
            if value.size > 5 * 1024 * 1024:
                raise serializers.ValidationError(
                    "File too large. Maximum size is 5MB."
                )
        return value

class FriendRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = FriendRequest
        fields = ['id', 'receiver', 'status', 'created_at']
        read_only_fields = ['id', 'status', 'created_at']

    def validate(self, data):
        if 'receiver' in data:
            if isinstance(data['receiver'], (int, str)):
                try:
                    data['receiver'] = UserProfile.objects.get(id=data['receiver'])
                except UserProfile.DoesNotExist:
                    raise serializers.ValidationError("Invalid receiver profile ID")

            # Get the sender's profile
            sender_profile = self.context['request'].user.profile
            
            # Check for self-request
            if sender_profile.id == data['receiver'].id:
                raise serializers.ValidationError("Cannot send friend request to yourself")
                
            # Check if already friends
            if sender_profile.friends.filter(id=data['receiver'].id).exists():
                raise serializers.ValidationError("Users are already friends")
                
            # Check for existing pending request
            if FriendRequest.objects.filter(
                sender=sender_profile,
                receiver=data['receiver'],
                status='pending'
            ).exists():
                raise serializers.ValidationError("A pending request already exists")

        return data

class VenueSerializer(serializers.ModelSerializer):
    distance = serializers.SerializerMethodField()
    current_vibe = serializers.SerializerMethodField()
    
    class Meta:
        model = Venue
        fields = ['id', 'name', 'address', 'city', 'location', 'description', 
                 'category', 'distance', 'current_vibe']
        
    def get_distance(self, obj):
        if hasattr(obj, 'distance'):
            return round(obj.distance.m, 2)
        return None
        
    def get_current_vibe(self, obj):
        cache_key = f'venue_vibe_{obj.id}'
        vibe = cache.get(cache_key)
        if vibe is None:
            recent_checkins = CheckIn.objects.filter(
                venue=obj,
                timestamp__gte=timezone.now() - timezone.timedelta(hours=2)
            ).values('vibe_rating').annotate(count=Count('id')).order_by('-count')
            
            vibe = {
                'rating': recent_checkins[0]['vibe_rating'] if recent_checkins else 'Unknown',
                'count': sum(c['count'] for c in recent_checkins)
            }
            cache.set(cache_key, vibe, timeout=300)  # Cache for 5 minutes
        return vibe

class CheckInSerializer(serializers.ModelSerializer):
    venue_id = serializers.IntegerField()

    class Meta:
        model = CheckIn
        fields = ['id', 'venue_id', 'vibe_rating', 'visibility']

    def create(self, validated_data):
        user = self.context['request'].user
        venue_id = validated_data.pop('venue_id')
        try:
            venue = Venue.objects.get(id=venue_id)
        except Venue.DoesNotExist:
            raise serializers.ValidationError({'venue_id': 'Venue not found'})
            
        return CheckIn.objects.create(
            user=user,
            venue=venue,
            **validated_data
        )

class VenueRatingSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    venue_name = serializers.CharField(source='venue.name', read_only=True)
    
    class Meta:
        model = VenueRating
        fields = ['id', 'user', 'venue', 'venue_name', 'rating', 'review',
                 'created_at', 'updated_at']
        read_only_fields = ['user', 'created_at', 'updated_at']

    def create(self, validated_data):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError("Must be authenticated to rate venue")
            
        # Check for existing rating
        existing_rating = VenueRating.objects.filter(
            user=request.user,
            venue=validated_data['venue']
        ).first()
        
        if existing_rating:
            raise serializers.ValidationError({
                "detail": "You have already rated this venue"
            })
            
        validated_data['user'] = request.user
        return super().create(validated_data)

class MeetupPingSerializer(serializers.ModelSerializer):
    sender_username = serializers.CharField(source='sender.username', read_only=True)
    receiver_username = serializers.CharField(source='receiver.username', read_only=True)
    venue_name = serializers.CharField(source='venue.name', read_only=True)
    
class MeetupPingSerializer(serializers.ModelSerializer):
    sender_username = serializers.SerializerMethodField()
    receiver_username = serializers.SerializerMethodField()
    venue_name = serializers.SerializerMethodField()

    class Meta:
        model = MeetupPing
        fields = ['id', 'sender', 'receiver', 'venue', 'status', 'message',
                 'created_at', 'expires_at', 'response_message',
                 'sender_username', 'receiver_username', 'venue_name']
        read_only_fields = ['id', 'created_at', 'sender']

    def get_sender_username(self, obj):
        return obj.sender.username if obj.sender else None

    def get_receiver_username(self, obj):
        return obj.receiver.username if obj.receiver else None

    def get_venue_name(self, obj):
        return obj.venue.name if obj.venue else None

    def validate(self, data):
        if 'receiver' in data and isinstance(data['receiver'], (int, str)):
            try:
                data['receiver'] = User.objects.get(id=data['receiver'])
            except User.DoesNotExist:
                raise serializers.ValidationError("Invalid receiver ID")

        if 'venue' in data and isinstance(data['venue'], (int, str)):
            try:
                data['venue'] = Venue.objects.get(id=data['venue'])
            except Venue.DoesNotExist:
                raise serializers.ValidationError("Invalid venue ID")

        return data

class DeviceTokenSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviceToken
        fields = ['id', 'device_type', 'token']
        read_only_fields = ['id']

    def create(self, validated_data):
        user = self.context['request'].user
        # Update or create the device token
        token, created = DeviceToken.objects.update_or_create(
            user=user,
            token=validated_data['token'],
            defaults={
                'device_type': validated_data['device_type'],
                'is_active': True
            }
        )
        return token

class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['id', 'type', 'title', 'message', 'data', 'is_read', 'created_at']
        read_only_fields = ['id', 'type', 'title', 'message', 'data', 'created_at']

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        # Add custom claims
        token['username'] = user.username
        token['email'] = user.email
        return token