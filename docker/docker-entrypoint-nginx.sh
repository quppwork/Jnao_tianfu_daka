#!/bin/sh
set -eu

OSS_BUCKET="${OSS_BUCKET:-jnao-talent-ai}"
OSS_ENDPOINT="${OSS_ENDPOINT:-oss-cn-beijing.aliyuncs.com}"
OSS_CDN_DOMAIN="${OSS_CDN_DOMAIN:-}"
OSS_MEDIA_SRC="'self' blob: data: https://${OSS_BUCKET}.${OSS_ENDPOINT}"
if [ -n "$OSS_CDN_DOMAIN" ]; then
  OSS_MEDIA_SRC="${OSS_MEDIA_SRC} https://${OSS_CDN_DOMAIN}"
fi
export OSS_BUCKET OSS_ENDPOINT OSS_MEDIA_SRC

envsubst '${OSS_BUCKET} ${OSS_ENDPOINT} ${OSS_MEDIA_SRC}' \
    < /etc/nginx/templates/default.conf.template \
    > /etc/nginx/conf.d/default.conf

exec nginx -g 'daemon off;'
