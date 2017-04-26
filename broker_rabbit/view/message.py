from flask import request, url_for
from flask.ext.restful import abort, Resource

from bson.objectid import ObjectId
from mongoengine.queryset.visitor import Q

from core.view_util import fields, BaseModelSchema, PaginationSerializer

from core.tools import get_pagination_urlargs, get_search_urlargs
from broker_rabbit.model.message import MESSAGE_STATUS
from dateutil.parser import parse as dateparse


def bind_message_api(broker_rabbit, api, base_resource_cls=Resource):
    Message = broker_rabbit.model.Message
    Message.set_link_builder_from_api('MessageRabbitAPI')

    class MessageSchema(BaseModelSchema):
        _links = fields.Method('get_links')

        def __init__(self, *args, full_access=False, **kwargs):
            super().__init__(*args, **kwargs)

        def get_links(self, obj):
            route = url_for('MessageRabbitAPI',
                            queue=obj.queue, item_id=obj.pk)
            return {
                'self': route,
                'parent': url_for('MessageRabbitListAPI', queue=obj.queue),
                'delete': route
            }

        class Meta:
            model = Message
            model_fields_kwargs = {key: {'dump_only': True}
                                   for key in ('queue', 'created',
                                               'origin', 'discriminant')}

    message_schema = MessageSchema()

    class MessageRabbitAPI(base_resource_cls):

        def get(self, queue, item_id):
            msg = Message.objects.get_or_404(pk=item_id, queue=queue)
            return message_schema.dump(msg).data

        def patch(self, queue, item_id):
            msg = Message.objects.get_or_404(pk=item_id, queue=queue)
            payload = request.get_json()
            msg, errors = message_schema.update(msg, payload)
            if errors:
                abort(400, **errors)

            msg.save()
            message_dump = message_schema.dump(msg).data
            if payload.get('status') == 'RETRY':
                broker_rabbit.send(queue, message_dump)
            return message_dump, 200

    class MessageRabbitListAPI(base_resource_cls):

        @staticmethod
        def _get_urlargs():
            urlargs = get_search_urlargs()
            extended_route = ""

            status = request.args.getlist('status') or MESSAGE_STATUS
            for s in status:
                extended_route += "&status=" + s
                if s not in MESSAGE_STATUS:
                    abort(400, status='must be %s' % str(MESSAGE_STATUS))
            filters = Q(status__in=status)
            if urlargs['q']:
                query = urlargs['q']
                extended_route += "&q=" + query
                q_filters = Q(discriminant=query) | Q(handler=query)
                if ObjectId.is_valid(query):
                    q_filters |= Q(pk=query)
                filters &= (q_filters)
            if urlargs['fq']:
                fquery = urlargs['fq'][0]
                extended_route += "&fq=" + fquery
                queries = fquery.split(' AND ')
                for query in queries:
                    key, value = query.split(':', 1)
                    if key == 'pk':
                        if ObjectId.is_valid(value):
                            filters &= Q(pk=value)
                        else:
                            abort(400, pk='%s is not a valid Message ID' % value)
                    elif key == 'discriminant':
                        filters &= Q(discriminant=value)
                    elif key == 'created':
                        from_date, to_date = value[1:-1].split(' TO ')
                        if from_date != '*':
                            try:
                                from_date = dateparse(from_date)
                            except ValueError as exc:
                                abort(400, from_date=str(exc))
                            filters &= Q(created__gte=from_date)
                        if to_date != '*':
                            try:
                                from_date = dateparse(to_date)
                            except ValueError as exc:
                                abort(400, to_date=str(exc))
                            filters &= Q(created__lte=to_date)
            return urlargs['page'], urlargs['per_page'], filters, extended_route

        def get(self, queue):
            page, per_page, filters, extended_route = self._get_urlargs()
            messages = Message.objects(Q(queue=queue) & filters).order_by(
                '-created').paginate(page=page, per_page=per_page)
            route = url_for('MessageRabbitListAPI', queue=queue)
            result = PaginationSerializer(message_schema, route).dump(messages).data
            result['_links'] = {
                'self': result['_links']['self'] + extended_route
            }
            return result

    class QueueRabbitAPI(base_resource_cls):

        @staticmethod
        def _get_status_count(queue):
            status_count = dict.fromkeys(MESSAGE_STATUS, 0)
            query = {
                "$group": {
                    "_id": "$status",
                    "count": {"$sum": 1}
                }
            }
            results = Message.objects(queue=queue).aggregate(query)
            for result in results:
                status = result['_id']
                status_count[status] = result['count']
            return status_count

        def get(self, queue):
            if queue not in broker_rabbit.queues:
                abort(404, _error='queue %s not found on the server' % queue)

            ret = {
                '_links': {
                    'messages': '/api/rabbit/queues/' + queue + '/messages',
                    'parent': '/api/rabbit/queues',
                    'self': '/api/rabbit/queues/' + queue
                },
                'id': queue,
                'queue': queue,
                'status': 'RUNNING',
                'status_count': self._get_status_count(queue)
            }
            return ret

    class QueueRabbitListAPI(base_resource_cls):

        def get(self):
            items = []
            for queue in broker_rabbit.queues:
                item = {
                    'id': queue,
                    'queue': queue,
                    'status': 'RUNNING',
                    '_links': {
                        'parent': '/api/rabbit/queues',
                        'messages': '/api/rabbit/queues/' + queue + '/messages',
                        'self': '/api/rabbit/queues/' + queue
                    }
                }
                items.append(item)

            ret = {
                '_meta': {
                    'page': 1,
                    'total': len(items),
                    'per_page': 12
                },
                '_items': items,
                '_links': {
                    'self': '/api/rabbit/queues?per_page=12&page=1'
                }
            }

            return ret

    api.add_resource(QueueRabbitAPI, '/queues/<string:queue>')
    api.add_resource(QueueRabbitListAPI, '/queues')
    api.add_resource(MessageRabbitAPI, '/queues/<string:queue>/messages/<objectid:item_id>')
    api.add_resource(MessageRabbitListAPI, '/queues/<string:queue>/messages')
