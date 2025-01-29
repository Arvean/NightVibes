import time
from datetime import timedelta
from unittest.mock import patch, MagicMock

from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.contrib.gis.geos import Point
from django.utils import timezone
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import Http404

from rest_framework.test import APITestCase, APIClient
from rest_framework import status

from App.models import (
    UserProfile, 
    Venue, 
    CheckIn, 
    FriendRequest, 
    MeetupPing, 
    VenueRating, 
    DeviceToken, 
    Notification
)

from App.notifications import NotificationService

from io import BytesIO
from PIL import Image

class BaseTestCase(APITestCase):
    def setUp(self):
        # Create users
        self.user1 = User.objects.create_user(
            username='user1', 
            email='user1@test.com',
            password='pass123'
        )
        self.user2 = User.objects.create_user(
            username='user2',
            email='user2@test.com',
            password='pass123'
        )
        
        # Create profiles and refresh from db
        self.profile1 = UserProfile.objects.get_or_create(user=self.user1)[0]
        self.profile2 = UserProfile.objects.get_or_create(user=self.user2)[0]
        
        # Make users friends
        self.profile1.friends.add(self.profile2)
        self.profile2.friends.add(self.profile1)
        
        # Create test venue
        self.venue = Venue.objects.create(
            name='Test Venue',
            address='123 Test St',
            city='Test City',
            location=Point(-74.0060, 40.7128),
            category='bar'
        )
        
        # Set up client authentication
        self.client = APIClient()
        self.client.force_authenticate(user=self.user1)

class UserProfileTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.profile_url = '/api/profile/' 

    def test_profile_retrieval(self):
        """Test profile retrieval and update operations"""
        response = self.client.get(self.profile_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], self.user1.username)

    def test_profile_update(self):
        """Test profile update operations"""
        update_data = {
            'bio': 'Test bio',
            'location_sharing': True
        }
        response = self.client.patch(self.profile_url, update_data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['bio'], 'Test bio')
        self.assertTrue(response.data['location_sharing'])

    def generate_image_file(self, format='PNG'):
        """Generates a valid image file in memory using Pillow."""
        file = BytesIO()
        image = Image.new('RGBA', size=(100, 100), color=(155, 0, 0, 255))  # Create a red square
        image.save(file, format=format)
        file.seek(0)
        return file

    def test_profile_picture_upload(self):
        """Test profile picture upload with valid and invalid file types"""

        # Test uploading a valid PNG image
        png_image = self.generate_image_file(format='PNG')
        png_uploaded = SimpleUploadedFile(
            name='test_image.png',
            content=png_image.read(),
            content_type='image/png'
        )

        response = self.client.patch(
            self.profile_url,
            {'profile_picture': png_uploaded},
            format='multipart'
        )
        self.assertEqual(
            response.status_code, 
            status.HTTP_200_OK,
            f"Expected 200 OK, got {response.status_code} with data {response.data}"
        )
        self.assertIn('profile_picture', response.data)

        # Test uploading an invalid file type (TXT)
        text_file = SimpleUploadedFile(
            'test.txt',
            b'test content',
            content_type='text/plain'
        )
        response = self.client.patch(
            self.profile_url,
            {'profile_picture': text_file},
            format='multipart'
        )
        self.assertEqual(
            response.status_code, 
            status.HTTP_400_BAD_REQUEST,
            f"Expected 400 Bad Request, got {response.status_code} with data {response.data}"
        )
        # Depending on where the validation fails (view or model), the error key might differ
        self.assertTrue(
            'error' in response.data or 'profile_picture' in response.data,
            "Expected an error message related to profile_picture."
        )
        if 'error' in response.data:
            self.assertEqual(
                response.data['error'],
                'Invalid file type. Only images are allowed.'
            )
        elif 'profile_picture' in response.data:
            self.assertIn(
                'File extension "txt" is not allowed',
                response.data['profile_picture'][0]
            )

    def test_location_update(self):
            """Test location update operations"""
            update_data = {
                'latitude': 40.7128,
                'longitude': -74.0060,
                'location_sharing': True
            }
            response = self.client.patch(self.profile_url, update_data)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            
            # Verify location was set correctly
            self.profile1.refresh_from_db()
            self.assertIsNotNone(self.profile1.location)
            self.assertEqual(self.profile1.location.y, 40.7128)  # latitude
            self.assertEqual(self.profile1.location.x, -74.0060)  # longitude

    def test_location_sharing_disabled(self):
        """Test location handling when sharing is disabled"""
        # First set a location with sharing enabled
        update_data = {
            'latitude': 40.7128,
            'longitude': -74.0060,
            'location_sharing': True
        }
        response = self.client.patch(self.profile_url, update_data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Now disable location sharing
        update_data = {
            'location_sharing': False
        }
        response = self.client.patch(self.profile_url, update_data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify location was cleared
        self.profile1.refresh_from_db()
        self.assertIsNone(self.profile1.location)

    def test_partial_location_update(self):
        """Test validation when only one coordinate is provided"""
        update_data = {
            'latitude': 40.7128,
            'location_sharing': True
        }
        response = self.client.patch(self.profile_url, update_data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Both latitude and longitude must be provided together', str(response.data))

class VenueTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        # Create additional venue for testing
        self.venue2 = Venue.objects.create(
            name='Test Club',
            address='456 Party Ave',
            city='Test City',
            location=Point(-74.0062, 40.7130),
            category='club'
        )

    def test_venue_listing(self):
        """Test venue listing with various filters"""
        # Test category filter - case insensitive
        response = self.client.get('/api/venues/', {'category': 'BAR'})  # Testing iexact
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        venues = [v for v in response.data if v['category'].lower() == 'bar']
        self.assertEqual(len(venues), 1)

    def test_venue_details(self):
        """Test venue detail operations"""
        response = self.client.get(f'/api/venues/{self.venue.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Test Venue')

        # Test current vibe endpoint
        response = self.client.get(f'/api/venues/{self.venue.id}/current_vibe/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('vibe', response.data)
        self.assertIn('checkins_count', response.data)

class CheckInTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.checkin_url = reverse('checkin-list')

    def test_checkin_creation(self):
        """Test check-in creation and validation"""
        data = {
            'venue_id': self.venue.id,
            'vibe_rating': 'Lively',
            'visibility': 'public'
        }
        response = self.client.post(self.checkin_url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(CheckIn.objects.count(), 1)

    @patch('App.notifications.NotificationService.send_nearby_friend_alert')
    def test_checkin_notifications(self, mock_notify):
        """Test notification triggering on check-in"""
        # Update friend's location to be nearby
        self.profile2.location_sharing = True
        self.profile2.location = Point(-74.0060, 40.7128)  # Same location as venue
        self.profile2.save()

        data = {
            'venue_id': self.venue.id,
            'vibe_rating': 'Lively',
            'visibility': 'public'
        }
        response = self.client.post(self.checkin_url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        mock_notify.assert_called_once()

    @patch('App.notifications.NotificationService.send_nearby_friend_alert')
    def test_checkin_notifications_far_friends(self, mock_notify):
        """Test that distant friends don't get notifications"""
        # Set friend's location far away
        self.profile2.location_sharing = True
        self.profile2.location = Point(-118.2437, 34.0522)  # Los Angeles coordinates
        self.profile2.save()

        data = {
            'venue_id': self.venue.id,
            'vibe_rating': 'Lively',
            'visibility': 'public'
        }
        response = self.client.post(self.checkin_url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        mock_notify.assert_not_called()

class MeetupPingTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.pings_url = reverse('ping-list')

    def test_ping_lifecycle(self):
        """Test complete meetup ping lifecycle"""
        data = {
            'receiver': self.user2.id,  # Send ID not object
            'venue': self.venue.id,     # Send ID not object
            'message': 'Want to meet?',
            'expires_at': (timezone.now() + timedelta(hours=1)).isoformat()
        }
        response = self.client.post('/api/pings/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        ping_id = response.data['id']

        # Test ping acceptance
        self.client.force_authenticate(user=self.user2)
        response = self.client.post(
            f'/api/pings/{ping_id}/accept/',
            {'message': 'Sure!'}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data']['status'], 'accepted')

    def test_ping_expiration(self):
        """Test ping expiration handling"""
        ping = MeetupPing.objects.create(
            sender=self.user1,
            receiver=self.user2,
            venue=self.venue,
            expires_at=timezone.now() + timedelta(seconds=1)
        )
        
        # Wait for expiration
        time.sleep(2)
        
        # Try to accept expired ping
        self.client.force_authenticate(user=self.user2)
        response = self.client.post(f'/api/pings/{ping.id}/accept/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('expired', str(response.data['error']).lower())

class NotificationTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.notification_service = NotificationService

    @patch('firebase_admin.messaging.send_multicast')
    @patch('firebase_admin.messaging.Notification')
    def test_nearby_friend_notification(self, mock_notification_class, mock_send):
        """Test nearby friend notifications with location"""
        # Setup locations
        self.profile1.location_sharing = True
        self.profile1.location = Point(-74.0060, 40.7128)
        self.profile1.save()
        
        self.profile2.location_sharing = True
        self.profile2.location = Point(-74.0062, 40.7130)
        self.profile2.save()
        
        # Create device token for receiving user
        token = DeviceToken.objects.create(
            user=self.user2,
            token='test-token-123',
            device_type='ios',
            is_active=True
        )
        
        # Configure mocks
        mock_response = MagicMock()
        mock_response.success_count = 1
        mock_send.return_value = mock_response
        
        # Send notification
        success = self.notification_service.send_nearby_friend_alert(
            self.user2,  # receiver
            self.user1,  # friend who checked in
            self.venue
        )
        
        # Verify Firebase notification was created correctly
        mock_notification_class.assert_called_once_with(
            title='Friend Nearby',
            body=f'{self.user1.username} is at {self.venue.name}'
        )

        # Verify Firebase message was sent with correct data
        mock_send.assert_called_once()
        call_args = mock_send.call_args[0][0]
        self.assertEqual(call_args.tokens, [token.token])
        self.assertEqual(call_args.data, {
            'type': 'nearby_friend',
            'friend_id': str(self.user1.id),
            'venue_id': str(self.venue.id)
        })
        
        self.assertTrue(success)
        
        # Verify notification was created in database
        notification = Notification.objects.get(
            user=self.user2,
            type='nearby_friend'
        )
        self.assertEqual(
            notification.message,
            f'{self.user1.username} is at {self.venue.name}'
        )
        self.assertEqual(notification.title, 'Friend Nearby')
        self.assertTrue(notification.is_sent)

    def test_notification_send_failure(self):
        """Test notification handling when Firebase fails"""
        @patch('firebase_admin.messaging.send_multicast')
        def test_failure(mock_send):
            mock_send.side_effect = Exception("Firebase error")
            
            success = self.notification_service.send_to_user(
                user=self.user1,
                notification_type='test',
                title='Test',
                message='Test message'
            )
            
            self.assertFalse(success)
            notification = Notification.objects.get(
                user=self.user1,
                type='test'
            )
            self.assertFalse(notification.is_sent)

    def test_notification_cleanup(self):
        """Test notification cleanup with location-based notifications"""
        # Create old notifications
        old_time = timezone.now() - timedelta(days=31)
        
        # Create notifications for different scenarios
        notifications = [
            Notification.objects.create(
                user=self.user1,
                type='nearby_friend',
                title='Friend Nearby',
                message='Test message'
            ),
            Notification.objects.create(
                user=self.user2,
                type='meetup_ping',
                title='Meetup Request',
                message='Test message'
            )
        ]
        
        # Update the timestamp for the old notification
        Notification.objects.filter(id=notifications[0].id).update(created_at=old_time)
        
        # Run cleanup
        self.notification_service.cleanup_old_notifications()
        
        # Verify old notifications were deleted
        self.assertEqual(
            Notification.objects.filter(id=notifications[0].id).count(),
            0
        )
        # Verify recent notifications remain
        self.assertEqual(
            Notification.objects.filter(id=notifications[1].id).count(),
            1
        )

class DeviceTokenTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.device_token_url = '/api/device-tokens/'
        self.device_token_data = {
            'device_type': 'ios',
            'token': 'test-device-token-123'
        }

    def test_device_token_management(self):
        """Test device token registration and updates"""
        # Test token registration
        response = self.client.post(self.device_token_url, self.device_token_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(DeviceToken.objects.filter(token='test-device-token-123').exists())

        # Test duplicate token handling (should update existing)
        response = self.client.post(self.device_token_url, self.device_token_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(DeviceToken.objects.filter(token='test-device-token-123').count(), 1)

    def test_token_cleanup(self):
        """Test cleanup of inactive tokens"""
        old_time = timezone.now() - timedelta(days=31)
        recent_time = timezone.now() - timedelta(days=1)
        
        # Create old inactive token
        old_token = DeviceToken.objects.create(
            user=self.user1,
            token='old-token',
            device_type='android',
            is_active=False
        )
        
        # Create recent inactive token
        recent_token = DeviceToken.objects.create(
            user=self.user1,
            token='recent-token',
            device_type='android',
            is_active=False
        )
        
        # Update last_used timestamps using update() to bypass auto_now
        DeviceToken.objects.filter(pk=old_token.pk).update(last_used=old_time)
        DeviceToken.objects.filter(pk=recent_token.pk).update(last_used=recent_time)
        
        # Run cleanup
        cleaned = DeviceToken.cleanup_inactive()
        self.assertEqual(cleaned, 1)  # Should only clean up old token
        self.assertFalse(DeviceToken.objects.filter(token='old-token').exists())
        self.assertTrue(DeviceToken.objects.filter(token='recent-token').exists())

class RatingTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.ratings_url = '/api/ratings/'

    def test_venue_rating(self):
        """Test venue rating functionality"""
        data = {
            'venue': self.venue.id,
            'rating': 4,
            'review': 'Great place!'
        }
        response = self.client.post(self.ratings_url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Test duplicate rating
        response = self.client.post(self.ratings_url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rating_updates(self):
        """Test updating existing ratings"""
        # Create initial rating
        rating = VenueRating.objects.create(
            user=self.user1,
            venue=self.venue,
            rating=3,
            review='Initial review'
        )
        
        update_data = {
            'rating': 4,
            'review': 'Updated review'
        }
        response = self.client.patch(f'{self.ratings_url}{rating.id}/', update_data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        rating.refresh_from_db()
        self.assertEqual(rating.rating, 4)
        self.assertEqual(rating.review, 'Updated review')

class IntegrationTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        # URLs we'll need for testing
        self.profile_url = '/api/profile/'
        self.friend_request_url = '/api/friend-requests/'
        self.checkin_url = '/api/checkins/'
        self.pings_url = '/api/pings/'
        
    def test_complete_user_journey(self):
        """Test complete user journey through the app with location features"""
        # 1. Update profile with location
        profile_data = {
            'bio': 'Love nightlife!',
            'location_sharing': True,
            'latitude': 40.7128,
            'longitude': -74.0060
        }
        response = self.client.patch(self.profile_url, profile_data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['bio'], 'Love nightlife!')
        
        # Verify location was set correctly
        self.profile1.refresh_from_db()
        self.assertIsNotNone(self.profile1.location)
        self.assertEqual(self.profile1.location.y, 40.7128)  # latitude
        self.assertEqual(self.profile1.location.x, -74.0060)  # longitude
        
        # 2. Create a new user to send friend request to
        new_user = User.objects.create_user(
            username='newuser',
            email='new@test.com',
            password='pass123'
        )
        new_profile = UserProfile.objects.get(user=new_user)
        
        # Set location for new user
        new_profile.location_sharing = True
        new_profile.location = Point(-74.0062, 40.7130)  # Nearby location
        new_profile.save()
        
        # 3. Send friend request
        friend_request_data = {
            'receiver': new_profile.id
        }
        response = self.client.post(self.friend_request_url, friend_request_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        request_id = response.data['id']
        
        # Verify friend request notification was created
        self.assertTrue(
            Notification.objects.filter(
                user=new_user,
                type='friend_request'
            ).exists()
        )
        
        # 4. Accept friend request (as new user)
        self.client.force_authenticate(user=new_user)
        response = self.client.post(f'{self.friend_request_url}{request_id}/accept/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # 5. Check-in at venue (as original user)
        self.client.force_authenticate(user=self.user1)
        checkin_data = {
            'venue_id': self.venue.id,
            'vibe_rating': 'Lively',
            'visibility': 'friends'
        }
        response = self.client.post(self.checkin_url, checkin_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify nearby friend notification was created (since users are within range)
        self.assertTrue(
            Notification.objects.filter(
                user=new_user,
                type='nearby_friend'
            ).exists()
        )
        
        # 6. Test nearby friends search
        response = self.client.get('/api/friends/nearby/', {
            'latitude': '40.7128',
            'longitude': '-74.0060',
            'radius': '1000'
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['nearby_friends']), 1)
        
        # 7. Send meetup ping (as new user)
        self.client.force_authenticate(user=new_user)
        ping_data = {
            'receiver': self.user1.id,
            'venue': self.venue.id,
            'message': "Let's meet up!",
            'expires_at': (timezone.now() + timedelta(hours=1)).isoformat()
        }
        response = self.client.post(self.pings_url, ping_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify meetup ping notification was created
        self.assertTrue(
            Notification.objects.filter(
                user=self.user1,
                type='meetup_ping'
            ).exists()
        )
        
        # 8. Accept ping (as original user)
        self.client.force_authenticate(user=self.user1)
        ping_id = response.data['id']
        response = self.client.post(
            f'{self.pings_url}{ping_id}/accept/',
            {'message': 'See you there!'}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify ping response notification was created
        self.assertTrue(
            Notification.objects.filter(
                user=new_user,
                type='ping_response'
            ).exists()
        )
        
        # 9. Verify notification counts
        self.assertEqual(
            Notification.objects.filter(user=new_user).count(),
            3  # friend_accepted + nearby_friend + ping_response
        )
        self.assertEqual(
            Notification.objects.filter(user=self.user1).count(),
            2  # friend_request_accepted + meetup_ping
        )

class FriendRequestTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.friend_request_url = '/api/friend-requests/'
        
        # Create a new user for friend request tests
        self.new_user = User.objects.create_user(
            username='newuser',
            email='new@test.com',
            password='pass123'
        )
        self.new_profile = UserProfile.objects.get(user=self.new_user)

    def test_friend_request_lifecycle(self):
        """Test complete friend request lifecycle"""
        # Send request
        request_data = {
            'receiver': self.new_profile.id
        }
        response = self.client.post(self.friend_request_url, request_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        request_id = response.data['id']
        
        # Verify request state
        friend_request = FriendRequest.objects.get(id=request_id)
        self.assertEqual(friend_request.status, 'pending')
        
        # Accept request
        self.client.force_authenticate(user=self.new_user)
        response = self.client.post(f'{self.friend_request_url}{request_id}/accept/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify friendship was established
        friend_request.refresh_from_db()
        self.assertEqual(friend_request.status, 'accepted')
        self.assertTrue(self.profile1.friends.filter(id=self.new_profile.id).exists())
        self.assertTrue(self.new_profile.friends.filter(id=self.profile1.id).exists())

    def test_friend_request_validation(self):
        """Test friend request validation rules"""
        # Test self-request
        response = self.client.post(self.friend_request_url, {
            'receiver': self.profile1.id
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Test duplicate request
        request_data = {
            'receiver': self.new_profile.id
        }
        response = self.client.post(self.friend_request_url, request_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        response = self.client.post(self.friend_request_url, request_data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

class NearbyFriendsTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.nearby_friends_url = '/api/friends/nearby/'
        
        # Enable location sharing and set locations
        self.profile1.location_sharing = True
        self.profile1.location = Point(-74.0060, 40.7128)  # (longitude, latitude)
        self.profile1.save()
        
        self.profile2.location_sharing = True
        self.profile2.location = Point(-74.0062, 40.7130)  # (longitude, latitude)
        self.profile2.save()

    def test_nearby_friends_search(self):
        """Test nearby friends search functionality"""
        params = {
            'latitude': '40.7128',
            'longitude': '-74.0060',
            'radius': '1000'  # 1km radius
        }
        response = self.client.get(self.nearby_friends_url, params)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['nearby_friends']), 1)

    def test_location_disabled_friends(self):
        """Test that friends with disabled location sharing are not included"""
        self.profile2.location_sharing = False
        self.profile2.save()

        params = {
            'latitude': '40.7128',
            'longitude': '-74.0060',
            'radius': '1000'
        }
        response = self.client.get(self.nearby_friends_url, params)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['nearby_friends']), 0)

class VenueRatingTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.rating_url = '/api/ratings/'

    def test_rating_with_auth(self):
        """Test venue rating with authenticated user"""
        data = {
            'venue': self.venue.id,
            'rating': 4,
            'review': 'Great ambiance and service!'
        }
        response = self.client.post(self.rating_url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['rating'], 4)
        self.assertEqual(response.data['venue'], self.venue.id)

    def test_rating_validation(self):
        """Test rating validation rules"""
        # Test invalid rating value
        data = {
            'venue': self.venue.id,
            'rating': 6,  # Invalid rating > 5
            'review': 'Test review'
        }
        response = self.client.post(self.rating_url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Test missing venue
        data = {
            'rating': 4,
            'review': 'Test review'
        }
        response = self.client.post(self.rating_url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rating_update(self):
        """Test updating an existing rating"""
        # Create initial rating
        initial_data = {
            'venue': self.venue.id,
            'rating': 3,
            'review': 'Initial review'
        }
        response = self.client.post(self.rating_url, initial_data)
        rating_id = response.data['id']

        # Update rating
        update_data = {
            'rating': 4,
            'review': 'Updated review'
        }
        response = self.client.patch(f'{self.rating_url}{rating_id}/', update_data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['rating'], 4)
        self.assertEqual(response.data['review'], 'Updated review')

class CheckInDetailTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.checkin_url = '/api/checkins/'
        # Create a check-in
        self.checkin = CheckIn.objects.create(
            user=self.user1,
            venue=self.venue,
            vibe_rating='Lively',
            visibility='public'
        )

    def test_checkin_visibility(self):
        """Test check-in visibility rules"""
        # Test public check-in
        response = self.client.get(f'{self.checkin_url}{self.checkin.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Test friends-only check-in
        self.checkin.visibility = 'friends'
        self.checkin.save()
        
        # Test as friend
        self.client.force_authenticate(user=self.user2)
        response = self.client.get(f'{self.checkin_url}{self.checkin.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Test as non-friend
        non_friend = User.objects.create_user('non_friend', 'non@test.com', 'pass123')
        self.client.force_authenticate(user=non_friend)
        response = self.client.get(f'{self.checkin_url}{self.checkin.id}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_checkin_deletion(self):
        """Test check-in deletion"""
        response = self.client.delete(f'{self.checkin_url}{self.checkin.id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(CheckIn.objects.filter(id=self.checkin.id).exists())

class VenueSearchTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.venues_url = '/api/venues/'
        # Create additional venues for testing
        self.venue2 = Venue.objects.create(
            name='Quiet Bar',
            address='789 Calm St',
            city='Test City',
            location=Point(-74.0070, 40.7140),
            category='bar',
            description='A quiet spot for conversation'
        )
        self.venue3 = Venue.objects.create(
            name='Dance Club',
            address='456 Party Ave',
            city='Test City',
            location=Point(-74.0080, 40.7150),
            category='club',
            description='High energy dance club'
        )

    def test_venue_search(self):
        """Test venue search functionality"""
        # Test search by name
        response = self.client.get(f'{self.venues_url}?search=quiet')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], 'Quiet Bar')

        # Test search by category
        response = self.client.get(f'{self.venues_url}?category=club')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], 'Dance Club')

    def test_venue_location_search(self):
        """Test location-based venue search"""
        params = {
            'latitude': '40.7140',
            'longitude': '-74.0070',
            'radius': '1000'  # 1km radius
        }
        response = self.client.get(self.venues_url, params)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should return venues within the radius
        self.assertTrue(len(response.data) >= 2)

class VenueVibeTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.current_vibe_url = f'/api/venues/{self.venue.id}/current_vibe/'

    def test_venue_vibe_calculation(self):
        """Test venue vibe calculation from check-ins"""
        # Create multiple check-ins
        CheckIn.objects.create(
            user=self.user1,
            venue=self.venue,
            vibe_rating='Lively',
            visibility='public'
        )
        CheckIn.objects.create(
            user=self.user2,
            venue=self.venue,
            vibe_rating='Lively',
            visibility='public'
        )
        
        response = self.client.get(self.current_vibe_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['vibe'], 'Lively')
        self.assertEqual(response.data['checkins_count'], 2)

    def test_venue_vibe_timeout(self):
        """Test venue vibe calculation timeout"""
        # Create an old check-in
        old_checkin = CheckIn.objects.create(
            user=self.user1,
            venue=self.venue,
            vibe_rating='Lively',
            visibility='public'
        )
        # Manually update timestamp to be old
        old_time = timezone.now() - timedelta(hours=3)
        CheckIn.objects.filter(id=old_checkin.id).update(timestamp=old_time)
        
        response = self.client.get(self.current_vibe_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['vibe'], 'Unknown')
        self.assertEqual(response.data['checkins_count'], 0)