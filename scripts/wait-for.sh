#!/bin/sh

# The MIT License (MIT)
#
# Copyright (c) 2017 Eficode Oy
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.

VERSION="2.2.3"


TIMEOUT=15
QUIET=0
HOST=""
PORT=""
PROTOCOL="tcp"
COMMAND=""

echoerr() {
  if [ "$QUIET" -ne 1 ]; then
    echo "$@" >&2
  fi
}

usage() {
  echo "Usage: $0 [-q] [-t timeout] host:port|url [-- command args]" >&2
  exit 1
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    -q|--quiet)
      QUIET=1
      shift
      ;;
    -t|--timeout)
      if [ "$#" -lt 2 ]; then
        usage
      fi
      TIMEOUT="$2"
      shift 2
      ;;
    -t*)
      TIMEOUT="${1#-t}"
      shift
      ;;
    --timeout=*)
      TIMEOUT="${1#*=}"
      shift
      ;;
    --)
      shift
      COMMAND="$*"
      break
      ;;
    http://*|https://*)
      HOST="$1"
      PROTOCOL="http"
      shift
      ;;
    *:*)
      HOST="${1%%:*}"
      PORT="${1##*:}"
      PROTOCOL="tcp"
      shift
      ;;
    *)
      echoerr "Unknown argument: $1"
      usage
      ;;
  esac
done

if ! [ "$TIMEOUT" -ge 0 ] 2>/dev/null; then
  echoerr "Invalid timeout: $TIMEOUT"
  exit 1
fi

if [ -z "$HOST" ]; then
  echoerr "Host or URL is required"
  usage
fi

if [ "$PROTOCOL" = "tcp" ] && [ -z "$PORT" ]; then
  echoerr "Port is required"
  usage
fi

if [ "$PROTOCOL" = "http" ]; then
  if ! command -v curl >/dev/null 2>&1; then
    echoerr "curl command is missing!"
    exit 1
  fi
else
  if ! command -v nc >/dev/null 2>&1; then
    echoerr "nc command is missing!"
    exit 1
  fi
fi

START_TIME=$(date +%s)

while :; do
  if [ "$PROTOCOL" = "http" ]; then
    curl --max-time 1 -fsS "$HOST" -o /dev/null >/dev/null 2>&1
  else
    nc -w 1 -z "$HOST" "$PORT" >/dev/null 2>&1
  fi

  if [ "$?" -eq 0 ]; then
    echoerr "Host $HOST is active"

    if [ -n "$COMMAND" ]; then
      exec sh -c "$COMMAND"
    fi

    exit 0
  fi

  CURRENT_TIME=$(date +%s)
  ELAPSED=$((CURRENT_TIME - START_TIME))

  if [ "$TIMEOUT" -ne 0 ] && [ "$ELAPSED" -ge "$TIMEOUT" ]; then
    echoerr "Operation timed out: $HOST"
    exit 1
  fi

  sleep 1
done
