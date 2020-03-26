import os
import math
import json
import uuid
import struct
import contextlib
from collections import defaultdict
from io import StringIO

__all__ = ('Sketch', 'Stroke', 'ControlPoint')

#
# UTILITY METHODS

"""
# sketch
    # b is a binfile instance.
    b.pack("<3I", *self.header)
    b.write_length_prefixed(self.additional_header)
    b.pack("<i", len(self.strokes))
    for stroke in self.strokes:
      stroke._write(b) # _write on the stroke object

# stroke
    b.pack("<i", self.brush_idx)
    b.pack("<4f", *self.brush_color)
    b.pack("<fII", self.brush_size, self.stroke_mask, self.cp_mask)
    self.stroke_ext_writer(b, self.extension) ##
    b.pack("<i", len(self.controlpoints))   # little endian, signed int
    for cp in self.controlpoints:
      cp._write(b, self.cp_ext_writer)

# control point
    p = self.position    # 3 float
    o = self.orientation # 4 floats
    # little endian, 7 4-byte floats 
    b.pack("<7f", p[0], p[1], p[2], o[0], o[1], o[2], o[3])
    cp_ext_writer(b, self.extension)
"""

#
# When the Sketch is packed a binfile writer is passed into the Sketch 
# 'binwrite' method. This writes the Sketch header, additional header, 
# and the count of Strokes. Then for every Stroke in the Sketch strokes 
# array it calls the _write() call on the Stroke object and passes the 
# binfile writer into it. Each stroke writes the brush index, the brush 
# color, the brush size, stroke mask, control point mask and the number
# of control points in this stroke. Then for each control point in the 
# control points array it writes 7 4-byte floats packed in little endian
# as well as the extension data. This comprises the sketch.
  
COOKIE = int(3312887245)
VERSION = int(5)
RESERVED = int(0)

#
# Format string lookup for pack/unpack, selected by a bitfield.
# It is used in _make_ext_reader() which is called from _make_stroke_ext_reader
# and _make_cp_ext_reader to make
# 
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

"""
Create a dictionary of name -> (bit,format)
'flags': (1, 'I')
'scale': (2, 'f')
'group': (4, 'I')
'seed': (8, 'I')
"""
STROKE_EXTENSION_BY_NAME = dict(
  (info[0], (bit, info[1]))
  for (bit, info) in STROKE_EXTENSION_BITS.items()
  if bit != 'unknown'
)

#
#
def _make_stroke_ext_reader(ext_mask, memo={}):
  return _make_ext_reader(STROKE_EXTENSION_BITS, ext_mask)

def _make_cp_ext_reader(ext_mask, memo={}):
  return _make_ext_reader(CONTROLPOINT_EXTENSION_BITS, ext_mask)

#
# ext_bits is always one of:
# CONTROLPOINT_EXTENSION_BITS, STROKE_EXTENSION_BITS
#
# ext_mask is passed in via _make_stroke_ext_reader or _make_cp_ext_reader
#  
def _make_ext_reader(ext_bits, ext_mask):
  """Helper for Stroke and ControlPoint parsing.
  Returns:
  - function reader(file) -> list<extension values>
  - function writer(file, values)
  - dict mapping extension_name -> extension_index
  """

  # Make struct packing strings from the extension details
  infos = []
  while ext_mask:
    bit = ext_mask & ~(ext_mask-1)
    ext_mask = ext_mask ^ bit
    try: info = ext_bits[bit]
    except KeyError: info = ext_bits['unknown'](bit)
    infos.append(info)

  print(infos) 
  
  if len(infos) == 0:
    return (lambda f: [], lambda f, vs: None, {})

  fmt = '<' + ''.join(info[1] for info in infos)
  names = [info[0] for info in infos]
  if '@' in fmt:
    # struct.unpack isn't general enough to do the job
    print(fmt, names, infos)
    fmts = ['<'+info[1] for info in infos]
    def reader(f, fmts=fmts):
      values = [None] * len(fmts)
      for i,fmt in enumerate(fmts):
        if fmt == '<@':
          nbytes, = struct.unpack('<I', f.read(4))
          values[i] = f.read(nbytes)
        else:
          values[i], = struct.unpack(fmt, f.read(4))
  else:
    def reader(f, fmt=fmt, nbytes=len(infos)*4):
      values = list(struct.unpack(fmt, f.read(nbytes)))
      return values

  def writer(f, values, fmt=fmt):
    return f.write(struct.pack(fmt, *values))

  lookup = dict( (name,i) for (i,name) in enumerate(names) )
  return reader, writer, lookup


