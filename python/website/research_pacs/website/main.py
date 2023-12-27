# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import base64
import json
import logging
import re
import sys
from datetime import datetime
from functools import wraps
from io import BytesIO

import boto3
import flask
from flask import request, g
from waitress import serve
from werkzeug.exceptions import HTTPException
from werkzeug.serving import WSGIRequestHandler
#from werkzeug.urls import url_encode
from werkzeug._internal import _url_encode as url_encode

import research_pacs.shared.dicom_json as rpacs_dicom_json
import research_pacs.shared.util as rpacs_util
from research_pacs.shared.database import DB, DBDicomJson, DBExportTasks
from research_pacs.shared.orthanc import OrthancClient
from research_pacs.website.env import get_env
from research_pacs.website.log import AccessLogger
from research_pacs.website.permission import PermissionsManager, PermissionError

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

# Don't display waitress logs
logger_waitress = logging.getLogger('waitress.queue')
logger_waitress.disabled = True

app = flask.Flask(__name__)
env = None
client = None


def main():
  logger.info('Starting website')
  
  try:
    global env
    env = get_env()

    # Create the clients
    global client
    client = rpacs_util.ClientList()
    client.add('access_logger', AccessLogger(env.access_log_file, env.log_excluded_prefixes, env.log_excluded_suffixes))
    client.add('orthanc', OrthancClient(env.orthanc_host, env.orthanc_user, env.orthanc_pwd))
    client.add('permissions', PermissionsManager(env.permissions_file, env.region))

  # Exit if any of the previous steps failed
  except Exception as e:
    logger.fatal(f'Failed to initialize the program - {e}')
    sys.exit(1)

  # Enable HTTP/1.1 and run the Flask application with Waitress
  WSGIRequestHandler.protocol_version = "HTTP/1.1"
  serve(app, host='0.0.0.0', port=8080, threads=4, _quiet=True)

  # Before the program exits
  logger.info('Stopping website')


def login_required(f):
  """
  Retrieve the user name and the user groups from the JWT tokens passed by the Application Load 
  Balancer via HTTP headers. The user name will be available in `g.user` and the groups in 
  `g.groups`. The request is aborted is no user name is found.
  
  """
  @wraps(f)
  def wrapper(*args, **kwargs):
    g.user = None
    g.groups = []
    
    # Parse the ID Token and Access Token to find the user name and groups
    for header in ('X-Amzn-Oidc-Data', 'X-Amzn-Oidc-Accesstoken'):
      if header in request.headers:
        encoded_payload = request.headers[header].split('.')[1]
        # Add a padding that may be missing in the JWT value
        encoded_payload_padding = encoded_payload + "====="
        decoded_payload = base64.b64decode(encoded_payload_padding).decode('utf-8')
        payload = json.loads(decoded_payload)
        if env.claim_user in payload:
          g.user = payload[env.claim_user]
        if env.claim_groups in payload:
          g.groups = payload[env.claim_groups]
          
    # Execute the wrapper function unless no user name was found
    assert g.user != None, 'No user name'
    return f(*args, **kwargs)
    
  return wrapper


@app.before_request
def before_request_func():
  """Log the request for debugging purposes"""
  logger.debug(f'Received a {request.method} request to {request.path}')


@app.after_request
def after_request_func(response):
  """Log the HTTP request and response in the access log file"""
  logger.debug(f'Sent the response - StatusCode={response.status_code}')
  client.access_logger.log_http_request(response)
  if g.get('db') != None:
    g.db.close()
  return response
  
  
@app.errorhandler(Exception)
def errorhandler_func(e):
  # Exception raised when the user as no profiles associated
  if isinstance(e, PermissionError):
    return flask.render_template('error.html', error_message="You don't have profiles associated to your user or your groups. Please check with your administrator."), 401
  # Flask exceptions
  elif isinstance(e, HTTPException):
    if e.code == 401:
      return flask.render_template('error.html', error_message='You are not authorized to view this page, or this page does not exist.'), 401
    else:
      logger.warning(f'Failed to process the request - Path={request.path} ResponseCode={e.code}')
      return flask.render_template('error.html', error_message=f'Something went wrong. Error code: {e.code}'), e.code
  # Other exceptions
  else:
    logger.error(f'Failed to process the request - Path={request.path} Error={e}')
    return flask.render_template('error.html', error_message='Something went wrong.'), 500

  
