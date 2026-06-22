# Intro

This README file will document the steps needed to build such a Docker and template from scratch, so that it can be used to start later a new project.

# When creating a new project

## .bashrc and .env

Copy the example of these files and modify if needed.
```
cp .bashrc.example .bashrc
cp .env.example .env
```

And then you need to add in `.env` these
```
# for the form
MASTER_ADMIN_USER=""
MASTER_ADMIN_PASSWORD=""
```s

And then need to copy the database from local to the VPS
```
scp sqlite_database_teams_01_250505.db abuzatu@194....:/home/abuzatu/Work/priceless/data/database/
```

And to make a backup from the VPS to the local computer
```
scp abuzatu@194....:/home/abuzatu/Work/priceless/data/database/sqlite_database_teams_01_250505.db /Users/abuzatu/Work/priceless/data/database/bk_from_Work/priceless/data/database/bk_from_VPS_sqlite_database_teams_01_250505_bk_250525_02.db
```

## Poetry

Usually they say you sould use poetry locally to create the first `pyproject.toml` and `poetry.lock`. But to be really safe and do not get any conflicts with local poetry, we first build the Docker without these files, just by installing poetry, then we ssh into docker and we run these commands. Any file created inside Docker appears also locally. So we have to comment out some lines. 

In `Dockerfile` comment out
```
# Copy poetry files and install
COPY pyproject.toml poetry.lock $WORKDIR/
RUN poetry install
```

In `bin/docker-start.sh` comment out
```
docker exec -i -t $PROJECT_NAME poetry install
```

Build the Docker image
```
make build
```

Note, getting a warning
```
3 warnings found (use docker --debug to expand):
 - LegacyKeyValueFormat: "ENV key=value" should be used instead of legacy "ENV key value" format (line 18)
 - UndefinedVar: Usage of undefined variable '$PYTHONPATH' (line 19)
 - LegacyKeyValueFormat: "ENV key=value" should be used instead of legacy "ENV key value" format (line 19)

What's next:
    View a summary of image vulnerabilities and recommendations → docker scout quickview 
```

Start the docker container
```
make start
```
Ssh into the container
```
make ssh
```
Inside you will see like
```
jumbo@f830073bfa07:/opt/app$
```
The `poetry` command is installed, as we can see
```
poetry
```
Create a new poetry environment with
```
poetry init
```
There are some interactive questions like
```
jumbo@f830073bfa07:/opt/app$ poetry init

This command will guide you through creating your pyproject.toml config.

Package name [app]:  
Version [0.1.0]:  
Description []:  template for Docker with FastAPI
Author [None, n to skip]:  Adrian Buzatu
License []:  
Compatible Python versions [^3.11]:  

Would you like to define your main dependencies interactively? (yes/no) [yes] no
Would you like to define your development dependencies interactively? (yes/no) [yes] no
Generated file

[tool.poetry]
name = "app"
version = "0.1.0"
description = "template for Docker with FastAPI"
authors = ["Adrian Buzatu"]
readme = "README.md"

[tool.poetry.dependencies]
python = "^3.11"


[build-system]
requires = ["poetry-core"]
build-backend = "poetry.core.masonry.api"


Do you confirm generation? (yes/no) [yes] yes
```
The result is the creation of a `pyproject.toml` file, which looks like above. To create the `poetry.lock` file run
```
poetry install
```
Exit the ssh with `exit`.

Uncomment in files `Dockerfile` the two lines in `poetry`. 
```
COPY pyproject.toml poetry.lock $WORKDIR/
RUN poetry install
```
and in `bin/docker-start.sh` uncomment
```
# docker exec -i -t $PROJECT_NAME poetry install
```

Remove the image and container with
```
make remove
```
Start again and this time to install `poetry` too. That means first run
```
make build
make start
```

## Then add packages to poetry

