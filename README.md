# Introduction

This repository contains a Python Tool that can be used to create Gaia-X Self Descriptions. In addition to just creating Self
Descriptions, they can also be automatically sent to a configured GXFS Federated Catalogue instance.

The tool provides an API based on Flask.

_Note: The code is still under development._

# Getting Started

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

## Usage

### Local test via docker-compose

This repository contains a docker-compose file to simplify testing the application on the local system. Therefore, the
easiest way to get the application up and running is by using docker-compose:

```console
$ docker-compose up
```

Please consider the following description of the exposed environment variables to adapt the application behavior.

### Environment variables

The following environment variables can be set to adapt the behavior of the application e.g. when running inside a
container.

| Name                                  | Type   | Optional | Default | Description                                                                                                          |
|---------------------------------------|--------|----------|---------|----------------------------------------------------------------------------------------------------------------------| 
| CREDENTIAL_ISSUER                     | String |          |         | The issuer set inside the Self Description. Usually a W3C DID                                                        |
| CREDENTIAL_ISSUER_PRIV_KEY_PEM_PATH   | String |          |         | Path to the private key (PEM format) of the Issuer certificate that is used to create a Proof for a Self Description |
| CLAIM_FILES_DIR                       | String | x        | _data_  | A folder related to the execution path of the script where to read Claim files from                                  |
| CLAIM_FILES_POLL_INTERVAL_SEC         | Float  | x        | _2.0_   | The poll interval used to check the `CLAIM_FILES_DIR` for new files                                                  | 
| CLAIM_FILES_CLEANUP_MAX_FILE_AGE_DAYS | Int    | x        | _1_     | The maximum age of processed files in the folder `CLAIM_FILES_DIR` to decide whether they should be cleaned up       |
| KEYCLOAK_SERVER_URL                   | String |          |         | The URL of the Keycloak Server which is used to retrieve JTWs to access the GXFS Federated Catalogue                 |
| FEDERATED_CATALOGUE_USER_NAME         | String |          |         | The Keycloak user which has appropriate permissions to add Self Desription to the Federated Catalogue                |
| FEDERATED_CATALOGUE_USER_PASSWORD     | String |          |         | Password for the Keycloak user                                                                                       |
| KEYCLOAK_CLIENT_SECRET                | String |          |         | The secret for the client `federated_catalogue`                                                                      |
| FEDERATED_CATALOGUE_URL               | String |          |         | The URL of the GXFS Federated Catalogue                                                                              |
| OPERATING_MODE                        | String | x        | _API_   | Describes the operating mode of the application. Can be either "API" or "HYBRID"                                     |

### Operating modes

The application can run in two operating modes which can be set via the environment variable `OPERATING_MODE`.

* `API`: In this mode, the application provides an API to create Self Descriptions and to write the created SDs to the
  configured GXFS Federated Catalogue.
* `HYBRID`: In this mode, the application provides an API but also starts a background task that monitors a specific directory
  for JSON files containing Claims and creates SDs for them which are automatically send to the configured GXFS Federated
  Catalogue. Please see the environment variables starting with `CLAIM_FILES_`.

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

| Parameter                            | Description                                                                                                                                   | Optional | Default                 |
|--------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------|----------|-------------------------|
| `image.repository`                   | The application image repository                                                                                                              |          | ""                      |
| `image.tag`                          | Overrides the Keycloak image tag whose default is the chart version                                                                           |          | ""                      |
| `volume.storageClassName`            | The k8s Storage Class to be used when setting the application `OPERATING_MODE` to `HYBRID`. See detailed information in the following section | x        | `""`                    |
| `volumeMounts.mountPath`             | Optionally override the fully qualified name                                                                                                  | x        | `/mnt/data/claim_files` |
| `container.main.env`                 | Provide environment variables to the Pod. Example: `container.main.env.KEYCLOAK_SERVER_URL=<value>`                                           | x        | See `values.yaml`.      |
| `ingress.className`                  | The className of the Ingress                                                                                                                  | x        | nginx                   |
| `ingress.enabled`                    | If `true`, an Ingress is created. In this case, the following ingress parameters should be provided as well (according to your environment)   | x        | true                    |
| `ingress.hosts[0].host`              | Host for the Ingress rule	                                                                                                                    | x        | chart-example.local     |
| `ingress.hosts[0].paths[0].path`     | Path for the Ingress rule                                                                                                                     | x        | /                       |
| `ingress.hosts[0].paths[0].pathType` | Path Type for the Ingress rule`                                                                                                               | x        | Prefix                  |
| `federatedCatalogue.user.name`       | Matches the environment variable listed above. Injects the value into the Pod via a Secret                                                    |          | ""                      |
| `federatedCatalogue.user.password`   | Matches the environment variable listed above. Injects the value into the Pod via a Secret                                                    |          | ""                      |
| `keycloak.realm.client_secret`       | Matches the environment variable listed above. Injects the value into the Pod via a Secret                                                    |          | ""                      |

Specify each parameter using the `--set key=value[,key=value]` argument to `helm upgrade`.

_Important: Please consider the mandatory environment variables listed above._

### Using `OPERATING_MODE = HYBRID`

In case you want to deploy the application with `OPERATING_MODE = HYBRID` inside a cluster e.g. to process Claim files that are
written by other Pods, it is necessary to provide a suitable Kubernetes Storage Class via the Helm Value
`volume.storageClassName`. When doing so, a Volume gets attached to the pod which can be shared with the Pods that create
the Claim files. The PVC name to be used to mount the same Volume by other Pods can be found in the file `helm/values.yaml` in
the value `volume.claimName`.

_Important: The Storage Class must support the Volume access mode `ReadWriteMany`._

## Postman Collection

This repository also contains a Postman collection that allows you to test the exposed HTTP endpoints.

# Contribute

The code was initially developed by msg systems AG.

Feel free to contribute to the code and open a Pull Request.

# License
MIT License - see [License](LICENSE).