@app.route('/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE'])
@login_required
def proxy_orthanc_func(*args, **kwargs):
  """By default, forward the request to the Orthanc server"""
  
  # Abort if the user is not authorized to view this page
  if not client.permissions.is_orthanc_request_allowed(request.method, request.path):
    flask.abort(401)
  
  # Forward the request and its content to the Orthanc server
  response = client.orthanc._request(
    method=request.method,
    full_path=request.full_path[1:],
    raise_error=False,
    headers={key: value for (key, value) in request.headers if key != 'Host'},
    data=request.get_data(),
    cookies=request.cookies,
    allow_redirects=False
  )

  # Reconstruct the original host URL as requested by the user
  initial_host_url = request.host_url[:-1]
  if 'X-Forwarded-Proto' in request.headers:
    initial_scheme = request.headers['X-Forwarded-Proto'].lower()
    initial_host_url.replace(request.scheme, initial_scheme)
  
  # Exclude the following headers from the Orthanc response, because they should be forwarded to 
  # the original user
  excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection', 'keep-alive']
  headers = [
    (name, value) if (name.lower() != 'location') 
    else (name, value.replace(client.orthanc._host, initial_host_url)) 
    for (name, value) in response.raw.headers.items() if name.lower() not in excluded_headers
  ]

  # Return the Orthanc response to the user
  return flask.Response(response.content, response.status_code, headers)

  
@app.route('/healthcheck')
def healthcheck_page():
  """Respond to the heartbeat request from the Application Load Balancer"""
  return flask.render_template('healthcheck.html')


@app.route('/', methods=['GET'])
@login_required
def home_page():
  """Home page"""
  orthanc_access = client.permissions.has_access_to_orthanc()
  return flask.render_template('home.html', user_guide_url=env.user_guide_url, orthanc_access=orthanc_access)


@app.route('/aws/logout')
def logout_page():
  """Logout page. Expire the ALB Authentication cookies and redirect to the Cognito logout page"""
  response = flask.make_response(flask.redirect(env.sign_out_url))
  response.set_cookie('AWSELBAuthSessionCookie-0', '', expires=0)
  response.set_cookie('AWSELBAuthSessionCookie-1', '', expires=0)
  response.set_cookie('AWSELBAuthSessionCookie-2', '', expires=0)
  response.set_cookie('AWSELBAuthSessionCookie-3', '', expires=0)
  return response
  

@app.route('/aws/me')
@login_required
def me_page():
  """Page My Permissons"""
  profiles = client.permissions.get_profiles_description()
  return flask.render_template('me.html', profiles=profiles)


def can_access_instance_or_series(f):
  """Check if the current user is allowed to access the DICOM instance or series"""
  
  @wraps(f)
  def wrapper(*args, **kwargs):
    # Generate a JSONPath query that corresponds to the current user's instance access 
    # permissions. If `jsonpath_query` is not empty, the current user does not have full 
    # access to all DICOM instances, so we check if the user is authorized to access this 
    # instance
    jsonpath_query = client.permissions.get_jsonpath_query('')
    if jsonpath_query == '':
      return f(*args, **kwargs)
    else:
      g.db = DB(env.pg_host, env.pg_port, env.pg_user, env.pg_pwd, env.pg_db)
      db_dicom_json = DBDicomJson(g.db)
      if 'instance_id' in kwargs and db_dicom_json.has_access_to_instance(jsonpath_query, kwargs['instance_id']):
        return f(*args, **kwargs)
      if 'series_id' in kwargs and db_dicom_json.has_access_to_series(jsonpath_query, kwargs['series_id']):
        return f(*args, **kwargs)
    # Abort if the current user is not authorized to access this instance or series
    flask.abort(401)
    
  return wrapper

  
@app.route('/aws/instances/<instance_id>/preview')
@login_required
@can_access_instance_or_series
def preview_instance_page(instance_id):
  """Page Preview a DICOM Instance"""
  nb_frames = client.orthanc.count_instance_frames(instance_id)
  return flask.render_template('preview.html', instance_id=instance_id, nb_frames_to_show=min(10,nb_frames), nb_frames_total=nb_frames)


@app.route('/aws/instances/<instance_id>/frames/<int:frame>/preview')
@login_required
@can_access_instance_or_series
def preview_instance_func(instance_id, frame):
  """Preview the frame of a DICOM Instance"""
  img_bytes = client.orthanc.download_instance_frame(instance_id, frame=frame)
  return flask.send_file(BytesIO(img_bytes), mimetype='image/png')
  
  
@app.route('/aws/instances/<instance_id>/download')
@login_required
@can_access_instance_or_series
def download_instance_func(instance_id):
  """Download a DICOM Instance as DCM"""
  file_bytes = client.orthanc.download_instance_dicom(instance_id)
  return flask.send_file(BytesIO(file_bytes), mimetype='application/dicom', as_attachment=True, attachment_filename=f'{instance_id}.dcm')
  
  
