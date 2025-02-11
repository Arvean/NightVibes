# models.py
from django.core.cache import cache
from django.db import transaction, models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator, MinValueValidator, MaxValueValidator
from django.conf import settings
from django.contrib.gis.db import models as gis_models
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from django.contrib.gis.geos import Point
from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta
import os


# TODO:
# Add venue suggestion
# Add nightlife plan

# Custom validator to ensure uploaded images don't exceed 5MB
def validate_image_size(value):
    max_size = 5 * 1024 * 1024  # 5MB
    if value.size > max_size:
        raise ValidationError('Image size cannot exceed 5MB.')

# UserProfile Model
# Extends the built-in Django User model with additional fields for the application
# Handles user relationships, location sharing, and profile customization
class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    bio = models.TextField(max_length=500, blank=True)
    location_sharing = models.BooleanField(default=False)
    location = gis_models.PointField(null=True, blank=True, srid=4326)
    profile_picture = models.ImageField(
        upload_to='profile_pics/',
        validators=[
            FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png']),
            validate_image_size
        ],
        null=True,
        blank=True
    )
    friends = models.ManyToManyField('self', blank=True)
    
    def __str__(self):
        return f"{self.user.username}'s profile"

    def clean(self):
        # Updated location validation
        if not self.location_sharing and self.location:
            raise ValidationError({
                'location_sharing': 'Cannot update location while location sharing is disabled'
            })

    def save(self, *args, **kwargs):
        # Handle profile picture cleanup (unchanged)
        if self.pk:
            try:
                old_instance = UserProfile.objects.get(pk=self.pk)
                if (old_instance.profile_picture and 
                    self.profile_picture and 
                    old_instance.profile_picture != self.profile_picture):
                    if os.path.isfile(old_instance.profile_picture.path):
                        os.remove(old_instance.profile_picture.path)
            except UserProfile.DoesNotExist:
                pass
            
        # Updated location handling
        if not self.location_sharing:
            self.location = None
            
        super().save(*args, **kwargs)
        
        # Cache invalidation (unchanged)
        cache.delete(f'user_friend_count_{self.id}')

    def update_location(self, lat, lng):
        """Updates user's location if location sharing is enabled"""
        if not self.location_sharing:
            raise ValidationError("Location sharing is disabled")
        self.location = Point(lng, lat)  # Note: Point takes (x,y) which is (longitude,latitude)
        self.save()

    def get_friend_count(self):
        """Get cached friend count"""
        cache_key = f'user_friend_count_{self.id}'
        count = cache.get(cache_key)
        if count is None:
            count = self.friends.count()
            cache.set(cache_key, count, timeout=3600)  # 1 hour cache
        return count

    # Updates user's location if location sharing is enabled
    def update_location(self, lat, lng):
        if not self.location_sharing:
            raise ValidationError("Location sharing is disabled")
        self.last_location_lat = lat
        self.last_location_lng = lng
        self.save()