In another tab in the same terminal to
```
make ssh
```
and there add new packages with
```
poetry add numpy
poetry add pandas
poetry add matplotlib
poetry add seaborn
poetry add jupyter
poetry add ipython
poetry add python-dotenv[cli]
poetry add coloredlogs
# Dagster
poetry add dagster dagster-postgres dagster-webserver
poetry add requests

# Core ibis
poetry add ibis-framework

# PostgreSQL dependencies
poetry add psycopg2-binary  # PostgreSQL adapter
poetry add 'ibis-framework[postgres]'

# SQLite dependencies
poetry add 'ibis-framework[sqlite]'

# DuckDB
poetry add 'ibis-framework[duckdb]'
```
And so on. This will update `pyproject.toml` and `poetry.lock` and gets them installed, so you can use right away. 

To uninstall a package
```
make remove dotenv
```


# You can run in Jupyter Notebook or iPython or scripts

## dotenv

We use `dotenv` to load the `.env` file (which we do not place in Git) with our environment variables, including API keys that must not be public. This way they are accessible in the scripts. For this we need

```
poetry add python-dotenv[cli]
```

And when running instead of `poetry run` we use `poetry run dotenv run`. The `.env` file looks like this
```
STAGE=DEVELOPMENT
TIMEZONE=UTC

# production example how to include API from a service we use
INPUT_SERVICE_URL = https://input-service.service-provider.io
INPUT_SERVICE_API_KEY = K88dfdkTsdsfd772dfdfd98374k7dGIF

API_KEY=foo
PYTHONPATH=src
LOGGING_LEVEL=DEBUG
```
And we can see that in both `Jupyter Notebook` or `iPython` we can have access to these environment variables with
```
import os
os.environ
```
and the variables appear there, for example
```
In [1]: import os

In [2]: os.environ
Out[2]: 
environ{'PATH': '/home/jumbo/.cache/pypoetry/virtualenvs/app-tq7C0_9c-py3.11/bin:/.local/share/pypoetry/bin/poetry:/home/jumbo/.local/bin:/home/jumbo/.poetry/bin:/home/jumbo/.local/share/pypoetry:/usr/local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin',
        'HOSTNAME': 'fd222f0cdf41',
        'TERM': 'xterm',
        'LANG': 'C.UTF-8',
        'GPG_KEY': 'A035C8C19219BA821ECEA86B64E628F8D684696D',
        'PYTHON_VERSION': '3.11.2',
        'PYTHON_PIP_VERSION': '22.3.1',
        'PYTHON_SETUPTOOLS_VERSION': '65.5.1',
        'PYTHON_GET_PIP_URL': 'https://github.com/pypa/get-pip/raw/d5cb0afaf23b8520f1bbcfed521017b4a95f5c01/public/get-pip.py',
        'PYTHON_GET_PIP_SHA256': '394be00f13fa1b9aaa47e911bdb59a09c3b2986472130f30aa0bfaf7f3980637',
        'WORKDIR': '/opt/app',
        'PYTHONPATH': 'src',
        'GIT_COMMIT_HASH': '',
        'HOME': '/home/jumbo',
        'VIRTUAL_ENV': '/home/jumbo/.cache/pypoetry/virtualenvs/app-tq7C0_9c-py3.11',
        'STAGE': 'DEVELOPMENT',
        'TIMEZONE': 'UTC',
        'INPUT_SERVICE_URL': 'https://input-service.service-provider.io',
        'INPUT_SERVICE_API_KEY': 'K88dfdkTsdsfd772dfdfd98374k7dGIF',
        'API_KEY': 'foo',
        'LOGGING_LEVEL': 'DEBUG'}

In [3]: 
```


## Jupyter Notebook

For Jupyter Notebook also its port `1336` must be added also in the `bin/docker-start.sh`.

Note though that for `Jupyter Notebook` it worked only after I did rebuilt the image and container. So you exit with
```
exit
```
and from the main repo
```
make remove
make build
make start
```

