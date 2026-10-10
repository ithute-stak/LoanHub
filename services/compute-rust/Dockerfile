FROM alpine:3.20 AS cpp-build
RUN apk add --no-cache build-base cmake boost-dev
WORKDIR /src/native-cpp
COPY native-cpp/CMakeLists.txt ./
COPY native-cpp/src ./src
RUN cmake -S . -B build -DCMAKE_BUILD_TYPE=Release \
    && cmake --build build --config Release

FROM rust:1.85-alpine AS rust-build
RUN apk add --no-cache build-base musl-dev
WORKDIR /src/compute-rust
COPY compute-rust/Cargo.toml ./
COPY compute-rust/src ./src
RUN cargo build --release

FROM alpine:3.20
RUN apk add --no-cache libstdc++ \
    && addgroup -S loanhub \
    && adduser -S -G loanhub loanhub
COPY --from=rust-build /src/compute-rust/target/release/loanhub-compute-rust /usr/local/bin/loanhub-compute-rust
COPY --from=cpp-build /src/native-cpp/build/loanhub_native /usr/local/bin/loanhub-native
COPY --from=cpp-build /src/native-cpp/build/libloanhub_native.so /usr/local/lib/libloanhub_native.so
ENV LOANHUB_CPP_LIBRARY_PATH=/usr/local/lib/libloanhub_native.so
USER loanhub
EXPOSE 8082
ENTRYPOINT ["/usr/local/bin/loanhub-compute-rust"]
