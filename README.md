Simple sender - reciver program, that transmits messages via sound. It implements:
NRZI, 4b5b encoding and crc32 as error checking.

Usage:
Sending:
"./genDzw.py (bits per second) (0's frequency) (1's frequency)"
in new line write: (receiver) (sender) (message) and the program will create sound for it.

Receiving:
"./recv.py (bits per second) (0's frequency) (1's frequency)"
