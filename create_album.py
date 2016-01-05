#!/usr/bin/env python
r"""
Creation of photo album from a list of picture filenames

Needs jhead__ program to be installed.

__ http://www.sentex.net/~mwandel/jhead/

EXAMPLES::

	create_album.py -i album.txt -l date --end 2015-03-10 -v
	create_album.py -i album.txt -l date --start 2015-03-10 -v

TODO:

    - Use jpeg python module instead of jhead (->no dependance + faster?)

AUTHORS:

    - Sebastien Labbe, december 2015, initial version
"""
import os
import argparse
import subprocess
from datetime import datetime
import calendar
from collections import Counter


class MonImage(object):
    def __init__(self, filename):
        self._filename = filename
        self.__datetime_file = None
        self.__datetime_taken = None

    def __repr__(self):
        x,y = self.resolution()
        a = "landscape" if self.is_landscape() else "portrait"
        dt = self.datetime().isoformat()
        return "Image Reso:{}x{} ({}) Date/Time:{}".format(x,y,a,dt)

    def filename(self):
        return self._filename
    def resolution(self):
        cmd = "jhead {} | grep Resolution".format(self._filename)
        a = subprocess.check_output(cmd, shell=True)
        L = a.split()
        assert L[0] == "Resolution"
        assert L[1] == ":"
        assert L[3] == "x"
        return int(L[2]), int(L[4]) # x, y

    def is_landscape(self):
        x, y = self.resolution()
        return x > y

    def _datetime_taken(self):
        if self.__datetime_taken is None:
            cmd = "jhead {} | grep Date/Time".format(self._filename)
            a = subprocess.check_output(cmd, shell=True)
            L = a.split()
            assert L[0] == "Date/Time"
            assert L[1] == ":"
            self.__datetime_taken = datetime.strptime(L[2]+L[3],'%Y:%m:%d%H:%M:%S')
        return self.__datetime_taken

    def _datetime_file(self):
        if self.__datetime_file is None:
            cmd = "jhead {} | grep 'File date'".format(self._filename)
            a = subprocess.check_output(cmd, shell=True)
            L = a.split()
            assert L[0] == 'File'
            assert L[1] == 'date'
            assert L[2] == ':'
            self.__datetime_file = datetime.strptime(L[3]+L[4],'%Y:%m:%d%H:%M:%S')
        return self.__datetime_file 

    def datetime(self):
        try:
            dt = self._datetime_taken()
        except subprocess.CalledProcessError:
            try:
                dt = self._datetime_file()
            except subprocess.CalledProcessError:
                print "unable to find date time for image :", self
        self.__datetime = dt
        return dt

    def year_month(self):
        dt = self.datetime()
        return dt.year, dt.month

def group_by_orientation(L, nlandscape=4, nportrait=4):
    output = []
    H = []
    V = []
    for im in L:
        if im.is_landscape():
            H.append(im)
        else:
            V.append(im)
        if len(H) == nlandscape:
            output.append(H)
            H = []
        if len(V) == nportrait:
            output.append(V)
            V = []
    if H:
        output.append(H)
    if V:
        output.append(V)
    return output

########
# Script
########

parser = argparse.ArgumentParser()
parser.add_argument("-i", "--input", type=str,
                    help="text file containing list of image filenames")
parser.add_argument("-l", "--label", type=str, default='date',
        help="label under images: ex: filename (default: date)")
parser.add_argument("-p", "--page", type=str, default='A4',
        help="page format for montage: <geometry>... (default:A4)")
parser.add_argument("-b", "--background", type=str, default='white',
        help="color of background, ex: lightblue (default: white)")
parser.add_argument("-s", "--start", type=str, default='2000-01-01',
        help="starting date of the album (defaut:2000-01-01)")
parser.add_argument("-e", "--end", type=str, default='2100-01-01',
                help="end date of the album (defaut:2100-01-01)")
parser.add_argument("-v", "--verbose", default=False, action='store_true', 
        help="print filenames per pages")
args = parser.parse_args()

# Read the list of images
with open(args.input) as f:
    s = f.read()

# Create image objects
print "Creation of the image objects..."
L = [MonImage(line.strip()) for line in s.splitlines()]

# Print number of images per month
print "Printing number of images per month..."
c = Counter([im.year_month() for im in L])
for key in sorted(c):
    year,month = key
    print "{} {:<10}: {:<3} {}".format(year, calendar.month_name[month], 
                                       c[key], "+"*c[key])
print "Total number of images: {}".format(len(L))

# Filter images according to date
start = datetime.strptime(args.start,'%Y-%m-%d')
end = datetime.strptime(args.end,'%Y-%m-%d')
print "Filtering images in the range {} to {}...".format(start.strftime("%Y%m%d"),
                                                         end.strftime("%Y%m%d"))
L = [im for im in L if start <= im.datetime() < end]

# Sort images chronologically
print "Sorting {} images chronologically ...".format(len(L))
L.sort(key=lambda im:im.datetime())
first_datetime = L[0].datetime()
last_datetime = L[-1].datetime()
print "First image is {}".format(first_datetime)
print "Last image is {}".format(last_datetime)

# Group by landscape/portrait groups
print "Group images into landscape/portrait pages...".format(len(L))
groups = group_by_orientation(L, nlandscape=3, nportrait=4)
print "Number of pages to create: {}".format(len(groups))

# Print filenames per pages
if args.verbose:
    for i,group in enumerate(groups):
        print "page {}:".format(i+1)
        for image in group:
            print image.filename()

# label under each image
# http://www.imagemagick.org/Usage/montage/
# http://www.imagemagick.org/script/escape.php
if args.label == 'date':
    label = "'%[EXIF:DateTimeOriginal]'"
elif args.label == 'filename':
    label = "'%f'"
else:
    raise ValueError("Unknown value for label (={})".format(args.label))

montage_cmd = ("montage -label {label} {files} -page {page}"
      " -tile {tile} -scale {scale}"
      " -border 4x4 -bordercolor Lavender"
      " -shadow -geometry {geometry}"
      " -auto-orient"
      " -background {background} {dir}/page{number:0>3d}.pdf")

# import tempfile
# tmpdirname = tempfile.mkdtemp()
tmpdirname = "/tmp"

# Call ImageMagick once for each page
print "Calling ImageMagick once for each page..."
for i,group in enumerate(groups):
    files = " ".join([im.filename() for im in group])
    if group[0].is_landscape():
        scale = 500
        geometry = "+85+5"
        tile = "1x3"
    else:
        scale = 240
        geometry = "+36+12"
        tile = "2x2"
    cmd = montage_cmd.format(label=label, files=files, 
            page=args.page, background=args.background, 
            tile=tile, scale=scale, geometry=geometry, 
            dir=tmpdirname, number=i)
    a = subprocess.check_output(cmd, shell=True)
    if (i+1) % 10 == 0:
        print i
    else:
        print i,

# Create output filname
prefix, ext = os.path.splitext(args.input)
output = "{}-{}-{}.pdf".format(prefix, first_datetime.strftime("%Y%m%d"),
        last_datetime.strftime("%Y%m%d"))

# Join all the pages into the album
print "\nFusion of all the pages into one album with pdfjam..."
files = ['{}/page{:0>3d}.pdf'.format(tmpdirname,i) for i in range(len(groups))]
cmd = 'pdfjam {} -o {}'.format(' '.join(files), output)
a = subprocess.check_output(cmd, shell=True)