@app.route('/aws/series/<series_id>/download')
@login_required
@can_access_instance_or_series
def download_series_func(series_id):
  """Download a DICOM Series as ZIP"""
  file_bytes = client.orthanc.download_series_zip(series_id)
  return flask.send_file(BytesIO(file_bytes), mimetype='application/zip', as_attachment=True, attachment_filename=f'{series_id}.zip')


@app.route('/aws/search')
@login_required
def search_page():
  """Page Search DICOM Instances"""
  
  def get_unique_series_ids(instances):
    """Retrieve the list of series ID related to the instances"""
    result = []
    for instance in instances:
      series_id = instance[1]
      if not series_id in result:
        result.append(series_id)
    return result
  
  # Retrieve the parameters from the query string
  query = request.args.get('query', default='')
  display_action = 'display' in request.args
  export_action = 'export' in request.args
  offset = int(request.args.get('offset', default=0))
  
  # Display the page with no results if the form was not submitted
  if display_action is False and export_action is False:
    return flask.render_template('search.html')
  
  # Translate the query and the user's instance access permissions into a JSON Path query
  try:
    jsonpath_query = client.permissions.get_jsonpath_query(query)
    logger.debug(f'Search - JSON Path Query: {jsonpath_query}')
  except ValueError:
    return flask.render_template('search.html', error_message='Your query is invalid.')
  
  g.db = DB(env.pg_host, env.pg_port, env.pg_user, env.pg_pwd, env.pg_db)
  db_dicom_json = DBDicomJson(g.db)
    
  # If the "Display" button was pressed
  if display_action is True:
    
    def generate_header(header_keywords, dicom_json):
      """Generate the accodion headers"""
      lines = []
      for keyword in header_keywords.split(','):
        value = rpacs_dicom_json.get_top_level_elem_value_from_dict(dicom_json, keyword)
        lines.append(f'{keyword}: <strong>{value}</strong>')
      return '<br>'.join(lines)
    
    def rewrite_full_path_new_offset(new_offset):
      args = request.args.copy()
      args['offset'] = new_offset
      return f'{request.path}?{url_encode(args)}'
    
    # Retrieve the number of instances and series that match the query, and associated details 
    # for up to `env.results_per_page` from the offset `offset`
    try:
      total_instances, total_series = db_dicom_json.count_instances(jsonpath_query)
      instances_in_page = db_dicom_json.search_instances_with_series(jsonpath_query, limit=env.results_per_page, offset=offset)
      series_ids_in_page = get_unique_series_ids(instances_in_page)
    except:
      logger.warning(f'Page {request.path} - Query: {query}')
      return flask.render_template('search.html', error_message='Failed to query the database. Please check your query and retry.')

    # Prepare a dict `results` that is used by the Jinja template to display the instances and 
    # series for the current page
    results = []
    for series_id in series_ids_in_page:
      series = {
        'SeriesId': series_id,
        'Instances': []
      }
      for instance in instances_in_page:
        instance_id = instance[0]
        instance_series_id = instance[1]
        index_in_series = instance[2]
        instance_json = instance[3]
        
        if instance_series_id == series_id:
          instance_json_keywords = rpacs_dicom_json.add_keywords_to_dicom_json(instance_json)
          series['Instances'].append({
            'InstanceId': instance_id,
            'IndexInSeries': index_in_series,
            'InstanceHeader': generate_header(env.instance_header_keywords, instance_json),
            'InstanceJSON': json.dumps(instance_json_keywords, indent=4, sort_keys=True)
          })
          if not 'SeriesHeader' in series:
            series['SeriesHeader'] = generate_header(env.series_header_keywords, instance_json)

      series['Instances'] = sorted(series['Instances'], key=lambda k: k['IndexInSeries'])
      results.append(series)
    
    # Calculate the pagination information
    pagination = {
      'TotalInstances': total_instances,
      'TotalSeries': total_series,
    }

    if offset > 0:
      pagination['PreviousEnabled'] = True
      left_new_offset = max(0, offset - env.results_per_page)
      pagination['PreviousLink'] = rewrite_full_path_new_offset(left_new_offset)
      pagination['PreviousRange'] = f'{left_new_offset+1} - {left_new_offset+env.results_per_page}'

    if offset + env.results_per_page < total_instances:
      pagination['NextEnabled'] = True
      right_new_offset = offset + env.results_per_page
      pagination['NextLink'] = rewrite_full_path_new_offset(right_new_offset)
      pagination['NextRange'] = f'{right_new_offset+1} - {min(right_new_offset+env.results_per_page, total_instances)}'

    orthanc_access = client.permissions.has_access_to_orthanc()
    response = flask.render_template('search.html', pagination=pagination, results=results, orthanc_access=orthanc_access)
    client.access_logger.log_search("Display", query, jsonpath_query, total_instances, total_series)
  
  # If the "Export" button was pressed, return a formatted JSON document for each of the DICOM 
  # instances matching the query
  if export_action is True:
    try:
      instances = db_dicom_json.search_instances_with_series(jsonpath_query)
      series_ids = get_unique_series_ids(instances)
    except:
      return flask.render_template('search.html', error_message='Failed to query the database. Please check your query and retry.')
    
    file_content = {'Series': []}
    for series_id in series_ids:
      series = {
        'SeriesId': series_id,
        'Instances': []
      }
      for instance in instances:
        instance_id = instance[0]
        instance_series_id = instance[1]
        index_in_series = instance[2]
        instance_json = instance[3]
        if instance_series_id == series_id:
          series['Instances'].append({
            'InstanceId': instance_id,
            'IndexInSeries': index_in_series,
            'InstanceJSON': rpacs_dicom_json.add_keywords_to_dicom_json(instance_json)
          })
      series['Instances'] = sorted(series['Instances'], key=lambda k: k['IndexInSeries'])
      file_content['Series'].append(series)

    file_json = json.dumps(file_content, indent=2, sort_keys=True)
    file_bytes = BytesIO(file_json.encode())
    response = flask.send_file(file_bytes, mimetype='application/json', as_attachment=True, attachment_filename='results.json')
    client.access_logger.log_search("Export", query, jsonpath_query, len(instances), len(series_ids))
    
  return response


