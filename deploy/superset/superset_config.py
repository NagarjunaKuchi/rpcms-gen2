# DEV configuration for the RPCMS dashboard (Apache Superset). Fixed secrets: local use only.
# A real deployment follows farmer-registry: Superset is a shared environment service with Keycloak sign-in
# (AUTH_OAUTH), real secrets, and the dashboard imported by a job. None of that is configured here.
import os

SECRET_KEY = os.environ["SUPERSET_SECRET_KEY"]
SQLALCHEMY_DATABASE_URI = "postgresql+psycopg2://superset_user:{}@postgres:5432/superset".format(os.environ["SUPERSET_DB_PASSWORD"])
TALISMAN_ENABLED = False
WTF_CSRF_ENABLED = True
