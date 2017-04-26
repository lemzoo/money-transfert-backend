import requests
from bson import json_util

from connector.exceptions import (
    ProcessMessageEventHandlerConfigError, ProcessMessageNoResponseError,
    ProcessMessageBadResponseError)
from connector.processor import register_processor


# Provide the webhook basic processor
@register_processor
def webhook(handler, msg):
    """
    Webhook processor, basically transmit the data direct to the webservice.

    Event handler context:
     - url, mandatory field
     - method (default: POST)
     - headers (i.g. {'Auth': 'Basic ...'}), ``Content-Type`` automatically
        set to ``application/json``
     - proxies (i.g. {'http': 'http://prox.y', 'https': 'https://prox.y'})
     - timeout (default: 60s)
    """
    h_context = handler.context
    if 'url' not in h_context:
        raise ProcessMessageEventHandlerConfigError(
            '`url` field is mandatory in event handler context')
    body = {'event': handler.event, 'origin': msg.origin,
            'timestamp': msg.created.isoformat(),
            'context': msg.context}
    json_body = json_util.dumps(body)
    url = h_context['url']
    timeout = h_context.get('timeout', 60)
    proxies = h_context.get('proxies')
    headers = h_context.get('headers', {})
    headers['Content-Type'] = 'application/json; charset=UTF-8'
    try:
        r = requests.request(h_context.get('method', 'POST'), url,
                             headers=headers, data=json_body.encode('utf-8'),
                             proxies=proxies, timeout=timeout)
    except (requests.ConnectionError, requests.Timeout) as e:
        raise ProcessMessageNoResponseError(str(e))
    result = 'Serveur %s answered:\n%s %s\n%s' % (url, r.status_code, r.reason, r.text)
    if r.ok:
        return result
    elif r.status_code in (503, 504):
        raise ProcessMessageNoResponseError(result)
    else:
        raise ProcessMessageBadResponseError(result)
