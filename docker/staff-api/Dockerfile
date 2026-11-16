# RPCMS (staff-api) -- thin image on the published registry-platform base.
# Build context = repo root. RP_VERSION pins the base image tag (see deploy/.env).
ARG RP_VERSION=0.0.0-develop.716
FROM openg2p/openg2p-registry-staff-api:${RP_VERSION}

ENV REGISTRY_EXTENSION_MODULE=openg2p_registry_refugee_extension

COPY refugee-extension/ /app/refugee-extension/
RUN pip install --no-cache-dir /app/refugee-extension

# WORKAROUND (upstream pin mismatch): the published staff-api base images
# (0.0.0-develop.716 and 1.2.1, checked) bundle iam-core@509f7ec, which imports
# openg2p_fastapi_common.utils.crypto, but the bundled openg2p-fastapi-common@02a8c18
# only has openg2p_fastapi_common.crypto -> ModuleNotFoundError at staff-api boot.
# Reinstall iam-core from a commit that matches (iam develop 8f02f18). --no-deps keeps
# every other package exactly as shipped in the base image.
ARG IAM_CORE_REF=8f02f18d4eec60949d204d37c74d1e03808e737c
RUN pip install --no-cache-dir --no-deps --force-reinstall \
      "git+https://github.com/openg2p/iam.git@${IAM_CORE_REF}#subdirectory=iam-core"
