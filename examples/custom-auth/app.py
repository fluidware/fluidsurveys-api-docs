import os
import httplib2

from flask import Flask, request, g, render_template, jsonify, session, redirect, url_for, json, abort
from flaskext.sqlalchemy import SQLAlchemy

from sqlalchemy.orm.collections import attribute_mapped_collection

from werkzeug.contrib.cache import MemcachedCache

from .urls import Href

cache = MemcachedCache(['127.0.0.1:11211'])

app = Flask(__name__)

app.secret_key = 'secret'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'

db = SQLAlchemy(app)

class APIClient(object):
	base_uri = Href('https://subdomain.fluidsurveys.dev/api/v2/')

	http = httplib2.Http()

	http.ca_certs = '/path/to/root-certificates.pem'
	http.add_credentials('email@example.com', 'password')

	def get(self, path, **args):
		resp, content = self.http.request(self.base_uri(path, **args))
		return json.loads(content)

	def post(self, path, **args):
		resp, content = self.http.request(self.base_uri(path, **args), 'POST', body='', headers={'Content-Length': '0'})
		return json.loads(content)

api = APIClient()

class User(db.Model):
	username = db.Column(db.String(64), primary_key=True, nullable=False)
	group = db.Column(db.String(64), nullable=False)

	responses = db.relationship('Response', collection_class=attribute_mapped_collection('survey'))

	def __init__(self, username, group):
		self.username = username
		self.group = group

	def __repr__(self):
		return '<User %s (%s)>' % (self.username, self.group)

class Response(db.Model):
	id = db.Column(db.Integer, primary_key=True)
	survey = db.Column(db.Integer)
	username = db.Column(db.String(64), db.ForeignKey(User.username))
	key = db.Column(db.String(128))

	user = db.relationship(User)

# OAuth 2.0 authorization endpoint
@app.route('/oauth/authorization', methods=['GET', 'POST'])
def oauth_authorization():
	# redirect to the login page if the user is not logged in
	if not get_session().get('user'):
		return redirect(Href(url_for('login'))(next=request.url))

	# otherwise, generate a temporary authorization code
	code = os.urandom(20).encode('hex')

	# find the client id from request
	client_id = request.args['client_id']

	# find the redirect_uri from the request
	redirect_uri = Href(request.args['redirect_uri'])

	# save the code, client id, and redirect uri (along with the session id of the current user)
	cache.set('oauth_code_%s' % code, {
		'client_id': client_id,
		'redirect_uri': redirect_uri,
		'session_id': request.cookies['sessionid']
	}, timeout=60 * 10)

	# redirect with code as a GET parameter
	return redirect(redirect_uri(code=code))

# OAuth 2.0 token endpoint
@app.route('/oauth/token', methods=['POST'])
def oauth_token():
	auth = request.authorization

	# require client authentication using Basic auth
	if not auth:
		response = jsonify({'error': 'invalid_client'})
		response.status_code = 401
		response.headers['WWW-Authenticate'] = 'Basic realm="Login Required"'
		return response

	# we could validate the client_id/secret from the HTTP authentication info here...
	client_id = auth.username

	if request.form.get('grant_type') == 'authorization_code':
		# get the stored authorization code info from the cache
		code = request.form['code']

		info = cache.get('oauth_code_%s' % code)

		# check that the client and redirection uri match
		redirect_uri = request.form.get('redirect_uri')

		if not info or info['client_id'] != client_id or info['redirect_uri'] != redirect_uri:
			return jsonify({'error': 'invalid_grant'})

		# delete the authorization code so that it cannot be reused
		cache.delete('oauth_code_%s' % code)

		# send the token information (token will be the session id)
		return jsonify({
			'access_token': info['session_id'],
			'token_type': 'bearer',
			'expires_in': 60 * 60,
			'refresh_token': info['session_id']
		})

	if request.form.get('grant_type') == 'refresh_token':
		# get the session whose id is the refresh token
		refresh_token = request.form['refresh_token']

		session = get_session(refresh_token)

		# check that the user for this session is still logged in
		if not session.get('user'):
			return jsonify({'error': 'invalid_grant'})

		# generate a new access token and send it to the client
		token = os.urandom(20).encode('hex')

		return jsonify({
			'access_token': token,
			'token_type': 'bearer',
			'expires_in': 60 * 60,
			'refresh_token': refresh_token
		})

	return jsonify({'error': 'invalid_request'})

# OAuth 2.0 callback endpoint
@app.route('/oauth/callback', methods=['POST'])
def oauth_callback():
	auth = request.authorization

	# require client authentication using Basic auth
	if not auth:
		response = jsonify({'error': 'invalid_client'})
		response.status_code = 401
		response.headers['WWW-Authenticate'] = 'Basic realm="Login Required"'
		return response

	# we could validate the client_id/secret from the HTTP authentication info here...
	client_id = auth.username

	# validate access token
	token = request.form.get('access_token')

	if token and request.form.get('method') == 'access_response':
		survey = request.form.get('survey')
		response = request.form.get('response')

		session = get_session(token)

		if not session.get('user'):
			return jsonify({'error': 'invalid_grant'})

		if not Response.query.filter_by(survey=survey, key=response, username=session.get('user')).count():
			abort(404)

		return jsonify({'success': True})

	return jsonify({'error': 'invalid_request'})

def get_session(session_id=None):
	if session_id is None:
		session_id = request.cookies.get('sessionid')

	if session_id:
		return cache.get('session_%s' % session_id) or {}
	else:
		return {}

@app.before_request
def add_user():
	username = get_session().get('user')

	g.user = User.query.get(username) if username else None

@app.route('/', methods=['POST', 'GET'])
def index():
	if g.user and g.user.group == 'ita':
		if request.method == 'POST':
			assessment = int(request.form['assessment'])
			client = request.form['client']

			response = api.post('/surveys/%s/responses/' % assessment)

			link = Response()
			link.survey = assessment
			link.username = client
			link.key = response['key']

			print response

			db.session.add(link)
			db.session.commit()

			return redirect('/')

	surveys = api.get('/surveys/')

	clients = User.query.filter_by(group='client')

	return render_template('index.html', surveys=surveys['surveys'], clients=clients)

@app.route('/auth/login/', methods=['POST', 'GET'])
def login():
	next = request.args.get('next', '/')

	session = get_session()

	if session.get('user'):
		return redirect(next)

	if request.method == 'POST':
		username = request.form['username']
		response = redirect(next)

		session_id = os.urandom(20).encode('hex')
		response.set_cookie('sessionid', session_id)
		cache.set('session_%s' % session_id, {'user': username})

		return response

	return """
	<form method="post" action="">
		<input type="type" name="username" />
		<input type="submit" name="login" value="Log in to external application" />
	</form>
	"""

@app.route('/auth/logout/', methods=['POST', 'GET'])
def logout():
	if request.method == 'POST':
		if 'sessionid' in request.cookies:
			cache.delete('session_%s' % request.cookies['sessionid'])

		return redirect('/')

	return """
	<form method="post" action="">
		<input type="submit" name="logout" value="Log out from external application" />
	</form>
	"""
