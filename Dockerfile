FROM python:3.9 as dependency-compilation
WORKDIR /tmp
RUN apt update && apt install -y\
    build-essential\
    libssl-dev\
    libffi-dev\
    python3-dev\
    cargo
RUN pip install --upgrade pip
RUN pip install\
    poetry\
    cryptography\
    py-bip39-bindings\
    py-ed25519-bindings\
    py-sr25519-bindings
COPY ./pyproject.toml ./poetry.lock* /tmp/
RUN poetry export -f requirements.txt --output requirements.txt --without-hashes

FROM python:3.9
WORKDIR /code
COPY --from=dependency-compilation /tmp/requirements.txt /code/requirements.txt
COPY --from=dependency-compilation /root/.cache/pip /root/.cache/pip
RUN pip install --upgrade pip
RUN pip install --upgrade -r /code/requirements.txt
COPY . /code/
WORKDIR /code/src
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "5000"]