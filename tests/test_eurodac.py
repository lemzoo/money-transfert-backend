import pytest

from tests import common
from flask import current_app
from sief.model.eurodac import generate_eurodac_ids


class TestCORS(common.BaseTest):

    def test_default(self):
        for i in range(0, 1000):
            eurodac = generate_eurodac_ids()[0]
            assert len(eurodac) == 10
            assert eurodac == 'XXX{:0>7}'.format(i)

    def test_multiple_ask(self):
        set_eurodac = set()
        for i in range(1000):
            eurodacs = generate_eurodac_ids(generate_number=10)
            for eurodac in eurodacs:
                assert len(eurodac) == 10
                assert eurodac not in set_eurodac
                set_eurodac.add(eurodac)

    def test_switch_env_variable(self):
        for i in range(0, 100):
            eurodac = generate_eurodac_ids()[0]
            assert len(eurodac) == 10
            assert eurodac == 'XXX{:0>7}'.format(i)
        current_app.config['EURODAC_PREFIX'] = '993'
        for i in range(0, 100):
            eurodac = generate_eurodac_ids()[0]
            assert len(eurodac) == 10
            assert eurodac == '993{:0>7}'.format(i)

    def test_simultaneous_generation(self):
        generate_eurodac_items = []
        concurrency = 150
        for i in range(0, concurrency):
            generate_eurodac_items.append([])

        def generate_eurodac(eurodac_list):
            with self.app.app_context():
                for i in range(0, 10):
                    eurodac = generate_eurodac_ids()[0]
                    assert len(eurodac) == 10
                    eurodac_list.append(eurodac)

        from multiprocessing.pool import ThreadPool
        pool = ThreadPool(processes=concurrency)
        results = pool.map(generate_eurodac, generate_eurodac_items)

        eurodac_set = set()
        for eurodac_list in generate_eurodac_items:
            for eurodac in eurodac_list:
                assert eurodac not in eurodac_set
                eurodac_set.add(eurodac)
