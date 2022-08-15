# At this stage we convert Poetry's dependency file into a more traditional
# requirements.txt to avoid installing Poetry into the final container.
# Although very slow, this cannot be skipped, as we need to resolve dependencies
# for the exact platform the client is using.
FROM python:3.10 as requirements-stage
WORKDIR /tmp
RUN pip install --upgrade pip
RUN pip install poetry
COPY ./pyproject.toml ./poetry.lock* /tmp/
RUN poetry export -f requirements.txt --output requirements.txt --without-hashes

# Final container build. Uses pre-compiled dependencies and requirements.txt
# obtained in the previous steps
FROM python:3.10
WORKDIR /src
COPY --from=requirements-stage /tmp/requirements.txt /src/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /src/requirements.txt
COPY ./src /src
HEALTHCHECK --interval=5s --timeout=3s --start-period=5s --retries=12 \
    CMD curl --fail http://localhost:5000/docs || exit 1
ENTRYPOINT ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "5000"]
