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
import logging
from google.appengine.api import memcache
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

class DummyNameserver(object):
  name = '(Fastest Local Nameserver)'

class CountryHandler(webapp.RequestHandler):
  """Handler for /ns/### requests."""
  

  def get(self, country_code):
    ns_count = {}
    avg_latencies = {}
    ns_data = {
      '__local__': {
        'name': '(Fastest local nameserver)',
        'ip': '__local__',
        'hostname': '__fastest.local__',
        'ns': DummyNameserver(),
        'count': 0,
        'is_global': True,
        'overall_position': -1,
        'positions': [],
        'averages': [],
        'results': []
      }
    }
    
    country = None
    total = 0
    last_timestamp = None
    submissions = self.get_cached_submissions(country_code)
    for sub in submissions:
      if not country:
        country = sub.country
      if not last_timestamp:
        last_timestamp = sub.timestamp
      total += 1

      fastest_local = None
      for ns_sub in sub.nameservers:
        ip = "%s" % ns_sub.nameserver.ip
        if ip not in ns_data:
          ns_data[ip] = {
            'name': ns_sub.nameserver.name,
            'ip': ip,
            'hostname': ns_sub.nameserver.hostname,
            'ns': ns_sub.nameserver,
            'is_global': ns_sub.nameserver.is_global,
            'overall_position': -1
        }
        if not ns_sub.nameserver.is_global and (not fastest_local or ns_sub.overall_average < fastest_local.overall_average):
          fastest_local = ns_sub

        ns_data[ip]['count'] = ns_data[ip].setdefault('count', 0) + 1
        if ns_sub.position < 15:
          ns_data[ip].setdefault('positions', []).append(ns_sub.position)
        ns_data[ip].setdefault('averages', []).append(ns_sub.overall_average)

        for run in ns_sub.results:
          ns_data[ip].setdefault('results', []).extend(run.durations)
      
      if fastest_local:
        ns_sub = fastest_local
        ns_data['__local__']['count'] += 1
        ns_data['__local__'].setdefault('positions', []).append(ns_sub.position)
        ns_data['__local__'].setdefault('averages', []).append(ns_sub.overall_average)
        for run in ns_sub.results:
          ns_data['__local__'].setdefault('results', []).extend(run.durations)
      
      if sub.primary_nameserver:
        if sub.primary_nameserver.name:
          ns_name = sub.primary_nameserver.name
        else:
          ns_name = sub.primary_nameserver.ip
      
      ns_count[ns_name] = ns_count.setdefault(ns_name, 0) + 1

    runs_data = []
    runs_data_global = []
    ns_popular_list = sorted(ns_data.values(), key=lambda x:(x['count']), reverse=True)
    for row in ns_popular_list:
      if 'results' in row:
        if row['ip'] != '__local__' and len(runs_data) < 10:
          runs_data.append((row['ns'], row['results']))
        if row['is_global']:
          runs_data_global.append((row['ns'], row['results']))
      if 'averages' in row:
        row['overall_average'] = CalculateListAverage(row['averages'])
      else:
        row['overall_average'] = -1
      if 'positions' in row:
        row['overall_position'] = CalculateListAverage(row['positions'])
      else:
        row['overall_position'] = -1
  
    template_values = {
      'country_code': country_code,
      'count': total,
      'popular_nameservers': ns_count.items(),
      'nsdata': ns_data.values(),
      'nsdata_raw': ns_data,
      'country': country,
      'submissions': submissions,
      'recent_submissions': submissions[0:15],
      'distribution_url': charts.DistributionLineGraph(runs_data, scale=350, sort_by=self._SortDistribution),
      'distribution_url_global': charts.DistributionLineGraph(runs_data_global, scale=350, sort_by=self._SortDistribution),
      'last_update': last_timestamp
    }
    path = os.path.join(os.path.dirname(__file__), 'templates', 'country.html')
    self.response.out.write(template.render(path, template_values))

  def _SortDistribution(self, a, b):
    """Sort distribution graph by name (for now)."""
    return cmp(a[0].name, b[0].name)
    
  def get_cached_submissions(self, country_code):
    key = "submissions-%s" % country_code
    submissions = memcache.get(key)
    if submissions is not None:
      return submissions

    query = models.Submission.all()
    query.filter("country_code =", country_code)
    query.filter('listed =', True)
    query.order('-timestamp')
    submissions = query.fetch(250)
    if not memcache.add(key, submissions, 7200):
      logging.error("Memcache set failed.")
    return submissions
      

