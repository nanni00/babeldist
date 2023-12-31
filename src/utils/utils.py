import os
import time
from typing import List


_log_dir_rel_path = 'src/log/'


def get_current_logfile_number(fname, extension='log'):
    ncpy = 1
    if not os.path.exists(_log_dir_rel_path + fname + '.' + extension):
        return _log_dir_rel_path + fname + '.' + extension
    else:
        while os.path.exists(_log_dir_rel_path + fname + '(' + str(ncpy - 1) + ')' + '.' + extension):
            ncpy += 1
        return _log_dir_rel_path + fname + '(' + str(ncpy - 1) + ')' + '.' + extension


def get_next_logfile_number(fname, extension='log'):
    ncpy = 1
    if not os.path.exists(_log_dir_rel_path + fname + '.' + extension):
        return _log_dir_rel_path + fname + '.' + extension
    else:
        while os.path.exists(_log_dir_rel_path + fname + '(' + str(ncpy) + ')' + '.' + extension):
            ncpy += 1
        return _log_dir_rel_path + fname + '(' + str(ncpy) + ')' + '.' + extension


def get_full_class_name(obj):
    module = obj.__class__.__module__
    if module is None or module == str.__class__.__module__:
        return obj.__class__.__name__
    return module + '.' + obj.__class__.__name__


def get_progress_bar(perc):
    return str(perc) + ' ' +u"\u2588"*int(perc//10)
  

def get_localtime_str():
    lt = time.localtime()
    return f"{lt.tm_year}/{lt.tm_mon}/{lt.tm_mday} {lt.tm_hour}:{lt.tm_min}:{lt.tm_sec}"
                


class Queue:
    def __init__(self, qtype: str, start_nodes: List[str]):
        self.q = start_nodes if qtype == 'list' else set(start_nodes)
    
    def add_item(self, i):
        self.q.append(i) if type(self.q) is list else self.q.add(i)

    def pop_item(self, idx=0):
        return self.q.pop(idx) if type(self.q) is list else self.q.pop()
    
    def __str__(self) -> str:
        return str(self.q)