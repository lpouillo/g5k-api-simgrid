#!/usr/bin/env ruby

require 'rubygems'
require 'net/ssh/gateway'
require 'rest-client'
require 'json'
require 'optparse'

# PARAMETERS
grid_suffix='.grid5000.fr'       
latency=2.25E-3
node_power=100000
high_link_rate = 1E38

# OPTIONS
options = {}
optparse = OptionParser.new do|opts|
  opts.banner = "Usage: g5k_api_simgrid.rb -u g5k_api_login [-t compact|expanded]"
  opts.on( '-h', '--help', 'Display this screen' ) do
      puts opts
      exit
  end
 
  # Authentification
  opts.on( '-u', '--user login', 'Your login on grid5000 (mandatory)' ) do |login|
    options[:user] = login
  end
 
  # Output
  options[:outfile] = nil
  opts.on( '-o', '--outfile FILE', 'Name of the SimGrid platform file (default is standard output)' ) do |file|
    $stdout = File.new(file, 'w') 
  end
  
  options[:type] = 'compact'
  opts.on( '-t', '--type type', 'expanded (by nodes, default) of compact (by cluster)' ) do |type|
    options[:type] = type
  end
end

begin
  optparse.parse!
  mandatory = [:user]                                         
  missing = mandatory.select{ |param| options[param].nil? }        # 
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

# FUNCTION 


def api_connexion(options)
  # API connection through the gateway  
  access = Net::SSH::Gateway.new('access.grid5000.fr', options[:user])
  port = access.open('api-proxy.sophia.grid5000.fr', 443, 14443) 
  url='https://localhost:'+port.to_s
  return RestClient::Resource.new(url, :user => options[:user])
end

api=api_connexion(options)
all_sites = JSON.parse api['/sid/sites'].get(:accept => 'application/json')