#
# Utility class for rw of binary data
############################################
class binfile(object):
  # Helper for parsing
  def __init__(self, inf):
    self.inf = inf

  def read(self, n):
    return self.inf.read(n)

  def write(self, data):
    return self.inf.write(data)

  def read_length_prefixed(self):
    n, = self.unpack("<I")
    return self.inf.read(n)

  def write_length_prefixed(self, data):
    self.pack("<I", len(data))
    self.inf.write(data)

  def unpack(self, fmt):
    n = struct.calcsize(fmt)
    data = self.inf.read(n)
    return struct.unpack(fmt, data)

  def pack(self, fmt, *args):
    data = struct.pack(fmt, *args)
    return self.inf.write(data)


#
#
############################################
class Sketch(object):
  """Stroke data from a .tilt file. Attributes:
    .strokes    List of tilt.Stroke instances
    .filename   Filename if loaded from file, but usually None
    .header     Opaque header data"""

  def __init__(self):
    """source is either a file name, a file-like instance, or a Tilt instance."""
    self.filename = None
    self.header = [COOKIE, VERSION, RESERVED] # cookie, version, unused
    self.additional_header = ""
    self.strokes = []

  def add_stroke(self, stroke):
      if len(self.strokes) < 300000:
        self.strokes.append(stroke)

  def add_control_point_to_stroke(self, index, pos, rot):
    self.strokes[index].add_control_point(pos, rot)

  def pack(self):
    tmpf = StringIO()
    packed_data = self.binwrite(binfile(tmpf))
    return tmpf.getvalue()

  def binwrite(self, b):
    # b is a binfile instance.
    b.pack("<3I", *self.header)
    b.write_length_prefixed(self.additional_header)
    b.pack("<i", len(self.strokes))
    for stroke in self.strokes:
      stroke._write(b) # _write on the stroke object


