"""Linux descendant cleanup, including evaluator children in separate sessions."""

import os
import signal
from pathlib import Path


def snapshot():
    result = {}
    for path in Path("/proc").glob("[0-9]*/stat"):
        try:
            raw = path.read_text()
            fields = raw[raw.rfind(")") + 2 :].split()
            result[int(path.parent.name)] = (int(fields[1]), fields[19])
        except (OSError, ValueError, IndexError):
            continue
    return result


class ProcessTree:
    def __init__(self, pid):
        self.root = pid
        self.known = {}
        current = snapshot()
        self.root_identity = current.get(pid, (None, None))[1]
        self.observe()

    def observe(self):
        current = snapshot()
        roots = {
            pid
            for pid, identity in self.known.items()
            if pid in current and current[pid][1] == identity
        }
        if self.root in current and current[self.root][1] == self.root_identity:
            roots.add(self.root)
        while True:
            expanded = roots | {
                pid for pid, (parent, _) in current.items() if parent in roots
            }
            if expanded == roots:
                break
            roots = expanded
        for pid in roots:
            self.known[pid] = current[pid][1]

    def send(self, sig):
        current = snapshot()
        for pid, identity in self.known.items():
            if pid in current and current[pid][1] == identity:
                try:
                    os.kill(pid, sig)
                except ProcessLookupError:
                    pass

    def stop(self, process):
        # Freeze known descendants before rescanning so they cannot fork during cleanup.
        for _ in range(8):
            self.observe()
            count = len(self.known)
            self.send(signal.SIGSTOP)
            self.observe()
            if len(self.known) == count:
                break
        self.send(signal.SIGKILL)
        process.wait(timeout=5)
