#!/usr/bin/env python
import os, json
import xml.etree.ElementTree as ET
import xml.dom.minidom
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
default_routing = 'Full'
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
                    if not gr.has_edge(src, dst): gr.add_edge(src, dst, bandwith = rate, latency = latency)
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
                        sgr.add_edge(src, dst, bandwith = rate, latency = latency)
                    else:
                        tmp = nx.get_edge_attributes(sgr, 'bandwith')
                        if (src, dst) in tmp.keys():
                            nx.set_edge_attributes(sgr, 'bandwith', {(src, dst): rate+tmp[(src, dst)]})                                
    for cluster, cl_hosts in data_hosts[site].iteritems():
        for host in cl_hosts:
            src = host['uid']+'.'+site
            if not sgr.has_node(src): 
                sgr.add_node(src, kind = 'node', power = host['performance']['core_flops'], core = host['architecture']['smt_size'])        
            for adapt in filter(lambda n: n['enabled'] and not n['management'] and n['interface'] == 'Ethernet', host['network_adapters']):
                dst = adapt['switch']+'.'+site
                if not sgr.has_edge(src, dst): sgr.add_edge(src, dst, bandwith = adapt['rate'], latency = latency)
    site_gr[site] = sgr          
                

# Creating the AS
platform = ET.Element('platform')
main_as = ET.SubElement(platform, 'AS', attrib = {'id': 'grid5000.fr', 'routing': default_routing})    
for site in sites:
    ET.SubElement(main_as, 'AS', attrib = {'id': site+suffix, 'routing': default_routing})
# Creating the backbone links
for element1, element2, attrib in sorted(gr.edges_iter(data=True)):    
    ET.SubElement(main_as, 'link', attrib = {'id': element1+'_'+element2, 
                                              'latency': str(attrib['latency']), 
                                              'bandwith': str(attrib['bandwith'])})
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
                ET.SubElement( asroute, 'link_ctn', attrib = { 'id': path[i]+'_'+path[i+1]} )
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
                                              'bandwith': str(attrib['bandwith']) })
    for n,d in hosts:
        route = ET.SubElement(site_el, 'route', attrib = { 
                        'src': 'gw-'+site+'.'+site+suffix,
                        'dst': n+suffix} )
        path = nx.shortest_path(sgr, 'gw-'+site+'.'+site, n)
        for i in range(len(path)-1):
            ET.SubElement( route, 'link_ctn', attrib = { 'id': path[i]+'_'+path[i+1]} )
# Generating the XML file

platform = xml.dom.minidom.parseString("<?xml version='1.0' encoding='iso-8859-1'?>"+
                                       '<!DOCTYPE platform SYSTEM "http://simgrid.gforge.inria.fr/simgrid.dtd">'+
                                       ET.tostring(platform))
f = open('g5k_platform.xml', 'w')
f.write(  platform.toprettyxml() )
f.close()



