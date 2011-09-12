import urlparse
from werkzeug import urls
from werkzeug.datastructures import MultiDict, ImmutableMultiDict

class Href(bytes):
	def __new__(cls, base):
		return super(cls, Href).__new__(cls, base)

	@property
	def query(self):
		return ImmutableMultiDict(urls.url_decode(urlparse.urlsplit(self).query))

	@property
	def netloc(self):
		return urlparse.urlsplit(self).netloc

	def __call__(self, *path, **query):
		if path and isinstance(path[-1], dict):
			if query:
				raise TypeError('keyword arguments and query-dicts can\'t be combined')
			query, path = path[-1], path[:-1]
		elif query:
			query = dict((k[:-1] if k.endswith('_') else k, v) for k, v in query.items())

		url = urlparse.urlsplit(self)

		path = '/'.join(urls.url_quote(bit) for bit in path if bit).lstrip('/')

		if not url.path.endswith('/'):
			path = '/' + path

		params = urls.url_decode(url.query)
		params.update(query)

		url = url[:2] + (url.path + path, urls.url_encode(params)) + url[4:]

		return type(self)(urlparse.urlunsplit(url))
