FROM maven:3.9.9-eclipse-temurin-21 AS build
WORKDIR /src
COPY pom.xml ./
COPY src ./src
RUN mvn -q -DskipTests package

FROM eclipse-temurin:21-jre-alpine
RUN addgroup -S loanhub && adduser -S -G loanhub loanhub
COPY --from=build /src/target/worker-java-0.1.0.jar /app/worker-java.jar
USER loanhub
EXPOSE 8083
ENTRYPOINT ["java","-jar","/app/worker-java.jar"]
