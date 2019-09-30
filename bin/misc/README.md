
## Brush map   

```

```

## JSON representation of tilt brush stroke data
```json
    {
    "sketch":[
        {
            "brush":"guid",
            "size":0.0,
            "color":[
                0,
                0,
                0
            ],
            "cntlPts":[
                {
                "position":[
                    0.0,
                    0.0,
                    0.0
                ],
                "rotation":[
                    0.0,
                    0.0,
                    0.0,
                    0.0
                ]
                }
            ]
        }
    ]
    }
```

## Convert unity json to tilt
## Convert to unity json
```
[System.Serializable]
public struct SketchObject
{
        [System.Serializable]
        public struct StrokeColor
        {
            public int red;
            public int blue;
            public int green;
        }

        [System.Serializable]
        public struct Position
        {
            public float x;
            public float y;
            public float z;
        }

        [System.Serializable]
        public struct Rotation
        {
            public float x;
            public float y;
            public float z;
            public float q;
        }

        [System.Serializable]
        public struct ControlPoint
        {
            public Position position;
            public Rotation rotation;
        }

   [System.Serializable]
   public struct StrokeEntry
   {

      public int brushIndex;
      public float brushSize;
      public StrokeColor color;
      public ControlPoint[] ctrlPts; 

   }
 
   public SketchObject[] object;
}
```
## Goal, have a tb sketch work in 