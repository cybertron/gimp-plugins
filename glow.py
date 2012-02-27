#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

from gimpfu import *
from gimpenums import *

def innerglow(image, drawable, color, strength, size, outer, separate):
   gimp.tile_cache_ntiles(64) # Ah, much better
   width = drawable.width
   height = drawable.height
   
   pdb.gimp_image_undo_group_start(image)
   
   glowlayer = gimp.Layer(image, "Glow", width, height, RGBA_IMAGE, 100, NORMAL_MODE)
   image.add_layer(glowlayer, -1)
   savecolor = pdb.gimp_context_get_foreground()
   pdb.gimp_context_set_foreground(color)

   # Fill with selected color
   channel = pdb.gimp_selection_save(image)
   # We fill the whole layer so that later when we blur we don't end up with
   # a light border around the inside of the selection
   pdb.gimp_selection_all(image)
   pdb.gimp_edit_fill(glowlayer, FOREGROUND_FILL)
   
   pdb.gimp_selection_load(channel)
   if not outer:
      # Delete inside of selection
      pdb.gimp_selection_shrink(image, strength)
      pdb.gimp_edit_clear(glowlayer)
   else:
      pdb.gimp_selection_grow(image, strength)
      pdb.gimp_selection_invert(image)
      pdb.gimp_edit_clear(glowlayer)
      
   # Blur what's left
   pdb.gimp_selection_load(channel)
   if outer:
      pdb.gimp_selection_invert(image)
   pdb.plug_in_gauss_rle2(image, glowlayer, size, size)
   
   # Delete everything we don't want
   pdb.gimp_selection_invert(image)
   if not pdb.gimp_selection_is_empty(image):
      pdb.gimp_edit_clear(glowlayer)
      
   # It's extremely annoying to have the selection inverted after this runs
   if not outer:
      pdb.gimp_selection_invert(image)

   if not separate:
      pdb.gimp_image_merge_down(image, glowlayer, EXPAND_AS_NECESSARY)
   
   pdb.gimp_context_set_foreground(savecolor)
   
   pdb.gimp_image_undo_group_end(image)
   

register("glow",
         N_("Add glow to a selection"),
         "Help",
         "Cybertron",
         "Ben Nemec",
         "2009",
         "Glow...",
         "*",
         [(PF_IMAGE, "image", "Input image", None),
          (PF_DRAWABLE, "drawable", "Input drawable", None),
          (PF_COLOR, "color", "Color", (255, 255, 255)),
          (PF_SPINNER, "strength", "Strength", 10, (1, 10000, 1)),
          (PF_SPINNER, "size", "Size", 10, (1, 10000, 1)),
          (PF_BOOL, "outer", "Outer", False),
          (PF_BOOL, "separate", "Keep as Separate Layer", True)
          ],
         [],
         innerglow,
         menu="<Image>/Filters/Decor")

main()
