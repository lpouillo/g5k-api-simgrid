#!/usr/bin/env python

from execo import logger
from execo_g5k import get_g5k_sites
from topo5k import get_topology, get_backbone_graph, get_site_graph
import matplotlib.pyplot as plt
from networkx import graphviz_layout, draw_networkx_nodes, draw_networkx_edges,\
    draw_networkx_labels
#import matplotlib.patches as patches
#from copy import copy
#from math import sqrt
#from itertools import product

logger.setLevel('INFO')
logger.info('Starting')
sites = get_g5k_sites()

backbone, equips, hosts = get_topology()

logger.info('Generating the graph')
gr = get_backbone_graph(backbone)


for site in sites:
    sgr = get_site_graph(site, hosts[site], equips[site])
    gr.add_nodes_from(sgr.nodes_iter(data=True))
    gr.add_edges_from(sgr.edges_iter(data=True))

logger.info('Defining nodes and edges types')
### HACK FOR NANCY AND IB
for node in gr.nodes():
    if 'ib.' in node or 'stalc' in node or 'voltaire' in node or 'ib-' in node\
        or 'summit' in node or 'ipmi' in node or 'CICT' in node or 'mxl2' in node\
        or 'grelon' in node or 'myrinet' in node or 'salome' in node or 'interco' in node:
        gr.remove_node(node)

backbone = [node[0] for node in gr.nodes_iter(data=True)
    if node[1]['kind'] == 'renater']
gw_nodes = [node[0] for node in gr.nodes_iter(data=True)
    if node[1]['kind'] == 'router']
sw_nodes = [node[0] for node in gr.nodes_iter(data=True)
    if node[1]['kind'] == 'switch']
nodes_nodes = [node[0] for node in gr.nodes_iter(data=True)
    if node[1]['kind'] == 'node']

edges_1G = [(edge[0], edge[1]) for edge in gr.edges_iter(data=True)
    if edge[2]['bandwidth'] == 1000000000]
edges_3G = [(edge[0], edge[1]) for edge in gr.edges_iter(data=True)
    if edge[2]['bandwidth'] == 3000000000]
edges_10G = [(edge[0], edge[1]) for edge in gr.edges_iter(data=True)
    if edge[2]['bandwidth'] == 10000000000]
edges_20G = [(edge[0], edge[1]) for edge in gr.edges_iter(data=True)
    if edge[2]['bandwidth'] == 20000000000]
edges_other = [(edge[0], edge[1]) for edge in gr.edges_iter(data=True)
    if edge[2]['bandwidth'] not in [1000000000, 3000000000, 10000000000,
                                    20000000000]]

logger.info('Defining positions')
#pos = graphviz_layout(gr, prog='twopi')
pos = graphviz_layout(gr, prog='neato')

plt.figure(figsize=(15, 15))

logger.info('Drawing nodes')
draw_networkx_nodes(gr, pos, nodelist=backbone,
        node_shape='p', node_color='#9CF7BC', node_size=200)
draw_networkx_nodes(gr, pos, nodelist=gw_nodes,
        node_shape='8', node_color='#BFDFF2', node_size=300,
        labels=gw_nodes)
draw_networkx_nodes(gr, pos, nodelist=sw_nodes,
        node_shape='s', node_color='#F5C9CD', node_size=100)
draw_networkx_nodes(gr, pos, nodelist=nodes_nodes,
        node_shape='o', node_color='#F0F7BE', node_size=10)

logger.info('Drawing labels')
draw_networkx_labels(gr, pos,
    labels={node: node.split('-')[1].title() for node in backbone},
    font_size=16, font_weight='normal')
#draw_networkx_labels(gr, pos,
#    labels={node: node.split('.')[0].split('-')[0] for node in gw_nodes},
#    font_size=14, font_weight='normal')
draw_networkx_labels(gr, pos,
    labels={node: node.split('-')[0] for node in nodes_nodes if '-1.' in node},
    font_size=14, font_weight='normal')


logger.info('Drawing edges')
draw_networkx_edges(gr, pos, edgelist=edges_1G,
        edge_color='#aaaaaa', width=0.1)
draw_networkx_edges(gr, pos, edgelist=edges_3G,
        edge_color='#333333', width=0.3)
draw_networkx_edges(gr, pos, edgelist=edges_10G,
        width=1)

draw_networkx_edges(gr, pos, edgelist=edges_20G, width=2)

draw_networkx_edges(gr, pos, edgelist=edges_other,
        edge_color='r', width=1)

logger.info('Saving figure')
plt.axis('off')
plt.tight_layout()
plt.savefig('test.png', bbox_inches='tight', dpi=300)
