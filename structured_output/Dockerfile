# Imagen Lambda de la etapa 3: extracción de datos del KID con un LLM en Bedrock.
# Construir desde la raíz del repo: docker build -f structured_output/Dockerfile .
FROM public.ecr.aws/lambda/python:3.14

COPY structured_output/requirements.txt ${LAMBDA_TASK_ROOT}
RUN pip install --no-cache-dir -r ${LAMBDA_TASK_ROOT}/requirements.txt --target "${LAMBDA_TASK_ROOT}"

COPY common/ ${LAMBDA_TASK_ROOT}/common/
COPY structured_output/extractor_kid.py structured_output/app.py ${LAMBDA_TASK_ROOT}/

CMD ["app.handler"]
