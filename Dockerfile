	FROM python:3.12

	# Set environment variables
	ENV PIP_DISABLE_PIP_VERSION_CHECK 1
	ENV PYTHONDONTWRITEBYTECODE 1
	ENV PYTHONUNBUFFERED 1

	# Set work directory
	WORKDIR /code

	# Install dependencies
    COPY ./requirements.txt .
	RUN apt-get install -y gcc libpq-dev
	RUN pip install -r requirements.txt

	# Copy project
	COPY . .