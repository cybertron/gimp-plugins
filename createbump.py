#!/usr/bin/env python

from gimpfu import *
from gimpenums import *
from math import sqrt
from subprocess import *
from mmap import *
import os
#import threading
#import sys

invertx = False
inverty = False
width = 0
height = 0
wrap = True
bias = 0

numthreads = 4
useoop = False

def createbump(image, drawable, nreducestr,
               nreduceagg, numlayers, blur,
               biasin, method, invx, invy, wrapin, scale):
   gimp.tile_cache_ntiles(64) # Ah, much better
   global width
   width = int(float(image.width) * scale)
   global height
   height = int(float(image.height) * scale)
   global invertx
   invertx = invx
   global inverty
   inverty = invy
   global wrap
   wrap = wrapin
   global bias
   bias = biasin
   
   bumpmap = image.duplicate()
   bumpmap.flatten()
   pdb.gimp_image_scale(bumpmap, width, height)
   pdb.gimp_desaturate(bumpmap.layers[0])
   pdb.gimp_drawable_set_visible(bumpmap.layers[0], 0)
   # Causes weird artifacts
   #pdb.plug_in_sel_gauss(bumpmap, bumpmap.layers[0], nreducestr, nreduceagg)
   
   newlayer = gimp.Layer(bumpmap, "Bump Map", bumpmap.width, bumpmap.height, RGBA_IMAGE, 100, NORMAL_MODE)
   bumpmap.add_layer(newlayer, -1)
   
   writebump = Pixelops(bumpmap.layers[0])
   readheight = Pixelops(bumpmap.layers[1])
   
   # Start child processes and send them the necessay data
   if useoop:
      docalculation(writebump, readheight, "Generate", 1)
         
   # Or just do calculations here
   else:
      gimp.progress_init("Generating...")
      for x in range(0, width):
         if x % (width / 100 + 1) == 0:
            gimp.progress_update(float(x) / float(width))
            gimp.displays_flush()
         for y in range(0, height):
            if method == 1:
               normal = getnormal1(x, y, readheight, bias)
            elif method == 4:
               normal = getnormal4(x, y, readheight, bias)
            elif method == 9:
               normal = getnormalarb(x, y, readheight, bias, 3, 3)
            pixelval = chr(int(normal.x))
            pixelval += chr(int(normal.y))
            pixelval += chr(int(normal.z))
            pixelval += chr(255)
            writebump[x, y] = pixelval
         
   writebump.flush()
   
   for x in range(0, numlayers):
      bumpmap.add_layer(pdb.gimp_layer_copy(bumpmap.layers[x], -1))
      pdb.gimp_layer_set_mode(bumpmap.layers[0], OVERLAY_MODE)
      pdb.plug_in_gauss_rle2(bumpmap, bumpmap.layers[0], blur * float(sqrt(x) + 1), blur * float(sqrt(x) + 1))
      
      
   bumpmap.layers[0].merge_shadow()
   bumpmap.merge_visible_layers(CLIP_TO_IMAGE)
   pdb.plug_in_sel_gauss(bumpmap, bumpmap.layers[0], nreducestr, nreduceagg)
   
   # Now normalize the bump map
   if numlayers > 0 or nreducestr > 1:
      bumpmap.add_layer(gimp.Layer(bumpmap, "Normalized Bump Map", bumpmap.width, bumpmap.height, RGBA_IMAGE, 100, NORMAL_MODE), -1)
      normalized = Pixelops(bumpmap.layers[0])
      raw = Pixelops(bumpmap.layers[1])
      
      # Apparently it's actually faster to do this single-threaded than to
      # take the overhead hit copying data to the mmap'd file
      if False:
         docalculation(normalized, raw, "Normalize", 3)
      else:
         vec = vector()
         gimp.progress_init("Normalizing...")
         for x in range(0, width):
            if x % (width / 100 + 1) == 0:
               gimp.progress_update(float(x) / float(width))
               gimp.displays_flush()
            for y in range(0, height):
               vec.x = ord(raw.getval(x, y)[0])
               vec.y = ord(raw.getval(x, y)[1])
               vec.z = ord(raw.getval(x, y)[2])
               vec = vec.subtract(vector(128, 128, 128))
               vec.normalize()
               vec = vec.multiply(127)
               vec = vec.add(vector(128, 128, 128))
               pixelval = chr(int(vec.x))
               pixelval += chr(int(vec.y))
               pixelval += chr(int(vec.z))
               pixelval += chr(255)
               normalized[x, y] = pixelval
            
      normalized.flush()
   
   gimp.Display(bumpmap)
   gimp.displays_flush()
   
   pdb.gimp_image_clean_all(image)
   pdb.gimp_image_clean_all(bumpmap)
   

