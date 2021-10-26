# Permissions Configuration File

* [File structure](#file-structure)
* [Example](#example)
* [Updating and testing the configuration file](#updating-and-testing-the-configuration-file)

This page describes the expected structure for the YAML configuration file that allows you to define permissions profiles for the self-service portal (*website* component) and to assign profiles to users and groups.

## File structure

```
Profiles:
  ProfileName1:
    Description: str
    OrthancPathPatterns:
      Allow: str or list
      Deny: str or list
  ProfileName2:
    Description: str
    DICOMQueryFilter: str
  ...
  
Permissions:
  - Users: str or list
    Groups: str or list
    Profiles: str or list
  - ...
```

* `Profiles`: (Mandatory)
  * `ProfileName`: Name of the permissions profile
    * `Description`: (Mandatory) Description of the permissions profile displayed in the Permissions page
    * `OrthancPathPatterns`: (Conditional) List of path patterns that the profile allows or denies to make to the underlying Orthanc server (second Orthanc server). Specifying `OrthancPathPatterns` implicitly allows access to all the DICOM instances stored in the Research PACS. You can either define `OrthancPathPatterns` or `DICOMQueryFilter`, but not both.
      * `Allow`: List of path patterns that the profile allows to make to the underlying Orthanc server. You can use `**` to match any character, or `*` to match any character expect `/`
      * `Deny`: List of path patterns that the profile denies to make to the underlying Orthanc server. You can use `**` to match any character, or `*` to match any character expect `/`

    * `DICOMQueryFilter`: (Conditional) [DICOM instance query](dicom-instance-query.md) to restrict access only to the DICOM instances that match the query. You can either define `OrthancPathPatterns` or `DICOMQueryFilter`, but not both. 
    
* `Permissions`: (Mandatory) List of permissions assignments
  * `Users`: Username or list of usernames
  * `Groups`: Group or list of groups
  * `Permissions`: Profile name or list of profile names (see `ProfileName`) that are assigned to users whose user name is within `Users`, or whose groups are within `Groups`

## Example

```
Profiles:
  ResearcherAll:
    Description: "This profile allows access to all DICOM instances"
    OrthancPathPatterns:
      Allow:
        - ANY /app/**
        - GET /system
        - GET /patients
        - GET /patients/**
        - GET /series
        - GET /series/**
        - GET /studies
        - GET /studies/**
        - GET /instances
        - GET /instances/**
  ResearcherCT:
    Description: "This profile allows access to all CT DICOM instances"
    DICOMQueryFilter: Modality StrEquals CT

Permissions:
  - Users: user1
    Profiles: ResearcherAll
  - Groups: groups-ct
    Profiles: ResearcherCT
```

This configuration file specifies two profiles: `ResearcherAll` that allows access to all the DICOM instances and access to Orthanc read-only APIs, `ResearcherCT` that allows access to all the CT DICOM instances. The user `user1` is assigned the profile `ResearchAll`, and the users in the group `group-ct` are assigned the profile `ResearcherCT`.

## Updating and testing the configuration file

To update the configuration file, replace the current file by a new version, and the self-service portal will automatically reload it every 10 seconds. If the configuration file failed to load, a warning message is displayed in the logs and the previous permissions remains unchanged. Otherwise, the new configuration file is applied immediatly after the reload.
