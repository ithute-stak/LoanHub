package ls.co.loanhub.worker;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;

import java.io.IOException;
import java.net.InetSocketAddress;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.Base64;
import java.util.Comparator;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.TreeMap;
import java.util.concurrent.Executors;

public final class EventWorker {
    private static final ObjectMapper JSON = new ObjectMapper();

    private EventWorker() {}

    public static JsonNode canonicalize(JsonNode node) {
        if (node == null || node.isNull() || node.isValueNode()) {
            return node;
        }
        if (node.isArray()) {
            ArrayNode result = JSON.createArrayNode();
            for (JsonNode item : node) {
                result.add(canonicalize(item));
            }
            return result;
        }
        ObjectNode result = JSON.createObjectNode();
        List<Map.Entry<String, JsonNode>> fields = new ArrayList<>();
        node.fields().forEachRemaining(fields::add);
        fields.sort(Comparator.comparing(Map.Entry::getKey));
        for (Map.Entry<String, JsonNode> field : fields) {
            result.set(field.getKey(), canonicalize(field.getValue()));
        }
        return result;
    }

    public static String sha256(String value) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] bytes = digest.digest(value.getBytes(StandardCharsets.UTF_8));
            StringBuilder out = new StringBuilder(bytes.length * 2);
            for (byte item : bytes) {
                out.append(String.format("%02x", item));
            }
            return out.toString();
        } catch (Exception error) {
            throw new IllegalStateException(error);
        }
    }

    private static void json(HttpExchange exchange, int status, Object payload) throws IOException {
        byte[] body = JSON.writeValueAsBytes(payload);
        exchange.getResponseHeaders().set("Content-Type", "application/json");
        exchange.sendResponseHeaders(status, body.length);
        exchange.getResponseBody().write(body);
        exchange.close();
    }

    private static void canonicalizeEvent(HttpExchange exchange) throws IOException {
        if (!"POST".equals(exchange.getRequestMethod())) {
            json(exchange, 405, Map.of("error", "method_not_allowed"));
            return;
        }
        JsonNode request;
        try {
            request = JSON.readTree(exchange.getRequestBody());
        } catch (Exception error) {
            json(exchange, 400, Map.of("error", "invalid_json"));
            return;
        }
        String correlationId = request.path("correlation_id").asText("");
        String eventType = request.path("event_type").asText("");
        JsonNode payload = request.get("payload");
        if (correlationId.isBlank() || eventType.isBlank() || payload == null) {
            json(exchange, 422, Map.of("error", "missing_fields"));
            return;
        }

        JsonNode canonical = canonicalize(payload);
        String canonicalJson = JSON.writeValueAsString(canonical);
        Map<String, Object> response = new TreeMap<>();
        response.put("authoritative", false);
        response.put("canonical_json", canonicalJson);
        response.put("correlation_id", correlationId);
        response.put("event_type", eventType);
        response.put("payload_sha256", sha256(canonicalJson));
        json(exchange, 200, response);
    }

    private static BigDecimal decimal(JsonNode request, String field) {
        String raw = request.path(field).asText("");
        if (raw.isBlank()) {
            throw new IllegalArgumentException("missing_" + field);
        }
        return new BigDecimal(raw);
    }

    private static ObjectNode reason(String severity, String code, String message) {
        ObjectNode item = JSON.createObjectNode();
        item.put("severity", severity);
        item.put("code", code);
        item.put("message", message);
        return item;
    }

    private static void underwritingRules(HttpExchange exchange) throws IOException {
        if (!"POST".equals(exchange.getRequestMethod())) {
            json(exchange, 405, Map.of("error", "method_not_allowed"));
            return;
        }
        JsonNode request;
        try {
            request = JSON.readTree(exchange.getRequestBody());
        } catch (Exception error) {
            json(exchange, 400, Map.of("error", "invalid_json"));
            return;
        }

        final BigDecimal income;
        final BigDecimal minimumIncome;
        final BigDecimal installment;
        final BigDecimal maximumInstallment;
        final BigDecimal disposableAfter;
        final BigDecimal minimumDisposable;
        try {
            income = decimal(request, "monthly_income");
            minimumIncome = decimal(request, "min_verified_net_income");
            installment = decimal(request, "proposed_installment");
            maximumInstallment = decimal(request, "maximum_affordable_installment");
            disposableAfter = decimal(request, "disposable_after_installment");
            minimumDisposable = decimal(request, "min_disposable_after_installment");
        } catch (Exception error) {
            json(exchange, 422, Map.of("error", "invalid_decimal_input"));
            return;
        }

        boolean incomeMissing = income.compareTo(BigDecimal.ZERO) <= 0;
        boolean incomeBelowMinimum = !incomeMissing && income.compareTo(minimumIncome) < 0;
        boolean installmentAboveLimit = installment.compareTo(maximumInstallment) > 0;
        boolean disposableTooLow = disposableAfter.compareTo(minimumDisposable) < 0;
        boolean passed = !incomeMissing && !incomeBelowMinimum && !installmentAboveLimit && !disposableTooLow;

        ArrayNode reasons = JSON.createArrayNode();
        if (incomeMissing) {
            reasons.add(reason("error", "income_missing", "Monthly income is missing or zero."));
        } else if (incomeBelowMinimum) {
            reasons.add(reason("error", "income_below_minimum", "Monthly income is below the lender's configured minimum."));
        } else {
            reasons.add(reason("pass", "income_ok", "Monthly income meets the lender's configured minimum."));
        }

        if (installmentAboveLimit) {
            reasons.add(reason("error", "installment_above_limit", "The proposed installment exceeds the calculated affordability limit."));
        } else {
            reasons.add(reason("pass", "installment_within_limit", "The proposed installment is within the calculated affordability limit."));
        }

        if (disposableTooLow) {
            reasons.add(reason("error", "disposable_income_too_low", "Disposable income after the proposed installment is below the lender's minimum."));
        }

        ObjectNode response = JSON.createObjectNode();
        response.put("authoritative", false);
        response.put("passed", passed);
        response.put("decision", passed ? "pass" : "fail");
        response.set("reasons", reasons);
        json(exchange, 200, response);
    }

    private static String scalarText(JsonNode value) {
        if (value == null || value.isNull()) {
            return "";
        }
        if (value.isBoolean()) {
            return value.booleanValue() ? "True" : "False";
        }
        return value.asText();
    }

    private static String csvField(String raw) {
        String value = raw == null ? "" : raw;
        if (value.contains(",") || value.contains("\"") || value.contains("\r") || value.contains("\n")) {
            return "\"" + value.replace("\"", "\"\"") + "\"";
        }
        return value;
    }

    private static String titleCaseMetric(String raw) {
        String[] words = raw.replace('_', ' ').trim().split("\\s+");
        List<String> titled = new ArrayList<>();
        for (String word : words) {
            if (word.isBlank()) {
                continue;
            }
            String lower = word.toLowerCase(Locale.ROOT);
            titled.add(lower.substring(0, 1).toUpperCase(Locale.ROOT) + lower.substring(1));
        }
        return String.join(" ", titled);
    }

    private static void csvRow(StringBuilder out, String... values) {
        for (int index = 0; index < values.length; index++) {
            if (index > 0) {
                out.append(',');
            }
            out.append(csvField(values[index]));
        }
        out.append("\r\n");
    }

    private static void renderReportCsv(HttpExchange exchange) throws IOException {
        if (!"POST".equals(exchange.getRequestMethod())) {
            json(exchange, 405, Map.of("error", "method_not_allowed"));
            return;
        }
        JsonNode request;
        try {
            request = JSON.readTree(exchange.getRequestBody());
        } catch (Exception error) {
            json(exchange, 400, Map.of("error", "invalid_json"));
            return;
        }

        JsonNode metadata = request.get("metadata");
        JsonNode metrics = request.get("metrics_items");
        if (metadata == null || !metadata.isObject() || metrics == null || !metrics.isArray()) {
            json(exchange, 422, Map.of("error", "metadata_and_metrics_items_required"));
            return;
        }
        for (String key : List.of("title", "reference", "scope_name", "period_start", "period_end")) {
            if (!metadata.has(key)) {
                json(exchange, 422, Map.of("error", "missing_metadata_" + key));
                return;
            }
        }

        StringBuilder csv = new StringBuilder();
        csvRow(csv, "LoanHub Report", scalarText(metadata.get("title")));
        csvRow(csv, "Developed by", "Ithute Solutions");
        csvRow(csv, "Reference", scalarText(metadata.get("reference")));
        csvRow(csv, "Scope", scalarText(metadata.get("scope_name")));
        csvRow(csv, "Period start", scalarText(metadata.get("period_start")));
        csvRow(csv, "Period end", scalarText(metadata.get("period_end")));
        csvRow(csv);
        csvRow(csv, "Metric", "Value");

        for (JsonNode item : metrics) {
            if (!item.isArray() || item.size() != 2 || !item.get(0).isTextual()) {
                json(exchange, 422, Map.of("error", "invalid_metric_item"));
                return;
            }
            JsonNode value = item.get(1);
            if (value != null && (value.isArray() || value.isObject())) {
                json(exchange, 422, Map.of("error", "metric_values_must_be_scalar"));
                return;
            }
            csvRow(
                csv,
                titleCaseMetric(item.get(0).asText()),
                scalarText(value)
            );
        }

        byte[] plain = csv.toString().getBytes(StandardCharsets.UTF_8);
        byte[] bom = new byte[plain.length + 3];
        bom[0] = (byte) 0xEF;
        bom[1] = (byte) 0xBB;
        bom[2] = (byte) 0xBF;
        System.arraycopy(plain, 0, bom, 3, plain.length);

        json(exchange, 200, Map.of(
            "authoritative", false,
            "content_base64", Base64.getEncoder().encodeToString(bom),
            "sha256", sha256Bytes(bom)
        ));
    }

    public static String sha256Bytes(byte[] value) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] bytes = digest.digest(value);
            StringBuilder out = new StringBuilder(bytes.length * 2);
            for (byte item : bytes) {
                out.append(String.format("%02x", item));
            }
            return out.toString();
        } catch (Exception error) {
            throw new IllegalStateException(error);
        }
    }

    private static void batchSummary(HttpExchange exchange) throws IOException {
        if (!"POST".equals(exchange.getRequestMethod())) {
            json(exchange, 405, Map.of("error", "method_not_allowed"));
            return;
        }
        JsonNode request;
        try {
            request = JSON.readTree(exchange.getRequestBody());
        } catch (Exception error) {
            json(exchange, 400, Map.of("error", "invalid_json"));
            return;
        }
        JsonNode events = request.get("events");
        if (events == null || !events.isArray()) {
            json(exchange, 422, Map.of("error", "events_must_be_array"));
            return;
        }
        Map<String, Integer> counts = new TreeMap<>();
        int total = 0;
        for (JsonNode event : events) {
            String type = event.path("event_type").asText("unknown");
            counts.merge(type, 1, Integer::sum);
            total++;
        }
        json(exchange, 200, Map.of(
            "authoritative", false,
            "total", total,
            "counts_by_type", counts
        ));
    }

    public static void main(String[] args) throws Exception {
        int port = Integer.parseInt(System.getenv().getOrDefault("LOANHUB_JAVA_WORKER_PORT", "8083"));
        if (args.length > 0 && "--healthcheck".equals(args[0])) {
            HttpResponse<Void> response = HttpClient.newHttpClient().send(
                HttpRequest.newBuilder(URI.create("http://127.0.0.1:" + port + "/health/ready")).GET().build(),
                HttpResponse.BodyHandlers.discarding()
            );
            if (response.statusCode() != 200) {
                System.exit(1);
            }
            return;
        }
        HttpServer server = HttpServer.create(new InetSocketAddress("0.0.0.0", port), 0);
        server.createContext("/health/ready", exchange ->
            json(exchange, 200, Map.of("status", "ready", "runtime", "java"))
        );
        server.createContext("/v1/events/canonicalize", EventWorker::canonicalizeEvent);
        server.createContext("/v1/events/batch-summary", EventWorker::batchSummary);
        server.createContext("/v1/reports/render-csv", EventWorker::renderReportCsv);
        server.createContext("/v1/underwriting/rules", EventWorker::underwritingRules);
        server.setExecutor(Executors.newVirtualThreadPerTaskExecutor());
        server.start();
        System.err.printf("LoanHub Java event worker listening on 0.0.0.0:%d%n", port);
    }
}
