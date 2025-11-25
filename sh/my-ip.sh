#!/usr/bin/env bash

do_print() {
    local method=$1
    local address=$2

    if [[ -n $address ]]; then
        echo "Method: $method"
        echo "Address: $address"
        exit 0
    fi
}

method="$1"
address=""
if [[ "$method" == "local" ]]; then
    address=$(
        ifconfig \
        | grep -Eo 'inet (addr:)?([0-9]*\.){3}[0-9]*' \
        | grep -Eo '([0-9]*\.){3}[0-9]*' \
        | grep -v '127.0.0.1')
    do_print $method $address
fi

if which piactl > /dev/null && [[ $(piactl get connectionstate) == 'Connected' ]]; then
    method="ipinfo"
    address=$(curl -s ipinfo.io | jq -r '.ip')
    do_print $method $address
fi

method="opendns"
address=$(dig +short myip.opendns.com @resolver1.opendns.com)
do_print $method $address

method="ipinfo"
address=$(curl -s ipinfo.io | jq -r '.ip')
do_print $method $address

do_print "all" "unknown"
