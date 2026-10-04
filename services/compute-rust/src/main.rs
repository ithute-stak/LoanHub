use std::env;
use std::io::{Read, Write};
use std::net::{TcpListener, TcpStream};

fn query_i64(path: &str, key: &str) -> Option<i64> {
    let query = path.split_once('?')?.1;
    query.split('&').find_map(|pair| {
        let (name, value) = pair.split_once('=')?;
        if name == key { value.parse::<i64>().ok() } else { None }
    })
}

fn response(stream: &mut TcpStream, status: &str, body: &str) {
    let payload = format!(
        "HTTP/1.1 {status}\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{}",
        body.len(),
        body
    );
    let _ = stream.write_all(payload.as_bytes());
}

fn handle(mut stream: TcpStream) {
    let mut buffer = [0_u8; 4096];
    let Ok(size) = stream.read(&mut buffer) else { return; };
    let request = String::from_utf8_lossy(&buffer[..size]);
    let Some(first_line) = request.lines().next() else { return; };
    let mut parts = first_line.split_whitespace();
    let method = parts.next().unwrap_or("");
    let path = parts.next().unwrap_or("");

    if method == "GET" && path == "/health/ready" {
        response(&mut stream, "200 OK", r#"{"status":"ready","runtime":"rust"}"#);
        return;
    }

    if method == "GET" && path.starts_with("/v1/affordability-headroom") {
        let income = query_i64(path, "income_cents");
        let commitments = query_i64(path, "commitments_cents");
        let proposed = query_i64(path, "proposed_cents");
        match (income, commitments, proposed) {
            (Some(income), Some(commitments), Some(proposed)) => {
                let headroom = income.saturating_sub(commitments).saturating_sub(proposed);
                let body = format!(
                    r#"{{"passed":{},"headroom_cents":{},"authoritative":false}}"#,
                    headroom >= 0,
                    headroom
                );
                response(&mut stream, "200 OK", &body);
            }
            _ => response(&mut stream, "400 Bad Request", r#"{"error":"invalid_query"}"#),
        }
        return;
    }

    response(&mut stream, "404 Not Found", r#"{"error":"not_found"}"#);
}

fn main() {
    let addr = env::var("LOANHUB_RUST_COMPUTE_ADDR").unwrap_or_else(|_| "0.0.0.0:8082".to_string());
    let listener = TcpListener::bind(&addr).expect("bind rust compute worker");
    eprintln!("LoanHub Rust compute worker listening on {addr}");
    for stream in listener.incoming().flatten() {
        handle(stream);
    }
}
