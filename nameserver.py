#!/usr/bin/env python
#
# Copyright 2010 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
import cgi
import datetime
import operator
import os
from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp import util

from libnamebench import charts

import models


def CalculateListAverage(values):
  """Computes the arithmetic mean of a list of numbers."""
  values = [x for x in values if x != None]
  
  if not values:
    return 0
  return sum(values) / float(len(values))


class LookupHandler(webapp.RequestHandler):
  """Handler for /ns/### requests."""

  def get(self, ip):
    nameserver = models.NameServer.get_by_key_name(ip)
    template_values = {
      'ip': ip,
      'nameserver': nameserver
    }
    path = os.path.join(os.path.dirname(__file__), 'templates', 'nameserver.html')
    self.response.out.write(template.render(path, template_values))
    
class CountryHandler(webapp.RequestHandler):
  """Handler for /ns/### requests."""
  

  def get(self, country_code):
    ns_count = {}
    avg_latencies = {}
    ns_data = {}
    
    country = None
    total = 0
    last_timestamp = None
    
    for sub in models.Submission.all().filter("country_code = ", country_code).filter("listed = ", True).order('timestamp'):
      if not country:
        country = sub.country
      if not last_timestamp:
        last_timestamp = sub.timestamp
      total += 1
      
      for ns_sub in sub.nameservers:
        ip = "%s" % ns_sub.nameserver.ip
        if ip not in ns_data:
          ns_data[ip] = {'name': ns_sub.nameserver.name, 'ip': ip, 'hostname': ns_sub.nameserver.hostname, 'ns': ns_sub.nameserver }
        ns_data[ip]['count'] = ns_data[ip].setdefault('count', 0) + 1
        if ns_sub.position < 15:
          ns_data[ip].setdefault('positions', []).append(ns_sub.position)
        ns_data[ip].setdefault('averages', []).append(ns_sub.overall_average)

        for run in ns_sub.results:
          ns_data[ip].setdefault('results', []).extend(run.durations)
      
      if sub.primary_nameserver:
        if sub.primary_nameserver.name:
          ns_name = sub.primary_nameserver.name
        else:
          ns_name = sub.primary_nameserver.ip
      
      ns_count[ns_name] = ns_count.setdefault(ns_name, 0) + 1

    runs_data = []
    ns_popular_list = sorted(ns_data, key=operator.attrgetter('count'))
    ns_popular_list.reverse()
    for ns in ns_popular_list:
      if len(runs_data) < 10:
        if 'results' in ns_data[ns]:
          runs_data.append((ns_data[ns]['ns'], ns_data[ns]['results']))
      if 'averages' in ns_data[ns]:
        ns_data[ns]['overall_average'] = CalculateListAverage(ns_data[ns]['averages'])
      else:
        ns_data[ns]['overall_average'] = -1
      if 'positions' in ns_data[ns]:
        ns_data[ns]['overall_position'] = CalculateListAverage(ns_data[ns]['positions'])
      else:
        ns_data[ns]['overall_position'] = -1
        
    template_values = {
      'country_code': country_code,
      'count': total,
      'popular_nameservers': ns_count.items(),
      'nsdata': ns_data.values(),
      'country': country,
      'distribution_url_200': charts.DistributionLineGraph(runs_data, scale=350, sort_by=self._SortDistribution),
      'last_update': last_timestamp
    }
    path = os.path.join(os.path.dirname(__file__), 'templates', 'country.html')
    self.response.out.write(template.render(path, template_values))

  def _SortDistribution(self, a, b):
    """Sort distribution graph by name (for now)."""
    return cmp(a[0].name, b[0].name)

