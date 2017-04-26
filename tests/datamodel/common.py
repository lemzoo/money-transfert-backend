from pymongo import MongoClient
from mongopatcher import MongoPatcher

from sief.main import create_app


class DatamodelBaseTest:
    """
    Datamodel patch try to be as less intrusive as possible regading
    sief app & mongoengine. Thus we only use pymongo and don't need to
    initialize a full app.
    """

    @classmethod
    def setup_class(cls):
        app = create_app()  # dummy app just to retrieve default configuration
        cls.patches_dir = app.config['MONGOPATCHER_PATCHES_DIR']
        cls.conn = MongoClient(host=app.config['MONGODB_TEST_URL'])
        cls.db = cls.conn.get_default_database()
        cls.patch = None

    def setup_method(self, method):
        self.conn.drop_database(self.conn.get_default_database().name)
        self.patcher = MongoPatcher(self.db, patches_dir=self.patches_dir)
        if not self.patch and hasattr(self, 'BASE_VERSION') and hasattr(self, 'TARGET_VERSION'):
            self.patch = self.find_patch(self.BASE_VERSION, self.TARGET_VERSION)
            assert self.patch, 'Unknown patch %s -> %s' % (self.BASE_VERSION, self.TARGET_VERSION)

    def find_patch(self, base_version, target_version):
        for patch in self.patcher.discover():
            if patch.base_version == base_version and patch.target_version == target_version:
                return patch
