from functools import wraps
from flask import request
from flask.ext.cache import Cache


def _cached_fn_not_initialized(*args, **kwargs):
    raise RuntimeError('Cache has not been initialized')


def _make_cache_key(*args, **kwargs):
    return request.url


class CacheWithConfig:

    def __init__(self, app=None):
        self._cachers = []
        self._cache_engine = None
        self.enabled = False
        if app:
            self.init_app(app)

    def init_app(self, app):
        self.enabled = app.config['ENABLE_CACHE']
        if self.enabled:
            self._cache_engine = Cache(app, config={'CACHE_TYPE': 'simple'})
        for cacher in self._cachers:
            timeout = app.config[cacher['timeout_var']]
            if self.enabled and timeout:
                cacher['cached_fn'] = self._cache_engine.cached(
                    timeout, key_prefix=_make_cache_key)(cacher['fn'])
            else:
                cacher['cached_fn'] = cacher['fn']

    def cached_from_config(self, timeout_var):
        cacher = {'timeout_var': timeout_var}

        def decorator(fn):
            self._cachers.append(cacher)
            cacher['fn'] = fn
            cacher['cached_fn'] = _cached_fn_not_initialized

            @wraps(fn)
            def wrapper(*args, **kwargs):
                return cacher['cached_fn'](*args, **kwargs)

            return wrapper

        return decorator


default_cache = CacheWithConfig()
init_cache = default_cache.init_app
cached_from_config = default_cache.cached_from_config
