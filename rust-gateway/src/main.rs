use axum::{
    body::Body,
    extract::State,
    http::{header, HeaderMap, HeaderName, Request, Response, StatusCode},
    routing::get,
    Router,
};
use sha2::{Digest, Sha256};
use std::{net::SocketAddr, path::PathBuf, sync::Arc, time::Duration};
use tower_http::services::ServeDir;

#[derive(Clone)]
struct Gateway {
    root: PathBuf,
    upstream: String,
    client: reqwest::Client,
    revision: String,
}

fn revision(root: &std::path::Path) -> std::io::Result<String> {
    let mut digest = Sha256::new();
    for name in [
        "control.js",
        "control.css",
        "compact-nav.css",
        "v11.css",
        "yanbi.css",
        "yanbi-logo.webp",
        "yanbi-background.webp",
    ] {
        digest.update(name.as_bytes());
        digest.update(std::fs::read(root.join("static").join(name))?);
    }
    Ok(format!("{:x}", digest.finalize())[..16].to_owned())
}

fn routes(state: Gateway) -> Router {
    Router::new()
        .route("/", get(shell))
        .route("/miniapp", get(shell))
        .route("/admin", get(shell))
        .route("/zenvyre", get(shell))
        .route("/healthz", get(health))
        .nest_service("/static", ServeDir::new(state.root.join("static")))
        .fallback(proxy)
        .with_state(Arc::new(state))
}

async fn shell(State(state): State<Arc<Gateway>>) -> Response<Body> {
    let path = state.root.join("templates/miniapp.html");
    match tokio::fs::read_to_string(path).await {
        Ok(template) => {
            let html = template
                .replace("{{ asset_revision }}", &state.revision)
                .replace("{{ author }}", "Dev Anh Khôi")
                .replace("{{ version }}", "2.1.0");
            Response::builder()
                .status(StatusCode::OK)
                .header(header::CONTENT_TYPE, "text/html; charset=utf-8")
                .header(header::CACHE_CONTROL, "no-store, max-age=0")
                .body(Body::from(html))
                .expect("valid shell response")
        }
        Err(_) => plain(
            StatusCode::SERVICE_UNAVAILABLE,
            "Không tải được giao diện. Thử lại sau.",
        ),
    }
}

async fn health(State(state): State<Arc<Gateway>>) -> Response<Body> {
    let url = format!("{}/healthz", state.upstream);
    let check = tokio::time::timeout(Duration::from_secs(2), state.client.get(url).send()).await;
    match check {
        Ok(Ok(result)) if result.status().is_success() => Response::builder()
            .status(StatusCode::OK)
            .header(header::CONTENT_TYPE, "application/json")
            .header(header::CACHE_CONTROL, "no-store")
            .body(Body::from(
                r#"{"ok":true,"gateway":"rust","backend":"ready"}"#,
            ))
            .expect("valid health response"),
        _ => Response::builder()
            .status(StatusCode::SERVICE_UNAVAILABLE)
            .header(header::CONTENT_TYPE, "application/json")
            .header(header::CACHE_CONTROL, "no-store")
            .body(Body::from(
                r#"{"ok":false,"gateway":"rust","backend":"unavailable"}"#,
            ))
            .expect("valid health response"),
    }
}

fn hop_by_hop(name: &HeaderName) -> bool {
    matches!(
        name.as_str(),
        "connection"
            | "keep-alive"
            | "proxy-authenticate"
            | "proxy-authorization"
            | "te"
            | "trailer"
            | "transfer-encoding"
            | "upgrade"
            | "host"
    )
}

