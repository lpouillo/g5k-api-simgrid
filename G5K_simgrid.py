#!/usr/bin/env python
import os, json
import xml.etree.ElementTree as ET
from pprint import pprint
from execo import logger
from execo_g5k import api_utils as API
import networkx as nx
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from copy import copy
from math import sqrt
from itertools import product

logger.setLevel('INFO')

suffix = ''
default_routing = 'Floyd'
latency = 2.25E-3

sites = sorted(API.get_g5k_sites())

api_commit = API.get_resource_attributes('')['version']
data_backbone = None
data_hosts = {}
data_ne = {}

log = ''
get_data = False
try:
    os.mkdir('cache')
    logger.info('No cache found, directory created.')
    get_data = True
except:
    pass
    logger.info('Cache directory is present, checking commit version ...')
    
    try:
        f = open('cache/api_commit')
        local_commit = f.readline()
        f.close()
        if local_commit != api_commit:
            log += 'Cache is too old'
            get_data = True
        else:
            log += 'Already at the latest commit'
    except:
        pass
        log += 'No commit version found'
        get_data = True
        
    
logger.info(log)
 
if get_data:
    logger.info('Retrieving data ...')
    n_requests = 2
    
    data_backbone = API.get_resource_attributes('/network_equipments')['items']
    f = open('cache/backbone', 'w') 
    json.dump(data_backbone, f, indent=4)
    f.close()
    data_hosts = {}
    data_ne = {}
    
    for site in sites:
        logger.info(site)
        n_requests += 1
        data_hosts[site] = {}
        for cluster in API.get_site_clusters(site):
            logger.info('* '+cluster)
            n_requests += 1
            data_hosts[site][cluster] = API.get_resource_attributes(
                            'sites/'+site+'/clusters/'+cluster+'/nodes')['items']
            f = open('cache/'+cluster+'_hosts', 'w') 
            json.dump(data_hosts[site][cluster], f, indent=4)
            f.close()
        
        n_requests += 1
        f = open('cache/'+site+'_ne', 'w')
        data_ne[site] = API.get_resource_attributes('sites/'+site+'/network_equipments')['items']
        json.dump(data_ne[site], f, indent=4)
        f.close()
    
    f = open('cache/api_commit', 'w')
    f.write(api_commit)
    f.close()
    logger.info('n_requests = '+str(n_requests))
    
else:
    f_backbone = open('cache/backbone')
    data_backbone = json.load(f_backbone)
    f_backbone.close()    
    
    for site in sites:        
        data_hosts[site] = {}            
        for cluster in API.get_site_clusters(site):
            f_hosts = open('cache/'+cluster+'_hosts')
            data_hosts[site][cluster] = json.load(f_hosts)
            f_hosts.close()
        f_ne = open('cache/'+site+'_ne')
        data_ne[site] = json.load(f_ne)

gr = nx.Graph()
# Adding backbone equipments and links
for ne in data_backbone:
    if 'bordeaux' not in ne['uid']:
        src = ne['uid']
        if not gr.has_node(src): gr.add_node(src, kind = 'renater')    
        for lc in ne['linecards']:        
            for port in lc['ports']:
                kind = 'renater' if not port.has_key('kind') else port['kind'] 
                dst = port['uid'] if not port.has_key('site_uid') else port['uid']+'.'+port['site_uid']
                rate = lc['rate'] if not port.has_key('rate') else port['rate']
                
                if 'bordeaux' not in dst:
                    if not gr.has_node(dst): gr.add_node(dst, kind = kind)
                    if not gr.has_edge(src, dst): gr.add_edge(src, dst, bandwidth = rate, latency = latency)
# Adding sites equipements, links and hosts to the graphs
site_gr = {}
for site in sites:    
    sgr = nx.Graph()
    for ne in data_ne[site]:
        src = ne['uid']+'.'+site
        if not sgr.has_node(src): sgr.add_node(src, kind = ne['kind'])
        for lc in filter(lambda n: n.has_key('ports'), ne['linecards']):
            if not lc.has_key('kind'): 
                lc['kind'] = 'unknown'
            for port in filter(lambda p: p.has_key('uid'), lc['ports']):
                kind = lc['kind'] if not port.has_key('kind') else port['kind']
                dst = port['uid']+'.'+site
                rate = lc['rate'] if not port.has_key('rate') else port['rate'] 
                if kind in ['switch', 'router']:
                    if not sgr.has_node(dst): 
                        sgr.add_node(dst, kind = kind)
                    if not sgr.has_edge(src, dst): 
                        sgr.add_edge(src, dst, bandwidth = rate, latency = latency)
                    else:
                        tmp = nx.get_edge_attributes(sgr, 'bandwidth')
                        if (src, dst) in tmp.keys():
                            nx.set_edge_attributes(sgr, 'bandwidth', {(src, dst): rate+tmp[(src, dst)]})                                
    for cluster, cl_hosts in data_hosts[site].iteritems():
        for host in cl_hosts:
            src = host['uid']+'.'+site
            if not sgr.has_node(src): 
                sgr.add_node(src, kind = 'node', power = host['performance']['core_flops'], core = host['architecture']['smt_size'])        
            for adapt in filter(lambda n: n['enabled'] and not n['management'] and n['interface'] == 'Ethernet', host['network_adapters']):
                dst = adapt['switch']+'.'+site
                if not sgr.has_edge(src, dst): sgr.add_edge(src, dst, bandwidth = adapt['rate'], latency = latency)
    site_gr[site] = sgr          
                

