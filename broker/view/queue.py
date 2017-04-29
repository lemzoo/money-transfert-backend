from flask import url_for
from flask.ext.restful import abort, Resource

from broker.exceptions import QueueManifestError
from core.tools import get_pagination_urlargs
from core.view_util import fields, BaseModelSchema, PaginationSerializer


def bind_queue_api(broker, api, base_resource_cls=Resource):
    QueueManifest = broker.model.QueueManifest
    QueueManifest.set_link_builder_from_api('QueueAPI')

    class QueueSchema(BaseModelSchema):
        _links = fields.Method('get_links')

        def __init__(self, *args, full_access=False, **kwargs):
            super().__init__(*args, **kwargs)

        def get_links(self, obj):
            route = url_for('QueueAPI', queue=obj.pk)
            links = {
                'self': route,
                'parent': url_for('QueueListAPI'),
                'messages': url_for('MessageListAPI', queue=obj.queue)
            }
            if obj.status in ['RUNNING', 'FAILURE']:
                links['pause'] = url_for('QueuePauseAPI', queue=obj.queue)
            elif obj.status == 'PAUSED':
                links['resume'] = url_for('QueueResumeAPI', queue=obj.queue)
            return links

        class Meta:
            model = QueueManifest

    queue_schema = QueueSchema()

    class QueueAPI(base_resource_cls):
        def get(self, queue):
            queue = QueueManifest.objects.get_or_404(queue=queue)
            return queue_schema.dump(queue).data

    class QueuePauseAPI(base_resource_cls):

        def post(self, queue):
            queue = QueueManifest.objects.get_or_404(queue=queue)
            try:
                queue.controller.pause()
            except QueueManifestError as exc:
                abort(400, message=str(exc))
            return queue_schema.dump(queue).data

    class QueueResumeAPI(base_resource_cls):

        def post(self, queue):
            queue = QueueManifest.objects.get_or_404(queue=queue)
            try:
                queue.controller.resume()
            except QueueManifestError as exc:
                abort(400, message=str(exc))
            return queue_schema.dump(queue).data

    class QueueListAPI(base_resource_cls):

        def get(self):
            page, per_page = get_pagination_urlargs()
            qs = QueueManifest.objects.paginate(page=page, per_page=per_page)
            route = url_for('QueueListAPI')
            return PaginationSerializer(queue_schema, route).dump(
                qs).data

    api.add_resource(QueueListAPI, '/queues')
    api.add_resource(QueueAPI, '/queues/<string:queue>')
    api.add_resource(QueuePauseAPI, '/queues/<string:queue>/pause')
    api.add_resource(QueueResumeAPI, '/queues/<string:queue>/resume')
