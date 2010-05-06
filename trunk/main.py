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
import lookup
import submit
import tasks

# The minimum amount of time between submissions that we list
MIN_LISTING_DELTA = datetime.timedelta(hours=8)


class MainHandler(webapp.RequestHandler):
  """Handler for / requests"""
  def get(self):
    query = models.Submission.all()
#    query.filter('listed =', True)
    query.order('-timestamp')
    recent_submissions = query.fetch(10)
    template_values = {
      'recent_submissions': recent_submissions
    }  
    path = os.path.join(os.path.dirname(__file__), 'templates', 'index.html')
    self.response.out.write(template.render(path, template_values))
    
    
class IndexHostsHandler(webapp.RequestHandler):
    
  """Handler for /index_requests."""
  def get(self):
    hosts = []
    for record in db.GqlQuery("SELECT * FROM IndexHost WHERE listed=True"):
      hosts.append((str(record.record_type), str(record.record_name)))
    self.response.out.write(simplejson.dumps(hosts))



def main():
  url_mapping = [
      ('/', MainHandler),
      ('/id/(\d+)', lookup.LookupHandler),
      ('/index_hosts', IndexHostsHandler),
      ('/tasks/clear_dupes', tasks.ClearDuplicateIdHandler),
      ('/tasks/load_index_hosts', tasks.ImportIndexHostsHandler),
      ('/submit', submit.SubmitHandler)
  ]
  application = webapp.WSGIApplication(url_mapping,
                                       debug=True)
  util.run_wsgi_app(application)


if __name__ == '__main__':
  main()