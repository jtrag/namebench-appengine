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
    nearest_nameservers = self._GetNearestNameServers(submission)
    recommended = [submission.nameservers[0], nearest_nameservers[0], nearest_nameservers[1]]
    show_config = (
        'namebench_version',
        'python_version',
        'os_system',
        'timeout',
        'health_timeout',
        'health_thread_count',
        'benchmark_thread_count',
        'input_source'
    )
    config = []
    for key in show_config:
      config.append((key, getattr(submission, key)))
    
    template_values = {
      'id': id,
      'config': config,
      'submission': submission,
      'mean_duration_url': self._CreateMeanDurationUrl(submission),
      'min_duration_url': self._CreateMinimumDurationUrl(submission),
      'distribution_url_200': self._CreateDistributionUrl(submission, 200),
      'distribution_url': self._CreateDistributionUrl(submission, 3000),
      'recommended': recommended,
    }
    path = os.path.join(os.path.dirname(__file__), 'templates', 'lookup.html')
    self.response.out.write(template.render(path, template_values))    
  
  def _GetNearestNameServers(self, submission):
    return models.SubmissionNameServer.all().filter("submission =", submission).order("duration_min")

  def _CreateMeanDurationUrl(self, submission):
    runs_data = [(x.nameserver.name, x.averages) for x in submission.nameservers]
    return charts.PerRunDurationBarGraph(runs_data)

  def _CreateMinimumDurationUrl(self, submission):
    fastest_data = [(x.nameserver, x.duration_min) for x in self._GetNearestNameServers(submission)]
    return charts.MinimumDurationBarGraph(fastest_data)

  def _CreateDistributionUrl(self, submission, scale):
    runs_data = []
    for ns_sub in submission.nameservers:
      results = []
      for run in ns_sub.results:
        results.extend(run.durations)
      runs_data.append((ns_sub.nameserver, results))
    return charts.DistributionLineGraph(runs_data, scale=scale, sort_by=self._SortDistribution)

  def _SortDistribution(self, a, b):
    """Sort distribution graph by name (for now)."""
    return cmp(a[0].name, b[0].name)
    