```
make notebook
```
You will see a message like this
```
./bin/notebook-start.sh
[I 12:11:57.166 NotebookApp] Authentication of /metrics is OFF, since other authentication is disabled.

  _   _          _      _
 | | | |_ __  __| |__ _| |_ ___
 | |_| | '_ \/ _` / _` |  _/ -_)
  \___/| .__/\__,_\__,_|\__\___|
       |_|
                       
Read the migration plan to Notebook 7 to learn about the new features and the actions to take if you are using extensions.

https://jupyter-notebook.readthedocs.io/en/latest/migrate_to_notebook7.html

Please note that updating to Notebook 7 might break some of your extensions.

[W 12:11:57.316 NotebookApp] WARNING: The notebook server is listening on all IP addresses and not using encryption. This is not recommended.
[W 12:11:57.316 NotebookApp] WARNING: The notebook server is listening on all IP addresses and not using authentication. This is highly insecure and not recommended.
[I 12:11:57.318 NotebookApp] Serving notebooks from local directory: /opt/app
[I 12:11:57.318 NotebookApp] Jupyter Notebook 6.5.3 is running at:
[I 12:11:57.318 NotebookApp] http://localhost:1335/
[I 12:11:57.318 NotebookApp] Use Control-C to stop this server and shut down all kernels (twice to skip confirmation).
[W 12:11:57.319 NotebookApp] No web browser found: could not locate runnable browser.
```
And now the terminal becomes blocked with the Jupyter Server. You will see printouts here (logs) as you do actions in Jupyter Notebook. You copy the url `http://localhost:1335/`, put it into a browser and then you can use the Notebooks. Note we have a folder `notebooks` where we have the convention to place the Jypyter Notebook files, which have extension `.ipynb`.

## iPython

Interactive Python is lighter and you can develop as in a Jypyter Notebook, but from the terminal. You can run the code up to some point and then continue from there. A huge productivity boost when debugging for tests.

```
make ipython
```

It starts a terminal like this
```
./bin/ipython-start.sh
Python 3.11.2 (main, Mar 17 2023, 02:54:19) [GCC 8.3.0]
Type 'copyright', 'credits' or 'license' for more information
IPython 8.11.0 -- An enhanced Interactive Python. Type '?' for help.

In [1]: 
```

You can add lines like this
```
In [1]: import numpy as np

In [2]: 
```
You exit with `Control` + `D`, or type `exit` followed by `Enter`.


## Scripts

Or we can run scripts from the command line with `python`

```
./bin/dev/docker-exec.sh poetry run dotenv run python ./bin/run/run_sum.py
```

or with `ipython`

```
./bin/dev/docker-exec.sh poetry run dotenv run ipython ./bin/run/run_sum.py
```

And these scripts also use the modules we have built.

# Create a new module to use

In the `src` folder we create the folder `utils` that is defined as a Python module by creating inside the file `__init__.py`. Inside the folder we can create several files, like `sum.py` where we create a few functions. `PYTHONPATH` is already set from the `Dockerfile` to `/opt/app/src` folder, so that we can do in Jupyter Notebook `import utils.sum` and then call the function with `utils.sum.my_sum(1.1, 2.2)`. If we need to modify the `PYTHONPATH` later without modifying the docker image, we can do so in the `.env` file.

At the end of include statements we add this 
```
# allow to use an updated module and use the change directly by refreshing the cell
# without having to restart the entire notebook
%load_ext autoreload
%autoreload 2
```
in order to pick up automatically changes in our module and when we rerun the cell, we pick up the changes in Jupyter. That way we do not have to rerun the entire Notebook, or restart Jupyter or rebuilt the image. So very powerful.

# Linting

We first add to poetry
```
poetry add black
poetry add flake8
poetry add pydocstyle
poetry add mypy
```
Then we run 
```
make lint
```
Which in turns runs
```
./bin/docker-exec.sh poetry run black src &&\
./bin/docker-exec.sh poetry run flake8 --max-line-length=90 src &&\
./bin/docker-exec.sh poetry run pydocstyle --convention=google &&\
./bin/docker-exec.sh poetry run mypy --follow-imports=skip --ignore-missing-imports --disallow-untyped-defs
```
Not all this uses the poetry environment and not the local machine poetry.

We can also make checks and transformations every time we run a commit, using th

# GitHub

