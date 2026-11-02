from __future__ import annotations

from iexplain.runtime.tools import ToolContext, build_tools

DAY_START = 1614787200  # 2021-03-04 00:00:00 UTC
WINDOW_START = "2021-03-04 14:30:00"
WINDOW_END = "2021-03-04 15:00:00"
MEM_KPI = "OSLinux-OSLinux_MEMORY_MEMORY_MEMUsedMemPerc"
CPU_KPI = "OSLinux-CPU_CPU_CPUCpuUtil"


def _write_metric_container(tmp_path):
    rows = ["timestamp,cmdb_id,kpi_name,value"]
    # Flat daily baseline for both components, every hour.
    for hour in range(24):
        ts = DAY_START + hour * 3600
        rows.append(f"{ts},Redis02,{MEM_KPI},20.0")
        rows.append(f"{ts},Tomcat01,{CPU_KPI},30.0")
    # In-window samples: Redis02 memory spikes, Tomcat01 cpu stays flat.
    for ts, mem in ((1614839400, 21.0), (1614841020, 95.0), (1614841200, 90.0)):
        rows.append(f"{ts},Redis02,{MEM_KPI},{mem}")
        rows.append(f"{ts},Tomcat01,{CPU_KPI},31.0")
    target = tmp_path / "dataset" / "Bank" / "telemetry" / "2021_03_04" / "metric"
    target.mkdir(parents=True, exist_ok=True)
    (target / "metric_container.csv").write_text("\n".join(rows), encoding="utf-8")


def _write_log_service(tmp_path):
    rows = [
        "log_id,timestamp,cmdb_id,log_name,value",
        '1,1614841020,Redis02,redis,"OOM command not allowed when used memory > maxmemory"',
        '2,1614841020,Tomcat01,gc,"3748789.580: [GC (CMS Initial Mark) ...]"',
    ]
    target = tmp_path / "dataset" / "Bank" / "telemetry" / "2021_03_04" / "log"
    target.mkdir(parents=True, exist_ok=True)
    (target / "log_service.csv").write_text("\n".join(rows), encoding="utf-8")


def test_openrca_query_catalog_lists_components(tmp_path):
    _write_metric_container(tmp_path)
    tools = build_tools(["openrca_query"], ToolContext(tmp_path))
    result = tools["openrca_query"].call(
        {"op": "catalog", "telemetry_dir": "dataset/Bank/telemetry/2021_03_04"}
    )
    assert "Redis02" in result["components"]
    assert "Tomcat01" in result["components"]
    assert "memory" in result["kpi_categories"]
    assert "cpu" in result["kpi_categories"]


def test_openrca_query_metric_summary_localizes_anomaly(tmp_path):
    _write_metric_container(tmp_path)
    tools = build_tools(["openrca_query"], ToolContext(tmp_path))
    result = tools["openrca_query"].call(
        {
            "op": "metric_summary",
            "telemetry_dir": "dataset/Bank/telemetry/2021_03_04",
            "start_time": WINDOW_START,
            "end_time": WINDOW_END,
        }
    )
    top = result["ranked_anomalies"][0]
    assert top["component"] == "Redis02"
    assert top["category"] == "memory"
    assert top["peak_time"] == "2021-03-04 14:57:00"
    assert top["window_max"] == 95.0


def test_openrca_query_metric_series_reports_peak(tmp_path):
    _write_metric_container(tmp_path)
    tools = build_tools(["openrca_query"], ToolContext(tmp_path))
    result = tools["openrca_query"].call(
        {
            "op": "metric_series",
            "telemetry_dir": "dataset/Bank/telemetry/2021_03_04",
            "component": "Redis02",
            "kpi_category": "memory",
            "start_time": WINDOW_START,
            "end_time": WINDOW_END,
        }
    )
    assert result["peak"]["value"] == 95.0
    assert result["peak"]["time"] == "2021-03-04 14:57:00"


def test_openrca_query_log_search_filters(tmp_path):
    _write_metric_container(tmp_path)
    _write_log_service(tmp_path)
    tools = build_tools(["openrca_query"], ToolContext(tmp_path))
    result = tools["openrca_query"].call(
        {
            "op": "log_search",
            "telemetry_dir": "dataset/Bank/telemetry/2021_03_04",
            "query": "used memory",
            "component": "Redis02",
        }
    )
    assert result["match_count"] == 1
    assert result["matches"][0]["component"] == "Redis02"
