#!/usr/bin/env ruby

require 'pp'
require 'rubygems'
require 'net/ssh/gateway'
require 'rest-client'
require 'json'
require 'socket'
require 'optparse'
require 'graphviz'
 
# OPTIONS
$options = {}
optparse = OptionParser.new do|opts|
  opts.banner = "Usage: draw_g5k_topology.rb [-u g5k_api_login] [-v version] "
  opts.on( '-h', '--help', 'Display this screen' ) do
      puts opts
      exit
  end
  # Authentification
  opts.on( '-u', '--user login', 'Your login on grid5000 (mandatory if outside grid5000)' ) do |login|
    $options[:user] = login
  end
  $options[:identity_file] =  '~/.ssh/id_rsa'
  opts.on( '-i', '--identity_file identity_file', 'The path to your SSH public key required to connect inside Grid5000 (default: ~/.ssh/id_rsa)' ) do |identity_file|
    $options[:identity_file] = identity_file
  end
  # Output
  $options[:outdir] = '.'
  opts.on( '-o', '--outdir DIRECTORY', 'Directory to store the generate files (default: . )' ) do |dir|
    $options[:outdir]  = dir
  end
  # Api version
  $options[:api_version] = 'sid'
  opts.on( '-v', '--version API_VERSION', 'Version of the API to be used' ) do |api|
    $options[:api_version] = api
  end

end

begin
  optparse.parse!
  if not Socket.gethostname.include?('grid5000.fr')
    outside = true
    puts 'Running script from outside grid5000'
    mandatory = [:user]                                         # Enforce the presence of
  end
  missing = mandatory.select{ |param| $options[param].nil? }        # 
  if not missing.empty?                                            #
    puts "Missing options: #{missing.join(', ')}"                  #
    puts optparse                                                  #
    exit                                                           #
  end                                                              #
rescue OptionParser::InvalidOption, OptionParser::MissingArgument      #
  puts $!.to_s                                                           # Friendly output when parsing fails
  puts optparse                                                          #
  exit                                                                   #
end        


# API connection (through the gateway if outside grid5000)

if outside
  access = Net::SSH::Gateway.new('access.grid5000.fr', $options[:user])
  port = access.open('api-proxy.sophia.grid5000.fr', 443, 14443) 
  url = 'https://localhost:'+port.to_s
else
  url = 'https://api.grid5000.fr'
end
$api = RestClient::Resource.new(url, :user => $user)


# Defining the Hash for all data
topology = Hash.new

# Fetching site list
j_sites = JSON.parse $api[$options[:api_version]+'/sites'].get(:accept => 'application/json')
j_sites['items'].each{ |site|
  topology[site['uid']] = Hash.new
}
topology['backbone'] = Hash.new




# Getting equipments and generating global Hash
topology.each_key{ |site|
  puts site
  if site != 'backbone'
    ne_site = JSON.parse $api[$options[:api_version]+'/sites/'+site+'/network_equipments'].get(:accept => 'application/json')
  else
    ne_site = JSON.parse $api[$options[:api_version]+'/network_equipments'].get(:accept => 'application/json')
  end
  ne_site['items'].each{ |ne|
    topology[site][ne['uid']] = { 'kind' => ne['kind'], 'links' => [] }
    if ne.has_key?('linecards')
      ne['linecards'].each { |linecard| 
        if linecard.has_key?('ports')
          linecard['ports'].each{ |port|
            if port.has_key?('uid')
              if not port.has_key?('rate')
                if linecard.has_key?('rate')
                  port['rate'] = linecard['rate']
                else
                  port['rate'] = 0
                end
              end
              if not port.has_key?('kind')
                if linecard.has_key?('kind')
                  port['kind'] = linecard['kind']
                else
                  port['kind'] = 'renater'
                end
              end
              topology[site][ne['uid']]['links'] << {'dest' => port['uid'], 'rate' => port['rate'], 'kind' => port['kind']}
            end
          }
        end
      }
    end
  }
}

