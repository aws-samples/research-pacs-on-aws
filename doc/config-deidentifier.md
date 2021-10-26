# De-identifier Configuration File

* [File structure](#file-structure)
* [Example](#example)
* [Updating and testing the configuration file](#updating-and-testing-the-configuration-file)

## File structure

This page describes the expected structure of the YAML configuration file used by the de-identifier. The file contains four sections that are further detailed below:

* `Labels`: (Mandatory) Define labels to apply to the incoming DICOM files
* `Categories` (Optional): Define categories as a set of labels
* `ScopeToForward`: (Mandatory) Filter the DICOM files to be made available in the self-service portal
* `Transformation`: (Mandatory) Define transformation rules to apply to remove potentially identifying information

### Section `Labels`

This first section specifies labels that may be applied to the incoming DICOM files, based on queries that you define. Note that the label `ALL` is applied to all incoming DICOM instances.

```
Labels:
  - Name: str
    DICOMQueryFilter: str
  - ...
```

* `Name`: (Mandatory) Name of the label to apply
* `DICOMQueryFilter`: (Mandatory) The label is applied to the DICOM instances that match this [DICOM instance query](dicom-instance-query.md)

### Section `Categories`

This second section is **optional** and allows you to specify categories as a set of labels. A DICOM file matches a category if one its matching labels is part of that category.

```
Categories:
  - Name: str
    Labels: list
  - ...
```

`Categories` is a list where each item contains:

* `Name`: (Mandatory) Name of the category
* `Labels`: (Mandatory) List of label names associated with this category

### Section `ScopeToForward`

This third section specifies which incoming DICOM files are de-identified and sent to the second Orthanc server, based on their matching labels or categories. Otherwise, the DICOM file is discarded.

```
ScopeToForward:
  Labels: str or list
  ExceptLabels: str or list
  Categories: str or list
  ExceptCategories: str or list
```

* `Labels`: A DICOM file will be de-identified and sent to the second Orthanc server, if at least one of its matching labels is listed in this attribute
* `ExceptLabels`: A DICOM file will be discarded, if at least one of its matching label is listed in this attribute
* `Categories`: A DICOM file will be de-identified and sent to the second Orthanc server, if at least one of its matching labels is part of a category listed in this attribute
* `ExceptCategories`: A DICOM file will be discarded, if at least one of its matching labels is part of a category listed in this attribute

`ExceptLabels` and `ExceptCategories` prevail on `Labels` and `Categories`: for example, if the matching labels are in both `Labels` and `ExceptLabels`, the DICOM file is discarded. A DICOM file is also discarded if its labels or categories don't match any of the `Labels`, `ExceptLabels`, `Categories` or `ExceptCategories` attributes.

### Section `Transformations`

This section specifies transformation rules to apply to the DICOM files in order to remove potentially identifying information. You are solely responsible for defining which transformation rules to apply.

```
Transformations:
  - Scope:
      Labels: str or list
      ExceptLabels: str or list
      Categories: str or list
      ExceptCategories: str or list
    [One or more transformations]
  - ...
```

`Transformations` is a list where each item contains:

* `Scope`: (Mandatory) Specifies which DICOM files are applied the transformations
  * `Labels`: A DICOM file is in scope if at least one of its matching labels is listed in this attribute
  * `ExceptLabels`: A DICOM file is out of scope if at least one of its matching label is listed in this attribute
  * `Categories`: A DICOM file is in scope if at least one of its matching labels is part of a category listed in this attribute
  * `ExceptCategories`: A DICOM file is out of scope if at least one of its matching labels is part of a category listed in this attribute

* `[One or more transformations]`: List of transformations to apply to the scope of DICOM files. Here is the list of possible transformations, that are further detailed below:
  * `ShiftDateTime`
  * `RandomizeText`
  * `RandomizeUID`
  * `AddTags`
  * `RemoveBurnedInAnnotations`
  * `DeleteTags`
  * `Transcode`

#### Transformation `ShiftDateTime`

Shift the value of *date* data elements (VR `DA`) by a random number of days comprised between `-ShiftBy` and `+ShiftBy`, or the value of *time* data elements (VR `TM` or `DT`) by a random number of seconds between `-ShiftBy` and `+ShiftBy`.

```
    ShiftDateTime:
      - TagPatterns: str or list
        ExceptTagPatterns: str or list
        ShiftBy: int
        ReuseMapping: str
      - ...
```

`ShiftDateTime` is a list where each item corresponds to a transformation to apply, and contains:

* `TagPatterns`: (Mandatory) List of [tag path patterns](tag-path-pattern.md) to which the transformation is applied
* `ExceptTagPatterns`: (Optional) List of [tag path patterns](tag-path-pattern.md) to which the transformation is not applied
* `ShiftBy`: Integer
* `ReuseMapping`: See the [note below](#note-about-reusemapping)

#### Transformation `RandomizeText`

Replace the value of a data elements by a 8-character string that is randomly generated.

```
    RandomizeText:
      - TagPatterns: str or list
        ExceptTagPatterns: str or list
        Split: str
        IgnoreCase: bool
        ReuseMapping: str
      - ...
```

`RandomizeText` is a list where each item corresponds to a transformation to apply, and contains:

* `TagPatterns`: (Mandatory) List of [tag path patterns](tag-path-pattern.md) to which the transformation is applied
* `ExceptTagPatterns`: (Optional) List of [tag path patterns](tag-path-pattern.md) to which the transformation is not applied
* `Split`: (Optional) You can specifify a delimiter that is used to split the value in multiple parts, and each part is replaced by a 8-character random string
* `IgnoreCase`: (Optional) You can set this attribute to `True` to lowercase the data element value before it is replaced by a random string. `False` by default
* `ReuseMapping`: See the [note below](#note-about-reusemapping)

#### Transformation `RandomizeUID`

Replace the value of `UI` data elements by a UID that is randomly generated. An original value is always replaced by the same UID. For example, if two DICOM files are part of the same series, and if you configure a RandomizeUID transformation for the `SeriesInstanceUID` data element, the two DICOM files will have the same new value for the `SeriesInstanceUID` data element.

```
    RandomizeUID:
      - TagPatterns: str or list
        ExceptTagPatterns: str or list
```

`RandomizeUID` is a list where each item corresponds to a transformation to apply, and contains:

* `TagPatterns`: (Mandatory) List of [tag path patterns](tag-path-pattern.md) to which the transformation is applied
* `ExceptTagPatterns`: (Optional) List of [tag path patterns](tag-path-pattern.md) to which the transformation is not applied

#### Transformation `AddTags`

Add a new data element or replace the value of an existing data element.

```
    AddTags:
      - Tag: str
        VR: str
        Value: str
```

`AddTags` is a list where each item corresponds to a tag to add or modify, and contains:

* `Tag`: [Tag path](tag-path.md) of the tag to create
* `VR`: (Mandatory) VR of the new data element
* `Value`: (Mandatory) New value of the data element
* `OverwriteIfExists`: (Optional) Set to `True` to replace the data element if it already exists. Default is `False`

#### Transformation `RemoveBurnedInAnnotations`

Remove burned-in annotations in the pixel data by obscuring pixels that contains text. You can either provide coordinates of boxes to obscur, or you can use Amazon Rekognition to find text in an image.

```
    RemoveBurnedInAnnotations:
      - Type: str
        BoxCoordinates:
          - [left, top, right, bottom]
```

`RemoveBurnedInAnnotations` is a list where each item corresponds to a transformation to apply, and contains:

* `Type`: (Mandatory) Can be either `OCR` to use Amazon Rekognition, or `Manual` to define box coordinates manually
* `BoxCoordinates`: (Conditional) List of box coordinates to obscur. Must be defined if `Type` is `Manual`.

#### Transformation `DeleteTags`

Remove data elements, or empty their value.

```
    DeleteTags:
      - TagPatterns: str or list
        ExceptTagPatterns: str or list
        Action: str
```

`DeleteTags` is a list where each item corresponds to a transformation to apply, and contains:

* `TagPatterns`: (Mandatory) List of [tag path patterns](tag-path-pattern.md) to which the transformation is applied
* `ExceptTagPatterns`: (Optional) List of [tag path patterns](tag-path-pattern.md) to which the transformation is not applied
* `Action`: Can be either `Remove` to remove the data element, or `Empty` to empty its value

#### Transformation `Transcode`

Transcode the DICOM file to another Transfer Syntax. If no `Transcode` value is provided, the de-identified DICOM file will have the same Transfer Syntax than the original DICOM file.

```
    Transcode: str
```

* `Transcode`: Transfer Syntax UID. Example: `1.2.840.10008.1.2.1`

#### Note about `ReuseMapping`

By default, when using `ShiftDateTime` or `RandomizeText` transformations, a new random value is generated for each incoming DICOM file. You can specify the `ReuseMapping` attributes to reuse the replace the original value by the same random value:

* `SameSeries`: If two DICOM files have the same `SeriesInstanceUID`, an original value will be replaced by the same "target" value
* `SameStudy`: If two DICOM files have the same `StudyInstanceUID`, an original value will be replaced by the same "target" value
* `SamePatient`: If two DICOM files have the same `PatientID`, an original value will be replaced by the same "target" value
* `Always`: An original value will be replaced by the same "target" value

Example:

```
    ShiftDateTime:
      - TagPatterns: "StudyDate"
        ShiftBy: 30
        ReuseMapping: SameStudy
```

This allows you to have consistent values across multiple related DICOM files. This transformation shifts the value of `StudyDate` by a random number of days comprised between -30 and +30. If two DICOM files have the same `StudyInstanceUID`, and `StudyDate` has the same value for both DICOM files (should be the case), `StudyDate` will be replaced by the same date in both de-identified DICOM files.

## Example

**Important:** This example is only intended to illustrate the capabilities of the de-identifier, and should not be considered as a sufficient configuration file to remove potentially identifying information.

```
Labels:
  - Name: Documents
    DICOMQueryFilter: Modality StrEquals DOC
  - Name: US
    DICOMQueryFilter: Modality StrEquals US
  - Name: Modality CT ModelA
    DICOMQueryFilter: Modality StrEquals CT AND ManufacturerModelName StrEquals ModelA

ScopeToForward:
  Labels: ALL
  NotLabels: Documents

Transformations:
  - Scope:
      Labels: ALL
    ShiftDateTime:
      - TagPatterns: "*/PatientBirthDate"
        ShiftBy: 30
        ReuseMapping: SamePatient
      - TagPatterns: "StudyDate"
        ShiftBy: 30
        ReuseMapping: SameStudy
    RandomizeText:
      - TagPatterns: "*/{PN}"
        Split: ^
        IgnoreCase: True
        ReuseMapping: Always
    RandomizeUID:
      - TagPatterns:
          - "*/SOPInstanceUID"
          - "*/StudyInstanceUID"
          - "*/SeriesInstanceUID"
    DeleteTags:
      - TagPatterns: "*/XXX@XXXX"
        ExceptTagPatterns:
          - "*/0015{Private Creator}XX"
          - "0023XXXX"
        Action: Remove
  - Scope:
      Labels: US
    AddTags:
      - Tag: "00230010"
        VR: LO
        Value: My private tags
  - Scope:
      Labels: ALL
      NotLabels: Modality CT ModelA
    RemoveBurnedInAnnotations:
      - Type: OCR
  - Scope:
      Labels: Modality CT ModelA
    RemoveBurnedInAnnotations:
      - Type: Manual
        BoxCoordinates:
          - [0, 0, 50, 50]
          - [100, 100, 150, 150]
    Transcode: 1.2.840.10008.1.2.1
```

This configuration file defines three labels:
* `Documents` is applied to DICOM files whose Modality is DOC
* `US` where Modality is US
* `Modality CT ModelA` where Modality is CT and the Manufacturer Model Name is ModelA

All DICOM files are de-identified and sent to the second Orthanc server, except when the DICOM file matches the label `Documents`.

The following transformations are then applied to the DICOM files that not discarded:

* To each DICOM file:
  * Shift all `PatientBirthDate` data elements, wherever they occur in the dataset, by a random number of days between -30 and +30 days. When two DICOM files have the same value of `PatientID`, a given birth date is always replaced by the same shifted value
  * Shift the top-level `StudyDate` data element by a random number of days between -30 and +30 days. When two DICOM files have the same value for `StudyInstanceUID`, a given study date is always replaced by the same shift value
  * For all `PN` data elements, lowercase their value, split by `^` and replace each part by 8-character random string. Because `ReuseMapping: Always`, if `john^smith` is replaced by `abcdefgh^12345678`, `SMITH^John` will be replaced by `12345678^abcdefgh` whatever the `PN` element data is
  * Replace the data elements `SOPInstanceUID`, `StudyInstanceUID` and `SeriesInstanceUID` by a random UID, wherever they occur in the dataset
  * Remove all private tags from the dataset (`TagPatterns: "*/XXX@XXXX"`) expect if the tag group number is `0023`, or if the tag group number is `0015` and the private creator is `Private Creator`

* To each `US` DICOM file:
  * Add a top-level data element `00230010`

* To each DICOM file except if if it matches the label `Modality CT ModelA`:
  * Remove burned-in pixel annotations using OCR (Amazon Rekognition)

* To each DICOM file matching the label `Modality CT ModelA`:
  * Remove burned-in pixel annotations by obscuring specific locations in the pixel data
  * Transcode the DICOM file to `1.2.840.10008.1.2.1`

## Updating and testing the configuration file

The configuration file is loaded every time a new DICOM file is incoming. If you need to iteratively update and test a new version of the configuration file before it goes to "production" and becomes the default configuration file, you can send a message to the first SQS queue (see [Sending messages to a queue](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-using-send-messages.html)) to simulate a new DICOM file to process.

The content of the SQS queue should be a JSON document as follows:

```
{
  "EventType": "NewDICOM",
  "Source": str,
  "ConfigFile": str,
  "Destination": str,
  "LogFile": str,
  "Retry": bool
}
```

* `EventType`: (Mandatory) Must be equal to `NewDICOM`
* `Source`: (Mandatory) You can provide either:
  * A DICOM instance ID in the first Orthanc server using `orthanc://[instance-id]`. Example: `orthanc://123e4567-e89b-12d3-a456-426614174000`. Note that, by default, DICOM files are removed from the first Orthanc server after they have been processed by the de-identifier
  * Or a location to a S3 object using `s3://bucket/key`
  * Or a location to a file that exists in a local or locally-mounted file system. Example: `/tmp/file.dcm`

* `ConfigFile`: (Optional) You can use a custom configuration file by specifying either a location to a S3 object using `s3://bucket/key`, or a location to a file that exists in a local or locally-mounted file system. If you don't specify this attribute, the default configuration file is used.
* `Destination`: (Optional) You can provide a custom destination for the de-identified DICOM file by specifying either a location to a S3 object using `s3://bucket/key`, or a location to a file that exists in a local or locally-mounted file system. If you don't specify this attribute, the de-identified DICOM file is sent to the second Orthanc server.
* `LogFile`: (Optional) You can write the logs of the de-identification task to a JSON file by specifying either a location to a S3 object using `s3://bucket/key`, or a location to a file that exists in a local or locally-mounted file system
* `Retry`: By default, a SQS message is retried multiple times if an error occurs while it is being processed. To not retry the message, set this attribute to `False`
