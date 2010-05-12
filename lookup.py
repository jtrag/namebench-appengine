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

class LookupHandler(webapp.RequestHandler):
  """Handler for /id/### requests."""

  def get(self, id):
    submission = models.Submission.get_by_id(int(id))
    nsdata = models.SubmissionNameServer.all().filter("submission =", submission)
    ns_summary = self._CreateNameServerTable(nsdata)
    if not ns_summary:
      return self.response.out.write("Bummer. ID#%s (%s) has no data." % (id, submission.timestamp))
      
    recommended = [ns_summary[0]]
    reference = None
    
    for row in ns_summary:
      if row['is_reference']:
        reference = row
    
    for record in sorted(ns_summary, key=operator.itemgetter('duration_min')):
      if record['ip'] != recommended[0]['ip']:
        recommended.append(record)
        if len(recommended) == 3:
          break

    template_values = {
      'id': id,
      'index_data': [],     # DISABLED: self._CreateIndexData(nsdata)
      'nsdata': ns_summary,
      'submission': submission,
      'reference': reference,
      'best_nameserver': submission.best_nameserver,
      'best_improvement': submission.best_improvement,
      'config': self._GetConfigTuples(submission),
      'nsdata': self._CreateNameServerTable(nsdata),
      'mean_duration_url': self._CreateMeanDurationUrl(nsdata),
      'min_duration_url': self._CreateMinimumDurationUrl(nsdata),
      'distribution_url_200': self._CreateDistributionUrl(nsdata, 200),
#      'distribution_url': self._CreateDistributionUrl(nsdata, 3000),
      'recommended': recommended,
    }
    path = os.path.join(os.path.dirname(__file__), 'templates', 'lookup.html')
    self.response.out.write(template.render(path, template_values))    
  
  def _GetConfigTuples(self, submission):
    # configuration is only one row, so the for loop is kind of silly here.
    hide_keys = ['submission']
    
    show_config = []
    for configuration in submission.config:
      for key in sorted(models.SubmissionConfig.properties().keys()):
        if key not in hide_keys:
          show_config.append((key, getattr(configuration, key)))
    return show_config

  def _GetSubmissionNameServers(self, submission):
    return models.SubmissionNameServer.all().filter("submission =", submission)

  def _CreateMeanDurationUrl(self, nsdata):
    runs_data = [(x.nameserver.name, x.averages) for x in nsdata if not x.is_disabled]
#    return runs_data
    return charts.PerRunDurationBarGraph(runs_data)

  def _CreateMinimumDurationUrl(self, nsdata):
    fastest_nsdata = [x for x in sorted(nsdata, key=operator.attrgetter('duration_min')) if not x.is_disabled]
    min_data = [(x.nameserver, x.duration_min) for x in fastest_nsdata]
    return charts.MinimumDurationBarGraph(min_data)

  def _CreateDistributionUrl(self, nsdata, scale):
    runs_data = []
    for ns_sub in nsdata:
      results = []
      for run in ns_sub.results:
        results.extend(run.durations)
      runs_data.append((ns_sub.nameserver, results))
    return charts.DistributionLineGraph(runs_data, scale=scale, sort_by=self._SortDistribution)

  def _SortDistribution(self, a, b):
    """Sort distribution graph by name (for now)."""
    return cmp(a[0].name, b[0].name)

  def _CreateIndexData(self, nsdata):
    data = []
  
    for ns_sub in nsdata:
      for result in ns_sub.index_results:
        name = ns_sub.nameserver.name
        if not name:
          name = ns_sub.nameserver.ip
          
        data.append("['%s','%s',%0.3f,%i,'%s']," % (name, result.index_host.record_name,
                                                   result.duration, result.ttl, result.response))
    return ''.join(data)
    
  def _CreateNameServerTable(self, nsdata):
    table = []
    for ns_sub in nsdata:
      table.append({
        'ip': ns_sub.nameserver.ip,
        'name': ns_sub.nameserver.name,
        'is_disabled': ns_sub.is_disabled,
        'is_reference': ns_sub.is_reference,
        'sys_position': ns_sub.sys_position,
        'hostname': ns_sub.nameserver.hostname,
        'diff': ns_sub.diff,
        'check_average': ns_sub.check_average,
        'overall_average': ns_sub.overall_average,
        'duration_min': ns_sub.duration_min,
        'duration_max': ns_sub.duration_max,
        'error_count': ns_sub.error_count,
        'timeout_count': ns_sub.timeout_count,
        'nx_count': ns_sub.nx_count,
        'notes': ns_sub.notes
      })
    return table