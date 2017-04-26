from datetime import datetime


def load_date(document, field):
    date = document[field]['$date']
    return datetime.fromtimestamp(int(date) / 1000)


def compute_delay_date(date_begin, date_end):
    from workdays import networkdays as subdays
    if date_begin > date_end:  # swap them
        date_begin, date_end = date_end, date_begin
    value = subdays(date_begin, date_end)
    return value


def compute_delay(document, date):
    return compute_delay_date(date, load_date(document, 'date_debut'))
