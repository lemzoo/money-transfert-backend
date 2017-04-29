import logging


class Logger:

    def __init__(self):
        self.level = 0

    def set_log(self, log):
        self.level = log
        if self.level:
            logging.basicConfig(filename='bootstrap_analytics.log', level=logging.WARNING)

    def log(self, msg, lvl):
        if self.level:
            if lvl == 'CRITICAL':
                logging.critical(msg)
            elif lvl == 'DEBUG':
                logging.debug(msg)
            elif lvl == 'WARNING':
                logging.warning(msg)
            elif lvl == 'ERROR':
                logging.error(msg)
            else:
                logging.info(msg)

logger = Logger()


def build_key(k, name):
    key = str(k)
    if name:
        key = name + "." + str(k)
    return key


def flat_json(json):
    flat = {}

    def inner_flat(json, flat, name=None):
        if isinstance(json, (list)):
            for index, e in enumerate(json):
                key = build_key(index, name)
                if isinstance(e, (list, dict)):
                    inner_flat(e, flat, key)
                else:
                    flat[key] = e
            return flat

        for k in json.keys():
            if isinstance(json[k], (list, dict)):
                inner_flat(json[k], flat, build_key(k, name))
            else:
                key = build_key(k, name)
                flat[key] = json[k]

    inner_flat(json, flat)

    return flat


def diff_json(json1, json2):
    flat1 = flat_json(json1)
    flat2 = flat_json(json2)
    diff = set(flat1.items()) ^ set(flat2.items())
    return diff


def diff_json_key(json1, json2):
    diff = diff_json(json1, json2)
    diff = set(dict(diff).keys())
    return list(diff)


def own_by(key, json):
    keys = key.split(".")
    dic = json
    for k in keys:
        if k in dic:
            dic = dic[k]
        else:
            if isinstance(dic, list):
                try:
                    k = int(k)
                    if k < len(dic):
                        dic = dic[k]
                    else:
                        return False
                except:
                    return False
            else:
                return False
    return True


def build_filters(date_to, date=None):
    filters_on_collection = {}
    if date:
        filters_on_collection['doc_updated__gte'] = str(date)
    filters_on_collection['doc_updated__lte'] = str(date_to)

    return filters_on_collection
