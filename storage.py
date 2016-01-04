from gevent import sleep


class LimitedHandle(file):
    offset = 0

    def __init__(self, get_size, name, mode='r'):
        self.get_size = get_size
        super(LimitedHandle, self).__init__(name, mode)

    def read(self, size=None):
        max_size = self.get_size()
        if size is None:
            size = max_size - self.offset
        else:
            while self.offset + size > self.get_size():
                sleep(1)

        return super(LimitedHandle, self).read(size)

    def yield_all(self, chunk_size=100):
        for chunk in iter(lambda: self.read(chunk_size), ''):
            yield chunk
