from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.conf import settings
import os

def validate_image_size(value):
    max_size = 5 * 1024 * 1024  # 5MB
    if value.size > max_size:
        raise ValidationError('Image size cannot exceed 5MB.')

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    bio = models.TextField(max_length=500, blank=True)
    location_sharing = models.BooleanField(default=False)
    last_location_lat = models.FloatField(null=True, blank=True)
    last_location_lng = models.FloatField(null=True, blank=True)
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
        if not self.location_sharing and (self.last_location_lat or self.last_location_lng):
            raise ValidationError({
                'location_sharing': 'Cannot update location while location sharing is disabled'
            })

    def get_friend_count(self):
        cache_key = f'user_friend_count_{self.id}'
        count = cache.get(cache_key)
        if count is None:
            count = self.friends.count()
            cache.set(cache_key, count, timeout=3600)  # Cache for 1 hour
        return count

    def update_location(self, lat, lng):
        if not self.location_sharing:
            raise ValidationError("Location sharing is disabled")
        self.last_location_lat = lat
        self.last_location_lng = lng
        self.save()

# Signal to create UserProfile when a new User is created
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    try:
        instance.profile.save()
    except UserProfile.DoesNotExist:
        UserProfile.objects.create(user=instance)

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

# Update Venue model to use GeoDjango
class Venue(models.Model):
    name = models.CharField(max_length=255)
    address = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    location = models.PointField(srid=4326)  # Replace latitude/longitude with PointField
    description = models.TextField(blank=True)
    category = models.CharField(max_length=50, choices=[
        ('bar', 'Bar'),
        ('club', 'Club'),
        ('lounge', 'Lounge'),
        ('pub', 'Pub')
    ])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['category']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return self.name

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

    def __str__(self):
        return f"{self.user.username} at {self.venue.name}"

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
        if self.sender == self.receiver:
            raise ValidationError('Cannot send ping to yourself')
        
        if self.expires_at <= timezone.now():
            raise ValidationError('Expiration time must be in the future')

    def save(self, *args, **kwargs):
        # Set default expiration time to 2 hours from creation if not specified
        if not self.expires_at:
            self.expires_at = timezone.now() + timezone.timedelta(hours=2)
        super().save(*args, **kwargs)

    @property
    def is_expired(self):
        return timezone.now() >= self.expires_at

    def mark_expired(self):
        if self.status == 'pending' and self.is_expired:
            self.status = 'expired'
            self.save()
            return True
        return False