#
def site_to_AS(uid, api, grid_suffix, latency, type='compact')
  clusters=Array.new()
  hosts=Array.new()
  routers=Array.new()
  links=Array.new()
  
  # getting network equipments
  get_site_ne=JSON.parse api['/sid/sites/'+uid+'/network_equipments'].get(:accept => 'application/json')
  get_site_ne['items'].select { |ne| ne.has_key?('linecards')}.each { |ne|
    ne['linecards'].select { |card| card.has_key?('ports')}.each { |card|
        card['ports'].select{|port| port.has_key?('uid') and not port.has_key?('site_uid')}.each {|port|
        
          if (card['kind']!='node')
            routers.push("#{port['uid']}.#{uid}#{grid_suffix}")
          end
          if not links.include?(Hash["dst", "#{ne['uid']}.#{uid}#{grid_suffix}", "src","#{port['uid']}.#{uid}#{grid_suffix}","rate",card['rate']])
            links.push(Hash["src", "#{ne['uid']}.#{uid}#{grid_suffix}", "dst","#{port['uid']}.#{uid}#{grid_suffix}","rate",card['rate']])
          end
        }      
     }
    routers.uniq!
    links.uniq!
    
  }
  # getting nodes
  get_site_clusters=JSON.parse api['/sid/sites/'+uid+'/clusters'].get(:accept => 'application/json')
  get_site_clusters['items'].each  {|cluster|
      if (type=='compact')
         clusters.push(Hash["uid", cluster['uid'], "radical", "0-100", "power","100000", "grid_suffix", grid_suffix])
      else 
        get_cluster_nodes=JSON.parse api['/sid/sites/'+uid+'/clusters/'+cluster['uid']+'/nodes'].get(:accept => 'application/json')
        get_cluster_nodes['items'].sort_by { |e| e['uid'].sub(/^#{cluster['uid']}-/, '').to_i }.each {|node|
          hosts.push("#{node['uid']}.#{uid}#{grid_suffix}")
        }
        get_cluster_ne=JSON.parse api['/sid/sites/'+uid+'/clusters/'+cluster['uid']+'/network_equipments'].get(:accept => 'application/json')
        puts JSON::pretty_generate(get_cluster_ne)
        exit
      end
  }
  # generating XML
  puts  "  <AS id=\"#{uid}#{grid_suffix}\" routing=\"Floyd\">"
  
  if (type=='compact')
    clusters.each {|cluster|
      puts "    <cluster id=\"#{cluster['uid']}\" prefix=\"#{cluster['uid']}-\" grid_suffix=\"#{cluster['grid_suffix']}\" radical=\"#{cluster['radical']}\"  power=\"#{cluster['power']}\"    bw=\"#{cluster['bw']}\"     lat=\"#{cluster['lat']}\"/>"
    }
  else 
    routers.each {|router|  
      puts "    <router id=\"#{router}\"/>"
    }
    hosts.each {|host|  
      puts "    <host id=\"#{host}\" power=\"10000\"/>"
    }
    links.each {|link|
      puts "    <link id=\"#{link['src']}_#{link['dst']}\" bandwidth=\"#{link['rate']}\" latency=\"#{latency}\"/>"
    }
    links.each {|link|
      puts "    <route src=\"#{link['src']}\" dst=\"#{link['dst']}\"><link_ctn id=\"#{link['src']}_#{link['dst']}\"/></route>"
    }
  end
  puts  "  </AS>"
end


# Header
puts "<?xml version=\"1.0\"?>"
puts "<!DOCTYPE platform SYSTEM \"http://simgrid.gforge.inria.fr/simgrid.dtd\">"
puts "<platform version=\"3\">"
puts "<AS id=\"platform\" routing=\"Floyd\">"

# Grid5000
grid_ne = JSON.parse api['/sid/network_equipments'].get(:accept => 'application/json')
routers=Array.new()
links=Array.new()
grid_ne['items'].each {|ne|
  ne['linecards'].select { |card| card.has_key?('ports') and not card['ports'][0].has_key?('site_uid')}.each { |card|
    card['ports'].select{|port| not port.has_key?('site_uid')}.each { |port|
      routers.push("#{port['uid']}#{grid_suffix}")
      if not links.include?(Hash["dst", "#{ne['uid']}#{grid_suffix}", "src","#{port['uid']}#{grid_suffix}","rate",port['rate']])
        links.push(Hash["src", "#{ne['uid']}#{grid_suffix}", "dst","#{port['uid']}#{grid_suffix}","rate",port['rate']])        
      end
      
    }
  }
}
puts  "  <AS id=\"grid5000.fr\" routing=\"Floyd\">"
routers.uniq.each {|router|  
   puts "    <router id=\"#{router}\"/>"
}
links.each {|link|
  puts "    <link id=\"#{link['src']}_#{link['dst']}\" bandwidth=\"#{link['rate']}\" latency=\"#{latency}\"/>"
}
links.each {|link|
  puts "    <route src=\"#{link['src']}\" dst=\"#{link['dst']}\"><link_ctn id=\"#{link['src']}_#{link['dst']}\"/></route>"
}

puts "  </AS>"

# Sites
all_sites = JSON.parse api['/sid/sites'].get(:accept => 'application/json')
all_sites['items'].each do |site|
  site_to_AS(site['uid'],api,grid_suffix,latency,type=options[:type])  
end

# AS Route 
get_grid_ne=JSON.parse api['/sid/network_equipments'].get(:accept => 'application/json')
grid_ne=Hash.new()
get_grid_ne['items'].each do |ne|
  if ne.has_key?('linecards')
    ne['linecards'].each { |card| 
      if card.has_key?('ports')
        card['ports'].each { |port|
          if port.has_key?('uid') and port.has_key?('site_uid')
            grid_ne[ne['uid']]=Hash.new()
            grid_ne[ne['uid']]['src']='grid5000.fr'     
            grid_ne[ne['uid']]['dst']=port['site_uid']            
            if port.has_key?('rate')
              rate=port['rate']
            else 
              rate=high_link_rate
            end
            grid_ne[ne['uid']]['rate']=rate
            if port.has_key?('latency')
              grid_ne[ne['uid']]['latency']=port['latency']  
            else 
              grid_ne[ne['uid']]['latency']=latency
            end
          end
        }
      end
     }
  end
end
grid_ne.each do |uid,ne|
  puts "    <link id=\"#{ne['src']}_#{ne['dst']}#{grid_suffix}\" bandwidth=\"#{ne['rate']}\" latency=\"#{ne['latency']}\"/>"
end
grid_ne.each do |uid,ne|
  puts "    <ASroute src=\"#{ne['src']}\" gw_src=\"#{uid}#{grid_suffix}\" dst=\"#{ne['dst']}#{grid_suffix}\" gw_dst=\"gw.#{ne['dst']}#{grid_suffix}\"><link_ctn id=\"grid5000.fr_#{ne['dst']}#{grid_suffix}\"/></ASroute>"
end


puts "</AS>"
puts "</platform>"