@app.route('/aws/export', methods=['GET', 'POST'])
@login_required
def export_page():
  """Page Export DICOM Instances to Amazon S3"""

  def create_export_task():
    """Create a new export task. Returns `None` if the task was created, or an error message."""
    
    # Retrieve inputs from the form submitted
    query = request.form.get('query', default='')
    export_format = request.form.get('format', default='')
    export_json = request.form.get('json') == 'on'
    transcode = request.form.get('transcode', default='')
    s3_path = request.form.get('s3_path', default='')
    access_key = request.form.get('access_key', default='')
    secret_key = request.form.get('secret_key', default='')
    session_token = request.form.get('session_token', default='')
    
    # Verify the inputs
    try:
      assert export_format in ('dicom', 'png', 'jpeg'), 'The export format must be DICOM, PNG or JPEG.'
      match = re.search('^s3:\/\/([^\/]+)\/((?:|.+\/))$', s3_path)
      assert match, 'The S3 path is invalid. It must be "s3://bucket/" or "s3://bucket/prefix/", and it must end with a "/".'
      assert len(access_key) > 0, 'You must provide an AWS Access Key.'
      assert len(secret_key) > 0, 'You must provide an AWS Secret Key.'
    except Exception as e:
      return str(e)
    
    # Translate the query and the user's instance access permissions into a JSON Path query
    try:
      jsonpath_query = client.permissions.get_jsonpath_query(query)
      logger.debug(f'Export - JSON Path Query: {jsonpath_query}')
    except ValueError:
      return 'Your query is invalid.'
  
    # Reject the request if the user already has tasks with the "exporting" status
    if db_exports.has_user_ongoing_exports(g.user) is True:
      return 'You already have an ongoing export task. Please wait for the task to complete, or for one hour after the previous task was created.'
      
    # Add the export task into the database
    parameters = {
      'Query': query,
      'JSONPathQuery': jsonpath_query, 
      'Format': export_format,
      'ExportJSON': export_json,
      'Transcode': transcode,
      'S3Bucket': match.group(1),
      'S3Prefix': match.group(2)
    }
    task_id = db_exports.insert_task(g.user, parameters)
    client.access_logger.log_new_export(parameters, task_id)
  
    # Send a SQS message so that the website worker can process the export task
    client_sqs = boto3.client('sqs', region_name=env.region)
    client_sqs.send_message(
      QueueUrl=env.queue_url,
      MessageBody=json.dumps({
        'EventType': 'NewExport',
        'TaskId': task_id,
        'AccessKey': access_key,
        'SecretKey': secret_key,
        'SessionToken': session_token
      })
    )
  
  g.db = DB(env.pg_host, env.pg_port, env.pg_user, env.pg_pwd, env.pg_db)
  db_exports = DBExportTasks(g.db)
  error_message = None

  # Create a new export task if the form was submitted (method POST). If the creation succeeded,
  # redirect the user to the same page with a GET method to avoid multiple form submissions
  if request.method == 'POST':
    error_message = create_export_task()
    if error_message is None:
      return flask.redirect('/aws/export')
  
  # Display the export tasks for this user
  tasks = [
    {'Date': task[0], 'Status': task[1], 'Parameters': task[2], 'Results': task[3]}
    for task in db_exports.list_tasks()
  ]
  return flask.render_template('export.html', error_message=error_message, tasks=tasks)
