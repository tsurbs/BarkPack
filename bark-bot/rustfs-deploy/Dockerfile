FROM rustfs/rustfs:latest

# Use the official entrypoint. Configure entirely via Railway env vars:
#   RUSTFS_ACCESS_KEY  = your access key
#   RUSTFS_SECRET_KEY  = your secret key
#   RUSTFS_ADDRESS     = :${PORT}  (set via Railway variable reference)
#
# Add a Railway volume mounted at /data for persistent storage.

USER root
ENTRYPOINT []
CMD ["/bin/sh", "-c", "rustfs --address :${PORT:-9000} --access-key ${S3_ACCESS_KEY_ID:-rustfsadmin} --secret-key ${S3_SECRET_ACCESS_KEY:-rustfsadmin} /data"]
