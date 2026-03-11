# Use pgvector official image (postgres:16 + pgvector pre-installed)
FROM pgvector/pgvector:pg16

# Copy init scripts
COPY init.sql /docker-entrypoint-initdb.d/

EXPOSE 5432
