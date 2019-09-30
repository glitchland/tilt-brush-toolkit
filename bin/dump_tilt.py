#!/usr/bin/env python

# Copyright 2016 Google Inc. All Rights Reserved.
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

"""This is sample Python 2.7 code that uses the tiltbrush.tilt module
to view raw Tilt Brush data."""

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
  
def dump_json(sketch):
  """Converts the tilt sketch information to unity parsable JSON.
  This is essentially a list of stroke data."""
  sketch_map = {"strokes":[]}

  cookie, version, unused = sketch.header[0:3]
  sketch_map["cookie"] = cookie
  sketch_map["version"] = version
  sketch_map["unused"] = unused
  sketch_map["additional_header_length"] = len(sketch.additional_header)
  sketch_map["additional_header"] = sketch.additional_header

  for (i, stroke) in enumerate(sketch.strokes):
    sketch_map["strokes"].append(stroke_to_map(stroke))

  return json.dumps(sketch_map, indent=4, sort_keys=True)

def dump_sketch(sketch):
  """Prints out some rough information about the strokes.
  Pass a tiltbrush.tilt.Sketch instance."""
  cooky, version, unused = sketch.header[0:3]
  print 'Cooky:0x%08x  Version:%s  Unused:%s  Extra:(%d bytes)' % (
    cooky, version, unused, len(sketch.additional_header))
  if len(sketch.strokes):
    stroke = sketch.strokes[0]  # choose one representative one
    def extension_names(lookup):
      # lookup is a dict mapping name -> idx
      extensions = sorted(lookup.items(), key=lambda (n,i): i)
      return ', '.join(name for (name, idx) in extensions)
    print "Stroke Ext: %s" % extension_names(stroke.stroke_ext_lookup)
    if len(stroke.controlpoints):
      print "CPoint Ext: %s" % extension_names(stroke.cp_ext_lookup)

  for (i, stroke) in enumerate(sketch.strokes):
    print "%3d: " % i,
    dump_stroke(stroke)

def stroke_to_map(stroke):
  stroke_map = {}
  stroke_map["brush_index"] = stroke.brush_idx # XXX map this to a guid
  stroke_map["brush_color"] = [ stroke.brush_color[0], stroke.brush_color[1], stroke.brush_color[2], stroke.brush_color[3] ] #XXX (parse on unity side[ int(stroke.brush_color[0] * 255), int(stroke.brush_color[1] * 255), int(stroke.brush_color[2] * 255), int(stroke.brush_color[3] * 255)]
  stroke_map["brush_size"] = stroke.brush_size # XXX multiply this by scale?  
  stroke_map["stroke_extension"] = stroke.extension
  stroke_map["stroke_mask"] = stroke.stroke_mask
  stroke_map["cp_mask"] = stroke.cp_mask
  stroke_map["control_points"] = []

  for ctrl_point in stroke.controlpoints:
    ctrl_point_map = {}
    ctrl_point_map["position"] = [ctrl_point.position[0], ctrl_point.position[1], ctrl_point.position[2]]
    ctrl_point_map["rotation"] = [ctrl_point.orientation[0], ctrl_point.orientation[1], ctrl_point.orientation[2], ctrl_point.orientation[3]]
    ctrl_point_map["extension"] = ctrl_point.extension
    stroke_map["control_points"].append(ctrl_point_map)

  return stroke_map

def dump_stroke(stroke):
  """Prints out some information about the stroke."""
  if len(stroke.controlpoints) and 'timestamp' in stroke.cp_ext_lookup:
    cp = stroke.controlpoints[0]
    timestamp = stroke.cp_ext_lookup['timestamp']
    start_ts = ' t:%6.1f' % (cp.extension[timestamp] * .001)
  else:
    start_ts = ''

  try:
    scale = stroke.extension[stroke.stroke_ext_lookup['scale']]
  except KeyError:
    scale = 1

  print "Brush: %2d  Size: %.3f  Color: #%02X%02X%02X %s  [%4d]" % (
    stroke.brush_idx, stroke.brush_size * scale,
    int(stroke.brush_color[0] * 255),
    int(stroke.brush_color[1] * 255),
    int(stroke.brush_color[2] * 255),
    #stroke.brush_color[3],
    start_ts,
    len(stroke.controlpoints))

  print "\nStroke Control Points: \n---------------------"
  for ctrlPt in stroke.controlpoints:
    print "Position.....: [x: %f, y: %f, z: %f]" % (ctrlPt.position[0], ctrlPt.position[1], ctrlPt.position[2]) 
    print "Rotation (q).: ", ctrlPt.orientation
    print "Extension....: %s" % ctrlPt.extension
  print "--------------------- \n"

def main():
  import argparse
  parser = argparse.ArgumentParser(description="View information about a .tilt")
  parser.add_argument('--strokes', action='store_true', help="Dump the sketch strokes")
  parser.add_argument('--metadata', action='store_true', help="Dump the metadata")
  parser.add_argument('--json', action='store_true', help="Dump JSON for unity parsing")
  parser.add_argument('files', type=str, nargs='+', help="Files to examine")

  args = parser.parse_args()
  if not (args.strokes or args.metadata or args.json):
    print "You should pass at least one of --strokes , --metadata, or --json"

  for filename in args.files:
    t = Tilt(filename)
    if args.strokes:
      dump_sketch(t.sketch)
    if args.metadata:
      pprint.pprint(t.metadata)
    if args.json:
      print(dump_json(t.sketch))

if __name__ == '__main__':
  main()
