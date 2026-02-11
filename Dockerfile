FROM geopython/pygeoapi:latest

# Copy custom config
COPY pygeoapi.config.yml /pygeoapi/local.config.yml

# Copy custom process plugins
COPY processes/ /pygeoapi/ogc_processes/
RUN touch /pygeoapi/ogc_processes/__init__.py

# Make custom plugins importable by Python
ENV PYTHONPATH="/pygeoapi"

EXPOSE 80