#
#
#
#
#
#
#
#
##                    
##for u,d in sorted(gr.nodes_iter(data=True)):
##    print u.ljust(40), d['kind']
##for u,v,d in gr.edges_iter(data=True):
##    print u, v, d['rate']
#
##print nx.shortest_path(gr, 'taurus-1.lyon', 'gw-lyon.lyon')
#
##twopi,  sdfp, acyclic, nop,, dot, sfdp.
#
##fig = plt.figure(figsize = (20,20))
##left, width = 0.01, .98
##bottom, height = 0.01, .94
##right = left + width
##top = bottom + height
##plt.subplots_adjust(left=0.01, bottom=0.01, right=0.99, top=0.95,
##                wspace=0.05, hspace=0.05) 
##ncol = int(sqrt(len(site_gr.keys())))
##
##
##
##i_site = 1
##for site, graph in site_gr.iteritems():
##    
##    tmpgr = graph.copy()
##    for u, d in sorted(tmpgr.nodes_iter(data=True)):
##        if d['kind'] == 'switch':
##            if len(list(set(tmpgr.neighbors(u)) & set([ n for n,d in graph.nodes_iter(data=True) if d['kind']=='node' ]))) == 0:
##                graph.remove_node(u)
##    pos = nx.graphviz_layout(graph, prog = 'twopi')
##       
##    axes = fig.add_subplot(ncol, ncol, i_site, axisbg='#555555')
##    
##    
###    axes.set_title(site, fontdict = {'color': 'white', 'weight': 'bold'}, loc = 'right')
##    axes.get_xaxis().set_ticks([])
##    axes.get_yaxis().set_ticks([])
##    #nx.draw(gr, pos)
##    nx.draw_networkx_nodes(graph, pos, nodelist = [ n for n,d in graph.nodes_iter(data=True) if d['kind']=='renater' ], 
##                           node_color = '#9CF7BC', node_shape = 'v', node_size = 80, label = 'Backbone')
##    nx.draw_networkx_nodes(graph, pos, nodelist = [ n for n,d in graph.nodes_iter(data=True) if d['kind']=='router' ], 
##                           node_color = '#BFDFF2', node_shape = '8', node_size = 200, label = 'Gateway')
##    nx.draw_networkx_nodes(graph, pos, nodelist = [ n for n,d in graph.nodes_iter(data=True) if d['kind']=='switch' ], 
##                           node_color = '#F5C9CD', node_shape = 'd', node_size = 80, label = 'Switchs')
##    nx.draw_networkx_nodes(graph, pos, nodelist = [ n for n,d in graph.nodes_iter(data=True) if d['kind']=='node' ],
##                           node_color = '#F0F7BE', node_shape = 's', node_size = 10, label = 'Nodes')
##    #
##    #
##    nx.draw_networkx_edges(graph, pos, width = 3, edge_color = '#6AA57F', 
##            edgelist = [(u,v) for u,v,d in graph.edges_iter(data=True) if d['rate']== 10000000000 ] )
##    nx.draw_networkx_edges(graph, pos, width = 3, edge_color = '#FF8F8A', 
##            edgelist = [(u,v) for u,v,d in graph.edges_iter(data=True) if d['rate']== 50000000000 ] )
##    nx.draw_networkx_edges(graph, pos, width = 3, edge_color = '#FFFFFF', 
##        edgelist = [(u,v) for u,v,d in graph.edges_iter(data=True) if d['rate']== 30000000000 ] )
##    nx.draw_networkx_edges(graph, pos, width = 3, edge_color = '#FF443C', 
##            edgelist = [(u,v) for u,v,d in graph.edges_iter(data=True) if d['rate']== 3000000000 ] )
##    nx.draw_networkx_edges(graph, pos, width = 2, edge_color = '#5A5AFF', 
##            edgelist = [(u,v) for u,v,d in graph.edges_iter(data=True) if d['rate']== 2000000000 ] )
##    nx.draw_networkx_edges(graph, pos, width = 1, edge_color = '#6590A9', 
##            edgelist = [(u,v) for u,v,d in graph.edges_iter(data=True) if d['rate']== 1000000000 ] )
##    
##    nx.draw_networkx_labels(graph, pos, labels = { n: n.split('.')[0].split('-')[1] for n,d in graph.nodes_iter(data=True) if d['kind']=='renater' },
##                        font_size=12, font_color ='white')
##    sw_labels = {}
##    for n,d in graph.nodes_iter(data=True):
##        if (d['kind']== 'switch' or d['kind'] == 'router') and n.split('.')[0] not in sw_labels.values():
##            sw_labels[n] = n.split('.')[0]
##   
##
##    nx.draw_networkx_labels(graph, pos, labels = sw_labels,
##                        font_size=12, font_color ='white')
##    if i_site == 2:
##        plt.legend(bbox_to_anchor=[0.5, 1.17], 
##               loc='upper center', ncol= 10, prop={'size': 15}, shadow=True)
##    axes.text(right, bottom, site,
##        horizontalalignment='right',
##        verticalalignment='bottom',
##        transform=axes.transAxes,
##        fontdict = {'color': 'white', 'weight': 'bold'})
##    i_site += 1
##
##plt.show()
#
#
#
#lyon_pos = nx.graphviz_layout(site_gr['lyon'], prog = 'neato')
#
#pprint(lyon_pos)
#
#
#fig = plt.figure(figsize = (10,10))
#plt.subplots_adjust(left=0.01, bottom=0.01, right=0.99, top=0.99,
#                wspace=0.05, hspace=0.05)
#ax = fig.add_subplot(111)
#
#allgr = nx.compose_all( [gr]+site_gr.values())                    
#tmpgr = allgr.copy()
#for u, d in sorted(tmpgr.nodes_iter(data=True)):
#    if d['kind'] == 'switch':
#        if len(list(set(tmpgr.neighbors(u)) & set([ n for n,d in allgr.nodes_iter(data=True) if d['kind']=='node' ]))) == 0:
#            allgr.remove_node(u)
##
#pos = {}
#
#attr_sites = {} 
#for site in sites:
#    attr = API.get_site_attributes(site)
#    attr_sites[site] = {'latitude': attr['latitude'], 'longitude': attr['longitude']}
#
#renater_sites = filter(lambda n: 'renater' in n, pos.keys())
##xmin, xmax = min( [el[0] for el in [pos[val] for val in renater_sites] ]), max( [el[0] for el in [pos[val] for val in renater_sites] ])
##ymin, ymax = min( [el[1] for el in [pos[val] for val in renater_sites] ]), max( [el[1] for el in [pos[val] for val in renater_sites] ]) 
##latmin, latmax = min( [el['latitude']  for el in attr_sites.itervalues()]), max( [el['latitude'] for el in attr_sites.itervalues()])
##lonmin, lonmax = min( [el['longitude'] for el in attr_sites.itervalues()]), max( [el['longitude'] for el in attr_sites.itervalues()])
##xmin, xmax, ymin, ymax = 0, 500, 0, 900 
#
##print (lonmax-lonmin)
##site_gr
##print  
##newx = attr_sites['reims']['longitude']*xmax/lonmax
##newy = attr_sites['reims']['latitude']*ymax/latmax
##
##print newx, newy
##newpos = {'renater-'+site: (attr['longitude']*xmax/lonmax, attr['latitude']*ymax/latmax) 
##          for site, attr in attr_sites.iteritems() }
##newpos['renater-paris'] = (2.333*xmax/lonmax, 48.833*ymax/latmax)
##newpos['renater-marseille'] = (5.367*xmax/lonmax, 43.800*ymax/latmax)
##
##pprint(renater_sites)
##pprint(newpos)
##
##pos.update(newpos)
## 
##pprint( lyon_pos['gw-lyon.lyon'] )
##print newpos['renater-lyon']
#
#axes = fig.add_subplot(1, 1, 1, axisbg='#555555')
#
##    axes.set_title(site, fontdict = {'color': 'white', 'weight': 'bold'}, loc = 'right')
#axes.get_xaxis().set_ticks([])
#axes.get_yaxis().set_ticks([])
##nx.draw(gr, pos)
#nx.draw_networkx_nodes(allgr, pos, nodelist = [ n for n,d in allgr.nodes_iter(data=True) if d['kind']=='renater' ], 
#                       node_color = '#9CF7BC', node_shape = 'v', node_size = 80, label = 'Backbone')
#nx.draw_networkx_nodes(allgr, pos, nodelist = [ n for n,d in allgr.nodes_iter(data=True) if d['kind']=='router' ], 
#                       node_color = '#BFDFF2', node_shape = '8', node_size = 200, label = 'Gateway')
###nx.draw_networkx_nodes(allgr, pos, nodelist = [ n for n,d in allgr.nodes_iter(data=True) if d['kind']=='switch' ], 
###                       node_color = '#F5C9CD', node_shape = 'd', node_size = 80, label = 'Switchs')
###nx.draw_networkx_nodes(allgr, pos, nodelist = [ n for n,d in allgr.nodes_iter(data=True) if d['kind']=='node' ],
###                       node_color = '#F0F7BE', node_shape = 's', node_size = 10, label = 'Nodes')
####
####
#
#nx.draw_networkx_edges(allgr, pos, width = 3, edge_color = '#6AA57F', 
#        edgelist = [(u,v) for u,v,d in allgr.edges_iter(data=True) if 'renater' in u and 'renater' in v] )
##nx.draw_networkx_edges(allgr, pos, width = 3, edge_color = '#FF8F8A', 
##        edgelist = [(u,v) for u,v,d in allgr.edges_iter(data=True) if d['rate']== 50000000000 ] )
##nx.draw_networkx_edges(allgr, pos, width = 3, edge_color = '#FFFFFF', 
##        edgelist = [(u,v) for u,v,d in allgr.edges_iter(data=True) if d['rate']== 30000000000 ] )
##nx.draw_networkx_edges(allgr, pos, width = 3, edge_color = '#FF443C', 
##        edgelist = [(u,v) for u,v,d in allgr.edges_iter(data=True) if d['rate']== 3000000000 ] )
##nx.draw_networkx_edges(allgr, pos, width = 2, edge_color = '#5A5AFF', 
##        edgelist = [(u,v) for u,v,d in allgr.edges_iter(data=True) if d['rate']== 2000000000 ] )
##nx.draw_networkx_edges(allgr, pos, width = 1, edge_color = '#6590A9', 
##        edgelist = [(u,v) for u,v,d in allgr.edges_iter(data=True) if d['rate']== 1000000000 ] )
##    
##
#nx.draw_networkx_labels(allgr, pos, labels = { n: n.split('.')[0].split('-')[1] for n,d in allgr.nodes_iter(data=True) if d['kind']=='renater' },
#                    font_size=12, font_color ='white')
#
##sw_labels = {}
##for n,d in allgr.nodes_iter(data=True):
##    if (d['kind']== 'switch' or d['kind'] == 'router') and n.split('.')[0] not in sw_labels.values():
##        sw_labels[n] = n.split('.')[0]
##
##nx.draw_networkx_labels(allgr, pos, labels = sw_labels,
##                    font_size=12, font_color ='white')
#
#plt.savefig('graph_backbone.png')
#
##exit()
#
#
##routers = []
##switchs = []
##hosts = []
##
##
##for site in sites:    
##    site_hosts = data_hosts[site]    
##    for cluster, cl_hosts in site_hosts.iteritems():
##        for host in cl_hosts:
##            hosts.append(host['uid']+'.'+site)        
##            for adapt in filter(lambda n: n['enabled'] and not n['management'] and n['interface'] == 'Ethernet', host['network_adapters']):
##                if adapt['switch']+'.'+site not in gr.nodes():
##                    gr.add_node(adapt['switch']+'.'+site)
##                
##    
##    ne = data_ne[site]
##    for n in ne:
##        if gr.has_node(n['uid']+'.'+site):
##            for lc in filter(lambda lc: lc.has_key('ports'), n['linecards']):        
##                for port in filter(lambda p: p.has_key('uid'), lc['ports']):
##                    if port.has_key('kind'):
##                        kind = port['kind']
##                    else:
##                        kind = lc['kind']
##                if kind in [ 'router', 'node']:
##                    gr.add_edge (n['uid']+'.'+site, port['uid']+'.'+site)
##                if 'renater' in port['uid']:
##                    print
##                    gr.add_edge (n['uid']+'.'+site, port['uid']+'.')
##               
##
##gr.add_nodes_from(hosts, fillcolor='yellow', size=5,shape='square')
##hosts_colors = ['y' for host in hosts]
##hosts_size = [10 for host in hosts]
##pprint( gr.nodes() )
#
##for ne in data_backbone:
##    gr.add_node(ne['uid'])
##    for lc in ne['linecards']:
##        for port in lc['ports']:
##            gr.add_edge( ne['uid'], port['uid']  )
#                
#
#
#
#
##exit()
##
##ne = data_ne[site]
##
##for n in ne:
##    if 'ib' not in n['uid']:
##        gr.add_node(n['uid']+'.'+site)    
##    if n['kind'] == 'router':
##        routers.append(n['uid']+'.'+site)
##    if n['kind'] == 'switch':
##        switchs.append(n['uid']+'.'+site)
##    for lc in filter(lambda lc: lc.has_key('ports'), n['linecards']):        
##        for port in filter(lambda p: p.has_key('uid'), lc['ports']):
##            if port.has_key('kind'):
##                kind = port['kind']
##            else:
##                kind = lc['kind']
##            print kind
##            if kind == 'node' and port['uid'].split('-')[0] in clusters:
##                hosts.append(port['uid']+'.'+site)
##                gr.add_node(port['uid']+'.'+site)
##                gr.add_edge (n['uid']+'.'+site, port['uid']+'.'+site)              
##            if kind not in ['other', 'node']:
##                gr.add_node(port['uid']+'.'+site)
##                gr.add_edge (n['uid']+'.'+site, port['uid']+'.'+site)
##
##for node in switchs:
##    if len( list(set(hosts) & set(gr.neighbors(node))) ) == 0:
##       gr.remove_node(node)  
##
##
##
##                
##
##
###pprint(gr.nodes())
###print gr.neighbors('salome.lyon.grid5000.fr')
#
##pos = nx.graphviz_layout(gr, prog = 'sfdp') 
##nx.draw_networkx_nodes(gr, pos, nodelist = hosts, node_color = hosts_colors, node_shape = 's', node_size = hosts_size)
##
##
##plt.show()
#
##pprint(routers)
##pprint(switchs)
##pprint(edges)
##pprint(sorted(hosts, key = lambda name: (name.split('.',1)[0].split('-')[0], int( name.split('.',1)[0].split('-')[1] ))))
#
#
##exit()
#
#
#
#
#
## Create a Graph of the topology
#logger.info('Generating the graph')
#
#
#
#
#
#
#backbone_nodes = []
#backbone_edges = []
#for ne in data_backbone:
#    gr.add_node(ne['uid'])
#    backbone_nodes.append(ne['uid'])
#    for lc in ne['linecards']:
#        for port in lc['ports']:
#            if gr.has_node( port['uid']) and not gr.has_edge( ne['uid'], port['uid'] ):
#                gr.add_edge( ne['uid'], port['uid']  )
#                backbone_edges.append( ( ne['uid'], port['uid']  ))
#
##for site, cluster_nodes in data_hosts.iteritems():
##    for cluster, nodes in cluster_nodes.iteritems():
##        for node in nodes:
##            gr.add_node(node['uid']+'.'+site)
##            for n in filter(lambda n: n['enabled'] and not n['management'] and not n.has_key('guid') and n.has_key('switch'), node['network_adapters']):
##                if not gr.has_node(n['switch']+'.'+site):
##                    gr.add_node(n['switch']+'.'+site)
##                gr.add_edge(node['uid']+'.'+site, n['switch']+'.'+site)
##
#gw_nodes = []
#gw_edges = []
#sw_nodes = []
#sw_edges = []
#nodes_nodes =[]
#nodes_edges =[]
#for site, ne in data_ne.iteritems():
#    for n in ne:
#        if 'gw' in n['uid']:
#            gw_nodes.append(n['uid']+'.'+site)
#        gr.add_node(n['uid']+'.'+site)
#        for lc in filter(lambda lc: lc.has_key('ports'), n['linecards']):
#            for port in filter(lambda p: p.has_key('uid'), lc['ports']):
#                if not port.has_key('kind'):
#                    kind = lc['kind'] 
#                else:
#                    kind = port['kind']
#                
#                if kind == 'node' and port['uid'].split('-')[0] in clusters:
#                    
#                    nodes_nodes.append(port['uid']+'.'+site)
#                    nodes_edges.append((n['uid']+'.'+site, port['uid']+'.'+site))
#                    gr.add_node(port['uid']+'.'+site)
#                    gr.add_edge(n['uid']+'.'+site, port['uid']+'.'+site)
#                elif kind == 'switch' and 'ib' not in port['uid']:
#                    sw_edges.append((n['uid']+'.'+site, port['uid']+'.'+site))
#                    sw_nodes.append(port['uid']+'.'+site)
#                    gr.add_node(port['uid']+'.'+site)
#                    gr.add_edge(n['uid']+'.'+site, port['uid']+'.'+site)
#                elif kind == 'router':
#                    gr.add_node(port['uid']+'.'+site)
#                    gr.add_edge(n['uid']+'.'+site, port['uid']+'.'+site)
#                elif 'renater' in port['uid']:
#                    gr.add_node(port['uid'])
#                    gr.add_edge(n['uid']+'.'+site, port['uid'])
#                    gw_edges.append((n['uid']+'.'+site, port['uid']))
#                    print (n['uid']+'.'+site, port['uid'])
#
#
#plt.figure( figsize=(15,15) )
#pos = nx.graphviz_layout(gr, prog = 'sfdp')
#print type(pos)
#
#nx.draw_networkx_nodes(gr, pos, nodelist = backbone_nodes, node_shape = 'v', node_size = 50)
#nx.draw_networkx_edges(gr, pos, edgelist = backbone_edges)
#nx.draw_networkx_nodes(gr, pos, nodelist = gw_nodes, node_shape = '8', node_color = 'g', node_size = 150)
#nx.draw_networkx_edges(gr, pos, edgelist = gw_edges)
#nx.draw_networkx_nodes(gr, pos, nodelist = sw_nodes, node_color ='b', node_size = 100)
#nx.draw_networkx_edges(gr, pos, edgelist = sw_edges)
#nx.draw_networkx_nodes(gr, pos, nodelist = nodes_nodes, node_color ='y', node_size = 5)
#nx.draw_networkx_edges(gr, pos, edgelist = nodes_edges)
#
#labels = {}
#for node in gw_nodes:
#    labels[node] = node.split('.')[0]
##for node in nodes_nodes:
##    labels[node] = node.split('.')[0]
#nx.draw_networkx_labels(gr, pos, labels = labels)    
#
#pprint(sw_edges)
#
##plt.axis('off')
##nx.draw(gr, pos, with_labels=False,node_size=2)   
#plt.show()
#
##
##for items in 
##pprint( data_backbone)
#
