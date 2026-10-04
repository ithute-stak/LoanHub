FROM rust:1.82-alpine AS build
WORKDIR /src
COPY Cargo.toml ./
COPY src ./src
RUN cargo build --release

FROM alpine:3.20
RUN addgroup -S loanhub && adduser -S -G loanhub loanhub
COPY --from=build /src/target/release/loanhub-compute-rust /usr/local/bin/loanhub-compute-rust
USER loanhub
EXPOSE 8082
ENTRYPOINT ["/usr/local/bin/loanhub-compute-rust"]
