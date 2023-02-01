mod calendar;
mod schema;
mod scraping;
mod utils;

use actix_cors::Cors;
use actix_web::{get, middleware, web, App, HttpResponse, HttpServer};
use tokio::sync::Mutex;

const MAX_JSON_PAYLOAD: usize = 1024 * 1024; // 1 MB

#[get("/api/calendar/status")]
async fn health_status_handler() -> HttpResponse {
    let github_link = match std::env::var("GIT_COMMIT_SHA") {
        Ok(hash) => format!("https://github.com/TUM-Dev/navigatum/tree/{hash}"),
        Err(_) => "unknown commit hash, probably running in development".to_string(),
    };
    HttpResponse::Ok()
        .content_type("text/plain")
        .body(format!("healthy\nsource_code: {github_link}"))
}

#[actix_web::main]
async fn main() -> std::io::Result<()> {
    env_logger::init_from_env(env_logger::Env::default().default_filter_or("info"));

    let last_sync = web::Data::new(Mutex::new(None));
    let cloned_last_sync = last_sync.clone();
    actix_rt::spawn(async move {
        scraping::continous_scraping::start_scraping(cloned_last_sync).await;
    });
    HttpServer::new(move || {
        let cors = Cors::default()
            .allow_any_origin()
            .allow_any_header()
            .allowed_methods(vec!["GET"])
            .max_age(3600);

        App::new()
            .wrap(cors)
            .wrap(middleware::Logger::default().exclude("/api/calendar/health"))
            .wrap(middleware::Compress::default())
            .app_data(web::JsonConfig::default().limit(MAX_JSON_PAYLOAD))
            .service(health_status_handler)
            .service(
                web::scope("/api/calendar")
                    .configure(calendar::configure)
                    .app_data(last_sync.clone()),
            )
    })
    .bind(std::env::var("BIND_ADDRESS").unwrap_or_else(|_| "0.0.0.0:8060".to_string()))?
    .run()
    .await
}