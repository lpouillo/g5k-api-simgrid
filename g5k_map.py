#!/usr/bin/env python

from pprint import pprint
from geopy import geocoders  
from execo_g5k.api_utils import get_site_attributes, get_g5k_sites, get_resource_attributes, get_site_clusters, get_cluster_attributes
import Image, ImageDraw
import matplotlib as mpl
from mpl_toolkits.basemap import Basemap
from matplotlib.image import pil_to_array 
import matplotlib.pyplot as plt
import numpy as np


mpl.rcParams['font.family'] = 'serif'


attr_sites = {} 
for site in get_g5k_sites():
    attr = get_site_attributes(site)
    attr_sites[site] = {'latitude': attr['latitude'], 'longitude': attr['longitude']}

texts = []
lons_sites = []
lats_sites = []
lons_renater = []
lats_renater = [] 
links_10G = []
links_1G = []
sites_clusters = {}

net_equip = get_resource_attributes('/network_equipments')
gn = geocoders.GeoNames()

for equip in net_equip['items']:
    site = equip['uid'].split('-')[1]
    if site in attr_sites.keys():
        lons_sites.append(attr_sites[site]['longitude'])
        lats_sites.append(attr_sites[site]['latitude'])
        
#        sites_nodes = 0
        sites_clusters[site] = {}
        for cluster in get_site_clusters(site):
            cluster_nodes = get_resource_attributes('sites/'+site+'/clusters/'+cluster+'/nodes')['total']
            sites_clusters[site][cluster] = cluster_nodes 
#            sites_nodes += cluster_nodes
            
#        texts.append ( (attr_sites[site]['longitude'], attr_sites[site]['latitude'], site.title()+' ('+str(sites_nodes)+')' ))
        texts.append ( (attr_sites[site]['longitude'], attr_sites[site]['latitude'], site.title() ))
        for lc in equip['linecards']:
            for p in lc['ports']:
                dest = p['uid'].split('-')[1]
                rate = lc['rate'] if not p.has_key('rate') else p['rate']
                if dest in attr_sites.keys():
                    if rate == 10000000000 :
                        links_10G.append( ( attr_sites[site]['longitude'], attr_sites[site]['latitude'], 
                                        attr_sites[dest]['longitude'], attr_sites[dest]['latitude']) )
                    else:
                        links_1G.append( ( attr_sites[site]['longitude'], attr_sites[site]['latitude'], 
                                        attr_sites[dest]['longitude'], attr_sites[dest]['latitude']) )
                else:
                    attr = gn.geocode(dest+', France', exactly_one=False)[0]
                    if rate == 10000000000:
                        links_10G.append( ( attr_sites[site]['longitude'], attr_sites[site]['latitude'], 
                                        attr[1][1], attr[1][0]) )
                    else:
                        links_1G.append( ( attr_sites[site]['longitude'], attr_sites[site]['latitude'], 
                                        attr[1][1], attr[1][0]) )
                    lons_renater.append( attr[1][1])
                    lats_renater.append( attr[1][0])

plt.figure(figsize = (10, 10))


m = Basemap(projection='merc', llcrnrlat=42, urcrnrlat=51.5,
            llcrnrlon=-5, urcrnrlon=11, lat_ts=20, resolution='i')

pilImage = Image.open('osm_map_bg.png') 
pilImage = pilImage.transpose(Image.FLIP_TOP_BOTTOM)
rgba = pil_to_array(pilImage) 
im = m.imshow(rgba) 

# draw parallels and meridians.
m.drawparallels(np.arange(40.,55.,5.))
m.drawmeridians(np.arange(-5.,9.,5.))

for link in links_10G:
    m.drawgreatcircle(link[0], link[1], link[2], link[3], color='#444444', lw = 1)
for link in links_1G:
    m.drawgreatcircle(link[0], link[1], link[2], link[3], color='#444444', lw = 1, dashes =[1, 0, 0, 1])

x, y = m(lons_sites, lats_sites)
m.scatter(x, y, 20, marker='o', color='r')

x, y = m(lons_renater, lats_renater)
m.scatter(x, y, 15, marker='o', color='b')


for text in texts:
    diff_x = 0.2
    if text[2].split(' ')[0].lower() != 'lyon':
        diff_y = 0.
    else:
        diff_y = 1.0
    x,y = m(text[0]+diff_x, text[1]+diff_y)
    plt.text(x, y, text[2], color = '#222222', backgroundcolor='#eeeeee', fontsize = 14)
    cl_text = ''
    
    for cluster, n_nodes in sites_clusters[text[2].split(' ')[0].lower()].iteritems():
        cl_text += str(n_nodes).ljust(4, ' ')+cluster+' '+'\n'
        diff_y -= 0.2
    x,y = m(text[0]+diff_x, text[1]+diff_y)
    plt.text(x, y, cl_text[:-2], color = '#222222', backgroundcolor='#EEEEEE', fontsize = 8)

plt.savefig('g5k_map.png', dpi = 300, bbox_inches='tight') 

