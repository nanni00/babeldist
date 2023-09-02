import os

_log_dir_rel_path = '../log/'

def get_current_logfile_number(fname, extension='.log'):
    ncpy = 1
    if not os.path.exists(_log_dir_rel_path + fname + extension):
        return _log_dir_rel_path + fname + extension
    else:
        while os.path.exists(f'{_log_dir_rel_path}{fname}({ncpy}){extension}'):
            ncpy += 1
        return f'{_log_dir_rel_path}{fname}({ncpy}){extension}'