#
# This class represents a brush stroke.
# 
# All control points in a stroke are guaranteed to use the same set 
# of extensions.
############################################
class Stroke(object):
  """
    Data for a single stroke from a .tilt file. Attributes:
    .brush_idx      Index into Tilt.metadata['BrushIndex']; tells you the brush GUID
    .brush_color    RGBA color, as 4 floats in the range [0, 1]
    .brush_size     Brush size, in decimeters, as a float. Multiply by
                    get_stroke_extension('scale') to get a true size.
    .controlpoints  List of tilt.ControlPoint instances.

    .flags          Wrapper around get/set_stroke_extension('flags')
    .scale          Wrapper around get/set_stroke_extension('scale')

  Also see:
    has_stroke_extension(), 
    get_stroke_extension(), 
    set_stroke_extension().
  """

  # Stroke extension data:
  #   self.extension is a list of optional per-stroke data.
  #   self.stroke_ext_lookup maps the name of an extension field
  #   (eg, "flags") to an index in that list.
  #
  # Control point extension data:
  #   ControlPoint.extension is a list of optional per-CP data.
  #   The layout of this list is guaranteed to be identical to the
  #   layout of all other control points in the stroke.
  #
  #   Because of this homogeneity, the lookup table is stored in
  #   stroke.cp_ext_lookup, not in the control point.

  #
  # The only stroke extension that appears to be supported is 
  # 'scale'.
  def __init__(self, brush, color, size, stroke_mask, cp_mask):
    self.brush_idx = brush  
    self.brush_color = color
    self.brush_size = size
    self._controlpoints = []
    self.stroke_mask = stroke_mask
    self.cp_mask = cp_mask
    self.extension = [0] ## This might need to be changed

    _, self.stroke_ext_writer, self.stroke_ext_lookup = _make_stroke_ext_reader(self.stroke_mask)
    _, self.cp_ext_writer, self.cp_ext_lookup = _make_cp_ext_reader(self.cp_mask)

  # Get the stroke extension value by name
  # 'flags'
  # 'scale'
  # 'group'
  # 'seed'
  def __getattr__(self, name):
    """Get stroke extension by name"""
    if name in STROKE_EXTENSION_BY_NAME:
      try:
        return self.get_stroke_extension(name)
      except LookupError:
        raise AttributeError("%s (extension attribute)" % name)
    raise AttributeError(name)

  # Set the stroke extension value by name
  # 'flags': (1, 'I')
  # 'scale': (2, 'f')
  # 'group': (4, 'I')
  # 'seed': (8, 'I')
  def __setattr__(self, name, value):
    """Set stroke extension by name"""
    if name in STROKE_EXTENSION_BY_NAME:
      return self.set_stroke_extension(name, value)
    return super(Stroke, self).__setattr__(name, value)

  # Delete the stroke extension value by name
  # 'flags'
  # 'scale'
  # 'group'
  # 'seed'
  def __delattr__(self, name):
    """Delete stroke extension by name"""
    if name in STROKE_EXTENSION_BY_NAME:
      try:
        self.delete_stroke_extension(name)
        return
      except LookupError:
        raise AttributeError("%s (extension attribute)" % name)
    raise AttributeError(name)

  # 
  # Add a control point
  def add_control_point(self, pos, rot):
    if len(self._controlpoints) < 10000:
      ctrl_pt = ControlPoint(pos, rot, self.cp_mask)
      print(ctrl_pt)
      self._controlpoints.append(ctrl_pt)

  #
  # Return the list of control points
  def controlpoints(self):
    return self._controlpoints

  def has_stroke_extension(self, name):
    """
    Returns true if this stroke has the requested extension data.
    
    The current stroke extensions are:
      scale     Non-negative float. The size of the player when making this stroke.
                Multiply this by the brush size to get a true stroke size.
    """
    return name in self.stroke_ext_lookup

  def get_stroke_extension(self, name):
    """Returns the requested extension stroke data.
    Raises LookupError if it doesn't exist."""
    idx = self.stroke_ext_lookup[name]
    return self.extension[idx]

  def set_stroke_extension(self, name, value):
    """Sets stroke extension data.
    This method can be used to add extension data."""
    idx = self.stroke_ext_lookup.get(name, None)
    if idx is not None:
      print(idx)
      self.extension[idx] = value
    else:
      # Convert from idx->value to name->value
      name_to_value = dict( (name, self.extension[idx])
                            for (name, idx) in self.stroke_ext_lookup.items() )
      name_to_value[name] = value

      bit, exttype = STROKE_EXTENSION_BY_NAME[name]
      self.stroke_mask |= bit
      _, self.stroke_ext_writer, self.stroke_ext_lookup = \
          _make_stroke_ext_reader(self.stroke_mask)
      
      # Convert back to idx->value
      self.extension = [None] * len(self.stroke_ext_lookup)
      for (name, idx) in self.stroke_ext_lookup.items():
        self.extension[idx] = name_to_value[name]
                                                          
  def delete_stroke_extension(self, name):
    """Remove stroke extension data.
    Raises LookupError if it doesn't exist."""
    idx = self.stroke_ext_lookup[name]

    # Convert from idx->value to name->value
    name_to_value = dict( (name, self.extension[idx])
                          for (name, idx) in self.stroke_ext_lookup.items() )
    del name_to_value[name]

    bit, exttype = STROKE_EXTENSION_BY_NAME[name]
    self.stroke_mask &= ~bit
    _, self.stroke_ext_writer, self.stroke_ext_lookup = \
        _make_stroke_ext_reader(self.stroke_mask)

    # Convert back to idx->value
    self.extension = [None] * len(self.stroke_ext_lookup)
    for (name, idx) in self.stroke_ext_lookup.items():
      self.extension[idx] = name_to_value[name]

  def has_cp_extension(self, name):
    """
    Returns true if control points in this stroke have the requested extension data.
    All control points in a stroke are guaranteed to use the same set of extensions.

    The current control point extensions are:
      timestamp         In seconds
      pressure          From 0 to 1
    """
    return name in self.cp_ext_lookup

  def get_cp_extension(self, cp, name):
    """Returns the requested extension data, or raises LookupError if it doesn't exist."""
    idx = self.cp_ext_lookup[name]
    return cp.extension[idx]

  def set_cp_extension(self, cp, name, value):
    """Sets the requested extension data, or raises LookupError if it doesn't exist."""
    idx = self.cp_ext_lookup[name]
    cp.extension[idx] = value

  #
  # The b is a binary writer, which is passed down through the Sketch 
  # into this writer.
  def _write(self, b):
    b.pack("<i", self.brush_idx)
    b.pack("<4f", *self.brush_color)
    b.pack("<fII", self.brush_size, self.stroke_mask, self.cp_mask)
    self.stroke_ext_writer(b, self.extension) # pass the binary writer into the extension
                                              # writer
    b.pack("<i", len(self.controlpoints))     # little endian, signed int
    for cp in self.controlpoints:
      cp._write(b, self.cp_ext_writer)


#
#
#
#
class ControlPoint(object):
  """Data for a single control point from a stroke. Attributes:
    .position    Position as 3 floats. Units are decimeters.
    .orientation Orientation of controller as a quaternion (x, y, z, w)."""

  def __init__(self, pos, rot, ext):
    """Create a ControlPoint from pos (array of 3 floats), rot 
    (array of 4 floats) and extension (CONTROLPOINT_EXTENSION_BITS)"""
    self.position = pos    # 3 floats
    self.orientation = rot # 4 floats
    self.extension = ext   # 
    
  # the b is a binary writer which is passed down from the 
  # Stroke write method
  def _write(self, b, cp_ext_writer):
    p = self.position    # 3 float
    o = self.orientation # 4 floats
    # little endian, 7 4-byte floats 
    b.pack("<7f", p[0], p[1], p[2], o[0], o[1], o[2], o[3])
    cp_ext_writer(b, self.extension)