def docalculation(popsout, popsin, operation, count):
   gimp.progress_init("Sending data...")
   file = os.open("/home/cybertron/source/.dummymmap", os.O_RDWR)
   shmem = mmap(file, 20000000)
   for x in range(0, width):
      gimp.progress_update(float(x) / float(width))
      gimp.displays_flush()
      for y in range(0, height):
         shmem.write(popsin[x, y][0:count])

   shmem.close()
   os.close(file)
   
   gimp.progress_init("Starting threads...")
   childplist = []
   for i in range(0, numthreads):
      childplist.append(Popen("/home/cybertron/bin/bumphelper.py", stdin=PIPE, stdout=PIPE))
      childplist[i].stdin.write(operation + "\n")
      childplist[i].stdin.write(str(width) + "\n")
      childplist[i].stdin.write(str(height) + "\n")
      childplist[i].stdin.write(str((width / numthreads + 1) * i) + "\n")
      childplist[i].stdin.write(str(width / numthreads + 1) + "\n")
      childplist[i].stdin.write(str(bias) + "\n")
      childplist[i].stdin.write(str(invertx) + "\n")
      childplist[i].stdin.write(str(inverty) + "\n")
      childplist[i].stdin.write(str(wrap) + "\n")
   
   gimp.progress_init("Waiting for threads...")
   gimp.displays_flush()
   # Keep threads from blocking
   threadouts = ["" for i in range(0, numthreads)]
   alldone = False
   while not alldone:
      alldone = True
      for i in range(0, numthreads):
         if threadouts[i].find("EOD") == -1:
            threadouts[i] += childplist[i].stdout.read(50000)
            alldone = False

   gimp.progress_init("Retrieving results...")
   for i in range(0, numthreads):
      gimp.progress_update(float(i) / float(numthreads))
      gimp.displays_flush()
      output = threadouts[i]
      start = (width / numthreads + 1) * i
      calc = width / numthreads + 1
      if (start + calc > width):
         calc = width - start
      currpos = 0
      for x in range(start, start + calc):
         for y in range(0, height):
            pixelval = output[currpos]
            pixelval += output[currpos + 1]
            pixelval += output[currpos + 2]
            pixelval += chr(255)
            popsout[x, y] = pixelval
            currpos += 3
   

def getnormal4(x, y, heightmap, zbias):
   total = vector()
   count = 0
   currvec = vector(0, 0, ord(heightmap[x, y][0]))
   v1 = vector()
   v2 = vector()
   norm = vector()
   global invertx
   global inverty
   global width, height
   mx = width
   my = height
   
   offx = -1
   offy = -1
   if x + offx >= 0 and x + offx < mx and y + offy >= 0 and y + offy < my:
      v1 = vector(offx, 0, ord(heightmap[x + offx, y][0])).subtract(currvec)
      v2 = vector(0, offy, ord(heightmap[x, y + offy][0])).subtract(currvec)
      norm = v1.cross(v2)
      total = total.add(norm)
      count += 1
   
   offx = 1
   offy = -1
   if x + offx >= 0 and x + offx < mx and y + offy >= 0 and y + offy < my:
      v1 = vector(offx, 0, ord(heightmap[x + offx, y][0])).subtract(currvec)
      v2 = vector(0, offy, ord(heightmap[x, y + offy][0])).subtract(currvec)
      norm = v2.cross(v1)
      total = total.add(norm)
      count += 1
      
   offx = 1
   offy = 1
   if x + offx >= 0 and x + offx < mx and y + offy >= 0 and y + offy < my:
      v1 = vector(offx, 0, ord(heightmap[x + offx, y][0])).subtract(currvec)
      v2 = vector(0, offy, ord(heightmap[x, y + offy][0])).subtract(currvec)
      norm = v1.cross(v2)
      total = total.add(norm)
      count += 1
      
   offx = -1
   offy = 1
   if x + offx >= 0 and x + offx < mx and y + offy >= 0 and y + offy < my:
      v1 = vector(offx, 0, ord(heightmap[x + offx, y][0])).subtract(currvec)
      v2 = vector(0, offy, ord(heightmap[x, y + offy][0])).subtract(currvec)
      norm = v2.cross(v1)
      total = total.add(norm)
      count += 1
   
   retval = total.divide(count)
   retval.z += zbias
   retval.normalize()
   if invertx:
      retval.x *= -1
   if inverty:
      retval.y *= -1
   retval = retval.multiply(127)
   retval = retval.add(vector(128, 128, 128))
   return retval
   
   
def getnormal1(x, y, heightmap, zbias):
   total = vector()
   currvec = vector(0, 0, ord(heightmap[x, y][0]))
   v1 = vector()
   v2 = vector()
   norm = vector()
   global invertx
   global inverty
   global width, height
   global wrap
   mx = width
   my = height
   
   offx = 1
   offy = 1
   if x + offx >= mx:
      if wrap:
         offx = -x
      else:
         offx = -1
   if y + offy >= my:
      if wrap:
         offy = -y
      else:
         offy = -1
         
   v1 = vector(1, 0, ord(heightmap[x + offx, y][0])).subtract(currvec)
   v2 = vector(0, 1, ord(heightmap[x, y + offy][0])).subtract(currvec)
   total = v1.cross(v2)
      
   retval = total
   retval.z += zbias
   retval.normalize()
   if invertx:
      retval.x *= -1
   if inverty:
      retval.y *= -1
   retval = retval.multiply(127)
   retval = retval.add(vector(128, 128, 128))
   return retval
   
   
