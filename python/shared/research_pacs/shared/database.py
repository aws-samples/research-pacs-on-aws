# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import json
import logging

import psycopg2

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


class DB():
  
  def __init__(self, host, port, user, password, database, create_db=True):
    """
    Create a DB object.
    
    Args:
      host: Database host
      port: Database port
      user: Database user name
      Password: Database user password
      database: Name of the database
      create_db: Try to create the database if it does not exist

    """
    self.host = host
    self.port = port
    self.user = user
    self.password = password
    self.database = database
    self.create_db = create_db
    self._connection = None
    self._cursor = None


  def _connect(self, create_db=True):
    """
    Connect to the database. If the database does not exist, the function tries to connect to the 
    `postgre` database and create the database.
    
    Args:
      create_db: Set this parameter and `self.create_db` to `True` to create the database if it 
       does not exist
      
    """
    try:
      if self._connection is None:
        logger.debug(f'PostgreSQL - Connecting to the database Host={self.host} Database={self.database}')
        self._connection = psycopg2.connect(
          user = self.user,
          password = self.password, 
          host = self.host,
          port = self.port,
          database = self.database,
          connect_timeout = 5
        )
        self._connection.autocommit = True
      return self._connection
    except Exception as e:
      if f'database "{self.database}" does not exist' in str(e) and create_db is True and self.create_db is True:
        self._create_db()
        self._connect(create_db=False)
      else:
        raise e


  def _create_db(self):
    logger.debug(f'Creating the database {self.database}')
    db_create = DB(self.host, self.port, self.user, self.password, 'postgres', create_db=False)
    db_create.execute(f'CREATE DATABASE {self.database}')
    db_create.close()
        
        
  def _get_cursor(self):
    if self._cursor is None or self._cursor.closed:
      logger.debug('Creating the database cursor')
      if self._connection is None:
        self._connect()
      self._cursor = self._connection.cursor()
    return self._cursor
  
  
  def _execute(self, query, *args, retry=True):
    try:
      if self._connection is None:
        self._connect()
      if self._cursor is None:
        self._get_cursor()
      logger.debug(f'Executing the SQL query {query}')
      self._cursor.execute(query, *args)
    # Try to close and re-connect to the database if the execution failed and `retry` is True
    except Exception as e:
      if retry is True:
        logger.debug(f'Failed to execute the SQL query, retrying - {e}')
        self._close()
        self._connect()
        self._get_cursor()
        self._execute(query, *args, retry=False)
      else:
        raise e
  
  
  def _close(self):
    if self._connection != None:
      logger.debug('Closing the database')
      if self._cursor != None:
          self._cursor.close()
      self._connection.close()
    self._connection = None
    self._cursor = None
  
  
  def execute(self, query, *args):
    try:
      self._execute(query, *args)
    except Exception as e:
      err_msg = f'Failed to execute the SQL query {query} - {e}'
      logger.debug(err_msg)
      raise Exception(err_msg)
      
      
  def close(self):
    try:
      self._close()
    except Exception as e:
      logger.warning(f'Failed to close the database - {e}')
  
  
  def fetchone(self):
    try:
      return self._cursor.fetchone()
    except Exception as e:
      err_msg = f'Failed to fetch one result - {e}'
      logger.debug(err_msg)
      raise Exception(err_msg)


  def fetchall(self):
    try:
      return self._cursor.fetchall()
    except Exception as e:
      err_msg = f'Failed to fetch all results - {e}'
      logger.debug(err_msg)
      raise Exception(err_msg)


