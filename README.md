topo5k
======

A command line tool to retrieve Grid'5000 topology under several formats.
Current version includes, for Grid'5000, a site or a cluster:
- a map
- a SimGrid platform file

Based on execo 2.3 and Grid'5000 API. 


Usage
-----

  topo5k -m map
  
will generate a map.
 
  topo5k -m simgrid -r nancy
  
will produce the SimGrid platform file for Nancy.map






G5K_simgrid.py
--------------
A Python script that generate a platform file for the SimGrid software.
http://simgrid.gforge.inria.fr/

Requirements : 
- networkx
- execo


To generate the platform file, run

    ./G5K_simgrid.py
    
    

draw_g5k_topology.rb
--------------------

Gem dependencies :
- rubygems
- net-ssh-gateway
- rest-client
- json
- socket
- optparse
- graphviz
- media_wiki




