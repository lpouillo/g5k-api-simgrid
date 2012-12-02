#!/usr/bin/env python

import optparse, httplib2, sys, json

_arbitrary_host_power = 10000
_arbitrary_high_link_rate = 1E38
_arbitrary_site_link_latency = 1.0E-4
_arbitrary_backbone_link_latency = 2.25E-3
_arbitrary_renater_uplink_latency = 0.0
_routing_model = "Floyd"

def _get_canonical_link_name(src, dst):
    if src > dst:
        dst, src = src, dst
    return "%s_%s" % (src, dst)

def _dict_add_dict(d, k, added_dict):
    if not d.has_key(k):
        d[k] = added_dict
    else:
        d[k].update(added_dict)

class G5kToSimgridPlatformTranslator:

    def __init__(self, out_file, base_uri, username = None, password = None, headers = None, timeout = 300):
        self.out_file = out_file
        self.base_uri = base_uri.rstrip("/")
        self.headers = {
            'ACCEPT': 'application/json'
            }
        if headers:
            self.headers.update(headers)
        self.http = httplib2.Http(timeout = timeout,
                                  disable_ssl_certificate_validation = True)
        if username and password:
            self.http.add_credentials(username, password)

    def _get(self, relative_uri):
        uri = self.base_uri + "/" + relative_uri.lstrip("/")
        response, content = self.http.request(uri,
                                              headers = self.headers)
        if response['status'] not in ['200', '304']:
            raise Exception, "unable to retrieve %s http response = %s, http content = %s" % (uri, response, content)
        return response, content

    def _site_to_AS(self, uri, naming_suffix, link_latency):
        _, content = self._get(uri)
        site = json.loads(content)
        try:
            _, content = self._get(uri + "/network_equipments")
        except:
            return "" # ignore sites which don't have network_equipments
        equipments = json.loads(content)
        current_as = site['uid'] + naming_suffix
        domain = "." + current_as
        hosts = {}
        links = {}
        for equipment in equipments['items']:
            _dict_add_dict(hosts, equipment['uid'] + domain, { "router": True})
        
    
        
        for equipment in equipments['items']:
            if equipment.has_key('linecards'):
                for card_index, card in enumerate(equipment['linecards']):
                    if card.has_key('ports'):
                        for port in card['ports']:
                            if port.has_key('uid') and not port.has_key('site_uid'):
                                # only local links. if site_uid is present, this is a link going to another AS
                                link_characteristics = {}
                                if port.has_key('rate'):
                                    link_characteristics['rate'] = float(port['rate'])/8
                                else:
                                    link_characteristics['rate'] = _arbitrary_high_link_rate
                                link_characteristics['latency'] = link_latency
                                link_characteristics['src'] = equipment['uid'] + domain
                                link_characteristics['dst'] = port['uid'] + domain
                                _dict_add_dict(hosts, port['uid'] + domain, {})
                                _dict_add_dict(links, _get_canonical_link_name(equipment['uid'] + domain, port['uid'] + domain), link_characteristics)
        try:
            _, content = self._get(uri + "/clusters")
        except:
            content = None # ignore if no clusters / nodes (case for the grid5000 root)
        if content:
            clusters = json.loads(content)
            for cluster in clusters['items']:
                _, content = self._get(uri + "/clusters/" + cluster['uid'] + "/nodes")
                nodes = json.loads(content)
                for node in nodes['items']:
                    _dict_add_dict(hosts, node['uid'] + domain,
                                   { "power": _arbitrary_host_power,
                                     "router": False,
                                     "cluster": cluster['uid']})
        print >>self.out_file, '<AS id="%s" routing="%s">' % (current_as, _routing_model)
        for host in hosts:
            if hosts[host].get("router") == False:
                print >>self.out_file, '<host id="%s" power="%s"/>' % (host, hosts[host].get("power"))
            else:
                print >>self.out_file, '<router id="%s"/>' % (host,)
        for link in links:
            print >>self.out_file, '<link id="%s" bandwidth="%s" latency="%s"/>' % (link, links[link]['rate'], links[link]['latency'])
        for link in links:
            print >>self.out_file, '<route src="%s" dst="%s"><link_ctn id="%s"/></route>' % (links[link]['src'], links[link]['dst'], link)
        print >>self.out_file, '</AS>'

    def translate(self):
        print >>self.out_file, '<?xml version="1.0"?>'
        print >>self.out_file, '<!DOCTYPE platform SYSTEM "http://simgrid.gforge.inria.fr/simgrid.dtd">'
        print >>self.out_file, '<platform version="3">'
        print >>self.out_file, '<AS id="platform" routing="%s">' % (_routing_model,)
        self._site_to_AS("", ".fr", _arbitrary_backbone_link_latency)
        _, content = self._get("/sites")
        sites = json.loads(content)
        for site in sites['items']:
            self._site_to_AS("sites/%s" % (site['uid']), ".grid5000.fr", _arbitrary_site_link_latency)
        _, content = self._get("/network_equipments")
        equipments = json.loads(content)
        as_links = {}
        for equipment in equipments['items']:
            if equipment.has_key('linecards'):
                for card_index, card in enumerate(equipment['linecards']):
                    if card.has_key('ports'):
                        for port in card['ports']:
                            if port.has_key('uid') and port.has_key('site_uid'):
                                # only AS to AS links have site_uid
                                link_characteristics = {}
                                if port.has_key('rate'):
                                    link_characteristics['rate'] = float(port['rate'])/8
                                else:
                                    link_characteristics['rate'] = _arbitrary_high_link_rate
                                    # if we don't know the rate, set an arbirary high (infinite) rate
                                link_characteristics['src'] = "grid5000.fr"
                                link_characteristics['gw_src'] = equipment['uid'] + ".grid5000.fr"
                                link_characteristics['dst'] = port['site_uid'] + ".grid5000.fr"
                                link_characteristics['gw_dst'] = port['uid'] + "." + port['site_uid'] + ".grid5000.fr"
                                _dict_add_dict(as_links, _get_canonical_link_name("grid5000.fr", port['site_uid'] + ".grid5000.fr"), link_characteristics)
        for as_link in as_links:
            print >>self.out_file, '<link id="%s" bandwidth="%s" latency="%s"/>' % (as_link, as_links[as_link]['rate'], _arbitrary_renater_uplink_latency)
            # currently, set an arbitrary latency
        for as_link in as_links:
            print >>self.out_file, '<ASroute src="%s" gw_src="%s" dst="%s" gw_dst="%s"><link_ctn id="%s"/></ASroute>' % (as_links[as_link]['src'],
                                                                                                         as_links[as_link]['gw_src'],
                                                                                                         as_links[as_link]['dst'],
                                                                                                         as_links[as_link]['gw_dst'],
                                                                                                         as_link)
        print >>self.out_file, '</AS>'
        print >>self.out_file, '</platform>'

