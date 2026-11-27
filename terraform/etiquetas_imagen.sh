#!/usr/bin/env bash
# Genera la variable etiquetas_imagen de Terraform: para cada etapa (carpeta con Dockerfile),
# el SHA del último commit que cambió esa carpeta o common/. Así la etiqueta de la imagen solo
# cambia cuando cambia el código de la etapa, y Terraform solo actualiza esa Lambda.
#
# Uso (desde cualquier carpeta del repo, en Git Bash o Linux):
#   bash terraform/etiquetas_imagen.sh > terraform/imagenes.auto.tfvars.json
#
# Solo tiene en cuenta lo que está commiteado: los cambios sin commit no cambian la etiqueta.
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

separador=""
printf '{\n  "etiquetas_imagen": {'
for dockerfile in */Dockerfile; do
  etapa="${dockerfile%/Dockerfile}"
  etiqueta="$(git log -1 --format=%H -- "$etapa/" common/)"
  if [ -z "$etiqueta" ]; then
    echo "La etapa '$etapa' no tiene ningún commit: haz commit antes de desplegar." >&2
    exit 1
  fi
  printf '%s\n    "%s": "%s"' "$separador" "$etapa" "$etiqueta"
  separador=","
done
printf '\n  }\n}\n'
