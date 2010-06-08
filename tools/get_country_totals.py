#!/usr/bin/python
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

"""Get the total number of submissions per country."""

import code
import getpass
import pygeoip
import sys

base_path = "/usr/local/google_appengine"
sys.path.append(base_path)
sys.path.append('..')
sys.path.append('/Users/tstromberg/namebench-appengine')

sys.path.append(base_path + "/lib/yaml/lib")
sys.path.append(base_path + "/lib/webob")
sys.path.append(base_path + "/lib/django")


from google.appengine.ext.remote_api import remote_api_stub
from google.appengine.ext import db
import models

def auth_func():
    return raw_input('Username:'), getpass.getpass('Password:')

if len(sys.argv) < 2:
    print "Usage: %s app_id [host]" % (sys.argv[0],)
app_id = sys.argv[1]
if len(sys.argv) > 2:
    host = sys.argv[2]
else:
    host = '%s.appspot.com' % app_id

remote_api_stub.ConfigureRemoteDatastore(app_id, '/remote_api', auth_func, host)
print "Gathering totals..."
listed_ips = []
entities = models.Submission.all().fetch(100)
totals = {}
grand_total = 0

while entities:
  for entity in entities:
    grand_total += 1
    if entity.country in totals:
      totals[entity.country] += 1
    else:
      totals[entity.country] = 1
    
  entities = models.Submission.all().filter('__key__ >', entities[-1].key()).fetch(250)

print "-" * 72
for key in totals:
  print "%s\t%s" % (totals[key], key)
print "TOTAL: %s" % grand_total