if __name__ == '__main__':
    parser = optparse.OptionParser()
    parser.add_option("-u",
                      dest = "username",
                      default = None,
                      help = "Grid5000 API authentication username. Default = %default")
    parser.add_option("-p",
                      dest = "prompt_password",
                      action = "store_true",
                      default = False,
                      help = "prompt for Grid5000 API authentication password. Default = %default")
    parser.add_option("--uri",
                      dest = "uri",
                      default = "https://api.grid5000.fr/sid",
                      help = "grid5000 API URI. Default = %default")
    parser.add_option("--branch",
                      dest = "branch",
                      default = "master",
                      help = "Grid5000 API default branch to use. Default = %default")
    (options, args) = parser.parse_args()
    password = None
    if options.prompt_password:
        import getpass
        password = getpass.getpass("Grid5000 API authentication password")
    if options.username:
        try:
            import keyring
            if password:
                keyring.set_password("grid5000_api", options.username, password)
            else:
                password = keyring.get_password("grid5000_api", options.username)
        except:
            # only use keyring if available
            pass
    headers = {}
    if options.branch:
        headers = {
            'X-Api-Reference-Branch': options.branch,
            }
    translator = G5kToSimgridPlatformTranslator(sys.stdout,
                                                options.uri,
                                                username = options.username,
                                                password = password,
                                                headers = headers)
    translator.translate()
