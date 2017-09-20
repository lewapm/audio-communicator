#!/usr/bin/env python
# vim:ts=4:sts=4:sw=4:expandtab

import sys
import wave
import math as m
import time 
import binascii as bi
import pulseaudio as pa
import numpy as np
import string
from bitarray import bitarray
from datetime import datetime

timex = float(1/float(sys.argv[1])) # dlugosc trwania bita
freq0 = float(sys.argv[2]) # czestotliwosc 0
freq1 = float(sys.argv[3]) # czestotliwosc 1
t = 1
l = 1
w = ""
howLongListen = 5 
Dr = {} # slownik 5b na 4b

Dr["11110"] = "0000"
Dr["01001"] = "0001"
Dr["10100"] = "0010"
Dr["10101"] = "0011"
Dr["01010"] = "0100"    
Dr["01011"] = "0101"
Dr["01110"] = "0110"
Dr["01111"] = "0111"
Dr["10010"] = "1000"
Dr["10011"] = "1001"
Dr["10110"] = "1010"
Dr["10111"] = "1011"
Dr["11010"] = "1100"
Dr["11011"] = "1101"
Dr["11100"] = "1110"
Dr["11101"] = "1111"
    
def deconvert(s): # przekodowywanie wiadomosci z 5b na 4b
    c = ""
    w = ""
    for i in range(len(s)):
        w += s[i]
        if i%5 == 4:
            if w in Dr:
                c += Dr[w] 
                w = ""
            else:
                return -1
    return c

def nrzi2(s): # odkodowywanie nrzi
    k = 1
    w = ""
    for i in range(len(s)): # przechodze przez caly string
        if s[i] == str(k):  # i jezeli obecny bit jest taki sam jak poprzedni to wynikowego stringa doklejam 0     
            w += '0'
        else: # w przeciwnym wypaku doklejam 1
            w += '1'
            k = 1 - k  # i zapamietuje jaki bit teraz mialem   
    return w

def tobitarray(a, b):
    return bitarray(bin(a)[2:].zfill(b))

def create():   # tworzenie stringa 1010...11
    s = ""
    for x in range(62):
        if x%2 == 0:
            s += '1'
        else:
            s += '0'
    s +='11'
    return s

def listen(length, recorder):
    nframes = int(length * recorder.rate) 
    data = recorder.read(nframes) 
    d = np.fft.fft(data) # licze fft z tablicy data
    maxi = 0
    ind = 0
    for i in range(len(d)/2):       # wyliczam najwieksza wartosc i zapamietuje jej index oraz wartosc
        if np.absolute(maxi) < np.absolute(d[i]):
            maxi = d[i]
            ind = i
	return ind//length, np.absolute(maxi) # zwracam czestotliwosc dzwieku o najwiekszej wartosci i jej wartosc

def getfive(recorder): # sprawdzam czy otrzyma czestotliwosc jest bliska czestotliwosci f0 badz f1, a jezeli nie to zwracam ze jest szum czyli 2
    x = listen(timex, recorder)  # zwracam rowniez wartosc na danej dlugosci
    if abs(x[0] - freq0) < 10:
        return 0, x[1]
    elif abs(x[0] - freq1) < 10:
        return 1, x[1]
    return 2, x[1]

def check(recorder): # wyliczam przesuniecie
    k = 0
    ile = 0
    listenTime = 0.2 * timex # czas przesuniecia
    ar = []
    while k < howLongListen: # bedziemy sluchali 5 razy bo przesluwamy sie o 1/5 czasu
    	try:
        	ar.append(getfive(recorder)) # dodajemy do tablicy wynikowej wynik 
        except Exception as exce: # nie udalo sie nic wiecej przeczytac z recorder
        	pass
        listen(listenTime, recorder) # slucham przez listenTime i nastepnie nie interesueje mnie wynik
        k += 1 
    maks = 0 #maksymalna wartosc 
    przes = 0 # najlepsze przesuniecie
    for i in range(len(ar)):
    	if ar[i][0] == 0 or ar[i][0] == 1:
            if maks < ar[i][1]: # obecna najwieksza wartosc jest mniejsza niz obecnie przegladana i uzyskalismy 
    		    maks = ar[i][1]
    		    przes = i
    return przes

def recr(recorder):
    end = 0 # czekam na wiadomosc slucham tak dlugo az uzyskam dzwiek ktory jest blisko 0 lub 1 i jezeli dostalem to zakaladam, ze to juz jest preambula wiadmosci
    while end == 0:
    	try:
       		tmp = getfive(recorder)
       	except Exception:
       		return 
        if tmp[0] == 0 or tmp[0] == 1:
            end = 1    

