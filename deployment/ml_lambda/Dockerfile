
FROM public.ecr.aws/lambda/python:3.12

COPY requirements.txt ${LAMBDA_TASK_ROOT}/requirements.txt

RUN pip install --no-cache-dir \
    -r ${LAMBDA_TASK_ROOT}/requirements.txt \
    --target ${LAMBDA_TASK_ROOT}

COPY handler.py ${LAMBDA_TASK_ROOT}/handler.py

COPY no_show_model.joblib ${LAMBDA_TASK_ROOT}/no_show_model.joblib

CMD ["handler.lambda_handler"]
