from flask.ext import restful
from functools import partial

from broker_rabbit.view.message import bind_message_api


def bind_view(broker_rabbit, prefix=None, **kwargs):
    api = restful.Api(catch_all_404s=True)
    api.prefix = prefix

    # Avoid lowercasing of the endpoint
    def _wrap_add_resource(api):
        f = partial(api.add_resource)

        def wrapper(resource, *args, endpoint=None, **kwargs):
            endpoint = endpoint or resource.__name__
            return f(resource, *args, endpoint=endpoint, **kwargs)
        return wrapper
    api.add_resource = _wrap_add_resource(api)
    bind_message_api(broker_rabbit, api, **kwargs)
    return api


__all__ = ('bind_view', )
