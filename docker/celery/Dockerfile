# RPCMS (celery) -- thin image on the published registry-platform base.
# Build context = repo root. RP_VERSION pins the base image tag (see deploy/.env).
ARG RP_VERSION=0.0.0-develop.716
FROM openg2p/openg2p-registry-celery:${RP_VERSION}

ENV REGISTRY_EXTENSION_MODULE=openg2p_registry_refugee_extension

COPY refugee-extension/ /app/refugee-extension/
RUN pip install --no-cache-dir /app/refugee-extension

# WORKAROUND (upstream, observed on the published celery base): the worker dies at boot with
# "ModuleNotFoundError: No module named 'packaging'" (kombu's redis transport imports it, but the
# image does not ship it). Same family of fix as docker/staff-api: only add what is missing.
RUN pip install --no-cache-dir packaging

# PRECAUTION (not yet observed failing here): the staff-api base bundles an iam-core that does not match
# its fastapi-common (see docker/staff-api/Dockerfile). This celery image installs iam-core the same way,
# so pin it to the matching commit too. --no-deps leaves every other package as shipped.
ARG IAM_CORE_REF=8f02f18d4eec60949d204d37c74d1e03808e737c
RUN pip install --no-cache-dir --no-deps --force-reinstall \
      "git+https://github.com/openg2p/iam.git@${IAM_CORE_REF}#subdirectory=iam-core"
