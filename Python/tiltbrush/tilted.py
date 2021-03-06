import os
import math
import json
import uuid
import struct
import shutil
import sys
import tempfile
import contextlib
from collections import defaultdict
from io import BytesIO
import zipfile
import zlib

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
  
COOKIE = 3312887245
VERSION = 5
RESERVED = 0
DEFAULT_ENVIRONMENT = 'ab080599-e465-4a6d-8587-43bf495af68b'
METADATA_SCHEMA_VERSION = 2

BRUSH_LIST_ARRAY = [
  ('89d104cd-d012-426b-b5b3-bbaee63ac43c','Bubbles'),
  ('700f3aa8-9a7c-2384-8b8a-ea028905dd8c','CelVinyl'),
  ('0f0ff7b2-a677-45eb-a7d6-0cd7206f4816','ChromaticWave'),
  ('1161af82-50cf-47db-9706-0c3576d43c43','CoarseBristles'),
  ('79168f10-6961-464a-8be1-57ed364c5600','CoarseBristlesSingleSided'),
  ('1caa6d7d-f015-3f54-3a4b-8b5354d39f81','Comet'),
  ('c8313697-2563-47fc-832e-290f4c04b901','DiamondHull'),
  ('4391aaaa-df73-4396-9e33-31e4e4930b27','Disco'),
  ('d1d991f2-e7a0-4cf1-b328-f57e915e6260','DotMarker'),
  ('6a1cf9f9-032c-45ec-9b1d-a6680bee30f7','Dots'),
  ('0d3889f3-3ede-470c-8af4-f44813306126','DoubleTaperedFlat'),
  ('0d3889f3-3ede-470c-8af4-de4813306126','DoubleTaperedMarker'),
  ('d0262945-853c-4481-9cbd-88586bed93cb','DuctTape'),
  ('3ca16e2f-bdcd-4da2-8631-dcef342f40f1','DuctTapeSingleSided'),
  ('f6e85de3-6dcc-4e7f-87fd-cee8c3d25d51','Electricity'),
  ('02ffb866-7fb2-4d15-b761-1012cefb1360','Embers'),
  ('cb92b597-94ca-4255-b017-0e3f42f12f9e','Fire'),
  ('2d35bcf0-e4d8-452c-97b1-3311be063130','Flat'),
  ('55303bc4-c749-4a72-98d9-d23e68e76e18','FlatDeprecated'),
  ('280c0a7a-aad8-416c-a7d2-df63d129ca70','FlatSingleSided'),
  ('cf019139-d41c-4eb0-a1d0-5cf54b0a42f3','Highlighter'),
  ('6a1cf9f9-032c-45ec-9b6e-a6680bee32e9','HyperGrid'),
  ('dce872c2-7b49-4684-b59b-c45387949c5c','Hypercolor'),
  ('e8ef32b1-baa8-460a-9c2c-9cf8506794f5','HypercolorSingleSided'),
  ('2f212815-f4d3-c1a4-681a-feeaf9c6dc37','Icing'),
  ('f5c336cf-5108-4b40-ade9-c687504385ab','Ink'),
  ('c0012095-3ffd-4040-8ee1-fc180d346eaa','InkSingleSided'),
  ('4a76a27a-44d8-4bfe-9a8c-713749a499b0','Leaves'),
  ('ea19de07-d0c0-4484-9198-18489a3c1487','LeavesSingleSided'),
  ('2241cd32-8ba2-48a5-9ee7-2caef7e9ed62','Light'),
  ('4391aaaa-df81-4396-9e33-31e4e4930b27','LightWire'),
  ('d381e0f5-3def-4a0d-8853-31e9200bcbda','Lofted'),
  ('429ed64a-4e97-4466-84d3-145a861ef684','Marker'),
  ('79348357-432d-4746-8e29-0e25c112e3aa','MatteHull'),
  ('b2ffef01-eaaa-4ab5-aa64-95a2c4f5dbc6','NeonPulse'),
  ('f72ec0e7-a844-4e38-82e3-140c44772699','OilPaint'),
  ('c515dad7-4393-4681-81ad-162ef052241b','OilPaintSingleSided'),
  ('f1114e2e-eb8d-4fde-915a-6e653b54e9f5','Paper'),
  ('759f1ebd-20cd-4720-8d41-234e0da63716','PaperSingleSided'),
  ('e0abbc80-0f80-e854-4970-8924a0863dcc','Petal'),
  ('c33714d1-b2f9-412e-bd50-1884c9d46336','Plasma'),
  ('ad1ad437-76e2-450d-a23a-e17f8310b960','Rainbow'),
  ('faaa4d44-fcfb-4177-96be-753ac0421ba3','ShinyHull'),
  ('70d79cca-b159-4f35-990c-f02193947fe8','Smoke'),
  ('d902ed8b-d0d1-476c-a8de-878a79e3a34c','Snow'),
  ('accb32f5-4509-454f-93f8-1df3fd31df1b','SoftHighlighter'),
  ('cf7f0059-7aeb-53a4-2b67-c83d863a9ffa','Spikes'),
  ('8dc4a70c-d558-4efd-a5ed-d4e860f40dc3','Splatter'),
  ('7a1c8107-50c5-4b70-9a39-421576d6617e','SplatterSingleSided'),
  ('0eb4db27-3f82-408d-b5a1-19ebd7d5b711','Stars'),
  ('44bb800a-fbc3-4592-8426-94ecb05ddec3','Streamers'),
  ('0077f88c-d93a-42f3-b59b-b31c50cdb414','Taffy'),
  ('b468c1fb-f254-41ed-8ec9-57030bc5660c','TaperedFlat'),
  ('c8ccb53d-ae13-45ef-8afb-b730d81394eb','TaperedFlatSingleSided'),
  ('d90c6ad8-af0f-4b54-b422-e0f92abe1b3c','TaperedMarker'),
  ('1a26b8c0-8a07-4f8a-9fac-d2ef36e0cad0','TaperedMarker_Flat'),
  ('75b32cf0-fdd6-4d89-a64b-e2a00b247b0f','ThickPaint'),
  ('fdf0326a-c0d1-4fed-b101-9db0ff6d071f','ThickPaintSingleSided'),
  ('4391385a-df73-4396-9e33-31e4e4930b27','Toon'),
  ('a8fea537-da7c-4d4b-817f-24f074725d6d','UnlitHull'),
  ('d229d335-c334-495a-a801-660ac8a87360','VelvetInk'),
  ('10201aa3-ebc2-42d8-84b7-2e63f6eeb8ab','Waveform'),
  ('b67c0e81-ce6d-40a8-aeb0-ef036b081aa3','WetPaint'),
  ('dea67637-cd1a-27e4-c9b1-52f4bbcb84e5','WetPaintSingleSided'),
  ('5347acf0-a8e2-47b6-8346-30c70719d763','WigglyGraphite'),
  ('e814fef1-97fd-7194-4a2f-50c2bb918be2','WigglyGraphiteSingleSided'),
  ('4391385a-cf83-4396-9e33-31e4e4930b27','Wire')
]

