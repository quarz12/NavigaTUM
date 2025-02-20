use crate::scrape_task::ScrapeTask;
use log::{error, info};
use std::fmt;

use prometheus::labels;

mod models;
mod schema;
mod scrape_task;
mod utils;

struct TimeWindow {
    duration: chrono::Duration,
}

impl TimeWindow {
    fn init_from_env() -> Self {
        let time_window_months = std::env::var("SCRAPED_TIME_WINDOW_MONTHS")
            .expect("SCRAPED_TIME_WINDOW_MONTHS not set");
        let time_window_months = time_window_months
            .parse::<i64>()
            .expect("SCRAPED_TIME_WINDOW_MONTHS not a number");
        // 30 days/month is a simplification, but over-scraping by a few days probably does not matter
        Self {
            duration: chrono::Duration::days(time_window_months * 30),
        }
    }
}

impl fmt::Debug for TimeWindow {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        let num_years = self.duration.num_days() / 365;
        let num_remaining_days = self.duration.num_days() - num_years * 365;
        f.debug_struct("TimeWindow")
            .field("years", &num_years)
            .field("months", &(num_remaining_days / 30))
            .finish()
    }
}

#[tokio::main]
async fn main() {
    env_logger::init_from_env(env_logger::Env::default().default_filter_or("info"));

    let time_window = TimeWindow::init_from_env();
    info!("Scraping time window: {time_window:?}");
    let mut scraper = ScrapeTask::new(time_window.duration).await;
    scraper.scrape_to_db().await;
    scraper.delete_stale_results();

    info!("Pushing metrics to the pushgateway");
    tokio::task::spawn_blocking(move || {
        let address = std::env::var("PUSHGATEWAY_URL")
            .unwrap_or("pushgateway.monitoring.svc.cluster.local".to_string());
        prometheus::push_metrics(
            "navigatum_calendarscraper",
            labels! {"duration".to_owned() => format!("{time_window:?}"),},
            &address,
            prometheus::gather(),
            None,
        )
        .unwrap_or_else(|e| {
            error!("could not push metrics to the pushgateway, because: {e:?}");
        });
    })
    .await
    .expect("Spawing a blocking task failed");
}
