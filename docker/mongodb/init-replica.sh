#!/bin/sh
set -eu

MONGO_HOST="${MONGO_HOST:-mongodb:27017}"
REPLICA_SET_NAME="${REPLICA_SET_NAME:-rs0}"
REPLICA_MEMBER_HOST="${REPLICA_MEMBER_HOST:-${MONGO_HOST}}"

echo "Waiting for MongoDB at ${MONGO_HOST}..."
until mongosh --host "${MONGO_HOST}" --quiet --eval "db.adminCommand({ ping: 1 }).ok" >/dev/null 2>&1; do
  sleep 2
done

echo "Initializing replica set ${REPLICA_SET_NAME} if needed..."
mongosh --host "${MONGO_HOST}" --quiet <<EOF
try {
  const status = rs.status();
  if (status.ok === 1) {
    print("Replica set already initialized.");
  }
} catch (error) {
  rs.initiate({
    _id: "${REPLICA_SET_NAME}",
    members: [{ _id: 0, host: "${REPLICA_MEMBER_HOST}" }],
  });
}
EOF

echo "Waiting for replica set ${REPLICA_SET_NAME} to become writable..."
until mongosh --host "${MONGO_HOST}" --quiet --eval "quit(db.hello().isWritablePrimary ? 0 : 1)" >/dev/null 2>&1; do
  sleep 2
done

echo "Replica set ${REPLICA_SET_NAME} is ready."
