#!/usr/bin/env python

# 
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
#     http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
import os
import pprint
import sys

try:
  sys.path.append(os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), 'Python'))
  from tiltbrush.tilt import Tilt
except ImportError:
  print >>sys.stderr, "Please put the 'Python' directory in your PYTHONPATH"
  sys.exit(1)

def main():
  import argparse
  parser = argparse.ArgumentParser(description="Pack a custom unity sketch json into a .tilt")
  parser.add_argument('--json', action='store_true', help="JSON file to pack")
  parser.add_argument('--tilt', action='store_true', help=".tilt file to write to") 
  #parser.add_argument('files', type=str, nargs='+', help="Files to examine") ## XXX that t

  args = parser.parse_args()
  if not (args.tilt and args.json):
    print "You need to pass --json and --tilt"
 
  t = Tilt('sketch.json', True) # init from JSON
  tilt_bin = t.pack_sketch()
  newFile = open("test.tilt", "wb")
  newFile.write(tilt_bin)
  
#  for filename in args.files:
#    t = Tilt(filename)
#    if args.strokes:
#      dump_sketch(t.sketch)
#    if args.metadata:
#      pprint.pprint(t.metadata)
#    if args.json:
#      print(dump_json(t.sketch))
  
if __name__ == '__main__':
  main()


# write_sketch  