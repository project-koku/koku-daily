# koku-daily
A python application for gathering daily internal reporting data from a koku deployment


## Development

To get started developing with koku-daily first clone a local copy of the git repository:
```
git clone https://github.com/project-koku/koku-daily.git
````

This project is developed uses Pipenv. Many configuration settings can be read in from a ``.env`` file. To configure, do the following:

1. Copy `example.env` into a `.env`
2. Obtain database values and update the following in your `.env`:
```
DATABASE_HOST=localhost
DATABASE_PORT=15432
DATABASE_USER=postgres
DATABASE_PASSWORD=postgres
PGADMIN_PASSWORD=postgres
DATABASE_NAME=postgres
NAMESPACE=NAMESPACE
EMAIL_USER=EMAIL_USER
EMAIL_PASSWORD=EMAIL_PASSWORD
EMAIL_GROUPS={"engineering": "email1@foo.com", "marketing": "email2@foo.com"}
```
3. Then project dependencies and a virtual environment can be created using :
```
pipenv install --dev
```
4. To activate the virtual environment run :
```
pipenv shell
```
1. Install the pre-commit hooks for the repository :
```
pre-commit install
```

## Deploying to OpenShift

The `koku-daily` runs as a *CronJob* on OpenShift creating data daily. You can deploy it to OpenShift as follows:

1. Login to OpenShift
```
oc login
```
2. Select your project
```
oc project koku
```
3. Copy `openshift/example.parameters.properties` into a `openshift/parameters.properties`
4. Update the values within `openshift/parameters.properties`
5. Create OpenShift resources
```
oc process --param-file openshift/parameters.properties  -f openshift/ |  oc create -f -
```

_Note:_ Delete OpenShift resources with the following command:
```
oc process --param-file openshift/parameters.properties  -f openshift/ |  oc delete -f -
```
