package ls.co.loanhub.worker;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

class EventWorkerTest {
    private static final ObjectMapper JSON = new ObjectMapper();

    @Test
    void canonicalizeSortsNestedObjectKeys() throws Exception {
        JsonNode input = JSON.readTree("{\"z\":1,\"a\":{\"y\":2,\"b\":3}}");
        String result = JSON.writeValueAsString(EventWorker.canonicalize(input));
        assertEquals("{\"a\":{\"b\":3,\"y\":2},\"z\":1}", result);
    }

    @Test
    void sha256IsDeterministic() {
        assertEquals(
            "e400d25405baf415cc81bf1dfe8dea967d55a09c4e8e862e5a9c98fcd6f033c6",
            EventWorker.sha256("LoanHub")
        );
    }
}
