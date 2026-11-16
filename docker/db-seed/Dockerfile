# RPCMS db-seed -- thin image on the published registry-platform db-seed base.
# Replaces the reference registry's seed with the refugee extension's metadata.
ARG RP_VERSION=0.0.0-develop.716
FROM openg2p/openg2p-registry-db-seed:${RP_VERSION}

RUN rm -rf /seed/meta_data/* /seed/awe_meta_data/* /seed/templates/* /seed/seed-data/*

COPY refugee-extension/src/openg2p_registry_refugee_extension/meta_data/     /seed/meta_data/
COPY refugee-extension/src/openg2p_registry_refugee_extension/awe_meta_data/ /seed/awe_meta_data/
COPY refugee-extension/src/openg2p_registry_refugee_extension/templates/     /seed/templates/
