#!/usr/bin/env python
# vim:ts=4:sts=4:sw=4:expandtab

import binascii
from bitarray import bitarray
import numpy as np
import pulseaudio as pa

class Modulator:
    def __init__(self, framerate=48000, amplitude=1000, frequencies=(220,440), bauds=20):
        self.player = pa.simple.open(direction=pa.STREAM_PLAYBACK, format=pa.SAMPLE_S16LE, rate=framerate, channels=1)
        self.amplitude = amplitude
        self.frequencies = frequencies
        self.bauds = bauds
    def __call__(self, bits):
        for b in bits:
            step = np.pi*2*self.frequencies[b]/self.player.rate
            sample_count = int(self.player.rate/self.bauds)
            samples = (self.amplitude * np.sin(step * np.array(range(sample_count), dtype=np.float))).astype(np.int16)
            self.player.write(samples.tostring())
    def drain(self):
        self.player.drain()

class Demodulator:
    def __init__(self, framerate=48000, frequencies=(220,440), bauds=20):
        self.recorder = pa.simple.open(direction=pa.STREAM_RECORD, format=pa.SAMPLE_S16LE, rate=framerate, channels=1)
        self.frequencies = frequencies
        self.bauds = bauds
    def skip(self, part):
        sample_count = int(part*self.recorder.rate/self.bauds)
        self.recorder.read(sample_count*2)
    def __call__(self):
        sample_count = int(self.recorder.rate/self.bauds)
        samples = np.fromstring(self.recorder.read(sample_count*2), dtype=np.int16).astype(np.float) / 33000
        coefs = np.fft.fft(samples)
        freqs = np.fft.fftfreq(len(coefs))
        #coefs.resize(sample_count)
        coefs[0] = 0
        stats = sorted(zip(np.abs(coefs), np.abs(freqs * self.recorder.rate)))
        zero = 0.0
        one = 0.0
        other = 0.0
        for energy,freq in stats:
            near = lambda x,y,r : 1.0*x/y > r and 1.0*y/x > r
            if near(freq,self.frequencies[0],0.99):
                zero += energy
            elif near(freq,self.frequencies[1],0.99):
                one += energy
            elif not near(freq,self.frequencies[0],0.9) and not near(freq,self.frequencies[1],0.9):
                other = max(other,energy) 
        best = 'OTHER'
        if zero > one and zero > other:
            best = 'ZERO'
        if one > zero and one > other:
            best = 'ONE'
        #print(best, zero, one, other)
        return (zero, one, other)

map_4b5b = {
    '0000' : '11110',
    '0001' : '01001',
    '0010' : '10100',
    '0011' : '10101',
    '0100' : '01010',
    '0101' : '01011',
    '0110' : '01110',
    '0111' : '01111',
    '1000' : '10010',
    '1001' : '10011',
    '1010' : '10110',
    '1011' : '10111',
    '1100' : '11010',
    '1101' : '11011',
    '1110' : '11100',
    '1111' : '11101',
}
map_4b5b = dict([(bitarray(k),bitarray(v)) for (k,v) in map_4b5b.items()])
map_5b4b = dict([(v,k) for (k,v) in map_4b5b.items()])

class Encoder:
    def __init__(self):
        pass
    def __call__(self, source, destination, message):
        msg = bitarray()
        msg.extend(bin(source)[2:].zfill(32))
        msg.extend(bin(destination)[2:].zfill(32))
        msg.frombytes(message)
        crc = binascii.crc32(msg.tobytes()) & 0xffffffff
        msg.extend(bin(crc)[2:].zfill(32))
        msg = sum(msg.decode(map_5b4b),bitarray())
        return msg

class NRZ:
    def __init__(self):
        pass
    def __call__(self, message):
        mem = 0
        msg_nrz = []
        for b in message:
            if b:
                mem = 1 - mem
            msg_nrz.append(mem)
        return bitarray(msg_nrz)

class DENRZ:
    def __init__(self):
        pass
    def __call__(self, message):
        msg = bitarray('0')
        msg.extend(message)
        msg = bitarray([v[0] != v[1] for v in zip(msg[:-1],msg[1:])])

class Decoder:
    def __init__(self):
        pass
    def __call__(self, message):
        msg = bitarray()
        msg.extend(message)
        if len(msg)%5 != 0:
            return None
        msg = sum(msg.decode(map_4b5b), bitarray())
        crcc = binascii.crc32(msg[0:-32].tobytes()) & 0xffffffff
        crcc = bitarray(bin(crcc)[2:].zfill(32))
        src,dst,msg,crc = msg[0:32],msg[32:64],msg[64:-32],msg[-32:]
        if crcc != crc:
            return None
        src = int(str(src.unpack('0', '1')), 2)
        dst = int(str(dst.unpack('0', '1')), 2)
        msg = msg.tobytes()
        return (src, dst, msg)

class Transmitter:
    def __init__(self, modulator, encoder, address, prefix, suffix):
        self.modulator = modulator
        self.encoder = encoder
        self.source = address
        self.prefix = bitarray(prefix)
        self.suffix = bitarray(suffix)
    def __call__(self, destination, message):
        msg = bitarray()
        msg += self.encoder(self.source, destination, message)
        msg += self.suffix
        msg += self.suffix
        print(self.prefix+msg)
        self.modulator(self.prefix)
        self.modulator(msg) #TODO: NRZ
        self.modulator.drain()

class Receiver:
    def __init__(self, demodulator, decoder, address, prefix, suffix):
        self.demodulator = demodulator
        self.decoder = decoder
        self.destination = address
        self.prefix = bitarray(prefix)
        self.suffix = bitarray(suffix)
    def __call__(self):
        while True:
            known = 0
            fail = False
            while True:
                z,o,u = self.demodulator()
                self.demodulator.skip(0.2)
                if z+o > 2*u:
                    known += 1
                else:
                    known = 0
                if known > 5:
                    break
            stats = []
            for j in range(10):
                stats.append([])
            for i in range(4):
                for j in range(10):
                    z,o,u = self.demodulator()
                    stats[j].append(max(z-o-u,o-z-u))
                    self.demodulator.skip(0.1)
            stats = [np.average(a) for a in [sorted(a) for a in stats]]
            best = np.argmax(stats)
            self.demodulator.skip(best*0.1)
            val = lambda x,y,z : 0 if x > y else 1
            prev = val(*self.demodulator())
            while True:
                z,o,u = self.demodulator()
                if z+o < 2*u:
                    fail = True
                    break
                acct = val(z,o,u)
                if acct == prev:
                    break
                prev = acct
            if fail:
                continue
            if prev == 0:
                continue
            msg = bitarray()
            while True:
                z,o,u = self.demodulator() #TODO: DENRZ
                if z+o < 2*u:
                    fail = True
                    break
                msg.append(val(z,o,u))
                if len(msg) >= len(self.suffix) and len(msg)%5==0 and msg[-len(self.suffix):]==self.suffix:
                    msg = msg[:-len(self.suffix)]
                    print(self.prefix+msg+self.suffix+self.suffix)
                    msg = self.decoder(msg)
                    if msg:
                        return msg
                    else:
                        fail = True
                        break
