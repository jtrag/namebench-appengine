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
import os
from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp import util
from django.utils import simplejson

import models

MIN_QUERY_COUNT = 75
MIN_SERVER_COUNT = 7
# The minimum amount of time between submissions that we list
MIN_LISTING_DELTA = datetime.timedelta(hours=8)

def list_average(values):
  """Computes the arithmetic mean of a list of numbers."""
  if not values:
    return 0
  return sum(values) / float(len(values))


class SubmitHandler(webapp.RequestHandler):

  """Handler for result submissions."""

  def _duplicate_run_count(self, class_c, dupe_check_id):
    """Check if the user has submitted anything in the last 24 hours."""
    check_ts = datetime.datetime.now() - MIN_LISTING_DELTA
    query = 'SELECT * FROM Submission WHERE class_c=:1 AND dupe_check_id=:2 AND timestamp > :3'
    duplicate_count = 0
    for record in db.GqlQuery(query, class_c, dupe_check_id, check_ts):
      duplicate_count += 1
    return duplicate_count

  def _process_index_submission(self, index_results, ns_sub, index_hosts):
    """Process the index submission for a particular host."""

    for host, req_type, duration, answer_count, ttl, response in index_results:
      results = None

      for record in index_hosts:
        if host == record.record_name and req_type == record.record_type:
          results = models.IndexResult()
          results.submission_nameserver = ns_sub
          results.index_host = record
          results.duration = duration
          results.answer_count = answer_count
          results.ttl = ttl
          results.response = response
          results.put()
          break

      if not results:
        print "Odd, %s did not match." % host

  def post(self):
    """Store the results from a submission. Rather long."""
    notes = []
    dupe_check_id = self.request.get('duplicate_check')
    data = simplejson.loads(self.request.get('data'))
    class_c_tuple = self.request.remote_addr.split('.')[0:3]
    class_c = '.'.join(class_c_tuple)
    if self._duplicate_run_count(class_c, dupe_check_id):
      listed = False
    else:
      listed = True

    if data['config']['query_count'] < MIN_QUERY_COUNT:
      notes.append("Not enough queries to list.")
      listed = False

    if len(data['nameservers']) < MIN_SERVER_COUNT:
      notes.append("Not enough servers to list.")
      listed = False

    cached_index_hosts = []
    for record in db.GqlQuery("SELECT * FROM IndexHost WHERE listed=True"):
      cached_index_hosts.append(record)

    submission = models.Submission()
    submission.dupe_check_id = int(dupe_check_id)
    submission.class_c = class_c
    submission.listed = listed

    if 'geodata' in data:
      if 'latitude' in data['geodata']:
        submission.coordinates = ','.join((str(data['geodata']['latitude']), str(data['geodata']['longitude'])))
        submission.city = data['geodata']['address'].get('city', None)
        submission.region = data['geodata']['address'].get('region', None)
        submission.country = data['geodata']['address'].get('country', None)    
    submission.put()
    
    # Dump configuration for later reference.
    config = models.SubmissionConfig()
    config.submission = submission
    config.query_count = data['config']['query_count']
    config.run_count = data['config']['run_count']
    config.os_system = data['config']['platform'][0]
    config.os_release = data['config']['platform'][1]
    config.python_version = '.'.join(map(str, data['config']['python']))
    config.namebench_version = data['config']['version']
    config.benchmark_thread_count = data['config']['benchmark_thread_count']
    config.health_thread_count = data['config']['health_thread_count']
    config.health_timeout = data['config']['health_timeout']
    config.timeout = data['config']['timeout']
    config.input_source = data['config']['input_source']
    config.put()
    
    reference_latency = None
    for nsdata in data['nameservers']:
      if nsdata['sys_position'] == 0:
        reference_latency = list_average(nsdata['averages'])

    for nsdata in data['nameservers']:
      ns_record = models.NameServer.get_or_insert(nsdata['ip'], ip=nsdata['ip'],
                                                  name=nsdata['name'], hostname=nsdata['hostname'],
                                                  listed=False)
      ns_sub = models.SubmissionNameServer()
      ns_sub.submission = submission
      ns_sub.nameserver = ns_record
      ns_sub.averages = nsdata['averages']
      ns_sub.overall_average = list_average(nsdata['averages'])
      ns_sub.duration_min = nsdata['min']
      ns_sub.duration_max = nsdata['max']
      ns_sub.failed_count = nsdata['failed']
      ns_sub.is_error_prone = nsdata['is_error_prone']
      ns_sub.is_disabled = nsdata['is_disabled']
      ns_sub.nx_count = nsdata['nx']
      ns_sub.sys_position = nsdata['sys_position']
      ns_sub.position = nsdata['position']
      ns_sub.notes = nsdata['notes']
      if ns_sub.sys_position == 0:
        submission.primary_nameserver = ns_record
      elif reference_latency:
        ns_sub.improvement = ((reference_latency / ns_sub.overall_average) - 1) * 100

      ns_sub_instance = ns_sub.put()


      if ns_sub.position == 0:
        submission.best_nameserver = ns_record
        if not ns_sub.sys_position == 0 and ns_sub.improvement:
          submission.best_improvement = ns_sub.improvement

      for idx, run in enumerate(nsdata['durations']):
        run_results = models.RunResult()
        run_results.submission_nameserver = ns_sub
        run_results.run_number = idx
        run_results.durations = list(run)
        run_results.put()

      self._process_index_submission(nsdata['index'], ns_sub_instance, cached_index_hosts)

    # Final update with the primary_nameserver / best_nameserver data.
    submission.put()
    response = {
        'listed': listed,
        'url': '/id/%s' % submission.key().id(),
        'notes': notes
    }
    self.response.out.write(simplejson.dumps(response))
