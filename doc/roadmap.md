# Roadmap

We would love to hear from you about this solution, and how it can be better meet your requirements. Feel free to create an Issue in this GitHub repository, or to contact your AWS account team.

Here is a list of evolutions or new features that are considered for future versions:

* Allow researchers to generate pre-signed, user-specific temporary URL to access the DICOMweb plugin of the second Orthanc server. This will allow to interface the Research PACS with DICOM viewers using DICOMweb, if the DICOM viewers don't support sending a custom HTTP header Authorization in their requests, while auditing user activity.

* Augment medical images with non-DICOM health records, such as chest CT scans with COVID-19 severity characterization. Research PACS administrators would be able to send CSV files, the de-identifier would replaces patient identifiers with the same values than in DICOM files, which would allow to reconcialiate DICOM instances and health records.

* Integrate an advanced DICOM viewer in the self-service portal, such as OHIF, in the Preview page.

* Allow researchers to download an entire study from the Search page results. Note that it is already possible to download a DICOM instance as a DCM file, or a series as a ZIP file.

* Allow researchers to enter a free text when logging or querying the self-service portal, to reconciliate user activity in the self-service portal with authorizations granted by "review boards" to these researchers for specific research studies.
