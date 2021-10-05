# pydl2osmand
populate a pre-existing SQLite osmand map file, using a geoJson for the area, in order to build an offline map.
It may be of use for people who use tools like **MOBAC**, **SAS Planet**, **PortableBasemapServer** to build offline map files.

__This is highly unstable, unchecked , and probaly outdated code.__

## Why?
For years, I've been a big fan of the android app **OruxMaps**, for it's offline and raster capabilities.
Recently, I've discovered that **OsmAnd** also has some (little known) raster/offline features. And so I switched to **OsmAnd** and needed to port all my offline maps to it.

The GUI tools above are great for building **mbtiles** files. which are nicely supported by **OruxMaps**, but not by OsmAnd.
Also, I prefer a command-line tool for this kind of job.

## Requirement
 - loads of python 3 libs, including "supermercado". see file header.
 - a geojson with the extents that you want to download, it has to be on a **single line** due to a bug in some lib (mercado I think). there is plenty of online geojson editors.
 - an sqlite file compliant with OSMand file format, easiest way is to copy this file from the phone.
 - knowledge of how tile map services works.

## Usage
$ pydl2osmand.py --dbfile MiddleEarth.sqlite --geoJson southHobbitCounty.geojson --maxz 10 --threads 4
 - MiddleEarth.sqlite : the file you copied from the phone, must be preconfigured with map service infos like URL ....
 - southHobbitCounty.geojson : a polygon with the contour of the area you want to d/l, _on 1 line_ !
 - maxz 10 : max zoom, smallest zoom is 1 (the whole planet on 1 image tile), zoom 10 or 12 give nice country maps already, do not go above 15 or so except for very small areas (see geojson).
 - threads 4 : attempt to make things a little bit faster by parrallelizing jobs. don't expect much.
then go get a coffee, and monitor the sqlite file size !
