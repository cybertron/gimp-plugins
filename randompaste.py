#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

from gimpfu import *
from gimpenums import *
import random

def randompaste(image, drawable, count, rotate):
   gimp.tile_cache_ntiles(64) # Ah, much better
   width = drawable.width
   height = drawable.height
   random.seed()
   
   pdb.gimp_image_undo_group_start(image)
   
   current = None
   
   for i in range(count):
      current = pdb.gimp_edit_paste(drawable, False)
      x, y = current.offsets
      translatex = x + current.width
      translatey = y + current.height
      current.translate(-translatex, -translatey)
      current.translate(random.randint(0, width + current.width * 2), random.randint(0, height + current.height * 2))
      if rotate:
         pdb.gimp_rotate(current, 0, random.random() * 2 * math.pi)
      
   pdb.gimp_floating_sel_anchor(current)
   
   pdb.gimp_image_undo_group_end(image)
   

register("randompaste",
         N_("Randomly paste the contents of the clipboard"),
         "Help",
         "Cybertron",
         "Ben Nemec",
         "2010",
         "Random Paste...",
         "*",
         [(PF_IMAGE, "image", "Input image", None),
          (PF_DRAWABLE, "drawable", "Input drawable", None),
          (PF_SPINNER, "count", "Count", 100, (1, 10000, 1)),
          (PF_BOOL, "rotate", "Rotate", True)
          ],
         [],
         randompaste,
         menu="<Image>/Filters/Map")

main()
