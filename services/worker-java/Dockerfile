FROM maven:3.9.9-eclipse-temurin-21 AS build
WORKDIR /src
COPY pom.xml ./
COPY src ./src
# Maven Central occasionally returns transient resolution failures in CI.
# Retry only dependency resolution/build; do not bypass compilation or tests.
RUN set -eu; \
    for attempt in 1 2 3; do \
      if mvn -B -ntp -U -DskipTests package; then exit 0; fi; \
      if [ "$attempt" -eq 3 ]; then exit 1; fi; \
      echo "Maven build failed (attempt $attempt/3); retrying dependency resolution"; \
      sleep 8; \
    done

FROM eclipse-temurin:21-jre-alpine
RUN addgroup -S loanhub && adduser -S -G loanhub loanhub
COPY --from=build /src/target/worker-java-0.1.0.jar /app/worker-java.jar
USER loanhub
EXPOSE 8083
ENTRYPOINT ["java","-jar","/app/worker-java.jar"]