TILT_MAGIC_SENTINEL = 0x74696c54 #'tilT'
TILT_HEADER_SIZE = 16 
TILT_HEADER_VERSION = 1 
TILT_RESERVED_1 = 0
TILT_RESERVED_2 = 0

STANDARD_FILE_ORDER = [
  'header.bin',
  'thumbnail.png',
  'metadata.json',
  'main.json',
  'data.sketch'
]
STANDARD_FILE_ORDER = dict( (n,i) for (i,n) in enumerate(STANDARD_FILE_ORDER) )

class TiltHeader(object):
  """
    uint32 sentinel ('tilT')
    uint16 header_size (currently 16)
    uint16 header_version (currently 1)
    uint32 reserved
    uint32 reserved
  """
  def __init__(self):
    tmp = struct.pack(">I", TILT_MAGIC_SENTINEL)
    tmp += struct.pack("HHII", TILT_HEADER_SIZE, 
    TILT_HEADER_VERSION, TILT_RESERVED_1, TILT_RESERVED_2)
    self.data  = tmp

  def getData(self):
    return self.data

class TiltThumbnailPNG(object):

  def __init__(self, height = None, width = None):
    self.png = None 
    self.height = height 
    self.width = width

  def makeRGBPNG(self, R=[], G=[], B=[]):
    #_makePNG([[0,255,0],[255,255,255],[0,255,0]])
    if len(R) == 0:
      R = [0,0,0]
    if len(G) == 0:
      G = [0,0,0]
    if len(B) == 0:
      B = [0,0,0]

    return self.makePNG([R,G,B])

  def makePNG(self, data):
      def I1(value):
          return struct.pack("!B", value & (2**8-1))
      def I4(value):
          return struct.pack("!I", value & (2**32-1))
      # compute width&height from data if not explicit
      if self.height is None:
          self.height = len(data) # rows
      if self.width is None:
          self.width = 0
          for row in data:
              if self.width < len(row):
                  self.width = len(row) # get the widest part
      # generate these chunks depending on image type
      makeIHDR = True
      makeIDAT = True
      makeIEND = True
      png = b"\x89" + "PNG\r\n\x1A\n".encode('ascii')
      if makeIHDR:
          colortype = 0 # true gray image (no palette)
          bitdepth = 8 # with one byte per pixel (0..255)
          compression = 0 # zlib (no choice here)
          filtertype = 0 # adaptive (each scanline seperately)
          interlaced = 0 # no
          IHDR = I4(self.width) + I4(self.height) + I1(bitdepth)
          IHDR += I1(colortype) + I1(compression)
          IHDR += I1(filtertype) + I1(interlaced)
          block = "IHDR".encode('ascii') + IHDR
          png += I4(len(IHDR)) + block + I4(zlib.crc32(block))
      if makeIDAT:
          raw = b""
          for y in range(self.height):
              raw += b"\0" # no filter for this scanline
              for x in range(self.width):
                  c = b"\0" # default black pixel
                  if y < len(data) and x < len(data[y]):
                      c = I1(data[y][x])
                  raw += c
          compressor = zlib.compressobj()
          compressed = compressor.compress(raw)
          compressed += compressor.flush() #!!
          block = "IDAT".encode('ascii') + compressed
          png += I4(len(compressed)) + block + I4(zlib.crc32(block))
      if makeIEND:
          block = "IEND".encode('ascii')
          png += I4(0) + block + I4(zlib.crc32(block))
      return png

