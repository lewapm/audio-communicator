# vim:ts=4:sts=4:sw=4:expandtab

import ctypes
import numpy as np

import defs
import types

#TODO: safeguard 
library = ctypes.cdll.LoadLibrary('libpulse-simple.so.0')

library.strerror.restype = ctypes.c_char_p 

def safe_pa_call(fun):
    def inner(*args):
        error = ctypes.c_int(0)
        args = list(args)
        args.append(ctypes.pointer(error))
        ret = fun(*args)
        if error.value != 0:
            strerror = library.strerror(error)
            raise IOError(strerror)
        return ret
    return inner
pa_simple_new = safe_pa_call(library.pa_simple_new)
pa_simple_read = safe_pa_call(library.pa_simple_read)
pa_simple_write = safe_pa_call(library.pa_simple_write)
pa_simple_drain = safe_pa_call(library.pa_simple_drain)
pa_simple_flush = safe_pa_call(library.pa_simple_flush)
pa_simple_get_latency = safe_pa_call(library.pa_simple_get_latency)
pa_simple_free = library.pa_simple_free

class SimpleConnection(object):
    def __init__(self, connection, sample_spec, channel_map, buffer_attr):
        self.connection = connection
        self.sample_spec = sample_spec
        self.channel_map = channel_map
        self.buffer_attr = buffer_attr

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.close()

    def read_raw(self, size):
        if self.connection is None:
            raise IOError("Closed connection")
        data = (ctypes.c_uint8 * size)()
        pa_simple_read(self.connection, ctypes.pointer(data), size)
        return bytes(bytearray(data))

    def write_raw(self, data):
        if self.connection is None:
            raise IOError("Closed connection")
        pa_simple_write(self.connection, data, len(data))

    sample_length = {
        defs.SAMPLE_U8    : 1,
        defs.SAMPLE_S16LE : 2,
        defs.SAMPLE_S32LE : 4,
    }
    sample_type = {
        defs.SAMPLE_U8    : np.uint8,
        defs.SAMPLE_S16LE : np.int16,
        defs.SAMPLE_S32LE : np.int32,
    }

    def read(self, nsamples):
        if self.connection is None:
            raise IOError("Closed connection")
        sample_len = SimpleConnection.sample_length[self.format]
        sample_typ = SimpleConnection.sample_type[self.format]
                
        samples_raw = self.read_raw(nsamples*sample_len*self.channels)
        samples = np.fromstring(samples_raw, dtype=sample_typ).astype(np.float)
        return samples

    def write(self, samples):
        if self.connection is None:
            raise IOError("Closed connection")
        sample_len = SimpleConnection.sample_length[self.format]
        sample_typ = SimpleConnection.sample_type[self.format]
        samples = np.array(samples).astype(sample_typ).tostring()
        return self.write_raw(samples)

    def drain(self):
        if self.connection is None:
            raise IOError("Closed connection")
        pa_simple_drain(self.connection)

    def flush(self):
        if self.connection is None:
            raise IOError("Closed connection")
        pa_simple_flush(self.connection)

    def close(self):
        if self.connection is not None:
            pa_simple_free(self.connection)
            self.connection = None

    @property
    def latency(self):
        if self.connection is None:
            raise IOError("Closed connection")
        return pa_simple_get_latency(self.connection)

    @property
    def format(self):
        if self.connection is None:
            raise IOError("Closed connection")
        return self.sample_spec.format

    @property
    def rate(self):
        if self.connection is None:
            raise IOError("Closed connection")
        return self.sample_spec.rate

    @property
    def channels(self):
        if self.connection is None:
            raise IOError("Closed connection")
        return self.sample_spec.channels

def open(direction, format, rate, channels, name=None, stream_name=None, server=None, device=None):
    if name is None:
        name = 'python'
    if stream_name is None:
        stream_name = 'python'

    ss = types.pa_sample_spec()
    ss.format = format
    ss.rate = rate
    ss.channels = channels

#TODO: allow use of cm
    #cm = types.pa_channel_map()
    cm = None

#TODO: allow use of ba
    #ba = types.pa_buffer_attr()
    ba = None

    con = pa_simple_new(server, name, direction, device, stream_name, ctypes.pointer(ss) if ss is not None else None, ctypes.pointer(cm) if cm is not None else None, ctypes.pointer(ba) if ba is not None else None)

    return SimpleConnection(con, ss, cm, ba)