def getnormalarb(x, y, heightmap, zbias, xsamp, ysamp):
   total = vector()
   mainvec = vector(0, 0, ord(heightmap[x, y][0]))
   currvec = vector(0, 0, ord(heightmap[x, y][0]))
   v1 = vector()
   v2 = vector()
   norm = vector()
   global invertx
   global inverty
   global width, height
   mx = width
   my = height
   
   offx = 1
   offy = 1
   count = 0
   for currx in range(int(-xsamp / 2) + x, int(xsamp / 2) + x):
      for curry in range(int(-ysamp / 2) +y, int(ysamp / 2) + y):
         if currx >= 0 and currx + offx < mx and curry >= 0 and curry + offy < my:
            currvec = vector(0, 0, ord(heightmap[currx, curry][0]))
            v1 = vector(offx, 0, ord(heightmap[currx + offx, curry][0])).subtract(currvec)
            v2 = vector(0, offy, ord(heightmap[currx, curry + offy][0])).subtract(currvec)
            norm = v1.cross(v2)
            total = total.add(norm)
            count += 1
   
   print count
   retval = total.divide(count)
   retval = total
   retval.z += zbias
   retval.normalize()
   if invertx:
      retval.x *= -1
   if inverty:
      retval.y *= -1
   retval = retval.multiply(127)
   retval = retval.add(vector(128, 128, 128))
   return retval
   
   
# Just those vector functions that are needed for this application
class vector:
   def __init__(self, inx = 0, iny = 0, inz = 0):
      self.x = inx
      self.y = iny
      self.z = inz
      
      
   def dot(self, other):
      return self.x * other.x + self.y * other.y + self.z * other.z
   
   
   def cross(self, v):
      return vector(self.y * v.z - self.z * v.y, self.z * v.x - self.x * v.z, self.x * v.y - self.y * v.x)
   
   
   def add(self, other):
      return vector(self.x + other.x, self.y + other.y, self.z + other.z)
   
   def subtract(self, other):
      return vector(self.x - other.x, self.y - other.y, self.z - other.z)
   
   
   def divide(self, div):
      return vector(self.x / div, self.y / div, self.z / div)
   
   
   def multiply(self, mul):
      return vector(self.x * mul, self.y * mul, self.z * mul)
   
   
   def normalize(self):
      mag = self.magnitude()
      if mag != 0:
         self.x /= mag
         self.y /= mag
         self.z /= mag
      
   def magnitude(self):
      return (sqrt(self.x * self.x + self.y * self.y + self.z * self.z))
   
   
class Pixelops:
   def __init__(self, drawable):
      self.drawable = drawable
      self.xcache = -1
      self.ycache = -1
      self.currtile = None
      self.tilesize = 64
      
   def getval(self, x, y):
      xoff = x % self.tilesize
      yoff = y % self.tilesize
      if x / self.tilesize != self.xcache or y / self.tilesize != self.ycache:
         self.xcache = x / self.tilesize
         self.ycache = y / self.tilesize
         self.currtile = self.drawable.get_tile2(False, x, y)
      return self.currtile[xoff, yoff]
      
   def setval(self, x, y, val):
      xoff = x % self.tilesize
      yoff = y % self.tilesize
      if x / self.tilesize != self.xcache or y / self.tilesize != self.ycache:
         self.xcache = x / self.tilesize
         self.ycache = y / self.tilesize
         self.currtile = self.drawable.get_tile2(True, x, y)
      self.currtile[xoff, yoff] = val
      
   def flush(self):
      self.drawable.flush()
      self.drawable.merge_shadow()
      
   def __getitem__(self, key):
      return self.getval(key[0], key[1])
   
   def __setitem__(self, key, val):
      self.setval(key[0], key[1], val)
   

register("createbump",
         N_("Tool to extract a normal map from an image"),
         "Help",
         "Cybertron",
         "Ben Nemec",
         "2008",
         "Create Bumpmap...",
         "*",
         [(PF_IMAGE, "image", "Input image", None),
          (PF_DRAWABLE, "drawable", "Input drawable", None),
          (PF_SLIDER, "nreducestr", "Noise Reduction Strength", 1, (1, 100, .1)),
          (PF_SLIDER, "nreduceagg", "Noise Reduction Agressiveness", 50, (0, 255, .1)),
          (PF_SPINNER, "numlayers", "Number of Layers to Blur", 0, (0, 100, 1)),
          (PF_SLIDER, "blur", "Blur Coefficient", 1, (0, 10, .1)),
          (PF_SLIDER, "bias", "Z Bias", 0, (0, 255, .1)),
          (PF_RADIO, "method", "Method (deprecated)", 1, (("1 Sample", 1), ("4 Samples", 4), ("3x3", 9))),
          (PF_TOGGLE, "invertx", "Invert X", 0),
          (PF_TOGGLE, "inverty", "Invert Y", 0),
          (PF_TOGGLE, "wrap", "Wrap", 1),
          (PF_SLIDER, "scale", "Scale", 1, (0, 1, .01))
          ],
         [],
         createbump,
         menu="<Image>/Filters/Map")

main()
