# Tag Paths

## Language reference

This page describes the language reference for the `Tag` attribute in the `AddTags` section of the [de-identifier configuration file](config-deidentifier.md). A tag path represent a data element in a DICOM file to create or modify.

A tag path can be either:

* A tag keyword (e.g. `PatientName`)
* A hexadecimal number (e.g. `00100010`)

To create or modify the value of a tag that is contained in a sequence data element, a tag path may be composed of multiple *tags* separated by a comma, and you can eventually specify an item-number for the sequence data element value. For example:

* `Sequence.NewTag` or `Sequence[%].NewTag` represents the data element `NewTag` contained in **each** value of the sequence data element `Sequence`
* `Sequence[0].00191008` represents the data element `00191008` contained in the **first** value of the sequence data element `Sequence`

## Examples

* `PatientName` represents the top-level data element whose tag keyword is `PatientName`
* `00191008` represents the top-level data element whose tag hexadecimal number is `00191008`
* `Sequence[0].Tag1` represents the data element whose tag keyword is `Tag1` in the first value of the top-level sequence data element `Sequence`
* `Sequence[%].Tag1` represents the data element whose tag keyword is `Tag1` in each value of the top-level sequence data element `Sequence`
