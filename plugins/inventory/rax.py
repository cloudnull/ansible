#!/usr/bin/env python

# (c) 2013, Jesse Keating <jesse.keating@rackspace.com>
#
# This file is part of Ansible,
#
# Ansible is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Ansible is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Ansible.  If not, see <http://www.gnu.org/licenses/>.

DOCUMENTATION = '''
---
inventory: rax
short_description: Rackspace Public Cloud external inventory script
description:
  >
  Generates inventory that Ansible can understand by making API request to
  Rackspace Public Cloud API
  - |
    >
    When run against a specific host, this script returns the following
    variables:
        rax_os-ext-sts_task_state
        rax_addresses
        rax_links
        rax_image
        rax_os-ext-sts_vm_state
        rax_flavor
        rax_id
        rax_rax-bandwidth_bandwidth
        rax_user_id
        rax_os-dcf_diskconfig
        rax_accessipv4
        rax_accessipv6
        rax_progress
        rax_os-ext-sts_power_state
        rax_metadata
        rax_status
        rax_updated
        rax_hostid
        rax_name
        rax_created
        rax_tenant_id
        rax__loaded

    where some item can have nested structure.
  - credentials are set in a credentials file
version_added: None
options:
  creds_file:
    description:
     - File to find the Rackspace Public Cloud credentials in
    required: true
    default: null
  region_name:
    description:
      - Region name to use in request
    required: false
    default: DFW
author: Jesse Keating
notes:
  - Two environment variables can be set, RAX_CREDS and RAX_REGION.
  - If the RAX_CREDS is not set the default ANSIBLE_CONFIG will be used.
  - Look at rax.ini for an example of the available config file.
  - RAX_CREDS points to a credentials file appropriate for pyrax
  - RAX_REGION defines a Rackspace Public Cloud region (DFW, ORD, LON, ...)
requirements: [ "pyrax" ]
examples:
    - description: List server instances
      code: RAX_CREDS=~/.raxpub RAX_REGION=ORD rax.py --list
    - description: List server instance properties
      code: RAX_CREDS=~/.raxpub RAX_REGION=ORD rax.py --host <HOST_IP>
'''

import argparse
import ConfigParser
try:
    import json
except:
    import simplejson as json
import os
import sys

try:
    import pyrax
except ImportError:
    print('[pyrax] is required for this module')
    sys.exit(1)

# Setup the parser
parser = argparse.ArgumentParser(
    description='List active instances',
    epilog=('List by itself will list all the active instances. Listing a'
            ' specific instance will show all the details about the instance.')
)

parser.add_argument('--list',
                    action='store_true',
                    default=True,
                    help='List active servers')
parser.add_argument('--host',
                    help='List details about the specific host (IP address)')
args = parser.parse_args()


def nova_load_config_file():
    p = ConfigParser.SafeConfigParser()
    path1 = os.environ.get('RAX_CREDS_FILE',
                           os.environ.get('ANSIBLE_CONFIG', "~/rax.ini"))
    path2 = os.getcwd() + "/rax.ini"
    path3 = "/etc/ansible/rax.ini"

    for path in path1, path2, path3:
        if os.path.exists(path):
            p.read(path)
            break
    else:
        return None
    return p, path


# setup the auth
try:
    creds, path = nova_load_config_file()
    if creds.get('rackspace_cloud', 'region') is not None:
        region = creds.get('rackspace_cloud', 'region')
    elif os.environ.get('RAX_REGION'):
        region = os.environ.get('RAX_REGION')
    else:
        sys.exit('No Region was found in your config File "%s" or in an ENV'
                 ' "RAX_REGION".' % path)
except KeyError, e:
    sys.stderr.write('Unable to load %s\n' % e.message)
    sys.exit(1)
else:
    region = region.upper()

try:
    # setting the rax identity per pyrax issue 79
    pyrax.settings.set('identity_type', 'rackspace')
    pyrax.set_credential_file(os.path.expanduser(path),
                              region=region)
except Exception, e:
    sys.stderr.write("%s: %s\n" % (e, e.message))
    sys.exit(1)

# Execute the right stuff
if not args.host:
    groups = {}

    # Cycle on servers
    for server in pyrax.cloudservers.list():
        # Define group (or set to empty string)
        try:
            group = server.metadata['group']
        except KeyError:
            group = 'undefined'

        # Create group if not exist and add the server
        _server = (server.name, server.accessIPv4)
        groups.setdefault(group, []).append('%s: %s' % _server)

    # Return server list
    print(json.dumps(groups, indent=2))
    sys.exit(0)

# Get the deets for the instance asked for
results = {}
# This should be only one, but loop anyway
for server in pyrax.cloudservers.list():
    if server.accessIPv4 == args.host:
        for key in [key for key in vars(server) if
                    key not in ('manager', '_info')]:
            # Extract value
            value = getattr(server, key)
    
            # Generate sanitized key
            results['rax_%s' % key] = value

print(json.dumps(results, indent=2))
sys.exit(0)