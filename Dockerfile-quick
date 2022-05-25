FROM python:3.9
WORKDIR /src
COPY requirements.txt /src/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt
COPY ./src /src
WORKDIR /src
ENTRYPOINT ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "5000", "--no-access-log"]
