#!/usr/bin/env bash

jq "$@" | bat -l json
