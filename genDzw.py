#!/usr/bin/env python
# vim:ts=4:sts=4:sw=4:expandtab

import sys
import wave
import math as m

import binascii as bi
import pulseaudio as pa
import numpy as np
import string
from bitarray import bitarray


sample_map = {
    1 : pa.SAMPLE_U8,
    2 : pa.SAMPLE_S16LE,
    4 : pa.SAMPLE_S32LE,
}
sample_type = {
    1 : np.uint8,
    2 : np.int16,
    4 : np.int32,
}

player = pa.simple.open(direction=pa.STREAM_PLAYBACK, format=sample_map[2], rate=44100, channels=1)

def music(timeInSeconds, frequency, x): # tworzenie tablicy do playera o czestotliwosci frequency i czas trwania timeInSeconds
    ile = 44100 * timeInSeconds # wyliczenie ile wartosci nalezy dodac do playera, aby otrzymac dzwiek o podanej czestotliwosci
    array = [int(np.sin(2*i * np.pi * frequency / 44100) * 22050) for i in range(int(ile))] # tworzenie tablicy wartosci sinusa 
    # tak, ze dla jednego okresu mamy 44100/frequency wartosci
    player.write(array)      

D = {}
Dr = {}

# slownik z 4b5b
D["0000"] =	"11110"	
D["0001"] = "01001"	
D["0010"] =	"10100"	
D["0011"] = "10101"	
D["0100"] = "01010"	
D["0101"] = "01011"	
D["0110"] = "01110"	
D["0111"] = "01111"	
D["1000"] = "10010"	
D["1001"] = "10011"	
D["1010"] = "10110"	
D["1011"] = "10111"	
D["1100"] = "11010"	
D["1101"] = "11011"	
D["1110"] = "11100"	
D["1111"] = "11101"
    
def convert1(s): # przepuszczenie wiadomosci przez 4b5b
    c = ""
    w = ""
    for i in range(len(s)):
        w += s[i]
        if i%4 == 3:
            c += D[w]
            w = ""
    return c
    
def nrzi1(s): #nrzi z 4b5b
    k = 1
    l = ['0', '1']
    w = ""
    for i in range(len(s)):
        if s[i] == '0':
            w += str(k)
        else:
            k = 1 - k            
            w += str(k)
    return w

def tobitarray(a, b): # stworzenie bitarray z inta i dopelnienie 0 aby mial dlugosc b
    return bitarray(bin(a)[2:].zfill(b))

def readx(a, com, b): #tworzenie wiadomosci 
    bcom = bitarray()
    ba = tobitarray(a, 48) # bitarray z inta odbiorcy
    ba += tobitarray(b, 48) # bitarray z inta nadawcy
    ba += tobitarray(len(com), 16) # dlugosc 
    bcom.fromstring(com) # przekodowanie wiadomosci z ASCII na kod binarny
    ba += bcom
    ba += bitarray(bin(bi.crc32(ba)&0xffffffff)[2:].zfill(32)) #crc32 z wiadomosci
    return ba
   
def create():   # tworzenie stringa 1010...11
    s = ""
    for x in range(62):
        if x%2 == 0:
            s += '1'
        else:
            s += '0'
    s +='11'
    return s

t = 1
l = 1
w = ""

for line in sys.stdin:
    tmp = string.split(line, ' ') # wczytany string rozdzielony spacja
    t = long(tmp[0]) # adres nadawcy
    l = long(tmp[1]) # adres odbiorcy
    s = tmp[2] # poczatek wiadomosc
    for i in range(3, len(tmp)):  # sklejanie wiadomosci
        s += " " + tmp[i]            
    if s[len(s)-1] == '\n':  # usuniecie znaku konca linii        
        s = s[:len(s)-1]
    ba = readx(l, s, t) # konwersja na bitarray
    s = ""
    for i in range(len(ba)): # zamiana bitarray'a na stringa
        if ba[i] == False:
            s += '0'
        else:            
            s += '1'

    s = convert1(s) # zamiana przez 4b5b
    res = create() # na poczatek wiadomosci dodanie stringa 1010...11
    res += nrzi1(s) # doklejenie do konca wiadomosci przekodowanej wiadomosci przez nrzi

    for i in range(len(res)): # tworzenie dzwieku
        if res[i] == '0':
            music(float(1/float(sys.argv[1])), float(sys.argv[2]), 0)
            s += '0'
        else:
            music(float(1/float(sys.argv[1])), float(sys.argv[3]), 1)
            s += '1'
    # drain playera
    player.drain()


