from sqlalchemy.orm import declarative_base

# The single declarative base for the whole app. Every model module (elections,
# monitor, shared) imports it from here — never calls declarative_base() itself.
# One Base means one MetaData, and MetaData is what Alembic diffs against the
# database; three separate registries would make autogenerate think two-thirds
# of the schema no longer exists.
Base = declarative_base()
