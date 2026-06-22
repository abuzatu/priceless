# FROM python:3.11.4-slim-buster
# FROM python:3.11.4-slim-bullseye
FROM python:3.11.4-slim-bookworm
RUN pip install --upgrade pip

RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get -y install curl build-essential libpq-dev openssh-client procps \
    wget gnupg2 unzip sudo \
    less \
    # emacs23-nox \
    cmake \
    pandoc \
    texlive-xetex texlive-fonts-recommended texlive-plain-generic \
    sqlite3 \
    wkhtmltopdf \
    libreoffice-calc libreoffice-common --no-install-recommends

# Print the version of SQLite3
RUN sqlite3 --version

# Download and install latest SQLite (3.44.2 as of December 2023)
# RUN wget https://www.sqlite.org/2023/sqlite-autoconf-3440200.tar.gz \
#     && tar xvfz sqlite-autoconf-3440200.tar.gz \
#     && cd sqlite-autoconf-3440200 \
#     && ./configure --prefix=/usr/local \
#     && make \
#     && make install \
#     && cd .. \
#     && rm -rf sqlite-autoconf-3440200* \
#     && ldconfig

# add if want to run GUI inside our docker from our local machine: x11vnc



ENV WORKDIR=/opt/priceless
# ENV PYTHONPATH=$PYTHONPATH:$WORKDIR/src
# ENV PYTHONPATH=$WORKDIR/src
ENV PYTHONPATH=/usr/local/lib/python3.11/site-packages
ENV PYTHONPATH=$WORKDIR/src:$PYTHONPATH
WORKDIR $WORKDIR

RUN groupadd --gid 1000 jumbo && \
    adduser --system jumbo --uid 1000 --gid 1000 && \
    # chown -R jumbo:jumbo $WORKDIR \
    usermod -aG sudo jumbo && \
    echo 'jumbo ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/jumbo && \
    chmod 0440 /etc/sudoers.d/jumbo && \
    # Create and set up home directory explicitly
    mkdir -p /home/jumbo && \
    chown jumbo:jumbo /home/jumbo

USER jumbo
ENV HOME=/home/jumbo

# Set up bashrc
COPY --chown=jumbo:jumbo .bashrc $WORKDIR
RUN ln -s $WORKDIR/.bashrc $HOME/.bashrc

RUN curl -sSL https://install.python-poetry.org | python3 -
ENV PATH="/.local/share/pypoetry/bin/poetry:/home/jumbo/.local/bin:/home/jumbo/.poetry/bin:/home/jumbo/.local/share/pypoetry:${PATH}"

# Copy poetry files and install
COPY pyproject.toml poetry.lock README.md $WORKDIR/
#vRUN poetry config installer.modern-installation false
RUN poetry --version
# RUN poetry run pip install debugpy
# RUN poetry remove yfinance
# RUN poetry update

# to regenerate the lock file when
# RUN poetry lock --no-update 
# pyproject.toml changed significantly since poetry.lock was last generated.
# RUN poetry lock --no-update  # Regenerate the lock file
# now poetry install
RUN poetry install

# Playwright Chromium (system deps as root, browser binaries as jumbo)
USER root
RUN poetry run playwright install-deps chromium
USER jumbo
RUN poetry run playwright install chromium

# use Dockerignore
COPY --chown=jumbo:jumbo . $WORKDIR

ARG GIT_COMMIT_HASH
ENV GIT_COMMIT_HASH=${GIT_COMMIT_HASH}

