FROM alpine:3.20 AS cpp-build
RUN apk add --no-cache build-base cmake
WORKDIR /src/native-cpp
COPY native-cpp/CMakeLists.txt ./
COPY native-cpp/src ./src
RUN cmake -S . -B build -DCMAKE_BUILD_TYPE=Release \
    && cmake --build build --config Release

FROM rust:1.85-alpine AS rust-build
WORKDIR /src/compute-rust
COPY compute-rust/Cargo.toml ./
COPY compute-rust/src ./src
RUN cargo build --release

FROM alpine:3.20
RUN addgroup -S loanhub && adduser -S -G loanhub loanhub
COPY --from=rust-build /src/compute-rust/target/release/loanhub-compute-rust /usr/local/bin/loanhub-compute-rust
COPY --from=cpp-build /src/native-cpp/build/loanhub_native /usr/local/bin/loanhub-native
ENV LOANHUB_CPP_KERNEL_PATH=/usr/local/bin/loanhub-native
USER loanhub
EXPOSE 8082
ENTRYPOINT ["/usr/local/bin/loanhub-compute-rust"]
