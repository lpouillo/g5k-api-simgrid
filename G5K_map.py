#!/usr/bin/env python
from pprint import pprint
from execo import logger
from execo_g5k import api_utils as API
from execo_g5k import get_g5k_sites
from topo5k import get_topology, get_backbone_graph, get_site_graph
import matplotlib.pyplot as plt
from geopy import geocoders
from networkx import graphviz_layout, draw_networkx, draw_networkx_nodes, draw_networkx_edges, \
draw_networkx_labels, spring_layout, draw_shell
#import matplotlib.patches as patches
#from copy import copy
#from math import sqrt
#from itertools import product

logger.setLevel('INFO')
logger.info('Starting')

sites = get_g5k_sites()

sites = ['lyon', 'sophia', 'grenoble']

backbone, equips, hosts = get_topology()

gr = get_backbone_graph(backbone)



for site in sites:
    sgr = get_site_graph(site, hosts[site], equips[site])
    gr.add_nodes_from(sgr.nodes_iter(data = True))
    gr.add_edges_from(sgr.edges_iter(data = True))
logger.info('Generating the graph')
plt.figure( figsize=(15,15) )

logger.info('Defining nodes and edges types')
backbone = [ node for node in gr.nodes_iter(data=True) 
            if node[1]['kind'] == 'renater' ]
gw_nodes = [ node[0] for node in gr.nodes_iter(data=True) 
            if node[1]['kind'] == 'router' ]
sw_nodes = [ node[0] for node in gr.nodes_iter(data=True) 
            if node[1]['kind'] == 'switch' ]
nodes_nodes = [ node[0] for node in gr.nodes_iter(data=True) 
            if node[1]['kind'] == 'node' ]

edges_1G = [ (edge[0], edge[1]) for edge in gr.edges_iter(data=True) 
             if edge[2]['bandwidth'] == 1000000000 ]
edges_10G = [ (edge[0], edge[1]) for edge in gr.edges_iter(data=True) 
             if edge[2]['bandwidth'] == 10000000000 ]
edges_20G = [ (edge[0], edge[1]) for edge in gr.edges_iter(data=True) 
             if edge[2]['bandwidth'] == 20000000000 ]
edges_other = [ (edge[0], edge[1]) for edge in gr.edges_iter(data=True) 
             if edge[2]['bandwidth'] not in [ 1000000000, 10000000000, 20000000000 ] ]

logger.info('Defining positions of Renater points')
pos = {}
g = geocoders.osm

renater_nodes = []
for renater in backbone:
    loc = renater[0].split('-')[1]+', France' if renater[0].split('-')[1] != 'luxembourg' \
            else 'Luxembourg, Luxembourg'
    get_loc = g.Nominatim().geocode(loc)
    pos[renater[0]] =  ( get_loc[1][1], get_loc[1][0] )
    renater[1]['pin'] = True
    renater_nodes.append(renater[0])

pos = graphviz_layout(gr, prog = 'neato')   

logger.info('Drawing nodes')    
draw_networkx_nodes(gr, pos, nodelist = renater_nodes, node_shape = 'v', node_size = 50)
draw_networkx_labels(gr, pos, labels = {node:node.split('-')[1].title() for node in renater_nodes} )

draw_networkx_nodes(gr, pos, nodelist = gw_nodes, node_shape = '8', node_color = 'g', node_size = 150,
                    labels = gw_nodes)
draw_networkx_nodes(gr, pos, nodelist = sw_nodes, node_color ='b', node_size = 75)
draw_networkx_nodes(gr, pos, nodelist = nodes_nodes, node_color ='y', node_size = 5)

draw_networkx_edges(gr, pos, edgelist = edges_20G, width = 2)
draw_networkx_edges(gr, pos, edgelist = edges_10G)
draw_networkx_edges(gr, pos, edgelist = edges_1G, edge_color = '#aaaaaa', width = 0.5)
draw_networkx_edges(gr, pos, edgelist = edges_other, edge_color = 'r', width = 1)



plt.savefig('test.png')

exit()


kinds = []
for node in gr.nodes_iter(data=True):
    kind = node[1]['kind']
    if kind not in kinds:
        kinds.append(node[1]['kind'])
    
print kinds
exit()
print [ node for node in gr.nodes_iter(data=True) if node[1].has_key('kind') and node[1]['kind'] == 'node' ]

exit()

draw_networkx(gr, pos, with_labels = False)






nx.draw_networkx_nodes(gr, pos, nodelist = backbone_nodes, node_shape = 'v', node_size = 50)
nx.draw_networkx_edges(gr, pos, edgelist = backbone_edges)
nx.draw_networkx_nodes(gr, pos, nodelist = gw_nodes, node_shape = '8', 
                       node_color = 'g', node_size = 150)
nx.draw_networkx_edges(gr, pos, edgelist = gw_edges)
nx.draw_networkx_nodes(gr, pos, nodelist = sw_nodes, node_color ='b', node_size = 100)
nx.draw_networkx_edges(gr, pos, edgelist = sw_edges)
nx.draw_networkx_nodes(gr, pos, nodelist = nodes_nodes, node_color ='y', node_size = 5)
nx.draw_networkx_edges(gr, pos, edgelist = nodes_edges)

labels = {}
for node in gw_nodes:
    labels[node] = node.split('.')[0]
#for node in nodes_nodes:
#    labels[node] = node.split('.')[0]
nx.draw_networkx_labels(gr, pos, labels = labels)    

pprint(sw_edges)

#plt.axis('off')
#nx.draw(gr, pos, with_labels=False,node_size=2)   
plt.show()

#
#for items in 
#pprint( data_backbone)

