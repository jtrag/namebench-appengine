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
    nsdata = self._GetSubmissionNameServers(submission).order("overall_average")
    nsdata_nearest = self._GetSubmissionNameServers(submission).order("duration_min")
    recommended = [nsdata[0]]
    
    # We need to make sure the nearest server is not also the fastest.
    for record in nsdata_nearest:
      if record.key() != recommended[0].key():
        recommended.append(record)
      
      if len(recommended) == 3:
        break

    template_values = {
      'id': id,
      'config': self._GetConfigTuples(submission),
      'nsdata': nsdata,
      'submission': submission,
      'mean_duration_url': self._CreateMeanDurationUrl(nsdata),
      'min_duration_url': self._CreateMinimumDurationUrl(nsdata_nearest),
      'distribution_url_200': self._CreateDistributionUrl(nsdata, 200),
      'distribution_url': self._CreateDistributionUrl(nsdata, 3000),
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
    runs_data = [(x.nameserver.name, x.averages) for x in nsdata]
    return charts.PerRunDurationBarGraph(runs_data)

  def _CreateMinimumDurationUrl(self, nsdata_nearest):
    fastest_data = [(x.nameserver, x.duration_min) for x in nsdata_nearest]
    return charts.MinimumDurationBarGraph(fastest_data)

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
