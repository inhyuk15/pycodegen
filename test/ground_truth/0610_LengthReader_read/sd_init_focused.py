class LengthReader(object):
    def __init__(self, unreader, length):
        self.unreader = unreader
        self.length = length

class Unreader(object):
    def read(self, size=None):
        ...
    def unread(self, data):
        ...
