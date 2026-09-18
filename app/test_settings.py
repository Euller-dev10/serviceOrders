from app.settings import *  # noqa: F401,F403

import os

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }
}

MEDIA_ROOT = os.path.join(BASE_DIR, 'media_test')