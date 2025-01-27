import firebase_admin
from firebase_admin import credentials, messaging
from django.conf import settings
from django.db.models import Q
from datetime import timedelta
from django.utils import timezone
from .models import Notification, DeviceToken

# Initialize Firebase Admin SDK
cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
firebase_admin.initialize_app(cred)

class NotificationService:
    @staticmethod
    def send_to_user(user, notification_type, title, message, data=None):
        """
        Send notification to all active devices of a user
        """
        if data is None:
            data = {}

        # Create notification record
        notification = Notification.objects.create(
            user=user,
            type=notification_type,
            title=title,
            message=message,
            data=data
        )

        # Get all active device tokens for the user
        device_tokens = DeviceToken.objects.filter(
            user=user,
            is_active=True
        ).values_list('token', flat=True)

        # If no devices, just save the notification
        if not device_tokens:
            return True

        try:
            # Prepare the message
            message = messaging.MulticastMessage(
                notification=messaging.Notification(
                    title=title,
                    body=message,
                ),
                data=data,
                tokens=list(device_tokens),
            )
            
            # Send the message
            response = messaging.send_multicast(message)
            
            # Update notification status
            notification.is_sent = response.success_count > 0
            notification.save()
            
            return notification.is_sent
        except Exception as e:
            print(f"Error sending notification: {str(e)}")
            return False

    @staticmethod
    def send_friend_request(sender, receiver):
        """Send notification for new friend request"""
        return NotificationService.send_to_user(
            user=receiver,
            notification_type='friend_request',
            title='New Friend Request',
            message=f'{sender.username} sent you a friend request',
            data={
                'type': 'friend_request',
                'sender_id': str(sender.id),
                'sender_username': sender.username
            }
        )

    @staticmethod
    def send_meetup_ping(ping):
        """Send notification for new meetup ping"""
        return NotificationService.send_to_user(
            user=ping.receiver,
            notification_type='meetup_ping',
            title='New Meetup Request',
            message=f'{ping.sender.username} wants to meet at {ping.venue.name}',
            data={
                'type': 'meetup_ping',
                'ping_id': str(ping.id),
                'sender_id': str(ping.sender.id),
                'venue_id': str(ping.venue.id)
            }
        )

    @staticmethod
    def send_nearby_friend_alert(user, friend, venue):
        """Send notification when a friend checks in nearby"""
        return NotificationService.send_to_user(
            user=user,
            notification_type='nearby_friend',
            title='Friend Nearby',
            message=f'{friend.username} is at {venue.name}',
            data={
                'type': 'nearby_friend',
                'friend_id': str(friend.id),
                'venue_id': str(venue.id)
            }
        )

    @staticmethod
    def cleanup_old_notifications():
        """Clean up notifications older than 30 days"""
        threshold = timezone.now() - timedelta(days=30)
        Notification.objects.filter(created_at__lt=threshold).delete()