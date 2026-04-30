#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
#
# decode_panic_qr.py — decode a Linux drm_panic QR code URL to kmsg text.
#
# Transcribed and adapted from the JavaScript implementation:
#   Copyright (c) 2024 Jocelyn Falempe
#   https://github.com/kdj0c/panic_report (MIT License)
#
# Python port: the decoding logic is a faithful translation of
# numbers_to_data() and numbers_to_data2() from panic_report.js.
# Key difference: JavaScript's Uint8Array silently truncates values
# to 8 bits on assignment; Python requires explicit '& 0xff' masks.
#
# Usage:
#     python3 decode_panic_qr.py "<url_from_zbarimg>"
#
# The URL comes from scanning the QR code on a drm_panic screen with zbarimg:
#     zbarimg --raw /path/to/oops.png
#
# Two encodings are supported:
#   z=  (v6.14+, FIDO2 spec): 17 decimal digits -> 7 bytes, little-endian base-256
#   zl= (v6.10-v6.13 legacy): 4 decimal digits -> 13 bits, bit-packed

import sys
import zlib
import urllib.parse


def numbers_to_data2(s):
    """v6.14+ FIDO2 encoding: 17 decimal digits -> 7 bytes (little-endian base-256)."""
    main_len = (len(s) // 17) * 7
    rem_len = (len(s) % 17) * 2 // 5
    out = bytearray(main_len + rem_len)
    off = 0
    for i in range(0, len(s), 17):
        chunk = s[i:i + 17]
        num = int(chunk)
        nb = 7 if len(chunk) == 17 else rem_len
        for _ in range(nb):
            out[off] = num % 256
            num //= 256
            off += 1
    return bytes(out)


def numbers_to_data(s):
    """Legacy v6.10-v6.13 encoding: 4 decimal digits -> 13 bits, bit-packed."""
    nctb = [0, 4, 7, 10, 13]
    bits = (len(s) // 4) * 13 + nctb[len(s) % 4]
    out = bytearray(bits // 8)
    extra, off, byte_off, rem = bits % 8, 0, 0, 0
    for i in range(0, len(s), 4):
        chunk = s[i:i + 4]
        num = int(chunk)
        nl = nctb[len(chunk)]
        b = off + nl
        if byte_off * 8 + b >= len(out) * 8:
            b -= extra
        if b < 8:
            rem += num << (8 - b)
            off = b
        elif b < 16:
            out[byte_off] = (rem + (num >> (b - 8))) & 0xff
            byte_off += 1
            rem = (num << (16 - b)) & 0xff
            off = b - 8
        else:
            out[byte_off] = (rem + (num >> (b - 8))) & 0xff
            byte_off += 1
            out[byte_off] = (num >> (b - 16)) & 0xff
            byte_off += 1
            rem = (num << (24 - b)) & 0xff
            off = b - 16
    return bytes(out)


def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <panic_report_url>", file=sys.stderr)
        sys.exit(1)

    url = sys.argv[1]
    frag = url.split('#', 1)[1] if '#' in url else urllib.parse.urlparse(url).query
    params = urllib.parse.parse_qs(frag.lstrip('?'))

    a = params.get('a', ['unknown'])[0]
    v = params.get('v', ['unknown'])[0]
    z = params.get('z', [None])[0]
    zl = params.get('zl', [None])[0]

    if z:
        data = numbers_to_data2(z)
    elif zl:
        data = numbers_to_data(zl)
    else:
        print("Error: no 'z' or 'zl' parameter found in URL", file=sys.stderr)
        sys.exit(1)

    kmsg = zlib.decompress(data).decode('utf-8', errors='replace')
    print(f"Arch: {a}  Kernel: {v}")
    print('=' * 60)
    print(kmsg)


if __name__ == '__main__':
    main()