async fn proxy(State(state): State<Arc<Gateway>>, request: Request<Body>) -> Response<Body> {
    let path = request.uri().path_and_query().map_or("/", |v| v.as_str());
    let url = format!("{}{}", state.upstream, path);
    let (parts, body) = request.into_parts();
    let mut outbound = state.client.request(parts.method, url);
    let mut headers = HeaderMap::new();
    for (name, value) in &parts.headers {
        if !hop_by_hop(name) {
            headers.append(name, value.clone());
        }
    }
    outbound = outbound
        .headers(headers)
        .body(reqwest::Body::wrap_stream(body.into_data_stream()));
    let upstream = match outbound.send().await {
        Ok(response) => response,
        Err(_) => {
            return plain(
                StatusCode::SERVICE_UNAVAILABLE,
                "Máy chủ xử lý đang gián đoạn. Hãy thử lại.",
            )
        }
    };
    let status =
        StatusCode::from_u16(upstream.status().as_u16()).unwrap_or(StatusCode::BAD_GATEWAY);
    let mut response = Response::builder().status(status);
    for (name, value) in upstream.headers() {
        if !hop_by_hop(name) {
            response = response.header(name, value);
        }
    }
    response
        .body(Body::from_stream(upstream.bytes_stream()))
        .expect("valid proxy response")
}

fn plain(status: StatusCode, message: &'static str) -> Response<Body> {
    Response::builder()
        .status(status)
        .header(header::CONTENT_TYPE, "text/plain; charset=utf-8")
        .header(header::CACHE_CONTROL, "no-store")
        .body(Body::from(message))
        .expect("valid error response")
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let root = PathBuf::from(std::env::var("YANBI_ROOT").unwrap_or_else(|_| ".".into()));
    let upstream =
        std::env::var("YANBI_PYTHON_UPSTREAM").unwrap_or_else(|_| "http://127.0.0.1:5001".into());
    let port: u16 = std::env::var("PORT")
        .unwrap_or_else(|_| "5000".into())
        .parse()?;
    let client = reqwest::Client::builder()
        .connect_timeout(Duration::from_secs(3))
        .redirect(reqwest::redirect::Policy::none())
        .build()?;
    let state = Gateway {
        revision: revision(&root)?,
        root,
        upstream,
        client,
    };
    let address = SocketAddr::from(([0, 0, 0, 0], port));
    let listener = tokio::net::TcpListener::bind(address).await?;
    axum::serve(listener, routes(state))
        .with_graceful_shutdown(async {
            let _ = tokio::signal::ctrl_c().await;
        })
        .await?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use axum::body::to_bytes;
    use tower::ServiceExt;

    fn fixture(upstream: &str) -> Gateway {
        Gateway {
            root: PathBuf::from(".."),
            upstream: upstream.into(),
            client: reqwest::Client::new(),
            revision: "fixture".into(),
        }
    }

    #[tokio::test]
    async fn shell_survives_backend_failure_but_health_does_not_claim_ready() {
        let app = routes(fixture("http://127.0.0.1:1"));
        let shell = app
            .clone()
            .oneshot(Request::builder().uri("/").body(Body::empty()).unwrap())
            .await
            .unwrap();
        assert_eq!(shell.status(), StatusCode::OK);
        let text = to_bytes(shell.into_body(), 100_000).await.unwrap();
        assert!(String::from_utf8_lossy(&text).contains("id=\"startup-panel\""));
        let health = app
            .oneshot(
                Request::builder()
                    .uri("/healthz")
                    .body(Body::empty())
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(health.status(), StatusCode::SERVICE_UNAVAILABLE);
    }

    #[tokio::test]
    async fn proxy_preserves_admin_cookie_and_csrf() {
        let upstream = Router::new().route(
            "/api/miniapp/session",
            get(|headers: HeaderMap| async move {
                let cookie = headers
                    .get(header::COOKIE)
                    .unwrap()
                    .to_str()
                    .unwrap()
                    .to_owned();
                let csrf = headers
                    .get("x-csrf-token")
                    .unwrap()
                    .to_str()
                    .unwrap()
                    .to_owned();
                format!("{cookie}|{csrf}")
            }),
        );
        let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
        let address = listener.local_addr().unwrap();
        tokio::spawn(async move { axum::serve(listener, upstream).await.unwrap() });
        let request = Request::builder()
            .uri("/api/miniapp/session")
            .header(header::COOKIE, "session=fixture")
            .header("x-csrf-token", "csrf-fixture")
            .body(Body::empty())
            .unwrap();
        let response = routes(fixture(&format!("http://{address}")))
            .oneshot(request)
            .await
            .unwrap();
        assert_eq!(response.status(), StatusCode::OK);
        let body = to_bytes(response.into_body(), 100).await.unwrap();
        assert_eq!(&body[..], b"session=fixture|csrf-fixture");
    }
}