# Creating the AS
platform = ET.Element('platform', attrib = {'version': '3'})
main_as = ET.SubElement(platform, 'AS', attrib = {'id': 'grid5000.fr', 'routing': default_routing})    
for site in sites:
    ET.SubElement(main_as, 'AS', attrib = {'id': site+suffix, 'routing': default_routing})
# Creating the backbone links
for element1, element2, attrib in sorted(gr.edges_iter(data=True)):
    element1, element2 = sorted( [element1, element2 ] )   
    ET.SubElement(main_as, 'link', attrib = {'id': element1+'_'+element2, 
                                              'latency': str(attrib['latency']), 
                                              'bandwidth': str(attrib['bandwidth'])})
# Creating the backbone routes between gateways
gws = [ n for n,d in gr.nodes_iter(data=True) if 'gw' in n ]
for el in product(gws, gws):
    if el[0] != el[1]:
        p = main_as.find("./ASroute/[@gw_src='"+el[1]+"'][@gw_dst='"+el[0]+"']")
        if p is None:
            asroute = ET.SubElement(main_as, 'ASroute', attrib = {
                        'gw_src': el[0]+suffix, 'gw_dst': el[1]+suffix, 
                        'src': el[0].split('.')[0].split('-')[1]+suffix,
                        'dst': el[1].split('.')[0].split('-')[1]+suffix} )
            path = nx.shortest_path(gr, el[0], el[1])
            for i in range(len(path)-1):
                el1, el2 = sorted( [path[i], path[i+1] ] )
                ET.SubElement( asroute, 'link_ctn', attrib = { 'id': el1+'_'+el2} )
# Creating the elements on each site
for site, sgr in site_gr.iteritems():
    site_el = main_as.find("./AS/[@id='"+site+"']")
    # Creating the routers    
    routers = sorted( [ node for node in sgr.nodes_iter(data=True) if node[1]['kind'] == 'router' ])
    for router, attrib in routers:
        ET.SubElement(site_el, 'router', attrib = {'id': router})
    # Creating the hosts
    hosts = sorted( [ node for node in sgr.nodes_iter(data=True) if node[1]['kind'] == 'node' ], 
                  key = lambda node: (node[0].split('.',1)[0].split('-')[0], int( node[0].split('.',1)[0].split('-')[1] )))    
    for n,d in hosts:
        ET.SubElement(site_el, 'host', attrib = { 'id': n, 'power': str(d['power']), 'core': str(d['core'])})
    # Creating the links    
    switchs = sorted( [ node for node in sgr.nodes_iter(data=True) if node[1]['kind'] == 'switch' ])
    for element1, element2, attrib in sgr.edges_iter(data=True):
        element1, element2 = sorted([element1, element2])
        ET.SubElement(site_el, 'link', attrib = {'id': element1+'_'+element2, 
                                              'latency': str(attrib['latency']), 
                                              'bandwidth': str(attrib['bandwidth']) })
    for n,d in hosts:
        route = ET.SubElement(site_el, 'route', attrib = { 
                        'src': 'gw-'+site+'.'+site+suffix,
                        'dst': n+suffix} )
        path = nx.shortest_path(sgr, 'gw-'+site+'.'+site, n)
        for i in range(len(path)-1):
            el1, el2 = sorted( [path[i], path[i+1] ] )
            ET.SubElement( route, 'link_ctn', attrib = { 'id': el1+'_'+el2} )

# Generating the XML file
def indent(elem, level=0):
  i = "\n" + level*"  "
  if len(elem):
    if not elem.text or not elem.text.strip():
      elem.text = i + "  "
    if not elem.tail or not elem.tail.strip():
      elem.tail = i
    for elem in elem:
      indent(elem, level+1)
    if not elem.tail or not elem.tail.strip():
      elem.tail = i
  else:
    if level and (not elem.tail or not elem.tail.strip()):
      elem.tail = i

indent(platform)
tree = ET.ElementTree (platform)
f = open('g5k_platform.xml', 'w')
f.write( '<?xml version=\'1.0\'?>\n<!DOCTYPE platform SYSTEM "http://simgrid.gforge.inria.fr/simgrid.dtd">\n')
tree.write(f)
f.close()

