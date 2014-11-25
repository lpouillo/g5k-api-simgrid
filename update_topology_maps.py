#!/usr/bin/env python
import sys
import json
from wikitools import wiki, page, wikifile
from os import environ, mkdir
from execo import logger
from networkx import is_isomorphic
from networkx.readwrite import json_graph
from execo_g5k.topology import g5k_graph, treemap
from argparse import ArgumentParser
from execo_g5k.api_utils import get_g5k_sites

parser = ArgumentParser(prog=sys.argv[0],
                        description='Update topology maps on the' +
                        ' Grid\'5000 wiki')
parser.add_argument('site', help='Choose the site')
args = parser.parse_args()
site = args.site
if site not in get_g5k_sites():
    logger.error('%s is not a valid G5K site')

_json_dir = environ['HOME'] + '/.execo/topology/'
try:
    mkdir(_json_dir)
except:
    pass

logger.setLevel('WARNING')
g = g5k_graph([site])
logger.setLevel('INFO')
try:
    with open(_json_dir + site + '.json', 'r') as infile:
        old_json = json.load(infile)
    g_old = json_graph.node_link_graph(old_json)
    if is_isomorphic(g, g_old):
        logger.info('No change in graph since last map generation')
        update_needed = False
except:
    logger.info('No old json file')
    update_needed = True
    pass

if update_needed:
    logger.info('Updating wiki image and json cache')
    pagename = site.title() + ' Network Topology'
    text = "This page is generated automatically from the Network API " + \
        "and shows you the topology of [[" + site.title() + ":Network]].\n\n" + \
        "[[File:topo_" + site + ".png|500px|center]]"
    website = wiki.Wiki("http://140.77.13.123/mediawiki/api.php")
    website.login('lolo', password='prout')
    topo = page.Page(website, pagename)
    topo.edit(text=text)
    fig = treemap(g, layout='neato')
    fig.savefig("topo_" + site + ".png")
    upload_file = wikifile.File(website, "topo_" + site + ".png")
    upload_file.upload(open("topo_" + site + ".png"),
                       ignorewarnings=True)
    fresh_json = json_graph.node_link_data(g)
    with open(_json_dir + site + '.json', 'w') as outfile:
        json.dump(fresh_json, outfile)
