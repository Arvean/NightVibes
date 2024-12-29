# tasks.py - Background tasks
from celery import shared_task
from django.utils import timezone
from datetime import timedelta

@shared_task
def cleanup_old_checkins():
    """Remove check-ins older than 24 hours"""
    cutoff = timezone.now() - timedelta(hours=24)
    CheckIn.objects.filter(timestamp__lt=cutoff).delete()

@shared_task
def update_venue_statistics():
    """Update cached venue statistics"""
    for venue in Venue.objects.all():
        current_vibe = venue.get_current_vibe()
        cache.set(f'venue_vibe_{venue.id}', current_vibe, timeout=300)