class DBKeyJsonValue():
  """
  Store key / JSON items in a PostgreSQL instance.
  
  """

  def __init__(self, db_client, table_name):
    """
    Args:
      db_client (str): DB object
      table_name (str): Name of the table where key-value items are stored in the PostgreSQL instance
    
    """
    logger.debug(f'Creating a new DBKeyJsonValue object with TableName={table_name}')
    self._table = table_name
    self._db = db_client
    sql_query = f"CREATE TABLE IF NOT EXISTS {self._table} (key VARCHAR(250) PRIMARY KEY, value JSONB);"
    self._db.execute(sql_query)


  def get(self, key, init_value=None, retry=True):
    """
    Args:
      key (str): Key
      init_value (dict, Optional): If no item exists for this key, create an item with 
        `init_value` as the value. Default is None
      retry (bool): Attempt to create an item if `init_value` is not None, and retry is `True`
      
    """
    logger.debug(f'PostgreSQL - Retrieving the JSON value for key="{key}" in the table "{self._table}"')
    sql_query = f"SELECT value FROM {self._table} WHERE key = %s;"
    self._db.execute(sql_query, (key,))
    state = self._db.fetchone()
    if state != None:
      return state[0]
    else:
      if init_value != None and retry is True:
        self.insert(key, init_value)
        return self.get(key, init_value, retry=False)
      else:
        return None


  def insert(self, key, value_dict):
    logger.debug(f'PostgreSQL - Inserting the JSON value for key="{key}" in the table "{self._table}"')
    sql_query = f"INSERT INTO {self._table} (key, value) VALUES (%s, %s);"
    value_str = json.dumps(value_dict)
    self._db.execute(sql_query, (key, value_str))


  def upsert(self, key, value_dict):
    logger.debug(f'PostgreSQL - Upserting the JSON value for key="{key}" in the table "{self._table}"')
    sql_query = f"INSERT INTO {self._table} (key, value) VALUES (%s, %s) ON CONFLICT (key) DO UPDATE SET value = %s;"
    value_str = json.dumps(value_dict)
    self._db.execute(sql_query, (key, value_str, value_str))
    
    
  def update(self, key, new_value_dict):
    logger.debug(f'PostgreSQL - Updating the JSON value for key="{key}" in the table "{self._table}"')
    sql_query = f"UPDATE {self._table} SET value = %s WHERE key = %s;"
    new_value_str = json.dumps(new_value_dict)
    self._db.execute(sql_query, (new_value_str, key))


  def delete(self, key):
    logger.debug(f'PostgreSQL - Deleting the JSON value for key="{key}" in the table "{self._table}"')
    sql_query = f"DELETE FROM {self._table} WHERE key = %s;"
    self._db.execute(sql_query, (key,))


class DBDicomJson():
  """
  Store DICOM datasets as JSON document in a PostgreSQL table to make it easier and more 
  performant to query.
  
  """

  def __init__(self, db_client, table_name='rpacs_dicom_json'):
    """
    Args:
      db_client (str): DB object
      table_name (str): Name of the table
    
    """
    logger.debug(f'Creating a new DBDicomJson object')
    self._table = table_name
    self._db = db_client
    sql_query = f"CREATE TABLE IF NOT EXISTS {self._table} (instance_id VARCHAR(50) PRIMARY KEY, series_id VARCHAR(50), index_in_series INTEGER, add_time TIMESTAMP, dicom JSONB);"
    self._db.execute(sql_query)


  def upsert_instance(self, instance_id, series_id, index_in_series, dicom_dict):
    """
    Insert a new instance, or update its content if the instance ID already exists in the database.
    
    Args:
      instance_id (str): Instance ID in Orthanc
      series_id (str): Series ID in Orthanc
      index_in_series (int): Instance index in the series
      dicom_dict (json): JSON document representing a DICOM file
      
    """
    logger.debug(f'PostgreSQL - Upserting the JSON document for DICOM instance ID={instance_id}')
    sql_query = f"INSERT INTO {self._table} (instance_id, series_id, index_in_series, add_time, dicom) VALUES (%s, %s, %s, current_timestamp, %s) ON CONFLICT (instance_id) DO UPDATE SET series_id = %s, index_in_series = %s, add_time = current_timestamp, dicom = %s;"
    dicom_str = json.dumps(dicom_dict)
    self._db.execute(sql_query, (instance_id, series_id, index_in_series, dicom_str, series_id, index_in_series, dicom_str))


  def _get_sql_query(self, jsonpath_query, col_returned, limit=None, offset=None, order_results=False, additional_filter=None):
    """
    Parse and generate a SQL query according to the arguments passed. Returns the SQL query and the 
    first argument to pass.
    
    Args:
      jsonpath_query (str): Condition part of the JSON Path query
      col_returned (str): List of columns returned
      limit (int): Maximum number of results to return
      offset (int): Skip `offset` rows before beginning to return rows
      order_results (bool): Order the results, most recently added come first
      additional_filter (str): Additional query condition
    
    """
    arg = f'$ ? ({jsonpath_query})' if jsonpath_query != '' else None
    sql_query = f'SELECT {col_returned} FROM {self._table}'
    sql_query += " WHERE dicom @? %s" if jsonpath_query != '' else ''
    sql_query += f" AND {additional_filter}" if additional_filter != None else ''
    sql_query += ' ORDER BY add_time DESC' if order_results is True else ''
    sql_query += f' LIMIT {limit}' if limit != None else ''
    sql_query += f' OFFSET {offset};' if offset != None else ';'
    return sql_query, arg


  def count_instances(self, jsonpath_query=''):
    """
    Return the number of Orthanc instances that match the JSON Path query, and the number of 
    distinct series that include these instances.
    
    """
    logger.debug(f'PostgreSQL - Counting the DICOM instances that match the query "{jsonpath_query}"')
    sql_query, first_arg = self._get_sql_query(jsonpath_query, 'COUNT(instance_id), COUNT(DISTINCT series_id)')
    self._db.execute(sql_query, (first_arg,))
    response = self._db.fetchone()
    return response[0], response[1]
    
    
  def search_instance_ids(self, jsonpath_query, limit=None):
    """
    Return a list of Orthanc instance IDs that match the JSON Path query.
    
    """
    logger.debug(f'PostgreSQL - Searching the DICOM instances that match the query "{jsonpath_query}"')
    sql_query, first_arg = self._get_sql_query(jsonpath_query, 'instance_id', limit, order_results=True)
    self._db.execute(sql_query, (first_arg,))
    return self._db.fetchall()
    
    
  def search_instances(self, jsonpath_query, limit=None):
    """
    Return a list of Orthanc instance IDs and associated JSON documents containing DICOM tags 
    that match the JSON Path query.
    
    """
    logger.debug(f'PostgreSQL - Searching the DICOM instances that match the query "{jsonpath_query}"')
    sql_query, first_arg = self._get_sql_query(jsonpath_query, 'instance_id, dicom', limit, order_results=True)
    self._db.execute(sql_query, (first_arg,))
    return self._db.fetchall()
    
    
  def search_instances_with_series(self, jsonpath_query, limit=None, offset=None):
    """
    Return a list of Orthanc instance IDs that match the JSON Path query, with their associated 
    series ID and DICOM tags.
    
    """
    logger.debug(f'PostgreSQL - Searching the DICOM instances that match the query "{jsonpath_query}"')
    sql_query, first_arg = self._get_sql_query(jsonpath_query, 'instance_id, series_id, index_in_series, dicom', limit, offset, order_results=True)
    self._db.execute(sql_query, (first_arg,))
    return self._db.fetchall()
    
    
  def list_instance_ids(self):
    """
    Return the full list of IDs of all Orthanc instances indexed in the database.
    
    """
    logger.debug(f'PostgreSQL - Listing the DICOM instances from the database')
    sql_query = f"SELECT instance_id FROM {self._table};"
    self._db.execute(sql_query)
    return [i[0] for i in self._db.fetchall()]
    
    
  def has_access_to_instance(self, jsonpath_query, instance_id):
    """
    Return True is the JSON Path query match the instance ID.
    
    """
    logger.debug(f'PostgreSQL - Checking if the DICOM instance ID={instance_id} matches the query "{jsonpath_query}"')
    sql_query, first_arg = self._get_sql_query(jsonpath_query, 'COUNT(instance_id)', additional_filter='instance_id = %s')
    self._db.execute(sql_query, (first_arg, instance_id))
    return self._db.fetchone()[0] > 0
    
    
  def has_access_to_series(self, jsonpath_query, series_id):
    """
    Return True is the JSON Path query match at least once instance whose series ID is `series_id`.
    
    """
    logger.debug(f'PostgreSQL - Checking if the DICOM series ID={series_id} matches the query "{jsonpath_query}"')
    sql_query, first_arg = self._get_sql_query(jsonpath_query, 'COUNT(instance_id)', additional_filter='series_id = %s')
    self._db.execute(sql_query, (first_arg, series_id))
    return self._db.fetchone()[0] > 0


  def delete_instance(self, instance_id):
    """
    Delete an instance from the database.
    
    """
    logger.debug(f'PostgreSQL - Deleting the instance ID={instance_id} from the database')
    sql_query = f"DELETE FROM {self._table} WHERE instance_id = %s;"
    self._db.execute(sql_query, (instance_id,))


class DBExportTasks():
  """
  Store information about the export tasks to Amazon S3.
  
  """

  def __init__(self, db_client, table_name='rpacs_export_tasks'):
    """
    Args:
      db_client (str): DB object
      table_name (str): Name of the table
    
    """
    logger.debug(f'Creating a new DBExportTasks object')
    self._table = table_name
    self._db = db_client
    sql_query = f"CREATE TABLE IF NOT EXISTS {self._table} (id SERIAL PRIMARY KEY, user_name VARCHAR(250), status VARCHAR(10), add_time TIMESTAMP, parameters JSONB, results JSONB);"
    self._db.execute(sql_query)


  def has_user_ongoing_exports(self, user):
    """
    Return `True` if the user has already an ongoing task (status = exporting) that was launched 
    less than one hour ago.
    
    """
    logger.debug(f'PostgreSQL - Checking if the user "{user}" has ongoing export tasks')
    sql_query = f"SELECT COUNT(id) FROM {self._table} WHERE user_name = %s AND STATUS = 'exporting' AND EXTRACT(EPOCH FROM current_timestamp-add_time) < 3600;"
    self._db.execute(sql_query, (user,))
    return self._db.fetchone()[0] > 0


  def insert_task(self, user, parameters_dict):
    """
    Insert a new export task.
    
    Args:
      user (dict): Current user name
      parameters_dict (dict): Export task parameters
    
    """
    logger.debug(f'PostgreSQL - Inserting a new export task')
    sql_query = f"INSERT INTO {self._table} (user_name, status, add_time, parameters, results) VALUES (%s, 'exporting', current_timestamp, %s, %s) RETURNING id;"
    parameters_str = json.dumps(parameters_dict)
    self._db.execute(sql_query, (user, parameters_str, "{}"))
    return self._db.fetchone()[0]


  def list_tasks(self):
    """
    List export tasks.
    
    """
    logger.debug(f'PostgreSQL - Listing the export tasks')
    sql_query = f"SELECT TO_CHAR(add_time, 'YYYY/MM/DD HH24:MI'), status, parameters, results FROM {self._table} ORDER BY add_time DESC;"
    self._db.execute(sql_query)
    return self._db.fetchall()


  def get_task(self, task_id):
    """
    Get the parameters of a given task.
    
    Args:
      task_id (int): Task ID
    
    """
    logger.debug(f'PostgreSQL - Retrieving details for the export task ID={task_id}')
    sql_query = f"SELECT parameters FROM {self._table} WHERE id = %s;"
    self._db.execute(sql_query, (task_id,))
    return self._db.fetchone()[0]


  def update_task(self, task_id, status, results_dict):
    """
    Update the status and results of a task.
    
    Args:
      task_id (int): Task ID
      status (str): New status
      results_dict (dict): Export task results
    
    """
    logger.debug(f'PostgreSQL - Updating the export task ID={task_id}')
    sql_query = f"UPDATE {self._table} SET status = %s, results = %s WHERE id = %s;"
    results_str = json.dumps(results_dict)
    self._db.execute(sql_query, (status, results_str, task_id,))


class DBDicomMapping():
  """
  Store the mapping between the initial values a data element in the original DICOM file and 
  their corresponding values in the de-identified DICOM file.
  
  
  """

  def __init__(self, db_client, table_name='rpacs_dicom_mapping'):
    """
    Args:
      db_client (str): DB object
      table_name (str): Name of the table
    
    """
    logger.debug(f'Creating a new DBDicomMapping object')
    self._table = table_name
    self._db = db_client
    sql_query = (
      f"CREATE TABLE IF NOT EXISTS {self._table} (value_type VARCHAR(8) NOT NULL, old_value TEXT NOT NULL, scope_type VARCHAR(10) NOT NULL, "
      "scope_value TEXT NOT NULL, new_value TEXT NOT NULL, PRIMARY KEY (value_type, old_value, scope_type, scope_value));"
    )
    self._db.execute(sql_query)


  def add_or_get_mapping(self, value_type, old_value, new_value, scope_type, scope_value):
    """
    Add a mapping between a value `old_value` contained an original DICOM file, and the value 
    `new_value` by which  it must be replaced in the de-identified DICOM file. `scope_type` and 
    `scope_value` specifies the scope of the mapping.
    
    For example, if `value_type` = TEXT, `old_value` = `phi`, `new_value` = `masked_phi`, 
    `scope_type` = `patient` and `scope_value` = `patient1`, then the value `phi` should be 
    replaced by `masked_phi` if the data element PatientID is equal to `patient1`.
    
    If the mapping does not exist, it adds a new entry in the database. If it exists, a constraint 
    on primary key is raised, and the function returns the existing `new_value`.
    
    Args:
      value_type (str): Type of value. Currently `UID`, `DATETIME` and `TEXT` are used
      old_value (str): Initial value
      new_value (str): Value by which the initial value must be replaced
      scope_type (str): Currently `always`, `patient`, `study`, `series` and `instance` are used
      tag_value (str): Equals to `always` if `scope_type` is `always`, the value of PatientID if 
        ``scope_type` is `patient`, the value of StudyInstanceID if `scope_type` is `study`, etc.
    
    """
    sql_query = (
      f"INSERT INTO {self._table} (value_type, old_value, scope_type, scope_value, new_value) VALUES (%s, %s, %s, %s, %s) "
      "ON CONFLICT (value_type, old_value, scope_type, scope_value) DO UPDATE SET old_value=excluded.old_value RETURNING new_value;"
    )
    self._db.execute(sql_query, (value_type, old_value, scope_type, scope_value, new_value))
    return self._db.fetchone()[0]
