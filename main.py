# NotebookCloud: Main App Engine Server

# Uses the Python2.7 runtime and depends on /funcs.py

# Author: Carl Smith, Piousoft
# MailTo: carl.input@gmail.com

import os, random, hashlib

from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext.webapp import template
from google.appengine.ext import db
from google.appengine.api import users

from funcs import *

class BaseHandler(webapp.RequestHandler):

    user = users.get_current_user()
    
    def check_user(self):
    
        if not self.user: return None        
        
        try: return Account.gql('WHERE user = :1', self.user)[0]
        except IndexError: return None


class MainScreen(BaseHandler):
    
    def get(self):

        acc = self.check_user()        
        if acc:

            if not acc.valid:
            
                html = template_dir + 'error.html'
                args = {'error': 'Your account details are invalid.'}
                self.response.out.write(template.render(html, args))
            
            else:
            
                html = template_dir + 'mainscreen.html'
                args = {'username': self.user.email()}
                self.response.out.write(template.render(html, args))

        else: self.redirect('/login')


class InstanceInfo(BaseHandler):
    '''Returns the instance info, as HTML, that the client displays as
    the instance list.'''
    
    def get(self):

        acc = self.check_user()
        if acc:
             
            time.sleep(3) # Takes some time to sync
                
            refresh, html = get_instance_list(
                acc.access_key, acc.secret_key
                )
                
            html += '1' if refresh else '0'

            self.response.out.write(html)

        else: self.redirect('/login')


class ServeDocs(BaseHandler):

    def get(self):
    
        html = template_dir + 'docs.html'
        self.response.out.write(template.render(html, {}))


class ServeForm(BaseHandler):

    def get(self):
        
        user = users.get_current_user()
        if user:

            html = template_dir + 'mainform.html'
            args = {'username': self.user.email()}
            self.response.out.write(template.render(html, args))

        else: self.redirect(users.create_login_url('/login'))        


class LaunchVM(BaseHandler):

    def get(self):

        acc = self.check_user()
        if acc:
        
            iclass = [
                't1.micro', 'm1.small', 'm1.medium', 'm1.large', 'm1.xlarge',
                'm2.xlarge', 'm2.2xlarge', 'm2.4xlarge', 'c1.medium',
                'c1.xlarge', 'cg1.4xlarge', 'cc1.4xlarge', 'cc2.8xlarge'
                ][int(self.request.get('iclass'))]
            
            reservation = str(create_vm(
                acc.access_key, acc.secret_key, acc.user_data, iclass
                )[1]).split(':')[1]
            
            acc.reservations.append(reservation)
            acc.put()
    
        self.redirect('/login')


class ControlVM(BaseHandler):

    def get(self):
        
        acc = self.check_user()
        if acc:
        
            instance_list = [self.request.get('instance')]
            action = self.request.get('action')
            control_vm(action, instance_list, acc.access_key, acc.secret_key)
            self.redirect('/')
            
        else: self.redirect('/login')


class UpdateUserDetails(BaseHandler):

    def post(self):
        
        if not self.user: self.redirect('/login')

        else:
        
            password_0 = self.request.get('pwd0')
            password_1 = self.request.get('pwd1')
            access_key = self.request.get('key0')
            secret_key = self.request.get('key1')
            
            rejection = (
                '<br><br>&nbsp;&nbsp;&nbsp;&nbsp;Your account has '
                '<span class=bolder>not</span> been updated.'
                )
            
            if password_0 != password_1:
            
                path = os.path.join(
                    os.path.dirname(__file__), 'templates/error.html'
                    )
                args = {'error': 'Passwords must match.'+rejection}
                self.response.out.write(template.render(path, args))
            
            elif not valid_keys(access_key, secret_key):
            
                path = os.path.join(
                    os.path.dirname(__file__), 'templates/error.html'
                    )
                args = {'error': 'Invalid AWS keys.'+rejection}
                self.response.out.write(template.render(path, args))
                
            else:
            
                user_data = random.choice(('UK', 'US'))

                for x in range(4):
                    user_data += '|'
                    for y in range(8):
                        user_data += random.choice(
                            'abcdefghijklmnopqrstuvwxyz'
                            )            

                user_data += '|' + hash_password(password_0)
                
                try:
                
                    acc = Account.gql('WHERE user = :1', user)[0]
                
                except:
                
                    acc = Account()
                    acc.user = self.user
                    acc.reservations = []
                
                acc.user_data = user_data
                acc.access_key = access_key
                acc.secret_key = secret_key
                acc.valid = True
                acc.put()
                
                self.redirect('/')


class DeleteUserDetails(BaseHandler):

    def get(self):
    
        acc = self.check_user()
        if acc: acc.delete()      
        
        self.redirect('/login')
            
            
class Login(BaseHandler):

    def get(self):    
    
        acc = self.check_user()
        if acc:
            
            self.redirect('/')
        
        else:
        
            if self.user:
                
                lastline = (
                    'You\'re logged in with your Google Account.'
                    '<br><br><span class=pwd_good>{}</span><br><br>'
                    'You will need to create a NotebookCloud account'
                    ' to continue.<br><br><br>'
                    ).format(self.user.email())
                    
                button = 'Create NotebookCloud Account'
                goto = '/mainform'
            
            else: # if the user isn't logged into to google
            
                lastline = (
                    'You need to sign in with a Google Account. '
                    'Read the docs to learn more.<br><br><br>'
                    )
                    
                button = 'Log In With Google Account'
                goto = '/google_login'
                
            html = template_dir + 'homepage.html'
            args = {'goto': goto, 'lastline': lastline, 'button': button}
            self.response.out.write(template.render(html, args))


class GoogleLogin(BaseHandler):
    '''Just redirects users to Google's login thing.'''
    
    def get(self):
    
        self.redirect(users.create_login_url('/login'))


class Account(db.Model):
    
    user         = db.UserProperty()
    user_data    = db.StringProperty(multiline=False)
    access_key   = db.StringProperty(multiline=False)
    secret_key   = db.StringProperty(multiline=False)
    reservations = db.ListProperty(str)    
    valid        = db.BooleanProperty()


# Map and Serve
routes = [
    ('/login',          Login),
    ('/instance_info',  InstanceInfo),
    ('/google_login',   GoogleLogin),
    ('/control/.*',     ControlVM),
    ('/mainform',       ServeForm),
    ('/docs',           ServeDocs),
    ('/formsubmit',     UpdateUserDetails),
    ('/delete',         DeleteUserDetails),
    ('/launch/.*',      LaunchVM),
    ('/.*',             MainScreen)
    ]
    
run_wsgi_app(webapp.WSGIApplication(routes, debug=True))

