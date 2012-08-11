# NotebookCloud: EC2 Functions

# Uses the Python2.7 runtime and depends on /boto
# /main.py does import * all on this file

# Author: Carl Smith, Piousoft
# MailTo: carl.input@gmail.com

import random, hashlib, time, os

from google.appengine.api import urlfetch
from google.appengine.ext.webapp import template

import boto
from boto.ec2.connection import EC2Connection

template_dir = os.path.join(os.path.dirname(__file__), 'templates/')


def valid_keys(access_key, secret_key):
    '''Simply checks the given keys actually work.'''
    
    try: EC2Connection(access_key, secret_key).get_all_instances()       
    except: return False
    return True


def hash_password(password):
    '''This function is derived from passwd in IPython.lib. It hashes a
    password correctly for use with the IPython notebook server.'''
    
    h = hashlib.new('sha1')
    salt = ('%0' + str(12) + 'x') % random.getrandbits(48)
    h.update(password + salt)
    
    return ':'.join(('sha1', salt, h.hexdigest()))


def update_reservation_ids(access_key, secret_key, users_reservations):
    '''This function returns a list of ids for all instances we have launched
    that still exist.'''
    
    connection = EC2Connection(access_key, secret_key)
    
    aws_list = [
        str(res).split(':')[1]
        for res in connection.get_all_instances()
        ]
    
    return [ res for res in aws_list if res in users_reservations ]


def get_instance_list(access_key, secret_key, users_reservations):
    '''This function returns the html for the instance info that is displayed
    by the client in the Your Notebook Servers panel.'''
    
    tab = '&nbsp;&nbsp;&nbsp;&nbsp;' 
    html_output = ''
    refresh = False
    
    connection = EC2Connection(access_key, secret_key)
    
    reservations = [
        res for res in connection.get_all_instances()
        if str(res).split(':')[1] in users_reservations
        ]
        
    instances = [inst for res in reservations for inst in res.instances]

    for inst in instances:
        
        dns_name      = inst.__dict__['public_dns_name']
        state         = inst.__dict__['state']
        instance_type = inst.__dict__['instance_type']
        instance_id   = inst.__dict__['id']
        date, time    = inst.__dict__['launch_time'].split('T')
        
        time=time[:-5]

        transitional = False
        if (state == 'shutting-down' or state == 'pending'
            or state == 'stopping' or state == 'running'
            ): transitional = True
        
        # note: the variable `state` below will be changed to 'serving' if the
        # IPython server is online. nbc has no running state, all running
        # servers are classed as booting or serving
        if state == 'running': state = 'booting'
            
        html_string = (
            '<div class=instance>Instance id: <b>{}</b>Class: <b>{}</b>'
            'Born: <b>{}</b> ~ <b>{}</b><br>{}State: '
            ).format(instance_id + tab, instance_type + tab, time, date, tab)
        
        if dns_name:
            
            try: # check if the instance is actively serving
            
                urlfetch.fetch(
                    'https://'+dns_name+':8888',
                    validate_certificate=False,
                    deadline=25
                    ).content
                                
            except:
            
                state = '<b>'+state+'</b>'
                html_output += html_string + state + '</div>'
                
            else:
            
                html = template_dir + 'serving_buttons.html'
                args = {'instance': instance_id}
                serving_buttons = template.render(html, args)
                
                html_output += (
                    html_string +
                    '<a id="serving" href="https://{}:8888">serving</a>{}</div>'
                    ).format(dns_name, serving_buttons)
                
                # now we know we're running, not booting
                transitional = False

        else:
        
            if state == 'stopped':
            
                state = '<b>stopped</b>'
                html = template_dir + 'stopped_buttons.html'
                args = {'instance': instance_id}
                stopped_buttons = template.render(html, args)
                html_output += html_string + state + stopped_buttons + '</div>'
            
            else:
            
                state = '<b>'+state+'</b>'
                html_output += html_string + state + '</div>'
        
        if transitional: refresh = True
    
    if not html_output:
    
        html_output = (
            '<br>'+tab+'No instances (launched from NotebookCloud) '
            'exist on your AWS account. <br><br>'
            )
    
    return refresh, html_output


def create_vm(access_key, secret_key, user_details, instance_class):
    '''This function actually launches the new vms, one each time it's
    called. It creates a connection to EC2 on that account. It passes the
    password for the notebooks pre-hashed, as well as some random user
    details. It returns the connection object and the reservation object.
    '''

    connection = EC2Connection(access_key, secret_key)

    group_name  = 'notebookcloud_group'
    description = 'NotebookCloud: Default Security Group.'
    
    try: group = connection.create_security_group(group_name, description)
    except: pass
    else: group.authorize('tcp', 8888,8888, '0.0.0.0/0')

    reservation = connection.run_instances(
        'ami-affe51c6',
        instance_type=instance_class,
        security_groups=['notebookcloud_group'],
        user_data=user_details,
        max_count=1
        )
        
    return connection, reservation
    
    
def control_vm(action, instance_list, access_key, secret_key):
    '''Performs action on an existing instance or instances in instance_list.'''
    
    connection = EC2Connection(access_key, secret_key)
    
    if action == 'terminate':
        connection.terminate_instances(instance_ids=instance_list)
    
    elif action == 'stop':
        connection.stop_instances(instance_ids=instance_list)

    elif action == 'start':
        connection.start_instances(instance_ids=instance_list)
        
    elif action == 'reboot':
        connection.reboot_instances(instance_ids=instance_list)
        
    time.sleep(2) # this takes a moment to register
    

