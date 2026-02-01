# Build stage
FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    texlive-latex-base \
    texlive-fonts-recommended \
    texlive-fonts-extra \
    texlive-latex-extra \
    cron \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . .

RUN pip install --no-cache-dir -r requirements.txt

COPY cronjob /etc/cron.d/job-agent
RUN chmod 0644 /etc/cron.d/job-agent && crontab /etc/cron.d/job-agent

# Create log file
RUN touch /var/log/cron.log

CMD ["cron", "-f"]
