//! Phase 3 Fidelity–Cost Frontier.
//!
//! A `FrontierReport` aggregates one `FrontierPoint` per benchmark run,
//! mapping each (topology, proxy-mode, retention-config) combination to
//! its fidelity and cost coordinates.
//!
//! # Frontier Axes
//! - **Cost axis** — `spike_ratio = proxy_spikes / explicit_spikes`
//!   (lower = cheaper). Equal to 1.0 means the proxy drives the same total
//!   network activity as explicit. This metric is valid for both stateless
//!   (2-ch) and stateful (4-ch) proxies.
//!   The secondary diagnostic `event_ratio = proxy_events / explicit_events`
//!   measures scheduler queue overhead; for 4-ch it can exceed 1.0 because
//!   residual state is injected every slot even without new spikes.
//! - **Fidelity axis** — measured as `psth_correlation ∈ [-1, 1]`
//!   (higher = more faithful). Supplementary fields carry FR-delta and CV-delta.
//!
//! # Usage
//! ```rust,ignore
//! let mut report = FrontierReport::new("bench_e1_50k_sustained");
//! report.add(FrontierPoint::from_runs(
//!     "4ch-default",
//!     &rec_explicit, &rec_4ch, DT_S,
//! ));
//! println!("{}", report.summary_table());
//! report.write_csv("/tmp/frontier_data.csv").unwrap();
//! ```

use crate::experiment::harness::{RetentionRunResult, RunRecord};
use crate::experiment::metrics::{DynamicsComparison, PopulationDynamics, compare_dynamics};
use std::fmt::Write as FmtWrite;
use std::io::Write as IoWrite;

/// A single point on the fidelity–cost frontier.
///
/// One `FrontierPoint` represents one proxy configuration (label) run against
/// the explicit baseline on one benchmark topology.
#[derive(Debug, Clone)]
pub struct FrontierPoint {
    /// Human-readable label for this proxy configuration (e.g. `"4ch-default"`).
    pub label: String,

    // ── Cost fields ──────────────────────────────────────────────────────────
    /// Total events injected by the LPU proxy across the entire run.
    pub proxy_events: u64,
    /// Total events injected by the explicit run (baseline cost).
    pub explicit_events: u64,
    /// Scheduler queue event ratio: `proxy_events / explicit_events`.
    /// For stateful 4-ch proxies this can exceed 1.0 (residual drive injected
    /// every slot). Use `spike_ratio` for Go/Stop decisions.
    pub event_ratio: f32,
    /// **Primary cost metric**: `proxy_spikes / explicit_spikes`.
    ///
    /// Measures how much more (or less) the proxy drives network spiking
    /// relative to the explicit baseline. Stateful proxy residual shows up
    /// in `event_ratio` but only matters scientifically if it causes extra
    /// spikes, which `spike_ratio` captures directly. Values ≤ 1.5 indicate
    /// the proxy does not appreciably over-drive the network.
    pub spike_ratio: f32,
    /// Total spikes from the explicit run (for reference).
    pub explicit_spikes: u64,
    /// Total spikes from the proxy run (for reference).
    pub proxy_spikes: u64,

    // ── Fidelity fields ──────────────────────────────────────────────────────
    /// Pearson r of per-step population firing-rate traces.
    pub psth_correlation: f32,
    /// Relative FR error: `(lpu_fr - exp_fr) / exp_fr × 100` (%).
    pub mean_fr_delta_pct: f32,
    /// Relative CV_pop error (%).
    pub cv_pop_delta_pct: f32,
    /// Hz shift of PSD peak frequency.
    pub peak_freq_delta_hz: f32,

    // ── Summary dynamics ─────────────────────────────────────────────────────
    /// Explicit baseline mean firing rate (Hz).
    pub explicit_mean_fr_hz: f32,
    /// Proxy mean firing rate (Hz).
    pub proxy_mean_fr_hz: f32,

    // ── Retention telemetry ───────────────────────────────────────────────────
    /// Percentage of circuit edges retained explicitly (0.0 = all proxy, 100.0 = all explicit).
    /// Zero for pure-proxy runs; populated from `RetentionStats` for hybrid runs.
    pub retained_edges_pct: f32,
    /// Percentage of total injected scheduler events that went through the explicit
    /// (EventRouter) sub-path: `explicit_path_events / (explicit_path_events + proxy_events) × 100`.
    /// Zero for pure-proxy runs. This is event-routing telemetry — it measures how
    /// scheduling load is split between the two paths, not actual retained spike traffic.
    /// High values indicate the explicit (EventRouter) path dominates scheduling cost.
    pub explicit_event_share_pct: f32,
}