class ConversionError(Exception):
  """An error occurred in the zip <-> directory conversion process"""
  pass

class TiltArchive(object):
  def __init__(self):
    self.dirpath = tempfile.mkdtemp(suffix='.tilt', prefix='Untitled-')

  def write_header(self, hdr_data):
    with open(self.dirpath+"/header.bin","wb") as f:
      f.write(hdr_data)

  def write_sketch(self, sketch_data):
    with open(self.dirpath+"/data.sketch","wb") as f:
      f.write(sketch_data)

  def write_metadata(self, meta_data):
    with open(self.dirpath+"/metadata.json","w") as f:
      f.write(meta_data)

  def write_thumbnail(self, png_data):
    with open(self.dirpath+"/thumbnail.png","wb") as f:
      f.write(png_data)

  def get_filename(self):
    return self.dirpath

  def finalize(self):
    self.convert_dir_to_zip(self.dirpath, True)
    self.cleanup(self.dirpath)

  def convert_dir_to_zip(self, in_name, compress):
    in_name = os.path.normpath(in_name)  # remove trailing '/' if any
    out_name = in_name + '.part'
    if os.path.exists(out_name):
      raise ConversionError("Remove %s first" % out_name)
  
    def by_standard_order(filename):
      lfile = filename.lower()
      try:
        idx = STANDARD_FILE_ORDER[lfile]
      except KeyError:
        raise ConversionError("Unknown file %s; this is probably not a .tilt" % filename)
      return (idx, lfile)

    # Make sure metadata.json looks like valid utf-8 (rather than latin-1
    # or something else that will cause mojibake)
    try:
      with open(os.path.join(in_name, 'metadata.json'), 'r') as inf:
        #jsondata = inf.read() 
        import json
        json.load(inf)
    except IOError as e:
      raise ConversionError("Cannot validate metadata.json: %s" % e)
    except UnicodeDecodeError as e:
      raise ConversionError("metadata.json is not valid utf-8: %s" % e)
    except ValueError as e:
      raise ConversionError("metadata.json is not valid json: %s" % e)

    compression = zipfile.ZIP_DEFLATED if compress else zipfile.ZIP_STORED
    try:
      header_bytes = None

      zipf = BytesIO()
      with zipfile.ZipFile(zipf, 'a', compression, False) as zf:
        for (r, ds, fs) in os.walk(in_name):
          fs.sort(key=by_standard_order)
          for f in fs:
            fullf = os.path.join(r, f)
            if f == 'header.bin':
              with open(fullf, 'rb') as hdrfile:
                header_bytes = hdrfile.read()
              continue
            arcname = fullf[len(in_name)+1:]
            zf.write(fullf, arcname, compression)

      with open(out_name, 'wb') as outf:
        outf.write(header_bytes)
        outf.write(zipf.getvalue())

      tmp = in_name + '._prev'
      os.rename(in_name, tmp)
      os.rename(out_name, in_name)
      self._destroy(tmp)

    finally:
      self._destroy(out_name)

  def cleanup(self, dirpath):
    print(dirpath)
    #shutil.rmtree(dirpath)

  def _destroy(self, file_or_dir):
    import stat
    if os.path.isfile(file_or_dir):
      os.chmod(file_or_dir, stat.S_IWRITE)
      os.unlink(file_or_dir)
    elif os.path.isdir(file_or_dir):
      import shutil, stat
      for r,ds,fs in os.walk(file_or_dir, topdown=False):
        for f in fs:
          os.chmod(os.path.join(r, f), stat.S_IWRITE)
          os.unlink(os.path.join(r, f))
        for d in ds:
          os.rmdir(os.path.join(r, d))
      os.rmdir(file_or_dir)
    if os.path.exists(file_or_dir):
      raise Exception("'%s' is not empty" % file_or_dir)

