from rest_framework.views import exception_handler
from rest_framework.response import Response
from django.core.exceptions import ValidationError
from django.http import Http404
import logging

import firebase_admin
from firebase_admin import credentials, messaging
from django.conf import settings
from django.db.models import Q
from datetime import timedelta
from django.utils import timezone

logger = logging.getLogger(__name__)

def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)
    
    if response is None:
        if isinstance(exc, ValidationError):
            response = Response({
                'error': 'Validation Error',
                'details': exc.messages
            }, status=400)
        elif isinstance(exc, Http404):
            response = Response({
                'error': 'Not Found',
                'details': str(exc)
            }, status=404)
        else:
            logger.error(f"Unhandled exception: {exc}", exc_info=True)
            response = Response({
                'error': 'Internal Server Error',
                'details': 'An unexpected error occurred'
            }, status=500)
    
    # Add request ID for tracking
    if response is not None:
        response.data['request_id'] = context['request'].META.get('HTTP_X_REQUEST_ID')
    
    return response