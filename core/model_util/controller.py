from flask.ext.mongoengine import mongoengine, Document

from core.tools import abort


def parse_error_e11000(error):
    if 'E11000' in str(error):
        error = str(error)
        token = error.split('dup key')
        field = ''
        value = ''
        field = token[0].split(' ')[-2]
        field = field[0:field.rfind('_')]
        if '$' in field:
            field = field[field.find('$') + 1:len(field)]
        if "\"" in token[-1]:
            value = token[-1].split("\"")[1]
        else:
            value = token[-1]
        if field and value:
            error = "le champ %s doit être unique, valeur %s déjà existante" % (field, value)

    return error


class BaseController:

    """
    Controller base class, providing usefull function for handling document
    """

    def __init__(self, document):
        self.document = document

    def save_or_abort(self, abort=abort, if_match=None):
        try:
            if if_match is True:
                self.document.save(save_condition={"doc_version": self.document.doc_version})
            elif if_match:
                self.document.save(save_condition={"doc_version": if_match})
            else:
                self.document.save()
        except mongoengine.ValidationError as exc:
            errors = exc.to_dict()
            if errors:
                # ValidationErrors issued in the clean function are wrapped
                # in a useless NON_FIELD_ERRORS
                non_field_errors = errors.pop(mongoengine.base.NON_FIELD_ERRORS, {})
                if isinstance(non_field_errors, dict):
                    errors.update(non_field_errors)
                    abort(400, **errors)
                else:
                    abort(400, non_field_errors)
            else:
                abort(400, exc.message)
        except mongoengine.errors.NotUniqueError as exc:
            abort(400, parse_error_e11000(exc))
        except mongoengine.errors.FieldDoesNotExist as exc:
            abort(400, str(exc))

    def update(self, payload):
        for key, value in payload.items():
            setattr(self.document, key, value)


class ControlledDocument(Document):

    """
    Mongoengine abstract document providing a controller attribute to
    alter with style the document !
    """
    meta = {'abstract': True, 'controller_cls': BaseController}

    @property
    def controller(self):
        controller_cls = self._meta.get('controller_cls')
        if not controller_cls:
            raise NotImplementedError('No controller setted for this document')
        return controller_cls(self)

    def clean(self):
        """Automatically called at save time, triggers controller's clean"""
        ctrl = self.controller
        if hasattr(ctrl, 'clean'):
            ctrl.clean()