class MetaDataFile(object):
  # Helper for parsing
  def __init__(self):
    self.is_initialized = False 
    self.metadata = {
      "EnvironmentPreset": DEFAULT_ENVIRONMENT,
      "ThumbnailCameraTransformInRoomSpace": [ [ 0.0, 0.0, 0.0 ], [ 0.0, 0.0, 0.0, 0.0 ], 1.0 ],
      "SceneTransformInRoomSpace": [ [ 0.0, 0.0, 0.0 ], [ 0.0, 0.0, 0.0, 0.0 ], 1.0 ],
      "BrushIndex": [],
      "SchemaVersion": METADATA_SCHEMA_VERSION,
      "ModelIndex": [],
      "Mirror": {
        "Transform": [ [ 0.0, 0.0, 0.0 ], [ 0.0, 0.0, 0.0, 0.0 ], 1.0 ]
      },
      "Videos": [],
      "CameraPaths": []
    }
    for brush_tuple in BRUSH_LIST_ARRAY:
      print(brush_tuple)
      self.metadata["BrushIndex"].append(brush_tuple[0])
    
  def add_model(self, model_path):
    if self.is_initialized == False:
      return 

    model_details = {
      "FilePath": "", # this is relative to the tiltbrush folder
      "PinStates": [ False ], # support changint this later
      #support chaning this later (position, rotation)
      "RawTransforms": [ [ [ 0.0, 0.0, 0.0 ], [ 0.0, 0.0, 0.0, 0.0 ], 1.0 ]
      ],
      "GroupIds": [ 0 ]
    }
    self.metadata["ModelIndex"].append(model_details)

    return
    
  def get_metadata_json(self):
    return json.dumps(self.metadata, indent=4, sort_keys=True)

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
    print("[_make_ext_reader lambda] f:", f)     
    return (lambda f: [], lambda f, vs: None, {})

  fmt = '<' + ''.join(info[1] for info in infos)
  names = [info[0] for info in infos]
  if '@' in fmt:
    # struct.unpack isn't general enough to do the job
    fmts = ['<'+info[1] for info in infos]
    def reader(f, fmts=fmts):
      print("[_make_ext_reader reader 1] f:", f, "fmt:", fmt)      
      values = [None] * len(fmts)
      for i,fmt in enumerate(fmts):
        if fmt == '<@':
          nbytes, = struct.unpack('<I', f.read(4))
          values[i] = f.read(nbytes)
        else:
          values[i], = struct.unpack(fmt, f.read(4))
  else:
    def reader(f, fmt=fmt, nbytes=len(infos)*4):
      print("[_make_ext_reader reader 2] f:", f, "fmt:", fmt, "nbytes:", nbytes)      
      values = list(struct.unpack(fmt, f.read(nbytes)))
      print("values", values)
      return values

  def writer(f, values, fmt=fmt):
    print("[_make_ext_reader writer] f:", f, "values:", values, "fmt:", fmt)
    return f.write(struct.pack(fmt, *values))

  lookup = dict( (name,i) for (i,name) in enumerate(names) )

  return reader, writer, lookup


