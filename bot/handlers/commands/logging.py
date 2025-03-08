import logging
import os
import sys

def get_task_logger(task_name, log_dir='bot/assets/logs', encoding='utf-8'):
    log_file = os.path.join(log_dir, f'log_{task_name}.txt')
    log = logging.getLogger(task_name)
    log.setLevel(logging.DEBUG)
    if not log.handlers:
        formatter = logging.Formatter('[%(asctime)s] %(filename)s:%(lineno)d %(levelname)-8s %(message)s')
        fh = logging.FileHandler(log_file, encoding=encoding)
        fh.setFormatter(formatter)
        log.addHandler(fh)
        sh = logging.StreamHandler(stream=sys.stdout)
        sh.setFormatter(formatter)
        log.addHandler(sh)
    return log

def get_logger(name=__file__, file='bot/log.txt', encoding='utf-8'):
    log = logging.getLogger(name)
    log.setLevel(logging.DEBUG)
    formatter = logging.Formatter('[%(asctime)s] %(filename)s:%(lineno)d %(levelname)-8s %(message)s')
    fh = logging.FileHandler(file, encoding=encoding)
    fh.setFormatter(formatter)
    log.addHandler(fh)
    sh = logging.StreamHandler(stream=sys.stdout)
    sh.setFormatter(formatter)
    log.addHandler(sh)
    return log

log = get_logger()
