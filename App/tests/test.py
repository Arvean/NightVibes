from django.test import TestCase
from django.contrib.auth.models import User
from django.contrib.gis.geos import Point
from django.utils import timezone
from rest_framework.test import APITestCase
from rest_framework import status
from datetime import timedelta
from .models import UserProfile, FriendRequest, Venue, CheckIn, VenueRating, MeetupPing, DeviceToken, Notification
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.contrib.gis.db.models.functions import Distance
from django.test import override_settings
import json
import shutil
import tempfile

class UserProfileTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.profile = UserProfile.objects.get(user=self.user)
        
        # Create additional users for friendship tests
        self.user2 = User.objects.create_user(
            username='testuser2',
            email='test2@example.com',
            password='testpass123'
        )
        self.profile2 = UserProfile.objects.get(user=self.user2)
        
        self.user3 = User.objects.create_user(
            username='testuser3',
            email='test3@example.com',
            password='testpass123'
        )
        self.profile3 = UserProfile.objects.get(user=self.user3)

    def test_location_sharing_validation(self):
        """Test that location updates are only allowed when location sharing is enabled"""
        # Should raise ValidationError when updating location with sharing disabled
        self.profile.location_sharing = False
        with self.assertRaises(ValidationError):
            self.profile.update_location(lat=40.7128, lng=-74.0060)

        # Should succeed when location sharing is enabled
        self.profile.location_sharing = True
        self.profile.save()
        self.profile.update_location(lat=40.7128, lng=-74.0060)
        self.assertEqual(self.profile.last_location_lat, 40.7128)
        self.assertEqual(self.profile.last_location_lng, -74.0060)

    def test_friend_management(self):
        """Test friend addition and removal functionality"""
        # Test adding friends
        self.profile.friends.add(self.profile2)
        self.assertTrue(self.profile.friends.filter(id=self.profile2.id).exists())
        self.assertEqual(self.profile.get_friend_count(), 1)

        # Test mutual friendship
        self.assertTrue(self.profile2.friends.filter(id=self.profile.id).exists())
        
        # Test removing friends
        self.profile.friends.remove(self.profile2)
        self.assertFalse(self.profile.friends.filter(id=self.profile2.id).exists())
        self.assertEqual(self.profile.get_friend_count(), 0)

    def test_profile_picture_validation(self):
        """Test profile picture upload validations"""
        # Create a mock image file that's too large (>5MB)
        large_image = SimpleUploadedFile(
            "large_image.jpg",
            b"0" * (6 * 1024 * 1024),  # 6MB file
            content_type="image/jpeg"
        )
        
        with self.assertRaises(ValidationError):
            self.profile.profile_picture = large_image
            self.profile.full_clean()
            
        # Test invalid file extension
        invalid_file = SimpleUploadedFile(
            "test.txt",
            b"test content",
            content_type="text/plain"
        )
        
        with self.assertRaises(ValidationError):
            self.profile.profile_picture = invalid_file
            self.profile.full_clean()

    def test_location_privacy(self):
        """Test location privacy settings and interactions"""
        # Test that location is not shared with non-friends
        self.profile.location_sharing = True
        self.profile.update_location(lat=40.7128, lng=-74.0060)
        
        # Non-friend shouldn't see location
        self.assertFalse(self.profile2.can_see_location(self.profile))
        
        # Add as friend and verify location visibility
        self.profile.friends.add(self.profile2)
        self.assertTrue(self.profile2.can_see_location(self.profile))
        
        # Disable location sharing and verify
        self.profile.location_sharing = False
        self.profile.save()
        self.assertFalse(self.profile2.can_see_location(self.profile))

class VenueTests(TestCase):
    def setUp(self):
        self.venue = Venue.objects.create(
            name='Test Bar',
            address='123 Test St',
            city='Test City',
            location=Point(-74.0060, 40.7128),
            category='bar'
        )
        
        # Create test user for ratings
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create multiple venues for ranking tests
        self.venue2 = Venue.objects.create(
            name='Test Club',
            address='456 Party Ave',
            city='Test City',
            location=Point(-74.0062, 40.7130),
            category='club'
        )
        
        self.venue3 = Venue.objects.create(
            name='Test Lounge',
            address='789 Chill St',
            city='Test City',
            location=Point(-74.0065, 40.7135),
            category='lounge'
        )

    def test_venue_creation(self):
        """Test venue creation and basic attributes"""
        self.assertEqual(self.venue.name, 'Test Bar')
        self.assertEqual(self.venue.category, 'bar')
        self.assertTrue(isinstance(self.venue.location, Point))

    def test_venue_geolocation(self):
        """Test geolocation functionality of venues"""
        # Test that the point was created correctly
        self.assertEqual(self.venue.location.x, -74.0060)
        self.assertEqual(self.venue.location.y, 40.7128)
        
    def test_venue_rating_system(self):
        """Test venue rating functionality"""
        # Create ratings
        rating1 = VenueRating.objects.create(
            user=self.user,
            venue=self.venue,
            rating=4,
            review="Great atmosphere!"
        )
        
        # Test average rating calculation
        self.assertEqual(self.venue.average_rating(), 4.0)
        
        # Test rating constraints
        with self.assertRaises(ValidationError):
            VenueRating.objects.create(
                user=self.user,
                venue=self.venue,
                rating=6  # Invalid rating > 5
            )
            
        # Test duplicate rating prevention
        with self.assertRaises(IntegrityError):
            VenueRating.objects.create(
                user=self.user,
                venue=self.venue,
                rating=3
            )

    def test_venue_current_vibe(self):
        """Test venue vibe calculation from check-ins"""
        # Create recent check-ins
        CheckIn.objects.create(
            user=self.user,
            venue=self.venue,
            vibe_rating='Lively',
            visibility='public'
        )
        CheckIn.objects.create(
            user=self.user,
            venue=self.venue,
            vibe_rating='Lively',
            visibility='public'
        )
        CheckIn.objects.create(
            user=self.user,
            venue=self.venue,
            vibe_rating='Crowded',
            visibility='public'
        )
        
        # Test current vibe calculation
        current_vibe = self.venue.get_current_vibe()
        self.assertEqual(current_vibe['rating'], 'Lively')
        self.assertEqual(current_vibe['count'], 3)
        
    def test_venue_distance_calculation(self):
        """Test distance calculations between venues and points"""
        # Create a reference point (Times Square, NYC)
        times_square = Point(-73.9855, 40.7580)
        
        # Calculate distances
        venues = Venue.objects.annotate(
            distance=Distance('location', times_square)
        ).order_by('distance')
        
        # Verify distance ordering
        self.assertEqual(len(venues), 3)  # All venues retrieved
        self.assertTrue(
            venues[0].distance.m < venues[1].distance.m < venues[2].distance.m
        )
        
    def test_venue_category_filtering(self):
        """Test venue filtering by category"""
        # Test category counts
        category_counts = Venue.objects.values('category').annotate(
            count=Count('id')
        ).order_by('category')
        
        self.assertEqual(
            category_counts.get(category='bar')['count'], 
            1
        )
        self.assertEqual(
            category_counts.get(category='club')['count'], 
            1
        )
        self.assertEqual(
            category_counts.get(category='lounge')['count'], 
            1
        )

class CheckInTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.venue = Venue.objects.create(
            name='Test Club',
            address='456 Test Ave',
            city='Test City',
            location=Point(-74.0060, 40.7128),
            category='club'
        )
        self.client.force_authenticate(user=self.user)

    def test_checkin_creation(self):
        """Test creating a new check-in"""
        data = {
            'venue_id': self.venue.id,
            'vibe_rating': 'Lively',
            'visibility': 'public'
        }
        response = self.client.post('/api/checkins/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(CheckIn.objects.count(), 1)
        self.assertEqual(CheckIn.objects.first().vibe_rating, 'Lively')

    def test_checkin_visibility(self):
        """Test check-in visibility controls"""
        # Create private check-in
        private_checkin = CheckIn.objects.create(
            user=self.user,
            venue=self.venue,
            vibe_rating='Crowded',
            visibility='private'
        )
        
        # Create another user
        other_user = User.objects.create_user(
            username='otheruser',
            password='testpass123'
        )
        self.client.force_authenticate(user=other_user)
        
        # Try to view private check-in
        response = self.client.get(f'/api/checkins/{private_checkin.id}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

class FriendRequestTests(APITestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(
            username='user1',
            password='testpass123'
        )
        self.user2 = User.objects.create_user(
            username='user2',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user1)

    def test_friend_request_flow(self):
        """Test complete friend request flow: send, accept, verify friendship"""
        # Send friend request
        data = {'receiver': self.user2.profile.id}
        response = self.client.post('/api/friend-requests/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        request_id = response.data['id']

        # Accept friend request (as user2)
        self.client.force_authenticate(user=self.user2)
        response = self.client.post(f'/api/friend-requests/{request_id}/accept/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify friendship was established
        self.assertTrue(
            self.user1.profile.friends.filter(id=self.user2.profile.id).exists()
        )
        self.assertTrue(
            self.user2.profile.friends.filter(id=self.user1.profile.id).exists()
        )

class MeetupPingTests(APITestCase):
    def setUp(self):
        # Create users and establish friendship
        self.user1 = User.objects.create_user('user1', password='test123')
        self.user2 = User.objects.create_user('user2', password='test123')
        self.user1.profile.friends.add(self.user2.profile)
        
        self.venue = Venue.objects.create(
            name='Test Venue',
            address='789 Test Rd',
            city='Test City',
            location=Point(-74.0060, 40.7128),
            category='bar'
        )
        self.client.force_authenticate(user=self.user1)

    def test_meetup_ping_lifecycle(self):
        """Test full meetup ping lifecycle: create, accept, expire"""
        # Create ping
        data = {
            'receiver': self.user2.id,
            'venue': self.venue.id,
            'message': 'Want to meet up?',
            'expires_at': (timezone.now() + timedelta(hours=1)).isoformat()
        }
        response = self.client.post('/api/pings/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        ping_id = response.data['id']

        # Accept ping as user2
        self.client.force_authenticate(user=self.user2)
        response = self.client.post(
            f'/api/pings/{ping_id}/accept/',
            {'message': 'Sure!'}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify ping status
        ping = MeetupPing.objects.get(id=ping_id)
        self.assertEqual(ping.status, 'accepted')
        self.assertEqual(ping.response_message, 'Sure!')

    def test_ping_expiration(self):
        """Test that pings properly expire"""
        # Create ping that's about to expire
        ping = MeetupPing.objects.create(
            sender=self.user1,
            receiver=self.user2,
            venue=self.venue,
            expires_at=timezone.now() + timedelta(seconds=1)
        )
        
        # Wait for expiration
        time.sleep(2)
        
        # Verify ping is marked as expired
        ping.refresh_from_db()
        self.assertTrue(ping.is_expired)
        self.assertEqual(ping.status, 'expired')