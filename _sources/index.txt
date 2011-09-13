FluidSurveys Developer Documentation
====================================

.. toctree::
	:maxdepth: 2

Authentication
--------------

The custom authentication feature allows you to integrate FluidSurveys with your external
CMS or websites requiring user login. This is done using the standardized
`OAuth 2.0 protocol`_.

.. _OAuth 2.0 protocol: http://tools.ietf.org/html/draft-ietf-oauth-v2-20

Whenever a request for a survey is made, if custom authentication is enabled, FluidSurveys
will begin the OAuth 2.0 authorization code flow as a client using the current deployment
channel's settings (client ID/secret and authorization/token endpoints). These endpoints
must support transport-layer security (https). Also, to prevent session hijacking, client
authentication should be performed.

OAuth 2.0 Protocol Flow
~~~~~~~~~~~~~~~~~~~~~~~

A survey with custom authentication enabled will first redirect the user-agent (browser)
to the *authorization endpoint* with the following GET parameters:

.. http:get:: (endpoint_uri)/authorization

	:query response_type: will always be set to the value ``code``.
	:query client_id: the OAuth client ID assigned to FluidSurveys (currently ``fluidsurveys``).
	:query redirect_uri: the OAuth callback URI that the user will be redirected to after authenticating.

This page should authenticate the user, and a temporary authorization code associated with
the client ID and redirection URI should be generated.

When the user returns to the `redirect_uri` with an authentication code in the query
parameters, FluidSurveys requests an *access token* from the *token endpoint*. This token
allows OAuth-authenticated method calls for permission checking. The token endpoint must
support both the ``authorization_code`` and ``refresh_token`` grant types. For
session-based authentication, it is easiest to set both the refresh and access tokens to
the user's session identifier. This allows you to expire the tokens easily when the user
is logged out from your system. For more details, see `Section 4.1`_ of the RFC.

.. _Section 4.1: http://tools.ietf.org/html/draft-ietf-oauth-v2-20#section-4.1

.. http:post:: (endpoint_uri)/token

	:form grant_type: one of ``authorization_code`` or ``refresh_token``.
	:form client_id: the OAuth client ID assigned to FluidSurveys (currently ``fluidsurveys``).
	:form redirect_uri: the OAuth callback URI that the user will be redirected to after authenticating.

To check for authorization for a session to a given survey and response, a third OAuth
endpoint is used:

.. http:post:: (endpoint_uri)/callback

	This method should return an ``invalid_grant`` error if there is no user authenticated
	with the access token. If the user is recognized but is denied access to the response,
	this should return an HTTP 404 response instead.

	:form method: currently only ``access_response``.
	:form survey: the identifier of the survey which requires authorization.
	:form response: the key of the response which requires authorization.

There is also a `sample application`_ written in Python using Flask_ which demonstrates
the use of custom authentication.

.. _Flask: http://flask.pocoo.org/
.. _sample application: https://github.com/chideit/fluidsurveys-api-docs/tree/master/examples/custom-auth

REST API
--------

The REST API is accessed through HTTPS with Basic authentication using the user's API key
and password.

.. http:get:: /api/v2/surveys/

	Returns surveys that are accessible to the currently authenticated user. This method
	returns data in :mimetype:`application/json` format.

	Sample response: ::

		{
		  "total": 1,
		  "surveys": [{
		    "id": 17461,
		    "uri": "https://app.fluidsurveys.com/api/v2/surveys/17461/",
		    "deploy_uri": "http://app.fluidsurveys.com/s/test-survey/",
		    "responses": 10,
		    "creator": "username",
		    "name": "survey name"
		  }]
		}

.. http:get:: /api/v2/surveys/(id)/

	Returns details about the specified survey. This method returns data in
	:mimetype:`application/json` format.

	Sample response: ::

		{
		  "id": 17461,
		  "uri": "https://app.fluidsurveys.com/api/v2/surveys/17461/",
		  "deploy_uri": "http://app.fluidsurveys.com/s/test-survey/",
		  "responses": 10,
		  "creator": "username",
		  "name": "survey name",
		  "title": "survey title",
		  "description": "survey description",
		  "variables": {
		    "var1": {
		      "type": "string",
		      "label": "Question 1"
		    }
		  }
		}

.. http:get:: /api/v2/surveys/(id)/responses/

	Returns a list of responses to the specified survey that are accessible to the
	currently authenticated user. Pagination is supported through the `offset` and
	`limit` query parameters. This method returns data in :mimetype:`application/json`
	format.

	:query offset: response pagination offset (defaults to 0).
	:query limit: maximum number of results to return (defaults to 10).

	Sample response: ::

		{
		  "total": 2,
		  "responses": [{
		    "_completed": 0,
		    "_ip_address": "0.0.0.0"
		  }, {
		    "_completed": 1,
		    "_ip_address": "0.0.0.0"
		  }]
		}

.. http:post:: /api/v2/surveys/(id)/responses/

	Creates a new response to the survey specified by ``id``.

.. http:delete:: /api/v2/surveys/(id)/responses/

	Deletes response(s) to the survey specified by ``id``.

	:query response_ids: a "``+``"-separated list of response identifiers to be deleted.

.. http:get:: /api/v2/surveys/(id)/csv/

	Returns details about the specified survey.