impl FrontierPoint {
    /// Compute a `FrontierPoint` from a paired `(explicit, proxy)` run.
    ///
    /// # Arguments
    /// - `label`: arbitrary label string for this proxy configuration.
    /// - `rec_explicit`: output of `run_explicit()` (the ground-truth baseline).
    /// - `rec_proxy`: output of `run_lpu()` or `run_mixed()` (the proxy run).
    /// - `dt_s`: simulation timestep **in seconds** (e.g. `0.001` for 1 ms).
    pub fn from_runs(
        label: impl Into<String>,
        rec_explicit: &RunRecord,
        rec_proxy: &RunRecord,
        dt_s: f32,
    ) -> Self {
        let cmp: DynamicsComparison = compare_dynamics(rec_explicit, rec_proxy, dt_s);
        let dyn_exp = PopulationDynamics::from_record(rec_explicit, dt_s);
        let dyn_prx = PopulationDynamics::from_record(rec_proxy, dt_s);

        // Queue event ratio (diagnostic — can exceed 1.0 for stateful 4-ch proxy).
        let explicit_events = rec_explicit.total_events();
        let proxy_events = rec_proxy.total_events();
        let event_ratio = if explicit_events > 0 {
            proxy_events as f32 / explicit_events as f32
        } else {
            1.0
        };

        // Spike ratio — primary cost metric valid for both proxy types.
        let explicit_spikes: u64 = rec_explicit.steps.iter().map(|s| s.total_spikes as u64).sum();
        let proxy_spikes: u64 = rec_proxy.steps.iter().map(|s| s.total_spikes as u64).sum();
        let spike_ratio = if explicit_spikes > 0 {
            proxy_spikes as f32 / explicit_spikes as f32
        } else {
            1.0
        };

        Self {
            label: label.into(),
            proxy_events,
            explicit_events,
            event_ratio,
            spike_ratio,
            explicit_spikes,
            proxy_spikes,
            psth_correlation: cmp.psth_correlation,
            mean_fr_delta_pct: cmp.mean_fr_delta_pct,
            cv_pop_delta_pct: cmp.cv_pop_delta_pct,
            peak_freq_delta_hz: cmp.peak_freq_delta_hz,
            explicit_mean_fr_hz: dyn_exp.mean_fr_hz,
            proxy_mean_fr_hz: dyn_prx.mean_fr_hz,
            retained_edges_pct: 0.0,
            explicit_event_share_pct: 0.0,
        }
    }

    /// Compute a `FrontierPoint` from a hybrid retention run paired with an explicit baseline.
    ///
    /// `retained_edges_pct` comes from `RetentionStats.retention_fraction`.
    /// `explicit_event_share_pct` is the fraction of hybrid-run scheduler events that went
    /// through the explicit (EventRouter) sub-path: `explicit_events / (explicit + proxy) × 100`.
    /// This is event-routing telemetry, not a measure of retained spike traffic.
    pub fn from_retention_result(
        label: impl Into<String>,
        rec_explicit: &RunRecord,
        result: &RetentionRunResult,
        dt_s: f32,
    ) -> Self {
        let mut pt = Self::from_runs(label, rec_explicit, &result.record, dt_s);
        pt.retained_edges_pct = result.stats.retention_fraction * 100.0;
        let total_ev = result.explicit_events + result.proxy_events;
        pt.explicit_event_share_pct = if total_ev > 0 {
            result.explicit_events as f32 / total_ev as f32 * 100.0
        } else {
            0.0
        };
        pt
    }

    /// Returns `true` if this point meets the Phase 3 Go criteria:
    ///
    /// | Criterion              | Threshold | Rationale                             |
    /// |------------------------|-----------|---------------------------------------|
    /// | PSTH-r                 | ≥ 0.70    | Population waveform fidelity          |
    /// | mean FR delta          | ≤ 20 %    | Firing-rate accuracy                  |
    /// | spike_ratio (cost)     | ≤ 1.50    | Network activity load vs. explicit    |
    ///
    /// `spike_ratio` is used (not `event_ratio`) because stateful 4-ch proxy
    /// injects scheduler events every slot from residual state; what matters for
    /// scientific cost is how many extra spikes the proxy induces in the network.
    pub fn meets_go_criteria(&self) -> bool {
        self.psth_correlation >= 0.70
            && self.mean_fr_delta_pct.abs() <= 20.0
            && self.spike_ratio <= 1.50
    }

