#!/usr/bin/env python

import argparse
import os
import math
import pprint
import sys

"""Given a stroke or control point mask, prints human friendly
   description."""

"""
 A map of (name, and packer formatter) tuples for strokes:
 1 -> 'flags', 4 byte unsigned int
 2 -> 'scale', 4 byte float
 4 -> 'group', 4 byte unsigned int
 8 -> 'seed',  4 byte unsigned int
 'unknown' -> 'stroke_ext_VAR', 4 byte unsigned int unless all 0xffff bits are set and then
                                '@' which is a 4-byte-length-prefixed data blob.
"""
STROKE_EXTENSION_BITS = {
  0x1: ('flags', 'I'),
  0x2: ('scale', 'f'),
  0x4: ('group', 'I'),
  0x8: ('seed', 'I'),
  'unknown': lambda bit: ('stroke_ext_%d' % math.log(bit, 2),
                          'I' if (bit & 0xffff) else '@')
}

"""
 A map of (name, and packer formatter) tuples for control points:
 1 -> 'pressure', 4 byte float
 2 -> 'timestamp', 4 byte unsigned int
 unknown -> 'cp_ext_VAR', 4 byte unsigned int
"""
CONTROLPOINT_EXTENSION_BITS = {
  0x1: ('pressure', 'f'),
  0x2: ('timestamp', 'I'),
  'unknown': lambda bit: ('cp_ext_%d' % math.log(bit, 2), 'I')
}

try:
  sys.path.append(os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), 'Python'))
  from tiltbrush.tilt import Tilt
except ImportError:
  print >>sys.stderr, "Please put the 'Python' directory in your PYTHONPATH"
  sys.exit(1)

def _parse_extension(ext_bits, ext_mask):
  print("ext_mask:", ext_mask)

  infos = []
  while ext_mask:
    bit = ext_mask & ~(ext_mask-1)
    ext_mask = ext_mask ^ bit
    try: info = ext_bits[bit]
    except KeyError: info = ext_bits['unknown'](bit)
    infos.append(info)

  print(infos) 

def main():
    parser = argparse.ArgumentParser(description="Pack a custom unity sketch json into a .tilt")
    parser.add_argument('--ctrlpnt', action='store_true', help="Parse control point mask")
    parser.add_argument('--stroke', action='store_true', help="Parse stroke mask") 
    parser.add_argument('mask', type=int, nargs='+',
                      help="mask to process")

    args = parser.parse_args()
    if not (args.ctrlpnt or args.stroke):
        print("You need to pass --ctrlpnt or --stroke")

    if not len(args.mask) < 1:
        print("You need to pass an int mask to --ctrlpnt or --stroke")

    print(args)
    ext_mask = args.mask[0]
    # print name and packing format string
    # mask is TYPE for X with format string X, and values XXX
    if args.ctrlpnt:
        _parse_extension(CONTROLPOINT_EXTENSION_BITS, ext_mask)

    if args.stroke:
        _parse_extension(STROKE_EXTENSION_BITS, ext_mask)

if __name__ == '__main__':
    main()