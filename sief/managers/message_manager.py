from flask.ext.script import Manager
from broker.model.message import Message
from flask import current_app

message_manager = Manager(usage="Perform messages Operations")


@message_manager.command
def check_skip():
    """Skip all message that should have been skipped"""
    handlers_to_skip = [x.label for x in current_app.extensions[
        'broker'].event_handler._items if hasattr(x, 'to_skip') and getattr(x, 'to_skip')]
    if not handlers_to_skip:
        print("no message to be fixed.")
        return
    messages = Message.objects(status__in=['READY', 'FAILURE'])
    counter = 0
    for msg in messages:
        if msg.handler in handlers_to_skip:
            msg.status = 'SKIPPED'
            msg.save()
            counter += 1
    print("%s message(s) fixed." % counter)
