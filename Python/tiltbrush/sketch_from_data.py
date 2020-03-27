import os 
import sys 

# Make the tiltbrush submodule accessible for code imports
lib_path = os.path.abspath(os.path.join(__file__, '..', '..', 'Python'))
sys.path.append(lib_path)

from tilted import Sketch
from tilted import Stroke
from tilted import ControlPoint

STROKE_EXT_FLAGS = 'flags'
STROKE_EXT_SCALE = 'scale'
STROKE_EXT_GROUP = 'group'
STROKE_EXT_SEED  = 'seed'

my_sketch = Sketch()

brush_index  = 0 # the index into guid arr
stroke_color = [0.0, 0.0, 0.0, 0.0]  # RGBA color, as 4 floats in the range [0, 1]
stroke_size  = 0.1 # Brush size, in decimeters, as a float. (multiplied by scale)

stroke = Stroke(brush_index, stroke_color, stroke_size, 2, 2)
stroke.set_stroke_extension(STROKE_EXT_SCALE, 0.5)
print(stroke.get_stroke_extension(STROKE_EXT_SCALE))
my_sketch.add_stroke(stroke)

stroke_index = 0 #XXX add bounds checks for this
pos = [1.0, 1.0, 1.0]
rot = [1.0, 1.0, 1.0, 0.0]
my_sketch.add_control_point_to_stroke(stroke_index, pos, rot)

sketch_bin_data = my_sketch.pack()

sketch_file = open("sketch.data", "wb")
sketch_file_array = bytearray(sketch_bin_data)
sketch_file.write(sketch_file_array)