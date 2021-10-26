# DICOM Instance Query

## Language reference

This page describes the query language reference that allows you to search for DICOM instances in the Search and Export pages of the self-service portal, or to filter DICOM instances in the `DICOMFilterQuery` attribute of the [de-identifier configuration file](config-deidentifier.md) or the [permissions configuration file](config-permissions.md).

A query is composed of one or more conditions, combined with `AND` or `OR` operands. You can also enclose multiple conditions and operands in parenthesis `()` in order to change the predecence of operands (e.g. `(Condition1 OR Condition2) AND Condition3`).

Each condition is defined as `Tag Operator [Value]` where a `Value` is required for some operators only.

### Possible values for `Tag`

* A case-sensitive keyword (e.g. `Modality`)
* Or a hexadecimal number (e.g. `7FE00010`)
* Or a sequence of tags separated by dots (e.g. `SequenceOfUltrasoundRegions.RegionSpatialFormat`, `00186011.00186012` or `00186011.RegionSpatialFormat`)

### Possible values for `Operator`

Operator | Value | Description
--- | --- | ---
`Exists` | No value needed | The data element must exist
`NotExists` | No value needed | The data element must not exist
`Empty` | No value needed | At least one value of the data element must be empty
`NotEmpty` | No value needed | At least one value of the data element must not be empty
`StrEquals` | String that can eventually be enclosed with `"` or contains a wildcard character `*` | At least one value of the data element must equals `Value`, or match `Value` if wildcard characters are used (case insensitive)
`StrNotEquals` | String that can eventually be enclosed with `"` or contains a wildcard character `*` | At least one value of the data element value must not equals `Value`, and must not match `Value` if wildcard characters are used (case insensitive)
`NbEquals` | Integer or decimal value | At least one value of the data element value must be an integer or a decimal, and must equals `Value`
`NbNotEquals` | Integer or decimal value | At least one values of the data element value must be an integer or a decimal, and must not equals `Value`
`NbGreater` | Integer or decimal value | At least one value of the data element value must be an integer or a decimal, and must be greater than `Value`
`NbLess` | Integer or decimal value | At least one value of the data element value must be an integer or a decimal, and must be less than `Value`

## Examples

* `(Modality StrEquals CT OR Modality StrEquals MR) AND StudyDescription StrEquals "*chest*"`: The value of the data element `Modality` must equals `CT` or `MR`, and the value of the data element `StudyDescription` must contain `chest`.
* `ImageType StrEquals ORIGINAL AND Rows NbGreater 500 AND Rows NbLess 1000`: At least one value of the data element `ImageType` must equals `ORIGINAL` (this is a multi-valued data element) and the value of the data element `Rows` must be between `500` and `1000` (500 and 1000 excluded).
* `00190040.0019004A Exists`: There must be a top-level data element `00190040` whose value representation is `SQ`, and one of its values must contain a data element `0019004A`.

## How does it work

This section is intended for advanced readers, and explains how the query language is implemented within the solution.

Each DICOM file stored in the second Orthanc server is indexed in a PostgreSQL database as a JSON document, derived from the output of the [`to_json`](https://pydicom.github.io/pydicom/stable/reference/generated/pydicom.dataset.Dataset.html#pydicom.dataset.Dataset.to_json) function in pydicom.

PostgreSQL can store JSON data as a `jsonb` data type (see [JSON data type](https://www.postgresql.org/docs/13/datatype-json.html)) which supports the SQL/JSON path language from PostgreSQL 12 to efficiently query JSON data.

The solution translates human-readable queries into SQL/JSON path language, and executes the SQL/JSON path query in the PostgreSQL database to search for matching DICOM instances. For example, `Modality StrEquals CT AND Rows NbGreater 1000` gives `@.00080060 like_regex "CT" flag "i" && @.00280010.double() > 1000`. This provides more granularity and performance than using the [`/tools/find`](https://api.orthanc-server.com/#tag/System/paths/~1tools~1find/post`) Orthanc API or the DICOMweb API.