# Defining formatting function for nodes and edge
def format_node(graph, node_id, kind)
  if kind == 'virtual' or node_id.include?('renater')
    shape = 'rect'
    fillcolor = '#9CF7BC'
  elsif kind == 'router' or node_id.include?('gw') or node_id.include?('router')
    shape = 'doubleoctagon'
    fillcolor = '#BFDFF2'
  elsif kind == 'switch' or node_id.include?('switch')
    fillcolor = '#F5C9CD'
    shape = 'hexagon'
  elsif kind == 'cluster' or node_id.include?('cluster')
    fillcolor = '#F0F7BE'
    shape = 'diamond'
  else
    fillcolor = 'gray'
    shape = 'ellipse'
  end
  graph.add_nodes(node_id, {:style => "filled", 
                :fillcolor => fillcolor,
                :shape => shape })
  
end

class Array
  def to_ranges
      compact.sort.uniq.inject([]) do |r,x|
           r.empty? || r.last.last.succ != x ? r << (x..x) : r[0..-2] << (r.last.first..x)
      end
  end
end


def format_edge(graph, node_from, node_to, rate, label) 
  if rate == 10000000000
    color = '#9CF7BC'
    penwidth = 3
  elsif rate == 1000000000
    color = '#BFDFF2'
    penwidth = 2
  else
    color = '#F5C9CD'
    penwidth = 1
  end
  if label.class == [].class:
    label = label.uniq.sort.to_ranges.join(',')
  elsif label.class != 'str'.class
    label = ''
  end

  graph.add_edges(node_from, node_to, {:color => color, :penwidth => penwidth, :label => label})
end

# Creating directory to store graphs
if $options[:outdir] != '.'
  if !File.directory?($options[:outdir])
    Dir.mkdir($options[:outdir])
  end
end

# Generating images
topology.each{ |site, topo|
  nodes = {} 
  edges = {}
  g = GraphViz.new( :G, :type => :graph, :ratio => "0.5")  
  
  topo.each{ |equip_from, info| 
    if not nodes.has_key?(equip_from)
      nodes[equip_from]= { 'kind' => info['kind'] }
    end
    
    eq_cluster = {}
    info['links'].each { |link|
      if link['kind'] != 'node':
        if not nodes.has_key?(link['dest'])
          nodes[link['dest']]= { 'kind' => link['kind']}
        end
        if not (edges.has_key?(equip_from+'__'+link['dest']) or edges.has_key?(link['dest']+'__'+equip_from))  
          edges[equip_from+'__'+link['dest']] ={'rate' => link['rate']}
        end
      else
        cluster, radical = link['dest'].split('-')
        if not eq_cluster.has_key?(cluster)
          eq_cluster[cluster] = { 'radicals' => [radical.to_i], 'rate' => link['rate'] }
        elsif not eq_cluster[cluster]['radicals'].include?(radical.to_i)
          eq_cluster[cluster]['radicals'] << radical.to_i
        end
      end
    }
    if not eq_cluster.empty?
      eq_cluster.each { |cluster, params|
        nodes[cluster]= { 'kind' => 'cluster' }
        edges[equip_from+'__'+cluster] = {'rate' => params['rate'], 'label' => params['radicals']}
      }
    end
  }
  
    nodes.each{|node_id,info|
    # HACK TO NOT PRESENT NOT G5K CLUSTERS
    if not node_id.include?('talc') and not node_id.include?('grimage') 
      format_node(g, node_id, info['kind'])  
    end
    
  }
  
  edges.each{|edge_id,info|
    n_from, n_to = edge_id.split('__')
    # HACK TO NOT PRESENT NOT G5K CLUSTERS
    if not edge_id.include?('talc') and not edge_id.include?('grimage')
      format_edge(g, n_from, n_to, rate = info['rate'], label = info['label'])
    end
  
  }
  
  g.output( :png => $options[:outdir]+'/'+site+".png" )
}

