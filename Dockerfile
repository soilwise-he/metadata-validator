FROM python:3.12-slim

WORKDIR /app

COPY src/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/validationINSPIRE/validationByTestSuites.py .
COPY src/validationINSPIRE/concurrentValidation.py .
COPY docker/entrypoint.sh /entrypoint.sh

RUN useradd --system --no-create-home app && chown -R app /app
USER app

ENTRYPOINT ["/entrypoint.sh"]
