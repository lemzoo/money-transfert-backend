from functools import wraps
from datetime import datetime
from bson.json_util import dumps
from flask import current_app, request, Blueprint, abort
from traceback import format_exc


def debug_print(handler, msg):
    print('Handler.event %s' % handler.event)
    print('Message %s received' % msg.id)
    print(msg.body)

ALLOWED_KEYWORDS = ('spec', 'limit', 'skip', 'filter', 'sort')


def debug(func):
    """Debug decorator for the routes"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Use pymongo directly
        db = current_app.db.connection.get_default_database()
        col = db['connector_debug']
        payload = {
            'start': datetime.utcnow(),
            'path': request.path,
            'request': {
                'url': request.url,
                'data': request.get_data(),
                'headers': {k: v for k, v in request.headers},
            }
        }
        obj_id = col.insert(payload)
        try:
            ret = func(*args, **kwargs)
        except Exception as exc:
            payload['error'] = str(exc)
            raise
        else:
            payload['response'] = ret.data
        finally:
            payload['end'] = datetime.utcnow()
            obj_id = col.update({'_id': obj_id}, payload)
        return ret
    return wrapper


class RequestDebugger:
    def __init__(self, requests):
        self.requests = requests

    def get(self, *args, **kwargs):
        return self.request('GET', *args, **kwargs)

    def post(self, *args, **kwargs):
        return self.request('POST', *args, **kwargs)

    def patch(self, *args, **kwargs):
        return self.request('PATCH', *args, **kwargs)

    def put(self, *args, **kwargs):
        return self.request('PUT', *args, **kwargs)

    def delete(self, *args, **kwargs):
        return self.request('DELETE', *args, **kwargs)

    def request(self, method, url, data=None, json=None, **kwargs):
        # Use pymongo directly
        db = current_app.db.connection.get_default_database()
        col = db['connector_debug']
        payload = {
            'start': datetime.utcnow(),
            'path': url,
            'request': {
                'method': method,
                'url': url,
                'data': data,
                'json': json
            }
        }
        obj_id = col.insert(payload)
        try:
            ret = self.requests.request(method, url, data=data, json=json, **kwargs)
        except Exception:
            payload['error'] = format_exc()
            raise
        else:
            payload['status_code'] = ret.status_code
            payload['response'] = ret.text
        finally:
            payload['end'] = datetime.utcnow()
            obj_id = col.update({'_id': obj_id}, payload)
        return ret


connector_debug = Blueprint('connector_debug', __name__)


@connector_debug.route('/debug', methods=('POST', 'GET'))
def get_debug():
    if request.data:
        filt = request.get_json()
    else:
        filt = {}
    bad_keys = [key for key in filt.keys() if key not in ALLOWED_KEYWORDS]
    sorting = filt.pop('sort', {})
    if bad_keys:
        abort(400, "Invalid keywords %s" % bad_keys)
    db = current_app.db.connection.get_default_database()
    col = db['connector_debug']
    cursor = col.find(**filt).sort(sorting)
    return dumps({
        '_items': [c for c in cursor],
        '_query': filt,
        '_allowed_keywords': ALLOWED_KEYWORDS
    }, indent=True)
