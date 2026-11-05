"""Repeatable local queue benchmark. No Discord/Telegram/Zalo network calls."""
import sqlite3
import tempfile
import time
from pathlib import Path

from durable_tasks import TaskQueue


def trial(workers, count=25, service_seconds=0.04):
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / 'benchmark.db'

        def db():
            connection = sqlite3.connect(path, timeout=10)
            connection.row_factory = sqlite3.Row
            connection.execute('PRAGMA journal_mode=WAL')
            return connection

        def send(*_args):
            time.sleep(service_seconds)

        queue = TaskQueue(db, send, workers=workers)
        started = time.monotonic()
        for index in range(count):
            queue.submit('fixture', f'channel-{index % 5}', 'local fixture')
        queue.start()
        try:
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                if sum(row['status'] == 'COMPLETED' for row in queue.list('fixture')) == count:
                    return time.monotonic() - started
                time.sleep(0.01)
            raise TimeoutError('Fixture did not complete')
        finally:
            queue.close()


if __name__ == '__main__':
    for workers in (1, 5):
        samples = [trial(workers) for _ in range(3)]
        print(f'{workers} worker(s), 25 finite jobs, 5 independent channels, 40ms mock API: '
              f'{min(samples):.3f}–{max(samples):.3f}s; median {sorted(samples)[1]:.3f}s')
