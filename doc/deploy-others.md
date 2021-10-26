# Other Deployment Patterns

The first Orthanc server, the first *change pooler* and the *de-identifier* can be deployed either on AWS, or on premises if you choose to send already de-identified data to the cloud (note that using Amazon Rekognition to detect burned-in annotations in the pixel data will send original frames to the cloud).

Moreover, if you already have an on-premises system to de-identify medical images, you can choose to not deploy the first Orthanc server and the de-identifier, and forward the medical images directly to the second Orthanc server.

To deploy only the self-service portal on AWS (second Orthanc server, website and website workers components), follow the same instructions than [Deploy all components on AWS](deploy-all-aws.md) and choose `Self-service portal only` in **Deployment pattern**.

Then, you can either sent already de-identified DICOM files to the second Orthanc server, or provision Docker containers on-premises to run the first Orthanc server, the first change pooler and the de-identifier, using the Docker images available in the Amazon ECR repositories created by AWS CloudFormation.
