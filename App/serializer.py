from rest_framework import serializers
from django.contrib.auth.models import User
from .models import UserProfile, FriendRequest, Venue, CheckIn

class UserProfileSerializer(serializers.ModelSerializer):
    # TODO: Add more fine-grained controls "share location with friends only,
    # hide location from certain friends, etc."
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    
    class Meta:
        model = UserProfile
        fields = ['id', 'username', 'email', 'bio', 'location_sharing', 
                 'last_location_lat', 'last_location_lng', 'profile_picture']
        read_only_fields = ['id']

    def validate(self, data):
        # Validate location updates
        if not data.get('location_sharing', self.instance and self.instance.location_sharing):
            if data.get('last_location_lat') or data.get('last_location_lng'):
                raise serializers.ValidationError({
                    'location_sharing': 'Cannot update location while location sharing is disabled'
                })
        
        return data

    def update(self, instance, validated_data):
        # Handle profile picture update
        if 'profile_picture' in validated_data:
            # Delete old picture if it exists
            if instance.profile_picture:
                old_picture_path = instance.profile_picture.path
                if os.path.exists(old_picture_path):
                    os.remove(old_picture_path)
        
        return super().update(instance, validated_data)

class FriendRequestSerializer(serializers.ModelSerializer):
    sender_username = serializers.CharField(source='sender.user.username', read_only=True)
    receiver_username = serializers.CharField(source='receiver.user.username', read_only=True)

    class Meta:
        model = FriendRequest
        fields = ['id', 'sender', 'receiver', 'sender_username', 
                 'receiver_username', 'status', 'created_at']
        read_only_fields = ['id', 'sender_username', 'receiver_username', 
                           'created_at']

    def validate(self, data):
        sender = data.get('sender')
        receiver = data.get('receiver')

        if sender == receiver:
            raise serializers.ValidationError("Cannot send friend request to yourself")

        # Check if a friend request already exists
        existing_request = FriendRequest.objects.filter(
            sender=sender,
            receiver=receiver,
            status='pending'
        ).exists()

        if existing_request:
            raise serializers.ValidationError("A pending friend request already exists")

        # Check if users are already friends
        if sender.friends.filter(id=receiver.id).exists():
            raise serializers.ValidationError("Users are already friends")

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
    user = serializers.StringRelatedField(read_only=True)
    venue = VenueSerializer(read_only=True)
    venue_id = serializers.PrimaryKeyRelatedField(
        queryset=Venue.objects.all(),
        write_only=True
    )

    class Meta:
        model = CheckIn
        fields = ['id', 'user', 'venue', 'venue_id', 'timestamp', 
                 'vibe_rating', 'visibility']
        read_only_fields = ['id', 'timestamp']

    def create(self, validated_data):
        venue = validated_data.pop('venue_id')
        user = self.context['request'].user
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
            
        validated_data['user'] = request.user
        return super().create(validated_data)

class MeetupPingSerializer(serializers.ModelSerializer):
    sender_username = serializers.CharField(source='sender.username', read_only=True)
    receiver_username = serializers.CharField(source='receiver.username', read_only=True)
    venue_name = serializers.CharField(source='venue.name', read_only=True)
    
    class Meta:
        model = MeetupPing
        fields = ['id', 'sender', 'receiver', 'venue', 'status', 'message',
                 'created_at', 'expires_at', 'response_message',
                 'sender_username', 'receiver_username', 'venue_name']
        read_only_fields = ['id', 'created_at', 'sender_username', 
                           'receiver_username', 'venue_name']

    def validate(self, data):
        # Verify the receiver is a friend of the sender
        sender = self.context['request'].user
        receiver = data.get('receiver')
        
        if not sender.profile.friends.filter(user=receiver).exists():
            raise serializers.ValidationError(
                "Can only send pings to friends"
            )

        # Verify the expiration time is in the future
        expires_at = data.get('expires_at')
        if expires_at and expires_at <= timezone.now():
            raise serializers.ValidationError(
                "Expiration time must be in the future"
            )

        return data