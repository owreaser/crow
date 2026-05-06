# crow 🐦‍⬛
A way to define and manage your docker containers all in one place.

This code is made for my use case and may not be exactly what you want it to be.
Sorry.

## Installation
Make sure the pyyaml package is installed for python:
```sh
# pip:
pip install pyyaml

# pacman:
pacman -S python-yaml

# apt:
apt install python3-yaml
```

If you want to use crow as a command line tool, you can copy the `crow.py`
file to `/local/local/bin/` or something. So sophisticated, I know. Another
option is to keep the `crow.py` file in a specific place and add something like
`alias crow="sudo python3 /path/to/crow.py"` in your `.bashrc` or equivalent.

## Usage
Then, once you initially run `crow`, a configuration file will be created at
`/etc/crow.d/crow.conf`. You can control where your container configuration and
outputted files will be.

To generate the docker-compose and nginx output files, you can run `crow generate`.
To start the docker containers, run `crow up`, or `crow up -b` if you need to
build the containers.

To get a list of all commands that can be used with crow, you can run the `crow`
script without any arguments.

## Container Configuration
Container configuration files are yaml files that are placed in the directory
specified by the `container_folder` option in `crow.yaml`. They all follow the
same basic format:
```yaml
# This can be anything, but MUST BE UNIQUE.
# Multiple containers can be defined in the same file, or they can be spread
# out across several files. Whatever works best for you.
container_name:
  # One of these two options must be set for the configuration to be valid!
  # All other config options are optional!
  build: "/path/to/build-dir/" # This folder contains the Dockerfile file
  image: "docker/image:latest"

  # Makes the container use Cloudflare's DNS, instead of systemd-resolved or
  # whatever else your system uses
  dns_override: false

  # If it should fetch any new changes from git (recursing submodules) before
  # rebuilding the container. Useful if it's a container built from source
  # instead of a prebuilt image.
  git_pull: false
  git_pull: "only" # Go into the directory specified under the build option but don't build, just pull, for example if there's some static site served only with nginx and no backend.

  # Specify the port(s) to expose on the docker container
  port: 1234
  port: "1234:1234"
  port: [1234, "1234:1234"]
  port: "host" # Don't specify the specific port, instead use network_mode: host

  # Specify directory(ies) to pass through to the docker container
  dirs:
    "/path/to/source-dir": "/path/to/container-dir"

  # Optionally generate an additional nginx config
  nginx:
    host: "domain.example.com"

    # Whether or not to enable HTTP(S) protocols. One of these must be enabled.
    http: false
    https: true

    # A path to a file to include for the nginx config. Must be set if HTTPS is
    # enabled. Assumes the following two settings are set in that file:
    # ssl_certificate /etc/ssl/certs/domain.example.com.crt;
    # ssl_certificate_key /etc/ssl/private/domain.example.com.key;
    ssl_conf: "/path/to/domain.example.com-ssl-certs.conf"

    # The port to reverse-proxy requests to. Should be one specified in the
    # container configuration so it actually gets passed to the server
    port: 1234

    # Specify any static file directories nginx should serve
    static:
      "/static/": "/var/www/path/to/website-static/"
```
