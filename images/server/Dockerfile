FROM eclipse-temurin:25-jre-noble@sha256:b573af9e331196fbc42e246da4df24df9b6c556c73e7efddfde0511f1c9508c5
RUN apt-get update && apt-get install -y --no-install-recommends python3=3.12.3-0ubuntu2.1 python3.12=3.12.3-1ubuntu0.17 && rm -rf /var/lib/apt/lists/*
WORKDIR /data
COPY raceops /opt/raceops
ENV PYTHONPATH=/opt PYTHONDONTWRITEBYTECODE=1
USER 1000:1000
ENTRYPOINT ["java", "-Xms256M", "-Xmx1536M", "-jar", "/server.jar", "--nogui"]
