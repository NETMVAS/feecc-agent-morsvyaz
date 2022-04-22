# Commented out to save time on dependency resolving
# Uncomment lines to go full cycle instead of using precompiled requirements.txt

#FROM python:3.9 as requirements-stage
#WORKDIR /tmp
#RUN pip install poetry
#COPY ./pyproject.toml ./poetry.lock* /tmp/
#RUN poetry export -f requirements.txt --output requirements.txt --without-hashes

FROM python:3.9
WORKDIR /code
#COPY --from=requirements-stage /tmp/requirements.txt /code/requirements.txt
COPY requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt
COPY ./src /code
WORKDIR /code
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "5000", "--no-access-log"]
