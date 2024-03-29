# FLATMAN - FLexible Accuracy Testing MANager

## How to run

First create a (PostgreSQL) database named `fatman` and make sure the user running the server has access to it.

Then:

```sh
# Grab the code:
git clone ...

# Change the directory
cd flatman/

# Create a virtual environment and use it
virtualenv venv
source venv/bin/activate

# Install required packages
pip install -r requirements.txt

# Set the Flask application name
export FLASK_APP=fatman

# Create an initial configuration (including a custom secret key for the session cookies, will overwrite an existing `fatman.cfg` in your current directory)
flask createconfig

# Initialize the database (this is idempotent)
flask initdb

# Run the (development) server
FATMAN_SETTINGS=$PWD/fatman.cfg flask run

# Open the interface
xdg-open http://localhost:5000/admin/
```

## Web-Application Deployment

The web-frontend is based on AngularJS 2.0 + Bootstrap 3 and written in TypeScript.

To build/deploy it you need the following packages on your system:

* NodeJS
* NPM

After that, you can bootstrap it as follows:

```sh
# let NPM install all required JavaScript/TypeScript packages (in ./node_modules)
npm install

# setup required typings for TypeScript
./node_modules/.bin/typings install

# Build the JavaScript bundles
./node_modules/.bin/webpack
```

After that, the web-application should be available on:

  http://localhost:5000/app

Provided that the following things are set up and running:
* port-forward the postgresql server to the local host (`ssh -L 5432:localhost:5432 172.23.64.223`)
* start the fatman server locally (`FATMAN_SETTINGS=$PWD/fatman.cfg ./manage.py runserver -p 5000`) with the appropriate `DATABASE_HOST` in the config.
* start the Celery worker queue: `celery -A fatman.tasks -l INFO worker`
