FROM python:3.10-alpine
ARG ARG_APP_HOME=/home/app
ARG ARG_RUN_USER=app
ARG ARG_FLASK_APP=self_description_creator.py
ARG ARG_FLASK_RUN_PORT=8080

ENV FLASK_APP=${ARG_FLASK_APP}\
    FLASK_RUN_HOST=0.0.0.0\
    FLASK_RUN_PORT=${ARG_FLASK_RUN_PORT}\
    APP_HOME=${ARG_APP_HOME}

LABEL maintainer="msg"
LABEL project="GX4FM PLC-AAD"
LABEL description="Tool that creates Gaia-X Self Descriptions and is able to add them to a GXFS Federated Catalogue."

# Ensure application will be run as non-root user for safety reasons
RUN echo "Adding run user to system" \
    && addgroup -S ${ARG_RUN_USER} -g 1000 \
    && adduser -S ${ARG_RUN_USER} -u 1000 -G ${ARG_RUN_USER}

# Copy required resources and set appropriate permissions
COPY src ${ARG_APP_HOME}
COPY requirements.txt ${ARG_APP_HOME}/
RUN chown -R ${ARG_RUN_USER}:${ARG_RUN_USER} ${ARG_APP_HOME}

WORKDIR ${ARG_APP_HOME}

# Install dependencies for web app
RUN pip install --no-cache-dir -r requirements.txt

# Use user id instead of user name to allow Kubernetes to check for non-root user
USER 1000

EXPOSE ${ARG_FLASK_RUN_PORT}

CMD ["python", "self_description_creator.py"]