from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import render
from functools import wraps

def rate_limit(limit=10, window=60):
    """
    Rate limiting decorator using Django cache.
    Limits requests per IP address for a specific view.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            ip = request.META.get('REMOTE_ADDR', '127.0.0.1')
            cache_key = f"rl_{view_func.__name__}_{ip}"
            
            count = cache.get(cache_key)
            if count is None:
                cache.set(cache_key, 1, timeout=window)
            elif count >= limit:
                if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':
                    return JsonResponse({'error': 'Too many requests. Please try again later.'}, status=429)
                return render(request, '403.html', {'error': '429: Too Many Requests. Please try again later.'}, status=429)
            else:
                try:
                    cache.incr(cache_key)
                except ValueError:
                    # In case the backend doesn't support incr properly or value was removed
                    cache.set(cache_key, count + 1, timeout=window)
            
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator
