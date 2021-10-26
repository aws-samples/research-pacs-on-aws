# PostgreSQL Tables

This page describes the structure of the PostgreSQL tables used by the Research PACS on AWS solution. That does not include the tables that are created and used by Orthanc for [index storage](https://book.orthanc-server.com/plugins/postgresql.html).

## Table `rpacs_change_pooler_last_state`

Used by: Change pooler

Description: Store the last change ID (Seq) that was detected and processed by the change pooler in the first and in the second Orthanc server (see [Tracking changes](https://book.orthanc-server.com/users/rest.html#tracking-changes) in the Orthanc documentation).

Column | Data type | Description | Primary Key
--- | --- | --- | ---
key | VARCHAR(250) | Stores the Orthanc hostname | X
value | JSONB | Stores the change ID (Seq) |

## Table `rpacs_related_msg`

Used by: De-identifier

Description: When the de-identifier receives a SQS message corresponding to a new DICOM file stored in Amazon S3 or a local file system, the de-identifier first uploads the DICOM file to the first Orthanc server, in order to leverage from native Orthanc APIs. The change pooler will detect a new change and send another SQS message that the de-identifier will receive. This table enables to store the "instructions" (configuration file to use, destination for the de-identified DICOM file, etc.) passed with the first SQS message, and associate the second SQS message with the instructions of the first SQS message.

Column | Data type | Description | Primary Key
--- | --- | --- | ---
key | VARCHAR(250) | Stores the instance ID of the copy stored in the first Orthanc server | X
value | JSONB | Stores the instructions passed in the first SQS message |

## Table `rpacs_dicom_mapping`

Used by: De-identifier

Stores the mappings between an original value of a DICOM data element and the associated value in the de-identified DICOM file.

Column | Data type | Description | Primary Key
--- | --- | --- | ---
value_type | VARCHAR(8) | Equal to `UID`, `DATETIME` and `TEXT` based on the type of transformation that generated this mapping | X
old_value | TEXT | Value in the original DICOM file | X
scope_type | VARCHAR(10) | `always`, `patient`, `study`, `series` or `instance` | X
scope_value | TEXT | Equal to `always` if `scope_type` is `always`, the value of `PatientID` if `scope_type` is `patient`, the value of `StudyInstanceID` if `scope_type` is `study`, etc. | X
new_value | TEXT | Corresponding value in the de-identified DICOM file | 

## Table `rpacs_dicom_json`

Used by: Website, Website worker

Description: Stores the JSON representation of the de-identified DICOM files stored in the second Orthanc server, in order to make queries more granular and performant.

Column | Data type | Description | Primary Key
--- | --- | --- | ---
instance_id | VARCHAR(50) | Orthanc instance ID | X
series_id | VARCHAR(50) | Stores the value of the `SeriesInstanceUID` data element | 
index_in_series | INTEGER | Stores the value of the `InstanceNumber` data element | 
dicom | JSONB | JSON representation of the DICOM dataset | 

## Table `rpacs_export_tasks`

Used by: Website, Website worker

Description: Stores the list of export tasks to Amazon S3 and details about the task parameters and results.

Column | Data type | Description | Primary Key
--- | --- | --- | ---
id | SERIAL | Export task ID | X
user_name | VARCHAR(250) | User who creates the export task | 
status | VARCHAR(10) | `exporting`, `completed` or `failed` | 
add_time | TIMESTAMP | Export task creation time | 
parameters | JSONB | Export task parameters (JSON Path query, format, S3 location...) | 
results | JSONB | Results (number of instances exported or failed, error messages...) | 