By using VSCode we can commit to `GitHub` directly from VSCode.

# When there are conflicts in poetry.lock

When rebasing from `main` brandch and there are conflicts in `poetry.lock`,
remove the file via `poetry.lock`, ssh into the service via `make ssh`,
then recreate the file from `pyproject.toml` by running `poetry lock --no-update`.

# More shortcuts to MVPS

To login into server without password, as it uses the local key on my computer from ` ~/.ssh/config file` 
```
ssh mvps
```
To scp from the VPS server to my computer without password, to make a backup of the database with a script from my computer. 
```
scp mvps:/home/abuzatu/Work/priceless/data/database/sqlite_database_teams_01_250505.db /Users/abuzatu/Work/priceless/data/database/bk_from_VPS_sqlite_database_teams_01_250505_bk_250525_new.db
```

# To use tee windows on the MVPS server

To see all `tmux` seesions
```
tmux ls
```
I get answer
```
session_name_finance: 1 windows (created Sun Oct  1 13:50:58 2023)
session_name_health: 1 windows (created Sat Oct  7 19:49:36 2023)
session_name_motion: 1 windows (created Wed Oct 25 14:31:12 2023)
session_name_solar: 1 windows (created Sat Oct  7 19:49:01 2023)
```
To go into one of them 
```
tmux attach -t session_name_finance
```
or shorter version
```
tmux a -t session_name_finance
```
Once you're in a session, you can:
* Use `Ctrl+b d` to detach from the session (it will keep running in the background)
* Use `Ctrl+b c` to create a new window
* Use `Ctrl+b n` to go to the next window
* Use `Ctrl+b p` to go to the previous window
* Use `Ctrl+b &` to kill the current window
* Use `Ctrl+b [` to enter scroll mode (use arrow keys to scroll, press q to exit)

To create a new session called `session_name_priceless`:
```
tmux new -s session_name_priceless
```
Then go to the folder and start streamlit
```
cd priceless
make streamlit
```
Then detach to let it run
* Use `Ctrl+b d` to detach from the session (it will keep running in the background)

Later to attach to the existing session
```
tmux a -t session_name_priceless
```

# How to investigate disk space where it is used

Check the general usage
```
abuzatu@vps:~/Work/priceless/data/database$ df -h
Filesystem                         Size  Used Avail Use% Mounted on
tmpfs                              593M  8.7M  584M   2% /run
/dev/mapper/ubuntu--vg-ubuntu--lv   72G   48G   22G  70% /
tmpfs                              2.9G     0  2.9G   0% /dev/shm
tmpfs                              5.0M     0  5.0M   0% /run/lock
/dev/sda2                          2.0G  252M  1.6G  14% /boot
tmpfs                              593M  4.0K  593M   1% /run/user/1000
```

Check individual ones
```
sudo du -h --max-depth=1 / 2>/dev/null | sort -hr | head -15
54G	/
41G	/var
4.8G	/usr
4.6G	/home
1.4G	/snap
252M	/boot
8.7M	/run
6.3M	/etc
84K	/tmp
64K	/root
16K	/opt
16K	/lost+found
4.0K	/srv
4.0K	/mnt
4.0K	/media
```
Let's check what is inside folder var. It is `/var/lib/docker` that is using 39 GB. Check docker
```
docker system df
TYPE            TOTAL     ACTIVE    SIZE      RECLAIMABLE
Images          11        8         26.27GB   7.681GB (29%)
Containers      8         1         168.5MB   146.4MB (86%)
Local Volumes   0         0         0B        0B
Build Cache     192       0         7.771GB   7.771GB
```
So from 39 GB I can reclaim already 15 GB. 
Remove all stopped containers
```
docker container prune
```
Remove all not used
```
docker system prune -a --volumes
abuzatu@vps:/var/lib$ docker system prune -a --volumes
WARNING! This will remove:
  - all stopped containers
  - all networks not used by at least one container
  - all anonymous volumes not used by at least one container
  - all images without at least one container associated to them
  - all build cache

Are you sure you want to continue? [y/N] 
```