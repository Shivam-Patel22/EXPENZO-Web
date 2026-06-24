#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
        
    # Auto-migrate before starting the server so new clones work out of the box
    if len(sys.argv) > 1 and sys.argv[1] == 'runserver':
        execute_from_command_line(['manage.py', 'migrate'])
        
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
