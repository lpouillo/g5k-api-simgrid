#!/usr/bin/env python


from pprint import pprint
from execo import logger
from execo_g5k import get_g5k_sites
from itertools import product
from topo5k import get_topology, get_backbone_graph, get_site_graph
from networkx import shortest_path
from xml.dom import minidom
from xml.etree.ElementTree import Element, SubElement, tostring, parse

def prettify(elem):
    """Return a pretty-printed XML string for the Element.  """
    rough_string = tostring(elem, 'utf-8')
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ").replace('<?xml version="1.0" ?>\n', '')

logger.setLevel('INFO')

suffix = ''
default_routing = 'Floyd'
latency = 2.25E-3

sites = get_g5k_sites()

backbone, equips, hosts = get_topology()

gr = get_backbone_graph(backbone)
site_gr = {}
for site in sites:
    site_gr[site] = get_site_graph(site, hosts[site], equips[site])

# Creating the AS
platform = Element('platform', attrib = {'version': '3'})
main_as = SubElement(platform, 'AS', attrib = {'id': 'grid5000.fr', 'routing': default_routing})    
for site in sites:
    SubElement(main_as, 'AS', attrib = {'id': site+suffix, 'routing': default_routing})
# Creating the backbone links
for element1, element2, attrib in sorted(gr.edges_iter(data=True)):
    element1, element2 = sorted( [element1, element2 ] )   
    SubElement(main_as, 'link', attrib = {'id': element1+'_'+element2, 
                                              'latency': str(attrib['latency']), 
                                              'bandwidth': str(attrib['bandwidth'])})
# Creating the backbone routes between gateways
gws = [ n for n,d in gr.nodes_iter(data=True) if 'gw' in n ]
for el in product(gws, gws):
    if el[0] != el[1]:
        p = main_as.find("./ASroute/[@gw_src='"+el[1]+"'][@gw_dst='"+el[0]+"']")
        if p is None:
            asroute = SubElement(main_as, 'ASroute', attrib = {
                        'gw_src': el[0]+suffix, 'gw_dst': el[1]+suffix, 
                        'src': el[0].split('.')[0].split('-')[1]+suffix,
                        'dst': el[1].split('.')[0].split('-')[1]+suffix} )
            path = shortest_path(gr, el[0], el[1])
            for i in range(len(path)-1):
                el1, el2 = sorted( [path[i], path[i+1] ] )
                SubElement( asroute, 'link_ctn', attrib = { 'id': el1+'_'+el2} )
# Creating the elements on each site
for site, sgr in site_gr.iteritems():
    site_el = main_as.find("./AS/[@id='"+site+"']")
    # Creating the routers
    for node in sgr.nodes_iter(data=True):
        if 'kind' not in node[1]:
            print node[0]
            exit()
    routers = sorted( [ node for node in sgr.nodes_iter(data=True) if node[1]['kind'] == 'router' ])
    for router, attrib in routers:
        SubElement(site_el, 'router', attrib = {'id': router})
    # Creating the hosts
    hosts = sorted( [ node for node in sgr.nodes_iter(data=True) if node[1]['kind'] == 'node' ], 
                  key = lambda node: (node[0].split('.',1)[0].split('-')[0], int( node[0].split('.',1)[0].split('-')[1] )))    
    for n,d in hosts:
        SubElement(site_el, 'host', attrib = { 'id': n, 'power': str(d['power']), 'core': str(d['core'])})
    # Creating the links    
    switchs = sorted( [ node for node in sgr.nodes_iter(data=True) if node[1]['kind'] == 'switch' ])
    for element1, element2, attrib in sgr.edges_iter(data=True):
        element1, element2 = sorted([element1, element2])
        SubElement(site_el, 'link', attrib = {'id': element1+'_'+element2, 
                                              'latency': str(attrib['latency']), 
                                              'bandwidth': str(attrib['bandwidth']) })
    for n,d in hosts:
        route = SubElement(site_el, 'route', attrib = { 
                        'src': 'gw-'+site+'.'+site+suffix,
                        'dst': n+suffix} )
        path = shortest_path(sgr, 'gw-'+site+'.'+site, n)
        for i in range(len(path)-1):
            el1, el2 = sorted( [path[i], path[i+1] ] )
            SubElement( route, 'link_ctn', attrib = { 'id': el1+'_'+el2} )


f = open('g5k_platform.xml', 'w')
f.write( '<?xml version=\'1.0\'?>\n<!DOCTYPE platform SYSTEM "http://simgrid.gforge.inria.fr/simgrid.dtd">\n'+
         prettify(platform))
f.close()