# Signal handlers for automatic UserProfile creation
# Creates and saves UserProfile when a new User is created
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Creates UserProfile when a new User is created"""
    if created:
        UserProfile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """Saves UserProfile when User is saved"""
    instance.profile.save()

        
# FriendRequest Model
# Manages friend requests between users with status tracking
# Enforces validation rules for friend relationships
class FriendRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected')
    ]
    
    sender = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='sent_requests')
    receiver = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='received_requests')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('sender', 'receiver')

    def clean(self):
        if self.sender == self.receiver:
            raise ValidationError('Cannot send friend request to yourself')
        
        if self.status == 'accepted' and self.sender in self.receiver.friends.all():
            raise ValidationError('Users are already friends')

    @transaction.atomic
    def accept(self):
        """Accept friend request with transaction safety"""
        friend_request = FriendRequest.objects.select_for_update().get(pk=self.pk)
        
        if friend_request.status != 'pending':
            raise ValidationError("Request already processed")

        if self.status != 'pending':
            raise ValidationError('Only pending requests can be accepted')
            
        if self.sender == self.receiver:
            raise ValidationError('Cannot accept self-friend request')
            
        # Check if already friends
        if self.sender.friends.filter(id=self.receiver.id).exists():
            raise ValidationError('Users are already friends')
            
        self.status = 'accepted'
        self.save()
        
        # Add users as friends atomically
        self.sender.friends.add(self.receiver)
        self.receiver.friends.add(self.sender)


# Venue Model
# Represents nightlife venues with GeoDjango integration for location-based features
# Includes categorization and temporal tracking
class Venue(models.Model):
    name = models.CharField(max_length=255)
    address = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    location = gis_models.PointField(
        srid=4326,
        default=Point(0.0, 0.0)  # Default to null island
    )
    description = models.TextField(blank=True)
    category = models.CharField(max_length=50, choices=[
        ('bar', 'Bar'),
        ('club', 'Club'),
        ('lounge', 'Lounge'),
        ('pub', 'Pub')
    ])
    created_at = models.DateTimeField(default=timezone.now)  # Changed from auto_now_add
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['category']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return self.name

    def get_current_vibe(self):
        """Calculate and return the current vibe of the venue based on recent check-ins"""
        cache_key = f'venue_vibe_{self.id}'
        vibe = cache.get(cache_key)
        
        if vibe is None:
            with transaction.atomic():
                # Get check-ins from the last 2 hours
                recent_time = timezone.now() - timedelta(hours=2)
                recent_checkins = CheckIn.objects.filter(
                    venue=self,
                    timestamp__gte=recent_time
                ).values('vibe_rating').annotate(count=Count('id'))

                if not recent_checkins:
                    # If no recent check-ins, return None or a default value
                    vibe = None
                else:
                    # Get the most common vibe rating
                    vibe = max(recent_checkins, key=lambda x: x['count'])['vibe_rating']
                
                # Cache the result for 5 minutes
                cache.set(cache_key, vibe, timeout=300)
        
        return vibe

    def get_popularity_score(self):
        """Calculate venue popularity based on check-ins and ratings"""
        recent_time = timezone.now() - timedelta(hours=24)
        
        # Get number of check-ins in last 24 hours
        checkin_count = CheckIn.objects.filter(
            venue=self,
            timestamp__gte=recent_time
        ).count()
        
        # Get average rating
        avg_rating = VenueRating.objects.filter(venue=self).aggregate(
            models.Avg('rating')
        )['rating__avg'] or 0
        
        # Combine metrics (you can adjust the weights)
        popularity_score = (checkin_count * 0.7) + (avg_rating * 0.3)
        
        return round(popularity_score, 2)

# CheckIn Model
# Tracks user visits to venues with atmosphere ratings
# Supports different visibility levels for privacy control
class CheckIn(models.Model):
    VIBE_CHOICES = [
        ('Lively', 'Lively'),
        ('Chill', 'Chill'),
        ('Crowded', 'Crowded'),
        ('Empty', 'Empty'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    venue = models.ForeignKey(Venue, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)
    vibe_rating = models.CharField(max_length=20, choices=VIBE_CHOICES)
    visibility = models.CharField(
        max_length=20,
        choices=[
            ('public', 'Public'),
            ('friends', 'Friends Only'),
            ('private', 'Private')
        ],
        default='public'
    )

    class Meta:
        indexes = [
            models.Index(fields=['timestamp', 'venue']),
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['visibility'])
        ]    # Represents the current atmosphere of the venue

    def __str__(self):
        return f"{self.user.username} at {self.venue.name}"

# VenueRating Model
# Handles user ratings and reviews for venues
# Ensures one rating per user per venue
class VenueRating(models.Model):
    user = models.ForeignKey(User, related_name='venue_ratings', on_delete=models.CASCADE)
    venue = models.ForeignKey(Venue, related_name='ratings', on_delete=models.CASCADE)
    rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    review = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'venue')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username}'s {self.rating}-star rating for {self.venue.name}"

# MeetupPing Model
# Facilitates real-time meetup requests between users at venues
# Includes expiration handling and response tracking
class MeetupPing(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('declined', 'Declined'),
        ('expired', 'Expired')
    ]

    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_pings')
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_pings')
    venue = models.ForeignKey(Venue, on_delete=models.CASCADE, related_name='meetup_pings')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    message = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    response_message = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'expires_at']),
            models.Index(fields=['sender', 'receiver', 'status']),
        ]

    def clean(self):
        """Validate ping data"""
        if self.sender == self.receiver:
            raise ValidationError('Cannot send ping to yourself')
        
        if self.expires_at and self.expires_at <= timezone.now():
            raise ValidationError('Expiration time must be in the future')
            
        # Check if users are friends
        if not self.sender.profile.friends.filter(id=self.receiver.profile.id).exists():
            raise ValidationError('Can only send pings to friends')

    @transaction.atomic
    def accept(self, response_message=''):
        """Accept ping with transaction safety"""
        if self.status != 'pending':
            raise ValidationError('Only pending pings can be accepted')
            
        if self.is_expired:
            self.mark_expired()
            raise ValidationError('This ping has expired')
            
        self.status = 'accepted'
        self.response_message = response_message
        self.save()

    def save(self, *args, **kwargs):
        # Ensures all pings have an expiration time
        if not self.expires_at:
            self.expires_at = timezone.now() + timezone.timedelta(hours=2)
        super().save(*args, **kwargs)

    # Property to check if the ping has expired based on current time
    @property
    def is_expired(self):
        return timezone.now() >= self.expires_at

    # Automatically marks pings as expired when they pass their expiration time
    def mark_expired(self):
        if self.status == 'pending' and self.is_expired:
            self.status = 'expired'
            self.save()
            return True
        return False

class DeviceToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='device_tokens')
    token = models.CharField(max_length=255)
    device_type = models.CharField(
        max_length=20,
        choices=[
            ('ios', 'iOS'),
            ('android', 'Android'),
            ('web', 'Web')
        ]
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'token')
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['token'])
        ]

    def __str__(self):
        return f"{self.user.username}'s {self.device_type} device"

    @classmethod
    def cleanup_inactive(cls):
        """Clean up tokens that have been inactive for more than 30 days"""
        threshold = timezone.now() - timedelta(days=30)
        # First count the tokens that will be deleted
        to_delete = cls.objects.filter(
            is_active=False,
            last_used__lt=threshold
        )
        count = to_delete.count()
        # Then delete them
        to_delete.delete()
        return count

class Notification(models.Model):
    NOTIFICATION_TYPES = [
        ('friend_request', 'Friend Request'),
        ('friend_accepted', 'Friend Request Accepted'),
        ('meetup_ping', 'Meetup Ping'),
        ('ping_response', 'Ping Response'),
        ('nearby_friend', 'Nearby Friend'),
        ('venue_alert', 'Venue Alert')
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=255)
    message = models.TextField()
    data = models.JSONField(default=dict)  # Additional data payload
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    is_sent = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read']),
            models.Index(fields=['created_at'])
        ]