    /// One-line CSV row (no header).
    ///
    /// Column order matches `FrontierReport::csv_header()`.
    pub fn to_csv_row(&self) -> String {
        format!(
            "{},{},{},{:.4},{:.4},{},{},{:.4},{:.2},{:.2},{:.2},{:.2},{:.2}",
            self.label,
            self.explicit_events,
            self.proxy_events,
            self.event_ratio,
            self.spike_ratio,
            self.explicit_spikes,
            self.proxy_spikes,
            self.psth_correlation,
            self.mean_fr_delta_pct,
            self.explicit_mean_fr_hz,
            self.proxy_mean_fr_hz,
            self.retained_edges_pct,
            self.explicit_event_share_pct,
        )
    }
}

/// Aggregated frontier report for one benchmark topology.
///
/// Holds one `FrontierPoint` per proxy configuration tested on the same
/// explicit baseline, enabling direct Pareto comparison.
#[derive(Debug)]
pub struct FrontierReport {
    /// Benchmark identifier (e.g. `"bench_e1_50k_sustained"`).
    pub benchmark: String,
    /// All frontier points collected so far.
    pub points: Vec<FrontierPoint>,
}

impl FrontierReport {
    /// Create an empty report for the given benchmark.
    pub fn new(benchmark: impl Into<String>) -> Self {
        Self {
            benchmark: benchmark.into(),
            points: Vec::new(),
        }
    }

    /// Add a frontier point.
    pub fn add(&mut self, point: FrontierPoint) {
        self.points.push(point);
    }

    /// Sort points by descending PSTH-r then ascending event_ratio (Pareto front order).
    pub fn sort_pareto(&mut self) {
        self.points.sort_by(|a, b| {
            b.psth_correlation
                .partial_cmp(&a.psth_correlation)
                .unwrap_or(std::cmp::Ordering::Equal)
                .then_with(|| {
                    a.spike_ratio
                        .partial_cmp(&b.spike_ratio)
                        .unwrap_or(std::cmp::Ordering::Equal)
                })
        });
    }

