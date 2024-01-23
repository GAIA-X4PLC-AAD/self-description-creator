# Introduction

This repository contains a Python Tool that can be used to automate the process of creating _Gaia-X Self Descriptions_ based on
Claims provided as an input. In addition to just creating Self Descriptions, they can also be automatically sent to a configured
_XFSC Federated Catalogue_ instance.

A potential use case is to run the tool decentralized in the infrastructure of a (Service) Provider to enable an automated 
workflow for creation of Self Descriptions for new Services or Data Assets which are to be offered to other Participants in a 
Gaia-X Ecosystem.

There are different ways to provide the input and retrieve the created Self Description. The tool allows interaction via a
simple API, but is also able to process Claims automatically that are read from filesystem. More information on this can be
found in the section [Operating modes](#operating-modes).

![Usage](docs/SD%20Creator%20Usage.png "Use Cases")

_Note: The tool is actively used within our project and may therefore be continuously adjusted._

## Gaia-X compliance

The current version of the Gaia-X Architecture
Document ([22.10 Release](https://docs.gaia-x.eu/technical-committee/architecture-document/22.10/)) defines that a Self
Description qualified as Gaia-X compliant must be submitted to a Gaia-X Compliance Service instance and the resulting Compliance
Credential must be inserted into the Self Description. This seems to only apply to Self Descriptions where the types contained
in the `credentialSubject` of the provided Verifiable Credentials are defined by Gaia-X Trust Framework (see the following
[Issue](https://gitlab.com/gaia-x/lab/compliance/gx-compliance/-/issues/50)). Self Descriptions that contain a
Federation-specific type _do not_ seem to require a corresponding Compliance Credential.

Self Descriptions created by this tool currently _cannot_ become Gaia-X compliant, because a submit of the Self Description
to a
Compliance Service instance has not been implemented so far.
Regardless of that, the Self Descriptions are accepted by the current implementation of the XFSC Federated Catalogue
independent of
whether they contain a Compliance Credential or not.

## XFSC Federated Catalogue support

The tool has been tested with the current implementation of the
[XFSC Federated Catalogue](https://gitlab.eclipse.org/eclipse/xfsc/cat/fc-service) in Version 1.1.1. The Keycloak client used
within the tool to retrieve access tokens required for interaction with the Federated Catalogue API is configured to use
the same Keycloak Realm as the Catalogue.

# Getting Started

## Usage

### Local test via docker-compose

This repository contains a docker-compose file to simplify testing the application on the local system. Therefore, the
easiest way to get the application up and running is by using docker-compose:

```console
$ docker-compose up
```

Before you start using the docker-compose file, please consider the following description of the exposed environment
variables that describes the mandatory and optional variables that must be set to adapt the application behavior.

### Environment variables

The following environment variables can be set to adapt the behavior of the application e.g. when running inside a
container.

| Name                                   | Type   | Optional | Default | Description                                                                                                          |
|----------------------------------------|--------|----------|---------|----------------------------------------------------------------------------------------------------------------------| 
| CREDENTIAL_ISSUER                      | String |          |         | The issuer set inside the Self Description. It will not be checked, whether the issuer is valid                      |
| CREDENTIAL_ISSUER_PRIVATE_KEY_PEM_PATH | String |          |         | Path to the private key (PEM format) of the Issuer certificate that is used to create a Proof for a Self Description |
| CLAIM_FILES_DIR                        | String | x        | _data_  | Folder where Claim files should be read from                                                                         |
| CLAIM_FILES_POLL_INTERVAL_SEC          | Float  | x        | _2.0_   | The poll interval used to check the `CLAIM_FILES_DIR` for new files                                                  | 
| CLAIM_FILES_CLEANUP_MAX_FILE_AGE_DAYS  | Int    | x        | _1_     | The maximum age of processed files in the folder `CLAIM_FILES_DIR` to decide whether they should be cleaned up       |
| KEYCLOAK_SERVER_URL                    | String | x        | ""      | The URL of the Keycloak Server which is used to retrieve JTWs to access the XFSC Federated Catalogue                 |
| KEYCLOAK_CLIENT_SECRET                 | String | x        | ""      | The secret for the client `federated_catalogue`                                                                      |
| FEDERATED_CATALOGUE_USER_NAME          | String | x        | ""      | The Keycloak user which has appropriate permissions to add Self Description to the Federated Catalogue.              |
| FEDERATED_CATALOGUE_USER_PASSWORD      | String | x        | ""      | Password for the Keycloak user                                                                                       |
| FEDERATED_CATALOGUE_URL                | String | x        | ""      | The URL of the XFSC Federated Catalogue                                                                              |
| USE_LEGACY_CATALOGUE_SIGNATURE         | String | x        | False   | Use the legacy XFSC Federated Catalogue signature                                                                    |
| OPERATING_MODE                         | String | x        | _API_   | Describes the operating mode of the application. Can be either "API" or "HYBRID"                                     |

### Operating modes

The application can run in two operating modes which can be set via the environment variable `OPERATING_MODE`.

* `API`: In this mode, the application provides a HTTP API to create Self Descriptions and to write the created SDs to the
  configured XFSC Federated Catalogue.
* `HYBRID`: In this mode, the application provides a HTTP API but also starts a background task that monitors a specific directory
  for JSON files containing Claims and creates SDs for them which are automatically send to the configured XFSC Federated
  Catalogue. Please see the environment variables starting with `CLAIM_FILES_`.

### Interaction with XFSC Federated Catalogue

To enable interaction with a XFSC Federated Catalogue instance, certain environment variables having the following prefixes
must be configured:

* `KEYCLOAK_`
* `FEDERATED_CATALOGUE_`

### Postman Collection

This repository also contains a Postman collection that allows you to test the exposed HTTP endpoints.

## Development

In the following you'll find instructions to consider in the case you plan to apply changes to the application source code.

### Update requirements

Please make sure to update the used dependencies in the file `requirements.txt` to make the source code portable. This allows
others developers to create a Python Virtual Environment that contains the required dependencies to execute the code.

To make it easier maintaining the requirements, the tool `pipreqs` can be used.

```console
$ pip install pipreqs
$ pipreqs .
```

### Build and Test

To run the code on your local system, an appropriate Python environment must be configured which contains the required
dependencies.
The dependencies can be installed with the following command:

```console
$ pip install -r requirements.txt
```

## Deployment

To deploy the application in a Kubernetes Cluster there is also a Helm Chart available in the `helm/` directory.

### Installing the Chart

To install the chart with the release name `self-description-creator`:

```console
$ helm upgrade --install self-description-creator helm/self-description-creator
```

### Configuration

The following table lists the _most relevant_ configurable parameters of the Helm Chart and their default values (for more
information see `values.yaml`).

| Value                                | Description                                                                                                                                                                                           | Optional | Default             |
|--------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|----------|---------------------|
| `image.repository`                   | The application image repository                                                                                                                                                                      |          | ""                  |
| `image.tag`                          | Overrides the Keycloak image tag whose default is the chart version                                                                                                                                   |          | ""                  |
| `volume.storageClassName`            | The k8s Storage Class to be used when setting the application `OPERATING_MODE` to `HYBRID`. See detailed information in the following section                                                         | x        | `""`                |
| `volumeMounts.mountPath`             | Optionally override the fully qualified name                                                                                                                                                          | x        | `/mnt/data`         |
| `container.main.env`                 | Provide environment variables to the Pod. Example: `container.main.env.KEYCLOAK_SERVER_URL=<value>`                                                                                                   | x        | See `values.yaml`.  |
| `ingress.className`                  | The className of the Ingress                                                                                                                                                                          | x        | nginx               |
| `ingress.enabled`                    | If `true`, an Ingress is created. In this case, the following ingress parameters should be provided as well (according to your environment)                                                           | x        | true                |
| `ingress.hosts[0].host`              | Host for the Ingress rule	                                                                                                                                                                            | x        | chart-example.local |
| `ingress.hosts[0].paths[0].path`     | Path for the Ingress rule                                                                                                                                                                             | x        | /                   |
| `ingress.hosts[0].paths[0].pathType` | Path Type for the Ingress rule`                                                                                                                                                                       | x        | Prefix              |
| `federatedCatalogue.user.name`       | Matches the environment variable listed above. Injects the value into the Pod via a Secret                                                                                                            |          | ""                  |
| `federatedCatalogue.user.password`   | Matches the environment variable listed above. Injects the value into the Pod via a Secret                                                                                                            |          | ""                  |
| `keycloak.realm.client_secret`       | Matches the environment variable listed above. Injects the value into the Pod via a Secret                                                                                                            |          | ""                  |
| `credentialIssuer.privateKeyPem`     | The private key referenced via the environment variable `CREDENTIAL_ISSUER_PRIVATE_KEY_PEM_PATH`. Key will be injected into the Pod as a Secret file and the path to the file will be set accordingly |          | ""                  |

Specify each parameter using the `--set key=value[,key=value]` argument to `helm upgrade`. The value
`credentialIssuer.privateKeyPem` should be read directly from file via `--set-file key=<file_path>` to avoid issues due to
newlines contained in the file.

_Important: Please consider the mandatory environment variables listed above._

### Using `OPERATING_MODE = HYBRID`

In case you want to deploy the application with `OPERATING_MODE = HYBRID` inside a cluster e.g. to process Claim files that are
written by other Pods, it is necessary to provide a suitable Kubernetes Storage Class via the Helm Value
`volume.storageClassName`. When doing so, a Volume gets attached to the pod which can be shared with the Pods that create
the Claim files. The PVC name to be used to mount the same Volume by other Pods can be found in the file `helm/values.yaml` in
the value `volume.claimName`.

_Important: The Storage Class must support the Volume access mode `ReadWriteMany`._

# Contribute

The code was initially developed by msg systems AG.

Feel free to contribute to the code and open a Pull Request.

# License

MIT License - see [License](LICENSE).
