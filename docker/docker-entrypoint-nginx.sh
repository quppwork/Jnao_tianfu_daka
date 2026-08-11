#!/bin/sh
set -eu

OSS_BUCKET="${OSS_BUCKET:-jnao-talent-ai}"
OSS_ENDPOINT="${OSS_ENDPOINT:-oss-cn-beijing.aliyuncs.com}"
export OSS_BUCKET OSS_ENDPOINT

envsubst '${OSS_BUCKET} ${OSS_ENDPOINT}' \
    < /etc/nginx/templates/default.conf.template \
    > /etc/nginx/conf.d/default.conf

exec nginx -g 'daemon off;'
