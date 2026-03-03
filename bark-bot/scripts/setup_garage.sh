#!/bin/bash
node_id=$(docker exec barkbot_garage /garage status | awk '/NO ROLE ASSIGNED/{print $1}')
echo "Node ID: $node_id"
if [ -n "$node_id" ]; then
    docker exec barkbot_garage /garage layout assign -z garage -c 1G $node_id
    docker exec barkbot_garage /garage layout apply --version 1
fi

echo "Creating keys..."
docker exec barkbot_garage /garage key create barkbot > garage_keys.txt

echo "Creating bucket..."
docker exec barkbot_garage /garage bucket create barkbot-public

echo "Assigning permissions..."
docker exec barkbot_garage /garage bucket allow --read --write --owner barkbot-public --key barkbot

echo "Setting website config..."
docker exec barkbot_garage /garage bucket website --allow --index-document index.html barkbot-public

echo "Setup complete. Keys:"
cat garage_keys.txt
