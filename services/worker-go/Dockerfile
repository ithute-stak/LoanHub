FROM golang:1.23-alpine AS build
WORKDIR /src
COPY go.mod main.go ./
RUN CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /out/loanhub-go-worker .

FROM gcr.io/distroless/static-debian12:nonroot
COPY --from=build /out/loanhub-go-worker /loanhub-go-worker
EXPOSE 8081
USER nonroot:nonroot
ENTRYPOINT ["/loanhub-go-worker"]