#
# Utility class for rw of binary data. The 
# in_file is a BytesIO object.
############################################
class BinFile(object):
  # Helper for parsing
  def __init__(self, in_file):
    self.in_file = in_file

  def read(self, n):
    return self.in_file.read(n)

  def write(self, data):
    return self.in_file.write(data)

  def read_length_prefixed(self):
    n, = self.unpack("<I")
    return self.in_file.read(n)

  def write_length_prefixed(self, data):
    print("write_length_prefixed data: |", data, "|")
    self.pack_into_file("<I", len(data))
    self.in_file.write(data)
    #packed_data = struct.pack("<s", str.encode(data)) # convert string to bytes array
    #print(packed_data)
    #packed_len = struct.pack("<I", len(packed_data))
    #print(packed_len)
    #self.in_file.write(packed_len)
    #self.in_file.write(packed_data)

  def unpack_from_file(self, fmt):
    n = struct.calcsize(fmt)
    data = self.in_file.read(n)
    return struct.unpack(fmt, data)

  # In python *args is just convention. This is used 
  # when there are a variable number of expected 
  # arguments. 
  def pack_into_file(self, fmt, *args):
    print("pack_into_file fmt", fmt)
    print("pack_into_file args", *args)
    data = struct.pack(fmt, *args)
    print("pack_into_file data", data)
    return self.in_file.write(data)

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
    self.additional_header = b'' # 0 length data
    self.strokes = []

  def add_stroke(self, stroke):
      if len(self.strokes) < 300000:
        self.strokes.append(stroke)

  def add_control_point_to_stroke(self, index, pos, rot, ext=[]):
    print("adding point to stroke at index: ", index)
    self.strokes[index].add_control_point(pos, rot, ext)

  def pack(self):
    tmpf = BytesIO()
    packed_data = self.binwrite(BinFile(tmpf))
    print("pack:" , packed_data)
    return tmpf.getvalue()

  def binwrite(self, b):
    # b is a BinFile instance.
    print("binwrite: ", *self.header)
    b.pack_into_file("<3I", *self.header)
    b.write_length_prefixed(self.additional_header)
    b.pack_into_file("<i", len(self.strokes))
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
  def __init__(self, brush, color, size, stroke_mask, cp_mask, stroke_extension=[]):
    self.brush_idx = brush  
    self.brush_color = color
    self.brush_size = size
    self._controlpoints = []
    self.stroke_mask = stroke_mask
    self.cp_mask = cp_mask
    self.extension = stroke_extension

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

  
  def add_control_point(self, pos, rot, extensions = []):
    self.create_and_add_control_point(pos, rot, extensions)

  # 
  # Add a control point from properties
  def create_and_add_control_point(self, pos, rot, extensions = []):
    if len(self._controlpoints) < 10000:
      ctrl_pt = ControlPoint(pos, rot, extensions)
      print(ctrl_pt)
      self._controlpoints.append(ctrl_pt)

  # 
  # Add a control point
  def add_control_point_from_object(self, control_point):
    if len(self._controlpoints) < 10000:
      self._controlpoints.append(control_point)

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
    b.pack_into_file("<i", self.brush_idx)
    b.pack_into_file("<4f", *self.brush_color)
    b.pack_into_file("<fII", self.brush_size, self.stroke_mask, self.cp_mask)
    self.stroke_ext_writer(b, self.extension) # pass the binary writer into the extension
                                              # writer
    b.pack_into_file("<i", len(self._controlpoints))     # little endian, signed int
    print(self.cp_ext_writer)
    for cp in self._controlpoints:
      cp._write(b, self.cp_ext_writer)


#
#
# 
#
class ControlPoint(object):
  """Data for a single control point from a stroke. Attributes:
    .position    Position as 3 floats. Units are decimeters.
    .orientation Orientation of controller as a quaternion (x, y, z, w)."""

  def __init__(self, pos, rot, ext=[]):
    """Create a ControlPoint from pos (array of 3 floats), rot 
    (array of 4 floats) and extension (CONTROLPOINT_EXTENSION_BITS)"""
    self.position = pos    # 3 floats
    self.orientation = rot # 4 floats
    self.extension = ext   # array of extension settings
    
  # the b is a binary writer which is passed down from the 
  # Stroke write method
  def _write(self, b, cp_ext_writer):
    p = self.position    # 3 float
    o = self.orientation # 4 floats
    # little endian, 7 4-byte floats 
    b.pack_into_file("<7f", p[0], p[1], p[2], o[0], o[1], o[2], o[3])
    cp_ext_writer(b, self.extension)
