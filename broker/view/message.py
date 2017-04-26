from flask import request, url_for
from flask.ext.restful import abort, Resource

from broker.model.message import MESSAGE_STATUS
from core.tools import get_pagination_urlargs
from core.view_util import fields, BaseModelSchema, PaginationSerializer
from dateutil.parser import parse as dateparse
from mongoengine import ValidationError


def bind_message_api(broker, api, base_resource_cls=Resource):
    Message = broker.model.Message
    QueueManifest = broker.model.QueueManifest
    Message.set_link_builder_from_api('MessageAPI')

    class MessageSchema(BaseModelSchema):
        _links = fields.Method('get_links')

        def __init__(self, *args, full_access=False, **kwargs):
            super().__init__(*args, **kwargs)

        def get_links(self, obj):
            route = url_for('MessageAPI', queue=obj.queue, item_id=obj.pk)
            return {
                'self': route,
                'parent': url_for('MessageListAPI', queue=obj.queue),
                'delete': route
            }

        class Meta:
            model = Message
            model_fields_kwargs = {key: {'dump_only': True}
                                   for key in ('queue', 'created')}

    message_schema = MessageSchema()

    class MessageAPI(base_resource_cls):

        def get(self, queue, item_id):
            msg = Message.objects.get_or_404(pk=item_id, queue=queue)
            return message_schema.dump(msg).data

        def patch(self, queue, item_id):
            q = QueueManifest.objects.get_or_404(queue=queue)
            if q.status not in ['STOPPED', 'PAUSED']:
                abort(400, _error="Cannot alter message, queue %s is not"
                                  " PAUSED or STOPPED" % q.queue)
            msg = Message.objects.get_or_404(pk=item_id, queue=queue)
            msg, errors = message_schema.update(msg, request.get_json())
            if errors:
                abort(400, **errors)
            try:
                msg.save()
            except ValidationError as exc:
                abort(400, str(exc))
            return message_schema.dump(msg).data, 200

        def delete(self, queue, item_id):
            q = QueueManifest.objects.get_or_404(queue=queue)
            if q.status not in ['STOPPED', 'PAUSED']:
                abort(400, _error="Cannot delete message, queue %s is not"
                                  " PAUSED or STOPPED" % q.queue)
            msg = Message.objects.get_or_404(pk=item_id, queue=queue)
            msg, errors = message_schema.update(msg, {'status': "DELETED"})
            if errors:
                abort(400, **errors)
            try:
                msg.save()
            except ValidationError as exc:
                abort(400, str(exc))
            return {}, 204

    class MessageListAPI(base_resource_cls):

        @staticmethod
        def _get_urlargs():
            page, per_page = get_pagination_urlargs()
            extended_route = ""
            status = request.args.getlist('status') or ('READY', 'FAILURE')
            for s in status:
                extended_route += "&status=" + s
                if s not in MESSAGE_STATUS:
                    abort(400, status='must be %s' % str(MESSAGE_STATUS))
            filters = {'status__in': status}
            from_date = request.args.get('from')
            if from_date:
                try:
                    extended_route += "&from=" + from_date
                    from_date = dateparse(from_date)
                except ValueError as exc:
                    abort(400, **{'from': str(exc)})
                filters['created__gte'] = from_date
            to_date = request.args.get('to')
            if to_date:
                try:
                    extended_route += "&to=" + to_date
                    to_date = dateparse(to_date)
                except ValueError as exc:
                    abort(400, to=str(exc))
                filters['created__lte'] = to_date
            # Only first page
            return 1, per_page, filters, extended_route

        def get(self, queue):
            page, per_page, filters, extended_route = self._get_urlargs()
            messages = Message.objects(queue=queue, **filters).order_by(
                '+created').paginate(page=page, per_page=per_page)
            route = url_for('MessageListAPI', queue=queue)
            links = {'parent': url_for('QueueAPI', queue=queue)}
            result = PaginationSerializer(message_schema, route).dump(
                messages, links=links).data
            # Add extended_route informations into _links.self + remove next / prev link
            result['_links'] = {
                'self': result['_links']['self'] + extended_route,
                'parent': url_for('QueueAPI', queue=queue)
            }
            return result

    api.add_resource(MessageAPI, '/queues/<string:queue>/messages/<objectid:item_id>')
    api.add_resource(MessageListAPI, '/queues/<string:queue>/messages')
