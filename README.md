topo5k
======

A command line tool to retrieve Grid'5000 topology under several formats.
Current version includes, for Grid'5000, a site or a cluster:
- a map
- a SimGrid platform file

Based on execo 2.3-dev and Grid'5000 API. 


Usage
-----

    topo5k -m treemap
  
will generate a tree map of Grid'5000 (default mode).
 
    topo5k -m simgrid
  
will produce the SimGrid platform file for the whole platform.

You can specify one or several sites,

    topo5k -m treemap -r nancy 
    topo5k -m simgrid -r lyon,luxembourg   

 or directly used an oar/oargrid job id.

    topo5k -m treemap -j 49177
    topo5k -m simgrid -j grenoble:1659169 