    /// The CSV header line.
    pub fn csv_header() -> &'static str {
        "label,explicit_events,proxy_events,event_ratio,spike_ratio,\
         explicit_spikes,proxy_spikes,psth_r,mean_fr_delta_pct,\
         explicit_mean_fr_hz,proxy_mean_fr_hz,retained_edges_pct,explicit_event_share_pct"
    }

    /// Write a full CSV to `path` (creates or truncates the file).
    ///
    /// The output includes the header row followed by one data row per point.
    pub fn write_csv(&self, path: &std::path::Path) -> std::io::Result<()> {
        let mut f = std::fs::File::create(path)?;
        writeln!(f, "{}", Self::csv_header())?;
        for p in &self.points {
            writeln!(f, "{}", p.to_csv_row())?;
        }
        Ok(())
    }

    /// Render a human-readable Markdown table.
    ///
    /// Suitable for embedding in `docs/phase3/frontier_report.md`.
    pub fn markdown_table(&self) -> String {
        let mut out = String::new();
        writeln!(
            out,
            "# Fidelity–Cost Frontier: `{}`\n",
            self.benchmark
        )
        .unwrap();
        writeln!(
            out,
            "| Config | PSTH-r | FR Δ% | CV Δ% | Spike ratio | Ret-E% | Ev-Share% | Go? |"
        )
        .unwrap();
        writeln!(
            out,
            "|--------|--------|-------|-------|-------------|--------|-----------|-----|"
        )
        .unwrap();
        for p in &self.points {
            let go = if p.meets_go_criteria() { "✅" } else { "🚫" };
            writeln!(
                out,
                "| `{}` | {:.3} | {:.1} | {:.1} | {:.3} | {:.1} | {:.1} | {} |",
                p.label,
                p.psth_correlation,
                p.mean_fr_delta_pct,
                p.cv_pop_delta_pct,
                p.spike_ratio,
                p.retained_edges_pct,
                p.explicit_event_share_pct,
                go,
            )
            .unwrap();
        }
        out
    }

    /// Compact single-line summary (useful in test stderr output).
    pub fn summary_table(&self) -> String {
        let mut out = format!("[Frontier: {}]\n", self.benchmark);
        for p in &self.points {
            let ret_str = if p.retained_edges_pct > 0.0 {
                format!(
                    " ret_e={:.1}% ev_share={:.1}%",
                    p.retained_edges_pct, p.explicit_event_share_pct
                )
            } else {
                String::new()
            };
            out.push_str(&format!(
                "  {:30} psth_r={:.3} fr_delta={:+.1}% spike_ratio={:.3} ev_ratio={:.3}{} {}\n",
                p.label,
                p.psth_correlation,
                p.mean_fr_delta_pct,
                p.spike_ratio,
                p.event_ratio,
                ret_str,
                if p.meets_go_criteria() { "GO" } else { "STOP" },
            ));
        }
        out
    }

    /// Returns all points that meet the Go criteria, sorted by Pareto dominance.
    pub fn go_configs(&self) -> Vec<&FrontierPoint> {
        let mut go: Vec<&FrontierPoint> =
            self.points.iter().filter(|p| p.meets_go_criteria()).collect();
        go.sort_by(|a, b| {
            b.psth_correlation
                .partial_cmp(&a.psth_correlation)
                .unwrap_or(std::cmp::Ordering::Equal)
        });
        go
    }

    /// Returns the best config by PSTH-r (or `None` if the report is empty).
    pub fn best_by_fidelity(&self) -> Option<&FrontierPoint> {
        self.points
            .iter()
            .max_by(|a, b| {
                a.psth_correlation
                    .partial_cmp(&b.psth_correlation)
                    .unwrap_or(std::cmp::Ordering::Equal)
            })
    }

    /// Returns the cheapest config by spike_ratio (or `None` if the report is empty).
    pub fn cheapest(&self) -> Option<&FrontierPoint> {
        self.points.iter().min_by(|a, b| {
            a.spike_ratio
                .partial_cmp(&b.spike_ratio)
                .unwrap_or(std::cmp::Ordering::Equal)
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::experiment::harness::{RunRecord, StepRecord};

    fn make_record(total_spikes: u32, events: u32, units: usize) -> RunRecord {
        RunRecord {
            mode: None,
            total_units: units,
            num_chunks: 4,
            steps: (0..100u64)
                .map(|s| StepRecord {
                    slot: s,
                    total_spikes,
                    active_chunks: 2,
                    dormant_skips: 2,
                    events_injected: events,
                })
                .collect(),
        }
    }

    #[test]
    fn test_frontier_point_event_ratio() {
        let explicit = make_record(10, 100, 1000);
        let proxy = make_record(9, 60, 1000);
        let pt = FrontierPoint::from_runs("test", &explicit, &proxy, 0.001);
        // event_ratio = 60*100 / (100*100) = 6000/10000 = 0.6
        assert!(
            (pt.event_ratio - 0.6).abs() < 1e-4,
            "event_ratio={:.4} expected 0.6",
            pt.event_ratio
        );
        // spike_ratio = 9*100 / (10*100) = 900/1000 = 0.9
        assert!(
            (pt.spike_ratio - 0.9).abs() < 1e-4,
            "spike_ratio={:.4} expected 0.9",
            pt.spike_ratio
        );
    }

    #[test]
    fn test_go_criteria_passes() {
        // Construct a point that should pass all criteria.
        let pt = FrontierPoint {
            label: "good".into(),
            proxy_events: 60,
            explicit_events: 100,
            event_ratio: 0.60,
            spike_ratio: 1.10,
            explicit_spikes: 1000,
            proxy_spikes: 1100,
            psth_correlation: 0.85,
            mean_fr_delta_pct: 5.0,
            cv_pop_delta_pct: 10.0,
            peak_freq_delta_hz: 0.5,
            explicit_mean_fr_hz: 30.0,
            proxy_mean_fr_hz: 31.5,
            retained_edges_pct: 0.0,
            explicit_event_share_pct: 0.0,
        };
        assert!(pt.meets_go_criteria(), "should pass Go criteria");
    }

    #[test]
    fn test_go_criteria_fails_on_low_psth() {
        let pt = FrontierPoint {
            label: "bad".into(),
            proxy_events: 50,
            explicit_events: 100,
            event_ratio: 0.50,
            spike_ratio: 0.80,
            explicit_spikes: 1000,
            proxy_spikes: 800,
            psth_correlation: 0.50,
            mean_fr_delta_pct: 5.0,
            cv_pop_delta_pct: 5.0,
            peak_freq_delta_hz: 0.0,
            explicit_mean_fr_hz: 30.0,
            proxy_mean_fr_hz: 30.5,
            retained_edges_pct: 0.0,
            explicit_event_share_pct: 0.0,
        };
        assert!(!pt.meets_go_criteria(), "low PSTH-r should fail Go criteria");
    }

    #[test]
    fn test_report_markdown_table_non_empty() {
        let mut report = FrontierReport::new("test_bench");
        report.add(FrontierPoint {
            label: "2ch".into(),
            proxy_events: 80,
            explicit_events: 100,
            event_ratio: 0.80,
            spike_ratio: 1.05,
            explicit_spikes: 1000,
            proxy_spikes: 1050,
            psth_correlation: 0.72,
            mean_fr_delta_pct: 8.0,
            cv_pop_delta_pct: 5.0,
            peak_freq_delta_hz: 0.2,
            explicit_mean_fr_hz: 25.0,
            proxy_mean_fr_hz: 27.0,
            retained_edges_pct: 0.0,
            explicit_event_share_pct: 0.0,
        });
        let md = report.markdown_table();
        assert!(md.contains("test_bench"), "table should contain benchmark name");
        assert!(md.contains("2ch"), "table should contain point label");
        assert!(md.contains("Spike ratio"), "table must use spike_ratio column header");
        assert!(md.contains("✅"), "Go point should show ✅");
    }

    #[test]
    fn test_csv_row_column_count() {
        let pt = FrontierPoint {
            label: "cfg_a".into(),
            proxy_events: 72,
            explicit_events: 100,
            event_ratio: 0.72,
            spike_ratio: 0.95,
            explicit_spikes: 1000,
            proxy_spikes: 950,
            psth_correlation: 0.81,
            mean_fr_delta_pct: -3.2,
            cv_pop_delta_pct: 4.1,
            peak_freq_delta_hz: 0.1,
            explicit_mean_fr_hz: 28.0,
            proxy_mean_fr_hz: 27.1,
            retained_edges_pct: 0.0,
            explicit_event_share_pct: 0.0,
        };
        let row = pt.to_csv_row();
        let cols: Vec<&str> = row.split(',').collect();
        let header_cols: Vec<&str> = FrontierReport::csv_header().split(',').collect();
        assert_eq!(
            cols.len(),
            header_cols.len(),
            "CSV row must have same column count as header"
        );
    }

    #[test]
    fn test_write_csv_creates_file() {
        use std::io::Read;

        let mut report = FrontierReport::new("csv_test");
        report.add(FrontierPoint {
            label: "p1".into(),
            proxy_events: 50,
            explicit_events: 100,
            event_ratio: 0.50,
            spike_ratio: 0.95,
            explicit_spikes: 1000,
            proxy_spikes: 950,
            psth_correlation: 0.90,
            mean_fr_delta_pct: 2.0,
            cv_pop_delta_pct: 1.0,
            peak_freq_delta_hz: 0.05,
            explicit_mean_fr_hz: 20.0,
            proxy_mean_fr_hz: 20.4,
            retained_edges_pct: 0.0,
            explicit_event_share_pct: 0.0,
        });

        let dir = std::env::temp_dir();
        let path = dir.join("next_brain_frontier_test.csv");
        report.write_csv(&path).expect("write_csv must not fail");

        let mut contents = String::new();
        std::fs::File::open(&path)
            .unwrap()
            .read_to_string(&mut contents)
            .unwrap();

        assert!(
            contents.starts_with("label,"),
            "CSV must start with header"
        );
        assert!(contents.contains("p1"), "CSV must contain data row");
        std::fs::remove_file(&path).ok();
    }

    #[test]
    fn test_best_by_fidelity_and_cheapest() {
        let mut report = FrontierReport::new("pareto_test");
        report.add(FrontierPoint {
            label: "high_fidelity".into(),
            proxy_events: 90,
            explicit_events: 100,
            event_ratio: 0.90,
            spike_ratio: 1.20,
            explicit_spikes: 1000,
            proxy_spikes: 1200,
            psth_correlation: 0.95,
            mean_fr_delta_pct: 1.0,
            cv_pop_delta_pct: 1.0,
            peak_freq_delta_hz: 0.0,
            explicit_mean_fr_hz: 30.0,
            proxy_mean_fr_hz: 30.3,
            retained_edges_pct: 0.0,
            explicit_event_share_pct: 0.0,
        });
        report.add(FrontierPoint {
            label: "cheap".into(),
            proxy_events: 40,
            explicit_events: 100,
            event_ratio: 0.40,
            spike_ratio: 0.85,
            explicit_spikes: 1000,
            proxy_spikes: 850,
            psth_correlation: 0.72,
            mean_fr_delta_pct: 15.0,
            cv_pop_delta_pct: 8.0,
            peak_freq_delta_hz: 0.3,
            explicit_mean_fr_hz: 30.0,
            proxy_mean_fr_hz: 34.5,
            retained_edges_pct: 0.0,
            explicit_event_share_pct: 0.0,
        });

        assert_eq!(
            report.best_by_fidelity().unwrap().label,
            "high_fidelity"
        );
        assert_eq!(report.cheapest().unwrap().label, "cheap");
    }
}
