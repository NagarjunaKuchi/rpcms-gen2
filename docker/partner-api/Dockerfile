# RPCMS (partner-api) -- thin image on the published registry-platform base.
# Build context = repo root. RP_VERSION pins the base image tag (see deploy/.env).
ARG RP_VERSION=0.0.0-develop.716
FROM openg2p/openg2p-registry-partner-api:${RP_VERSION}

ENV REGISTRY_EXTENSION_MODULE=openg2p_registry_refugee_extension

COPY refugee-extension/ /app/refugee-extension/
RUN pip install --no-cache-dir /app/refugee-extension
