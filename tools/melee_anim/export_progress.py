"""Bounded local download progress and real render-log frame reporting."""
from contextlib import contextmanager
import re
import threading
import time


class ProgressRegistry:
    def __init__(self, limit=64, ttl=600):
        self.limit, self.ttl = limit, ttl
        self.jobs, self.lock = {}, threading.RLock()

    def _prune(self):
        now = time.monotonic()
        for key, row in list(self.jobs.items()):
            if row['status'] != 'working' and now-row['_updated'] > self.ttl:
                del self.jobs[key]

    def start(self, key):
        if not re.fullmatch(r'[a-zA-Z0-9_-]{16,80}', key):
            raise ValueError('Invalid progress ID')
        with self.lock:
            self._prune()
            if key in self.jobs:raise ValueError('Progress ID already used')
            while len(self.jobs) >= self.limit:
                finished = [k for k,v in self.jobs.items() if v['status'] != 'working']
                if not finished:raise ValueError('Too many active exports')
                del self.jobs[min(finished,key=lambda k:self.jobs[k]['_updated'])]
            self.jobs[key] = dict(status='working',phase='Preparing download',total=0,
                                  completed=0,files_completed=0,percent=0,
                                  frames_done=0,frames_total=0,unit='frames',label='',
                                  _updated=time.monotonic())
        return lambda event:self.update(key,event)

    def update(self, key, event):
        with self.lock:
            row = self.jobs[key]
            if row['status'] != 'working':return
            row.update(event)
            row['percent'] = max(0,min(99,float(row['percent'])))
            row['_updated'] = time.monotonic()

    def finish(self, key, error=None):
        with self.lock:
            row = self.jobs[key]
            row.update(status='error' if error else 'complete',
                       phase=error or 'Download ready',_updated=time.monotonic())
            if not error:row['percent']=100

    def get(self, key):
        with self.lock:
            self._prune()
            row = self.jobs.get(key)
            return {k:v for k,v in row.items() if not k.startswith('_')} if row else None


@contextmanager
def render_progress(log_path, total, callback):
    """Watch fresh stdout from the existing renderer; no guessed timers/counts."""
    if callback is None:
        yield
        return
    stop = threading.Event()
    previous = None

    def sample():
        nonlocal previous
        try:text = log_path.read_text(errors='replace')
        except OSError:return
        matches = re.findall(r'Rendered (\d+)/(\d+) frames', text)
        if matches:
            done, count = map(int,matches[-1])
            phase = 'Encoding rendered GIF' if done == count else 'Rendering frames'
        else:done,count,phase = 0,total,'Preparing animation'
        current = (phase,done,count)
        if current != previous:
            callback(*current)
            previous = current

    def watch():
        sample()
        while not stop.wait(.3):sample()

    thread = threading.Thread(target=watch,daemon=True)
    thread.start()
    try:yield
    finally:
        stop.set();thread.join();sample()
