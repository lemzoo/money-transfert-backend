from core import CoreResource
from sief import __version__ as BACKEND_VERSION


class VersionAPI(CoreResource):
    """Return the backend version.
    Version is retrieved from the sief module __version__ variable.
    """

    def get(self):
        return {
            '_links': {'self': '/version', 'root': '/'},
            'version': BACKEND_VERSION
        }
