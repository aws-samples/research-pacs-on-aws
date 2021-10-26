# Tag Path Patterns

## Language reference

This page describes the language reference for the `TagPatterns` and `NotTagPatterns` attributes of the [de-identifier configuration file](config-deidentifier.md). A tag path pattern represent a data element in a DICOM file or a set of data elements.

A tag path pattern is composed of one tag pattern, or more than one tag pattern separated by a comma to represent sequence attributes. Each tag pattern can be either:

* A case-sensitive keyword, where you can use wildcard characters `*` (e.g. `*Date` represents data elements whose tag keyword ends with Date)
* A hexadecimal tag number, where you can use `X` that matches any hex digit, or `@` that matches any even digit (e.g. `00100010` for the PatientName data element, `0023XXXX` for any data element whose group number is 0023, `XXX@XXXX` for any private data element)
* `xxxx{Private tag creator}yy` that represents private data elements whose group number is `xxxx`, whose corresponding private creator data element has a value equals to `Private tag creator`, and where `yy` matches any hex digit, `X` or `@` (e.g. `0023{ABC}XX` represents data elements whose group number is `0023` and private creator is `ABC`)
* `{VR}` where `VR` is a valid value representation (e.g. `{PN}` represents all PN data elements)

A tag path pattern can optionnally start with:

* `*/` to search for data elements that match the tag path pattern no matter where it appears (e.g. `*/PatientName` represents Patient Name data elements anywhere it occurs)
* `+/` to search for data elements that match the tag path pattern except in the top level (e.g. `+/PatientName` represents Patient Name data elements in any sequence level except the top level)
* If it does not start with `*/` or `+/`, it searches for data elements that match the tag path pattern in the top level only (e.g. `StudyDescription` represents the Study Description data element in the top level)

## Examples

* `+/*Date` represents data element whose tag keyword ends with "Date" that are not in the top level
* `*/XXX@XXXX` represents data elements whose group is an odd number, no matter where it appears
* `0010XXXX` represents data elements whose group number is `0010` in the top level
* `+/Sequence.Keyword` represents data elements whose tag keyword is `Keyword`, contained in a sequence data element whose tag keyword is `Sequence` and that is not in the top level
* `0023{ABC}XX` represents private data elements whose group number is `0023` and private creator is `ABC`
* `*/{DT}` represents data elements whose VR is `DT` no matter where they appear