def getMessage(recorder):
    val = 0.2*timex 
    przes = 0
    k=0
    while k < 5:
        przes = check(recorder) # wywoluje funkcje check, ktora wylicza najlepsze przesuniecie
        if przes != 0:
            listen(val*przes, recorder) # czekam przez odpowienia wielokrotnosc czasu    
        k += 1
    # zakladam ze moje przesuniecie jest juz dobre i zaczyam sluchac preambule az do mementu otrzymania 11 a nastepnie slucham wiadomosc
    try:
    	prev = getfive(recorder) # slucham kolejna wartosc
    	tmp = getfive(recorder) # i jeszcze nastepna
    except Exception:
    	return "2"
    s = str(prev[0]) + str(tmp[0]) # 
    while prev[0] != 1 or tmp[0] != 1: # slucham dopoki nie otrzymam dwoch 1 pod rzad
        prev = tmp
        try:
        	tmp = getfive(recorder) # czytam kolejna wartosc 
        except Exception: # nie ma nic wiecej w recorderze wyjatek
        	return "1"
        s += str(tmp[0])
    try: # slucham pierwszy bit wiadomosci
    	tmp = getfive(recorder)
    except Exception: # nie ma nic wiecej w recorderze
    	return "1"
    licz = 0
    bum = 0
    s=""
    while licz == 0: # bede sluchal tak dlugo az nie dostane wartosci szumu albo recorder sie nie skonczy
        s += str(tmp[0])
        try:
        	tmp = getfive(recorder)
        except Exception:
        	licz = 1
        if tmp[0] == 2: # dostalem szum
        	licz = 1
        bum += 1
    return s

def decode(ba):
    global t # wartosc odbiorce
    global l # wartosc nadawce
    global w # dlugosc wiadomosci
    s = bitarray()
    for i in range(len(ba)-32):
        if ba[i] == '0':
            s.append(False)
        else:
            s.append(True)
    bb = int(bin(bi.crc32(s)&0xffffffff)[2:], base = 2) # wyliczam crc32
    e = int(ba[len(ba)-32:], base = 2) # sprawdzam jakie mamy zapisane crc32
    bc = bin(bi.crc32(s)&0xffffffff)[2:]
    f = ba[len(ba)-32:]  
    if bb == e:  # jezeli crc32 sie zgadza to rozkodowuje wiadomosc
        t = long(ba[:48], base=2) # wyliczam odbiorce
        l = long(ba[48:96], base=2) # wyliczam nadawce
        x = long(ba[96:112], base=2) # wyliczam dlugosc wiadomosci
        q = len(ba) - 32 
        s = bitarray()
        for i in range(112, q): # czytam wiadomosc z bitarraya zamianieam string na bitarrya 
            if ba[i] == '0':
                s.append(False)
            else:
                s.append(True)
        w = bitarray.tostring(s) # zamianiam bity na wiadomosc
        if x != len(w): # jezeli dlugosc sie nie zgadza to rzucam bledem
            return -1
    else:# crc sie nie zgadza
        return -1

while True:
	(nchannels, sampwidth, sampformat, framerate) = (1, 2, pa.SAMPLE_S16LE, 44100) 
    recorder = pa.simple.open(direction=pa.STREAM_RECORD, format=sampformat, rate=framerate, channels=nchannels) # otwieram nowy recorders
    recr(recorder) # slucham tak dlugo az nie dostane wartosci 1 lub 0 
    tmp = getMessage(recorder) # slucham wiadomosci
    if len(tmp)%5 == 1: # moze sie zdarzyc, ze moje przesuniecie nie bylo idealne i jeszcze 0 lub 1 brzmialo przez bardzo krotki czas 
        tmp = tmp[:-1]
    if len(tmp) >= 180 and len(tmp) <= 15180 and (len(tmp))%5 == 0: # sprawdzam, czy ta wiadomosc ma odpowiednia dlugosc 
        s = nrzi2(tmp) # rozkodowywuje z nrzi
        s = deconvert(s) # zamieniam 5b na 4b
        if s != -1: # jezeli sie udalo, to rozkodowywuje wiadomosc
            if decode(s) == None:
                print("%d %d %s" % (l, t, w))
    recorder.close() # zamykam recorder i zaczynam od nowa sluchanie



